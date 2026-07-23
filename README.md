# Ollive Inference Logger

A lightweight chatbot with an auto-instrumenting SDK and an event-driven ingestion
pipeline for LLM inference logs.

- **Chatbot**: multi-turn chat backed by Groq (Llama 3.3 70B), React UI
- **SDK**: a decorator that wraps any LLM provider call and captures latency, token
  usage, status, and I/O previews with zero call-site logging code
- **Ingestion**: HTTP endpoint → Kafka → consumer → ClickHouse, decoupled so a slow
  or down analytics store never blocks a chat request
- **Storage**: Postgres for conversations/messages (OLTP), ClickHouse for inference
  logs (OLAP)

## Architecture

```
                     ┌──────────────┐
   Browser  ───────► │   frontend    │  React (Vite)
                     └──────┬───────┘
                            │ REST (JSON)
                            ▼
                     ┌──────────────┐        ┌─────────────┐
                     │   backend     │───────►│   Postgres   │  conversations,
                     │ (Django+DRF)  │        │              │  messages
                     └──────┬───────┘        └─────────────┘
                            │ complete_chat()
                            │ @log_inference (sdk/llm_logger.py)
                            ▼
                     ┌──────────────┐
                     │  Groq API     │
                     └──────────────┘
                            │
                            │ fire-and-forget POST (metadata only)
                            ▼
                     ┌──────────────┐
                     │ /api/ingest/  │  validate + parse (DRF serializer)
                     └──────┬───────┘
                            │ produce
                            ▼
                     ┌──────────────┐
                     │  Kafka topic  │  inference-logs
                     │ inference-logs│
                     └──────┬───────┘
                            │ poll + batch
                            ▼
                     ┌──────────────┐        ┌─────────────┐
                     │   consumer    │───────►│  ClickHouse  │  inference_logs
                     │ (mgmt command)│        │              │
                     └──────────────┘        └─────────────┘
```

Everything runs via a single `docker-compose.yml`: Postgres, ClickHouse, Kafka
(KRaft mode, no Zookeeper), the Django API, the Kafka→ClickHouse consumer worker,
and the React dev server.

## Setup

Prerequisites: Docker Desktop.

```bash
cp backend/.env.example backend/.env      # fill in GROQ_API_KEY
docker compose up -d --build

# first run only: create the initial Django migration/tables
docker compose run --rm backend python manage.py makemigrations chat
docker compose restart backend consumer
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000/api
- ClickHouse HTTP: http://localhost:8123 (user `default`, password from `backend/.env`)

Get a free Groq API key at https://console.groq.com.

## Ingestion flow

1. `chat/services/groq_client.py` calls Groq, wrapped by `@log_inference("groq")`
   from `sdk/llm_logger.py`. The decorator is the *entire* integration — the call
   site does no logging itself, which is what lets any future provider be
   "auto-instrumented" by wrapping its client call the same way.
2. The decorator times the call, builds a metadata payload (model, provider,
   latency, tokens, status, timestamps, conversation/message id, input/output
   previews truncated to 500 chars), and fires an async-style POST to
   `/api/ingest/`. Failure to deliver a log never raises — it's swallowed and
   logged locally, so observability can't break the chat path.
3. `ingestion/views.py` (`IngestLogView`) validates/parses the payload with a DRF
   serializer and publishes it onto the Kafka topic `inference-logs`. This view
   does no persistence itself — publishing is the only side effect, so it stays
   fast regardless of downstream storage health.
4. `ingestion/management/commands/consume_inference_logs.py` polls Kafka,
   batches events (up to 50, or every 2s), and bulk-inserts them into ClickHouse.
   Offsets are committed manually, only after a batch is durably written —
   at-least-once delivery. A crash between flush and commit can replay a few
   rows (duplicates) on restart, which is far cheaper for a log table than
   silently losing rows.

## Schema design decisions

**Postgres — `conversations` / `messages`** (OLTP, source of truth for chat)
- Normalized, low-volume, needs relational integrity (a message must belong to
  a conversation) and point lookups (resume a conversation by id) — a classic
  relational workload.
- `conversations.status` (`active`/`cancelled`) is a plain column rather than a
  soft-delete flag, since a cancelled conversation is still fully readable
  (resume/history), just no longer accepts new messages.

**ClickHouse — `inference_logs`** (OLAP, high-volume analytics/observability)
- Append-only event stream, queried mostly by time range and aggregated
  (latency/throughput/error-rate dashboards) — the workload ClickHouse is built
  for, and one Postgres would not scale well for at high log volume.
- `MergeTree`, partitioned by month, ordered by `created_at`. `conversation_id`
  was deliberately left out of the sort key: ClickHouse's `MergeTree` sorting
  key can't contain nullable columns (a log can exist without a conversation —
  e.g. a request that failed before one was created), and the dashboard access
  pattern is time-range-first anyway.
- A free-form `metadata JSON` column (finish reason, provider request id, etc.)
  is the pressure-release valve for provider-specific fields so the schema
  doesn't need a migration every time a new field shows up — traded against
  losing type safety/indexing on whatever lands in it.
- `inference_logs` intentionally does **not** live in Postgres via a foreign key
  to `messages`: the two stores serve different access patterns and failure
  domains. `conversation_id`/`message_id` are carried as plain UUIDs (no FK
  constraint across databases), so an inference log for a request that never
  produced a Postgres row (e.g. a validation failure) is still capturable.

## Tradeoffs made

- **HTTP hop before Kafka, instead of producing directly from the SDK.** Keeps
  the SDK provider-agnostic about the transport (it just POSTs JSON) and gives
  a single validation/parsing boundary (`IngestLogView`) instead of duplicating
  validation logic in every producer. Costs one extra network hop per log.
- **Kafka consumer as a Django management command**, not a separate framework
  service. Reuses Django settings/ORM-adjacent config wiring for free; the
  tradeoff is it isn't horizontally scaled via partitions/consumer groups today
  (a single consumer process) — trivial to add later by running more replicas
  in the same consumer group.
- **At-least-once, not exactly-once, delivery into ClickHouse.** Manual offset
  commits after a successful flush mean a crash mid-batch can duplicate rows.
  Accepted because analytics on inference logs tolerate small overcounts far
  better than silent gaps, and ClickHouse has no cheap transactional insert
  story to get exactly-once for free here.
- **Preview truncation (500 chars) instead of full input/output storage.**
  Keeps the hot log path small and avoids storing large prompts/completions
  twice (they already live in `messages`); full-fidelity replay isn't a goal
  of the logging system.
- **No auth/rate limiting** on the chat or ingestion endpoints — out of scope
  for a take-home, but the ingestion endpoint in particular would need at
  least a shared-secret header before being exposed beyond localhost.
- **Frontend runs via Vite dev server in Docker**, not a production build behind
  nginx — faster to iterate on, but not how it'd be deployed.

## What I'd improve with more time

- Streaming responses (SSE/WebSocket) from the chat endpoint instead of
  request/response, with the SDK logging latency-to-first-token separately
  from total latency.
- A small dashboard (latency p50/p95, throughput, error rate over time) backed
  directly by ClickHouse aggregation queries.
- PII redaction in the SDK before previews are sent to ingestion, not just
  truncation.
- Multi-provider support (the `@log_inference(provider=...)` decorator is
  already provider-agnostic; only `chat/services/groq_client.py` is Groq-specific).
- Horizontal scaling of the consumer via multiple partitions + consumer group
  replicas, and a dead-letter topic for events that fail to parse/insert
  instead of blocking the batch.
- Auth on both the chat and ingestion APIs, and moving secrets out of `.env`
  files into a real secrets manager for anything beyond local dev.
