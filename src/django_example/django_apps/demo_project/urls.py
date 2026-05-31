from django.urls import path

from src.django_example.django_apps.demo_one.views import parse_quantity_view
from src.django_example.django_apps.demo_three.views import transfer_view
from src.django_example.django_apps.demo_two.views import coupon_check_view

urlpatterns = [
    path("quantity", parse_quantity_view),
    path("coupon", coupon_check_view),
    path("transfer", transfer_view),
]
