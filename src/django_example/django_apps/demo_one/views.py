from django.http import HttpResponse


def parse_quantity_view(request):
    quantity = request.GET.get("q", "")
    if not quantity:
        raise ValueError("quantity is required")
    if quantity.startswith("-"):
        raise RuntimeError("negative quantity is forbidden")
    if quantity[0].isdigit() and int(quantity[0]) > 7:
        raise ArithmeticError("first digit is too large")
    return HttpResponse(f"ok:{quantity}")
