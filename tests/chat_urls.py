from django.urls import include, path

urlpatterns = [
    path("", include("djgent.chat.urls")),
]
