WEIGHTS = (3, 2, 7, 6, 5, 4, 3, 2)


def is_valid_orgnr(value: str) -> bool:
    if len(value) != 9 or not value.isascii() or not value.isdigit():
        return False
    total = sum(int(digit) * weight for digit, weight in zip(value, WEIGHTS))
    check = 11 - total % 11
    if check == 11:
        check = 0
    return check != 10 and check == int(value[8])
