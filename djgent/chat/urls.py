from django.urls import path

from . import views

app_name = "djgent_chat"

urlpatterns = [
    path("", views.chat_home, name="home"),
    path("chat/<uuid:conversation_id>/", views.chat_home, name="detail"),
    path("embed/", views.chat_embed, name="embed"),
    path("embed/<uuid:conversation_id>/", views.chat_embed, name="embed-detail"),
    path("api/chat/", views.chat_message, name="message"),
    path("api/conversations/new/", views.new_conversation, name="new"),
]
