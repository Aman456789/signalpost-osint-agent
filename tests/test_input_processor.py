import pytest

from agent_engine.errors import InvalidInput
from agent_engine.input_processor import MAX_BYTES, parse_input


def test_duplicates_are_merged():
    result = parse_input("923456783\n984851006\n923456783\n")
    assert result.accepted == ["923456783", "984851006"]
    assert result.duplicates_merged == 1
    assert result.rejected == []


def test_leading_zeros_are_kept():
    result = parse_input("012345674")
    assert result.accepted == ["012345674"]


def test_whitespace_blank_lines_and_commas():
    result = parse_input("  923456783 \r\n\r\n984851006, 923609016;\"982463718\"\n")
    assert result.accepted == ["923456783", "984851006", "923609016", "982463718"]


def test_bad_lines_get_a_reason_and_a_line_number():
    result = parse_input("923456783\nabc\n12345\n912345678\n")
    assert result.accepted == ["923456783"]
    assert [(r.line, r.value, r.reason) for r in result.rejected] == [
        (2, "abc", "non_digit"),
        (3, "12345", "length_not_9"),
        (4, "912345678", "mod11_checksum_failed"),
    ]


def test_size_limit():
    with pytest.raises(InvalidInput):
        parse_input(b"9" * (MAX_BYTES + 1))


def test_input_must_be_utf8():
    with pytest.raises(InvalidInput):
        parse_input(b"\xff\xfe923456783")


def test_byte_order_mark_is_ignored():
    result = parse_input(b"\xef\xbb\xbf923456783\n")
    assert result.accepted == ["923456783"]
