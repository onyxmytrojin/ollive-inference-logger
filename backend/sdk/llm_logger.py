"""
Lightweight auto-instrumentation SDK for LLM provider calls.

`@log_inference("provider-name")` wraps any function of the shape
`fn(*, messages, model, **kwargs) -> dict` and transparently captures
latency, token usage, status, and input/output previews around the call,
then ships them to the ingestion endpoint as a fire-and-forget HTTP POST.

Provider call sites (see chat/services/groq_client.py) don't do any logging
themselves — decorating the function is the entire integration, which is
what lets new providers be "auto-instrumented" just by wrapping their client
call the same way.
"""

import json
import logging
import time
from datetime import datetime, timezone
from functools import wraps

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

PREVIEW_MAX_LEN = 500


def _preview(text):
    if not text:
        return None
    text = str(text)
    return text if len(text) <= PREVIEW_MAX_LEN else text[:PREVIEW_MAX_LEN] + "…"


def _send_log(payload: dict) -> None:
    # Best-effort delivery: a slow/unavailable ingestion endpoint must never
    # slow down or break the chat request path.
    try:
        requests.post(settings.INGEST_URL, json=payload, timeout=2)
    except requests.RequestException:
        logger.warning("failed to deliver inference log to ingestion endpoint", exc_info=True)


def log_inference(provider: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*, messages, model, conversation_id=None, message_id=None, **kwargs):
            started_at = datetime.now(timezone.utc)
            start = time.monotonic()
            input_text = json.dumps(messages)

            try:
                result = fn(messages=messages, model=model, **kwargs)
            except Exception as exc:
                completed_at = datetime.now(timezone.utc)
                _send_log(
                    {
                        "conversation_id": conversation_id,
                        "message_id": message_id,
                        "provider": provider,
                        "model": model,
                        "status": "error",
                        "latency_ms": int((time.monotonic() - start) * 1000),
                        "error_message": str(exc),
                        "input_preview": _preview(input_text),
                        "request_started_at": started_at.isoformat(),
                        "request_completed_at": completed_at.isoformat(),
                    }
                )
                raise

            completed_at = datetime.now(timezone.utc)
            _send_log(
                {
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "provider": provider,
                    "model": model,
                    "status": "success",
                    "latency_ms": int((time.monotonic() - start) * 1000),
                    "prompt_tokens": result.get("prompt_tokens"),
                    "completion_tokens": result.get("completion_tokens"),
                    "total_tokens": result.get("total_tokens"),
                    "input_preview": _preview(input_text),
                    "output_preview": _preview(result.get("output")),
                    "request_started_at": started_at.isoformat(),
                    "request_completed_at": completed_at.isoformat(),
                    "metadata": result.get("metadata"),
                }
            )
            return result

        return wrapper

    return decorator
