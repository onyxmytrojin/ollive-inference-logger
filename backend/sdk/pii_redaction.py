"""
Best-effort PII redaction applied to log previews before they leave the
process. This only touches what gets shipped to the ingestion/observability
pipeline (input_preview/output_preview) — the actual chat content stored in
Postgres and shown to the user is never redacted.

Regex-based redaction is inherently incomplete (it won't catch PII that
doesn't match a known shape, e.g. a name), but it's a reasonable first line of
defense for the structured/high-confidence cases below.
"""

import re

_PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[REDACTED_EMAIL]"),
    (re.compile(r"\b(?:\d[ -]*?){13,16}\b"), "[REDACTED_CARD]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED_SSN]"),
    (re.compile(r"\b(?:\+?\d{1,3}[ -]?)?\(?\d{3}\)?[ -]?\d{3}[ -]?\d{4}\b"), "[REDACTED_PHONE]"),
    (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "[REDACTED_IP]"),
    (re.compile(r"\b(?:sk|pk|gsk|api)[-_][A-Za-z0-9]{16,}\b", re.IGNORECASE), "[REDACTED_SECRET]"),
]


def redact(text):
    if not text:
        return text
    for pattern, placeholder in _PATTERNS:
        text = pattern.sub(placeholder, text)
    return text
