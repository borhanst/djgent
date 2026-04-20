from django.urls import path

from . import views

app_name = "demo_app"

urlpatterns = [
    path("", views.home, name="home"),
]
