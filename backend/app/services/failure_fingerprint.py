import hashlib
import re
import logging

from app.models import TestResult

logger = logging.getLogger(__name__)

_ERROR_CLASSIFICATION_PATTERNS = [
    (lambda m: "AssertionError", lambda m: "Assertion" in m or "assert" in m.lower()),
    (lambda m: "TimeoutError", lambda m: "timeout" in m.lower() or "timed out" in m.lower()),
    (lambda m: "ConnectionError", lambda m: "connection" in m.lower() or "connect" in m.lower()),
    (lambda m: "NullPointerException", lambda m: "NullPointerException" in m),
    (lambda m: "NotFound", lambda m: "not found" in m.lower() or "no such file" in m.lower()),
    (lambda m: "PermissionError", lambda m: any(kw in m.lower() for kw in ("permission", "forbidden", "access denied"))),
    (lambda m: "ImportError", lambda m: "import" in m.lower() and "module" in m.lower()),
    (lambda m: "ModuleNotFoundError", lambda m: "ModuleNotFoundError" in m),
    (lambda m: "OSError", lambda m: m.startswith("OSError") or "no space" in m.lower()),
    (lambda m: "IndexError", lambda m: "index" in m.lower() and "out of range" in m.lower()),
    (lambda m: "HTTPError", lambda m: "HTTP" in m and "Error" in m),
]

_STACK_LINE_RE = re.compile(r'^\s*File "([^"]+)", line (\d+)(?:, in (\w+))?')


def classify_error(message: str | None) -> str:
    if not message:
        return "Unknown"
    m = message.strip()
    for _, check in _ERROR_CLASSIFICATION_PATTERNS:
        if check(m):
            return _(m)
    for pfx in ("TypeError", "ValueError", "KeyError", "AttributeError", "RuntimeError", "SyntaxError"):
        if m.startswith(pfx):
            return pfx
    first_line = m.split("\n")[0][:80]
    return first_line + ("..." if len(m.split("\n")[0]) > 80 else "")


def classify_modality(error_type: str, status: str) -> str:
    if error_type == "AssertionError" and status == "failed":
        return "assertion_failure"
    if error_type in ("TimeoutError", "ConnectionError", "HTTPError"):
        return "infrastructure_failure"
    if status == "broken":
        return "infrastructure_failure"
    if error_type == "NotFound":
        return "data_issue"
    return "unknown"


def parse_error_location(trace: str | None) -> dict | None:
    if not trace:
        return None
    for line in trace.split("\n"):
        m = _STACK_LINE_RE.match(line)
        if m:
            return {"file": m.group(1), "line": int(m.group(2)), "function": m.group(3) or ""}
    return None


def normalize_message(message: str) -> str:
    m = message.strip()
    m = re.sub(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "UUID", m)
    m = re.sub(r"\b0x[0-9a-fA-F]+\b", "HEX", m)
    m = re.sub(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?", "TS", m)
    m = re.sub(r"\b\d{10,13}\b", "TS", m)
    m = re.sub(r"\b\d+\b", "NUM", m)
    m = re.sub(r"'[^']{4,}'", "'STR'", m)
    m = re.sub(r'"[^"]{4,}"', '"STR"', m)
    return m


def hash_signature(normalized_message: str) -> str:
    return hashlib.md5(normalized_message.encode("utf-8")).hexdigest()


def _extract_labels(labels: dict | None) -> dict | None:
    if not labels:
        return None
    result = {}
    for item in labels if isinstance(labels, list) else []:
        name = item.get("name", "") if isinstance(item, dict) else ""
        value = item.get("value", "") if isinstance(item, dict) else ""
        if name and value:
            result[name] = value
    return result if result else None


def build_fingerprint(tr: TestResult) -> dict:
    sd = tr.status_details if isinstance(tr.status_details, dict) else {}
    msg = sd.get("message")
    trace = sd.get("trace")
    error_type = classify_error(msg)
    return {
        "error_type": error_type,
        "error_location": parse_error_location(trace),
        "signature_hash": hash_signature(normalize_message(msg or "")),
        "test_labels": _extract_labels(tr.labels),
        "failure_modality": classify_modality(error_type, tr.status),
        "environment_snapshot": None,
        "raw_message": msg,
        "raw_trace": trace,
    }
