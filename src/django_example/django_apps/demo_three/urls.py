from django.urls import path

from src.django_example.django_apps.demo_three.views import transfer_view

urlpatterns = [
    path("transfer", transfer_view),
]
