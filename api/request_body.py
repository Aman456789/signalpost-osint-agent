import json

from fastapi import Request

from agent_engine.errors import InvalidInput
from agent_engine.input_processor import MAX_BYTES, InputResult, parse_input
from api.problems import ProblemError

MAX_TEXT_BYTES = MAX_BYTES
MAX_JSON_BYTES = 2 * MAX_BYTES  # escaping newlines in JSON can double the size of the text
MAX_LINES = 10_000


def malformed(detail: str) -> ProblemError:
    return ProblemError(400, "malformed-request", "Malformed request", detail)


def too_large(detail: str) -> ProblemError:
    return ProblemError(413, "payload-too-large", "Payload too large", detail)


async def read_body(request: Request, limit: int) -> bytes:
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        raise too_large(f"The request body is larger than {limit:,} bytes.")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > limit:
            raise too_large(f"The request body is larger than {limit:,} bytes.")
    return bytes(body)


async def json_object(request: Request) -> dict:
    raw = await read_body(request, MAX_JSON_BYTES)
    try:
        data = json.loads(raw)
    except ValueError:
        raise malformed("The body is not valid JSON.") from None
    if not isinstance(data, dict):
        raise malformed("The body must be a JSON object.")
    return data


def parse_numbers(data: str | bytes) -> InputResult:
    """Size limits first, then the same parser the command line uses."""
    if isinstance(data, str):
        try:
            data = data.encode("utf-8")
        except UnicodeEncodeError:
            raise malformed("Input must be UTF-8 text.") from None
    if len(data) > MAX_TEXT_BYTES:
        raise too_large("Input is larger than 1 MB.")
    if len(data.splitlines()) > MAX_LINES:
        raise too_large(f"Input has more than {MAX_LINES:,} lines.")
    try:
        return parse_input(data)
    except InvalidInput as exc:
        raise malformed(str(exc)) from None


def rejected_items(result: InputResult) -> list[dict]:
    return [{"line": item.line, "value": item.value[:64], "reason": item.reason} for item in result.rejected]


def nothing_valid(result: InputResult) -> ProblemError:
    total = len(result.rejected)
    if total:
        detail = f"{total} of {total} inputs were rejected. No valid organisation numbers remain."
    else:
        detail = "No organisation numbers were found in the input."
    return ProblemError(422, "validation-error", "Validation failed", detail, rejected=rejected_items(result))
