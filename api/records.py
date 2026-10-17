import base64
import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from api.problems import ProblemError
from storage.store import StoreError, read_lines


def rows(path: Path) -> list[dict]:
    try:
        lines, _ = read_lines(path)
    except StoreError as exc:
        raise ProblemError(500, "storage-error", "Stored data is damaged", str(exc)) from None
    return [json.loads(line) for line in lines]


def dossiers(output_dir: Path) -> list[dict]:
    return rows(output_dir / "dossiers.jsonl")


def find_dossier(output_dir: Path, orgnr: str) -> dict | None:
    return next((row for row in dossiers(output_dir) if row["orgnr"] == orgnr), None)


def facts_by_id(output_dir: Path) -> dict[str, dict]:
    return {row["fact_id"]: row for row in rows(output_dir / "facts.jsonl")}


def sources_by_id(output_dir: Path) -> dict[str, dict]:
    return {row["source_id"]: row for row in rows(output_dir / "sources.jsonl")}


def rejections(output_dir: Path) -> list[dict]:
    return rows(output_dir / "rejections.jsonl")


def timestamp(text: str) -> float:
    return datetime.fromisoformat(text).timestamp()


def bad_cursor(detail: str = "The cursor is not valid.") -> ProblemError:
    return ProblemError(400, "malformed-request", "Malformed request", detail)


def encode_cursor(position: tuple, scope: str) -> str:
    raw = json.dumps({"scope": scope, "after": list(position)}).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str, scope: str) -> tuple:
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        found, after = data["scope"], tuple(data["after"])
    except (ValueError, KeyError, TypeError):
        raise bad_cursor() from None
    if found != scope:
        raise bad_cursor("The cursor was made for a different sort order or filter.")
    return after


def paginate(items: list, key: Callable, *, descending: bool, limit: int, cursor: str | None, scope: str):
    """Keyset pagination: key(item) is a tuple that is unique per item, the cursor is the last key sent."""
    items = sorted(items, key=key, reverse=descending)
    if cursor:
        after = decode_cursor(cursor, scope)
        try:
            items = [item for item in items if (key(item) < after if descending else key(item) > after)]
        except TypeError:
            raise bad_cursor() from None
    page = items[:limit]
    next_cursor = encode_cursor(key(page[-1]), scope) if len(items) > limit else None
    return page, next_cursor
