from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("demo_app.urls")),
    path("chat/", include("djgent.chat.urls")),
]
