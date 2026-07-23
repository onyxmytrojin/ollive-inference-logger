import json
import logging
import time
import uuid
from datetime import datetime

from confluent_kafka import Consumer
from django.conf import settings
from django.core.management.base import BaseCommand

from ingestion.clickhouse_client import ensure_schema, get_client

logger = logging.getLogger(__name__)

BATCH_SIZE = 50
BATCH_TIMEOUT_SECONDS = 2.0

COLUMNS = [
    "conversation_id",
    "message_id",
    "provider",
    "model",
    "status",
    "error_message",
    "latency_ms",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "input_preview",
    "output_preview",
    "request_started_at",
    "request_completed_at",
    "metadata",
]


def _parse_uuid(value):
    return uuid.UUID(value) if value else None


def _parse_datetime(value):
    return datetime.fromisoformat(value) if value else None


def _row_from_event(event: dict) -> list:
    return [
        _parse_uuid(event.get("conversation_id")),
        _parse_uuid(event.get("message_id")),
        event.get("provider"),
        event.get("model"),
        event.get("status"),
        event.get("error_message"),
        event.get("latency_ms"),
        event.get("prompt_tokens"),
        event.get("completion_tokens"),
        event.get("total_tokens"),
        event.get("input_preview"),
        event.get("output_preview"),
        _parse_datetime(event.get("request_started_at")),
        _parse_datetime(event.get("request_completed_at")),
        json.dumps(event.get("metadata")) if event.get("metadata") is not None else None,
    ]


class Command(BaseCommand):
    help = "Consume inference log events from Kafka and batch-insert them into ClickHouse."

    def handle(self, *args, **options):
        ensure_schema()
        client = get_client()

        consumer = Consumer(
            {
                "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
                "group.id": "inference-logs-clickhouse-writer",
                "auto.offset.reset": "earliest",
                # Offsets are committed manually, only after a batch is durably
                # written to ClickHouse: at-least-once delivery. A crash between
                # flush and commit can replay a few rows (duplicates), which is
                # far cheaper for an analytics/log table than silently losing them.
                "enable.auto.commit": False,
            }
        )
        consumer.subscribe([settings.KAFKA_INFERENCE_LOGS_TOPIC])

        self.stdout.write(self.style.SUCCESS("Kafka consumer started, writing to ClickHouse..."))

        batch = []
        last_flush = time.monotonic()

        try:
            while True:
                msg = consumer.poll(timeout=1.0)

                if msg is not None:
                    if msg.error():
                        logger.error("Kafka consumer error: %s", msg.error())
                    else:
                        event = json.loads(msg.value().decode("utf-8"))
                        batch.append(_row_from_event(event))

                timed_out = time.monotonic() - last_flush > BATCH_TIMEOUT_SECONDS
                if batch and (len(batch) >= BATCH_SIZE or timed_out):
                    if self._flush(client, batch):
                        consumer.commit(asynchronous=False)
                    batch = []
                    last_flush = time.monotonic()
        finally:
            consumer.close()

    def _flush(self, client, batch) -> bool:
        try:
            client.insert("inference_logs", batch, column_names=COLUMNS)
            self.stdout.write(f"Flushed {len(batch)} inference log(s) to ClickHouse")
            return True
        except Exception:
            logger.exception("failed to flush batch to ClickHouse")
            return False
