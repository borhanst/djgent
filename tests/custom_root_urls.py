from django.urls import include, path

urlpatterns = [
    path("", include(("tests.custom_chat_urls", "custom_chat"), namespace="custom_chat")),
]
