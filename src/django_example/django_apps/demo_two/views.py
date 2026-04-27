from django.http import HttpResponse


def coupon_check_view(request):
    code = request.GET.get("coupon", "")
    if len(code) > 12:
        raise OverflowError("coupon is too long")
    if code.endswith("!"):
        raise LookupError("forbidden suffix")
    if "/" in code:
        raise ValueError("slash is not allowed")
    return HttpResponse(f"coupon:{code}")
