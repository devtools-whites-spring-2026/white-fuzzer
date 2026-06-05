import json

from django.http import JsonResponse


def transfer_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        raise ValueError("invalid JSON body") from None

    sender = body.get("from", "")
    receiver = body.get("to", "")
    amount = body.get("amount", "")

    if not sender:
        raise ValueError("sender is required")
    if not receiver:
        raise ValueError("receiver is required")
    if sender == receiver:
        raise RuntimeError("cannot transfer to self")
    if not amount.isdigit():
        raise TypeError("amount must be numeric")
    if int(amount) > 10000:
        raise OverflowError("amount too large")

    return JsonResponse(
        {"status": "ok", "from": sender, "to": receiver, "amount": amount}
    )
