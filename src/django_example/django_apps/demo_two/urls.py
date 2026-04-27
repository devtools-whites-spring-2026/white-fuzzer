from django.urls import path

from src.django_example.django_apps.demo_two.views import coupon_check_view

urlpatterns = [
    path("coupon", coupon_check_view),
]
