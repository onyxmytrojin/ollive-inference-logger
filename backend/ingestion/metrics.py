from .clickhouse_client import get_client

# Query params are restricted to these keys only — never interpolated from
# arbitrary user input — so building SQL with an f-string here is safe.
WINDOW_SECONDS = {
    "15m": 15 * 60,
    "1h": 60 * 60,
    "6h": 6 * 60 * 60,
    "24h": 24 * 60 * 60,
}

# Bucket width is chosen per window so charts render a reasonable number of
# points regardless of the time range (e.g. ~30-90 buckets).
BUCKET_SECONDS = {
    "15m": 30,
    "1h": 60,
    "6h": 5 * 60,
    "24h": 15 * 60,
}

DEFAULT_WINDOW = "1h"


def get_summary(window: str) -> dict:
    window_seconds = WINDOW_SECONDS[window]
    query = f"""
        SELECT
            count() AS total_requests,
            countIf(status = 'error') AS error_count,
            avg(latency_ms) AS avg_latency_ms,
            quantile(0.5)(latency_ms) AS p50_latency_ms,
            quantile(0.95)(latency_ms) AS p95_latency_ms,
            quantile(0.99)(latency_ms) AS p99_latency_ms,
            sum(total_tokens) AS total_tokens
        FROM inference_logs
        WHERE created_at >= now() - INTERVAL {window_seconds} SECOND
    """
    rows = get_client().query(query).result_rows
    if not rows or rows[0][0] == 0:
        return {
            "total_requests": 0,
            "error_count": 0,
            "error_rate": 0.0,
            "avg_latency_ms": None,
            "p50_latency_ms": None,
            "p95_latency_ms": None,
            "p99_latency_ms": None,
            "total_tokens": 0,
        }

    total_requests, error_count, avg_latency, p50, p95, p99, total_tokens = rows[0]
    return {
        "total_requests": total_requests,
        "error_count": error_count,
        "error_rate": round(error_count / total_requests, 4),
        "avg_latency_ms": round(avg_latency, 1) if avg_latency is not None else None,
        "p50_latency_ms": round(p50, 1) if p50 is not None else None,
        "p95_latency_ms": round(p95, 1) if p95 is not None else None,
        "p99_latency_ms": round(p99, 1) if p99 is not None else None,
        "total_tokens": int(total_tokens or 0),
    }


def get_timeseries(window: str) -> list:
    window_seconds = WINDOW_SECONDS[window]
    bucket_seconds = BUCKET_SECONDS[window]
    query = f"""
        SELECT
            toStartOfInterval(created_at, INTERVAL {bucket_seconds} SECOND) AS bucket,
            count() AS requests,
            countIf(status = 'error') AS errors,
            avg(latency_ms) AS avg_latency_ms,
            quantile(0.95)(latency_ms) AS p95_latency_ms
        FROM inference_logs
        WHERE created_at >= now() - INTERVAL {window_seconds} SECOND
        GROUP BY bucket
        ORDER BY bucket
    """
    rows = get_client().query(query).result_rows
    return [
        {
            "bucket": bucket.isoformat(),
            "requests": requests,
            "errors": errors,
            "avg_latency_ms": round(avg_latency, 1) if avg_latency is not None else None,
            "p95_latency_ms": round(p95_latency, 1) if p95_latency is not None else None,
        }
        for bucket, requests, errors, avg_latency, p95_latency in rows
    ]
