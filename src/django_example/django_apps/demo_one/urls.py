from django.urls import path

from src.django_example.django_apps.demo_one.views import (
    parse_price_view,
    parse_quantity_view,
)

urlpatterns = [
    path("quantity", parse_quantity_view),
    path("price", parse_price_view),
]
