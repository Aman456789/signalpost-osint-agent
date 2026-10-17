from fastapi import APIRouter, Request

from api.request_body import json_object, malformed, nothing_valid, parse_numbers, rejected_items

router = APIRouter()


@router.post("/inputs/validate")
async def validate_inputs(request: Request):
    body = await json_object(request)
    text = body.get("text")
    if not isinstance(text, str):
        raise malformed("'text' must be a string.")
    if not isinstance(body.get("source_label"), (str, type(None))):
        raise malformed("'source_label' must be a string.")

    result = parse_numbers(text)
    if not result.accepted:
        raise nothing_valid(result)
    return {
        "accepted": result.accepted,
        "rejected": rejected_items(result),
        "duplicates_removed": result.duplicates_merged,
    }
