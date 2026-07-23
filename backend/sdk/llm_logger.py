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

from .pii_redaction import redact

logger = logging.getLogger(__name__)

PREVIEW_MAX_LEN = 500


def _preview(text):
    if not text:
        return None
    text = redact(str(text))
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


def log_inference_stream(provider: str):
    """
    Same auto-instrumentation as `log_inference`, but for a provider call that
    is itself a generator yielding `{"delta": str|None, "usage": dict|None,
    "finish_reason": str|None}` chunks. Chunks are forwarded to the caller
    unchanged as they arrive; the log is only sent once the stream is
    exhausted (or errors), since latency/tokens/output aren't known until then.
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*, messages, model, conversation_id=None, message_id=None, **kwargs):
            started_at = datetime.now(timezone.utc)
            start = time.monotonic()
            input_text = json.dumps(messages)
            output_chunks = []
            usage = {}
            first_token_at = None

            try:
                for chunk in fn(messages=messages, model=model, **kwargs):
                    delta = chunk.get("delta")
                    if delta:
                        if first_token_at is None:
                            first_token_at = time.monotonic()
                        output_chunks.append(delta)
                    if chunk.get("usage"):
                        usage = chunk["usage"]
                    yield chunk
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
                        "output_preview": _preview("".join(output_chunks)),
                        "request_started_at": started_at.isoformat(),
                        "request_completed_at": completed_at.isoformat(),
                    }
                )
                raise

            completed_at = datetime.now(timezone.utc)
            time_to_first_token_ms = (
                int((first_token_at - start) * 1000) if first_token_at else None
            )
            _send_log(
                {
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "provider": provider,
                    "model": model,
                    "status": "success",
                    "latency_ms": int((time.monotonic() - start) * 1000),
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                    "input_preview": _preview(input_text),
                    "output_preview": _preview("".join(output_chunks)),
                    "request_started_at": started_at.isoformat(),
                    "request_completed_at": completed_at.isoformat(),
                    "metadata": {"time_to_first_token_ms": time_to_first_token_ms},
                }
            )

        return wrapper

    return decorator
