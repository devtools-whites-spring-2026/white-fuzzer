def analyze_protocol_message(message: str) -> str:
    if not message.startswith("WFZ/1 "):
        return "unknown-protocol"

    payload = message.removeprefix("WFZ/1 ")
    fields = {}
    for chunk in payload.split(";"):
        if "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        fields[key.strip()] = value.strip()

    if fields.get("token") != "greybox":
        return "bad-token"

    if fields.get("mode") != "deep":
        return "shallow"

    if fields.get("stage") != "7":
        return "wrong-stage"

    checksum = fields.get("checksum")
    if checksum != str(len(fields["token"]) + len(fields["mode"])):
        return "bad-checksum"

    if fields.get("action") == "panic":
        raise RuntimeError("deep protocol crash")

    return "accepted"
