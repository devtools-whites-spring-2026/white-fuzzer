ALLOWED_NAME_CHARS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
)
MAX_VALUE_LENGTH = 1024


def parse_http_header(line: str) -> tuple[str, str]:
    if not line or line.isspace():
        raise ValueError("Empty header line")

    parts = line.split(": ")
    if len(parts) != 2:
        raise ValueError(f"Malformed header: {line!r}")

    name, value = parts

    name = name.strip()

    if not name[0].isalpha():
        raise ValueError(f"Header name must start with a letter: {name!r}")

    if not all(c in ALLOWED_NAME_CHARS for c in name):
        raise ValueError(f"Invalid characters in header name: {name!r}")

    value = value.strip()

    if len(value) > MAX_VALUE_LENGTH:
        raise ValueError("Header value too long")

    return name, value
