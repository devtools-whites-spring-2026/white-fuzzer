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


def parse_price_view(request):
    price = request.GET.get("p", "")
    if not price:
        raise ValueError("price is required")
    if not price.isdigit():
        raise TypeError("price must be numeric")
    if int(price) == 0:
        raise ZeroDivisionError("price cannot be zero")
    return HttpResponse(f"price:{price}")
