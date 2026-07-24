# Loom Demo Script — Ollive Inference Logger

Total runtime target: ~7-8 minutes. Actions to take are in **[brackets]** — everything
else is what to say, word for word. Before hitting record: have `docker compose up -d`
running, the Kubernetes deployment still up (`kubectl get pods -n ollive`), and a
browser tab open at `localhost:5173`.

---

## 1. Intro (0:00–0:25)

**[Screen: browser at localhost:5173, chat empty]**

> Hi, I'm [your name]. This is my submission for the take-home — a chatbot with a
> full inference logging and ingestion pipeline built around it. I deliberately
> built this on the stack Ollive actually runs in production: Python and Django on
> the backend, Kafka for event streaming, Postgres and ClickHouse for storage, and
> React on the frontend. Let me walk you through it.

---

## 2. Architecture overview (0:25–1:20)

**[Screen: open the README, scroll to the architecture diagram]**

> Here's the high-level flow. The React frontend talks to a Django backend over
> REST, with server-sent events for streaming responses. When a chat message comes
> in, the backend calls Groq — that's the LLM provider — through a lightweight SDK
> I built. That SDK is just a decorator: it wraps the provider call, times it,
> captures token usage and status, and fires that off to an ingestion endpoint.
> The ingestion endpoint validates the payload and publishes it onto a Kafka topic.
> A separate consumer process reads off that topic, batches events, and writes them
> into ClickHouse. Chat data itself — conversations and messages — lives in
> Postgres. So Postgres handles the transactional side, ClickHouse handles the
> high-volume analytics side, and Kafka in the middle means a slow or down
> ClickHouse can never block an actual chat request.

---

## 3. Live chat demo (1:20–4:15)

**[Screen: click "+ New conversation" — the centered composer and starter prompts show up]**

> Let's see it running. A brand-new conversation starts with a few example
> prompts instead of a blank screen.

**[Click the "Explain a concept" starter chip — it fills the input. Finish the sentence, e.g. "Explain how Kafka consumer groups work in 3 sentences." — send it]**

> Notice the response streams in token by token — that's server-sent events, not a
> single request/response call. And notice the sidebar —

**[Point at the sidebar entry for this conversation]**

> — the title isn't just the first few words I typed. It's generated from the
> actual exchange with a short follow-up call to the model once the reply
> finishes, so it reads like a real title.

**[Wait for it to finish. Click "Inspect" on the assistant message]**

> Every assistant message has an Inspect action. This pulls the actual latency,
> token counts, model, and status that got logged for this exact response —
> straight out of ClickHouse. So the observability system isn't just running in the
> background, it's wired directly into the product.

**[Click "Regenerate"]**

> I can also regenerate a response if I don't like it — that drops the last reply
> and re-streams a fresh one.

**[Type: "Give me a two-item bullet list with one bolded word." — send it]**

> Responses render as markdown — lists, bold text, code blocks.

**[In the sidebar: click the "+" next to "Groups", type a name like "Research", hit Enter]**

> Conversations can be organized into groups —

**[Drag the current conversation from the list onto the new group's header]**

> — just drag one onto a group to file it there. Dragging it onto "Chats" moves
> it back out.

**[Type into the search box]**

> Conversations are also searchable from the sidebar, and double-clicking one
> lets me rename it manually if I want something different from the
> auto-generated title.

**[Click "+ New conversation", send one throwaway message, then click "Cancel conversation"]**

> A conversation can also be cancelled, which blocks new messages but keeps the
> history fully readable — cancelled conversations move into their own section
> at the bottom of the sidebar.

**[Click on a different, older conversation in the sidebar to open it]**

> And clicking back into any past conversation resumes it with full history —
> covering list, resume, and cancel from the assignment's requirements.

---

## 4. Dashboard (4:15–5:15)

**[Click the "Dashboard" tab]**

> Switching to the Dashboard tab — this reads live off ClickHouse, no separate
> metrics store. This gauge is the overall success rate across inference calls,
> and next to it: total requests, error rate, average and p95 latency, and total
> tokens, over a selectable time window.

**[Hover over a point on one of the charts]**

> The charts have hover tooltips, plus a dedicated throughput chart, a latency
> chart showing average versus p95, and an errors chart.

**[Click a couple of the time-window buttons, e.g. 1 hour → 6 hours]**

---

## 5. PII redaction (5:15–6:00)

**[Click "Chat" tab, start a new conversation]**

> One more thing on the logging side — PII redaction. If I send a message with,
> say, a fake email address and phone number —

**[Type: "My email is john.doe@example.com and my phone is 555-123-4567" — send it]**

> — the actual conversation keeps the real values, since that's what the user
> needs to see. But if I look at what actually got logged for observability
> purposes —

**[Screen: terminal or ClickHouse query tool showing the redacted input_preview/output_preview for that message]**

> — the email and phone number are redacted before they ever left the process.
> That's a regex-based pass — it catches structured, high-confidence cases; I call
> out in the README that free-form PII, like names, would need a more
> sophisticated approach as a next step.

---

## 6. Kubernetes (6:00–6:45)

**[Screen: terminal, run `kubectl get pods -n ollive`]**

> Finally, this whole stack is also deployed on Kubernetes, not just Docker
> Compose. Here are the pods running on a self-hosted cluster — Postgres,
> ClickHouse, Kafka, backend, consumer, and frontend, all healthy.

**[Optional: run `kubectl get svc -n ollive`]**

> I hit a couple of real issues getting this running — for example, Kafka's
> controller quorum voter needed to point at localhost instead of the Kafka
> service, since a single-node broker talking to itself through a ClusterIP can
> fail to hairpin on some networking setups. That, and the rest of the deployment
> steps, are documented in the README.

---

## 7. Wrap-up (6:45–7:20)

**[Screen: README, scroll to schema/tradeoffs section]**

> To summarize the design decisions: Postgres for transactional chat data,
> ClickHouse for high-volume inference logs, Kafka decoupling the two so ingestion
> never blocks the chat path, and a decorator-based SDK that means adding a new
> LLM provider is a few lines of code, not a rewrite of the logging system. Setup
> instructions, the full schema reasoning, the tradeoffs I made, and what I'd
> improve with more time are all written up in the README.

> One last thing — there's also a live hosted link at [TODO: Vercel URL] if you
> want to try the chat directly without running anything locally. That
> deployment is chat-only — it's running the frontend, backend, and Postgres on
> free tiers, but skips Kafka and ClickHouse since there's no free, no-card
> hosting option for those. The full logging pipeline is exactly what I just
> showed running locally and on Kubernetes. Thanks for watching — happy to walk
> through the code in more detail.

**[Stop recording]**
