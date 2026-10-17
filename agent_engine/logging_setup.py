import json
import logging
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

SECRET_NAME = re.compile(r"(api|access|private|secret)[_-]?key|secret|token|password|authorization|credential|^key$", re.I)
URL = re.compile(r"https?://[^\s\"'<>]+")


def strip_query(text: str) -> str:
    def without_query(match: re.Match) -> str:
        parts = urlsplit(match.group(0))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

    return URL.sub(without_query, text)


def redact(value, name: str = ""):
    if SECRET_NAME.search(name):
        return "[redacted]"
    if isinstance(value, dict):
        return {key: redact(item, str(key)) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item, name) for item in value]
    if isinstance(value, str):
        return strip_query(value)
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": strip_query(record.getMessage()),
        }
        fields = getattr(record, "fields", None)
        if fields:
            entry.update(redact(fields))
        if record.exc_info:
            entry["error"] = strip_query(self.formatException(record.exc_info))
        return json.dumps(entry, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
