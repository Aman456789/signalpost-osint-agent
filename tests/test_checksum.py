import pytest

from validators.orgnr_checksum import is_valid_orgnr


@pytest.mark.parametrize("orgnr", ["923456783", "984851006", "012345674"])
def test_valid_numbers(orgnr):
    assert is_valid_orgnr(orgnr)


def test_check_digit_of_ten_is_invalid():
    # 91234567 gives a sum of 133, so the check digit would be 10
    assert not is_valid_orgnr("912345678")


@pytest.mark.parametrize("orgnr", ["", "12345678", "1234567890", "923456784"])
def test_wrong_length_or_wrong_check_digit(orgnr):
    assert not is_valid_orgnr(orgnr)


@pytest.mark.parametrize("orgnr", ["92345678a", "923 456 783", "٩٢٣٤٥٦٧٨٣", "92345678-"])
def test_non_digits(orgnr):
    assert not is_valid_orgnr(orgnr)
