def throw_if_1st_is_digit(x: str) -> int:
    if x[0].isdigit():
        raise Exception("Invalid input")
    return 1
