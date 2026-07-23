from functools import lru_cache

import clickhouse_connect
from django.conf import settings

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS inference_logs (
    id UUID DEFAULT generateUUIDv4(),
    conversation_id Nullable(UUID),
    message_id Nullable(UUID),
    provider LowCardinality(String),
    model LowCardinality(String),
    status Enum8('success' = 1, 'error' = 2),
    error_message Nullable(String),
    latency_ms Nullable(UInt32),
    prompt_tokens Nullable(UInt32),
    completion_tokens Nullable(UInt32),
    total_tokens Nullable(UInt32),
    input_preview Nullable(String),
    output_preview Nullable(String),
    request_started_at DateTime64(3),
    request_completed_at DateTime64(3),
    metadata Nullable(String),
    created_at DateTime64(3) DEFAULT now64(3)
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (created_at)
"""


@lru_cache(maxsize=1)
def get_client():
    return clickhouse_connect.get_client(
        host=settings.CLICKHOUSE_HOST,
        port=settings.CLICKHOUSE_PORT,
        username=settings.CLICKHOUSE_USER,
        password=settings.CLICKHOUSE_PASSWORD,
        database=settings.CLICKHOUSE_DATABASE,
    )


def ensure_schema() -> None:
    get_client().command(CREATE_TABLE_SQL)
