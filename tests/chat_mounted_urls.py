from django.urls import include, path

urlpatterns = [
    path("chat/", include("djgent.chat.urls")),
]
