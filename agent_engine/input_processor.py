import re
from dataclasses import dataclass, field

from agent_engine.errors import InvalidInput
from validators.orgnr_checksum import is_valid_orgnr

MAX_BYTES = 1_000_000
CELL_SEPARATORS = re.compile(r"[,;\t]")


@dataclass
class RejectedLine:
    line: int
    value: str
    reason: str  # length_not_9, non_digit or mod11_checksum_failed


@dataclass
class InputResult:
    accepted: list[str] = field(default_factory=list)
    rejected: list[RejectedLine] = field(default_factory=list)
    duplicates_merged: int = 0


def parse_input(raw: bytes | str) -> InputResult:
    data = raw.encode("utf-8") if isinstance(raw, str) else raw
    if len(data) > MAX_BYTES:
        raise InvalidInput("Input is larger than 1 MB")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise InvalidInput("Input must be UTF-8 text") from None

    result = InputResult()
    seen = set()
    for number, line in enumerate(text.splitlines(), start=1):
        for cell in CELL_SEPARATORS.split(line):
            value = cell.strip().strip('"').strip()
            if not value:
                continue
            reason = rejection_reason(value)
            if reason:
                result.rejected.append(RejectedLine(number, value, reason))
            elif value in seen:
                result.duplicates_merged += 1
            else:
                seen.add(value)
                result.accepted.append(value)
    return result


def rejection_reason(value: str) -> str | None:
    if not (value.isascii() and value.isdigit()):
        return "non_digit"
    if len(value) != 9:
        return "length_not_9"
    if not is_valid_orgnr(value):
        return "mod11_checksum_failed"
    return None
