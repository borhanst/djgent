from django.urls import path

from . import views


urlpatterns = [
    path("", views.chat_home, name="chat-home"),
    path("chat/<uuid:conversation_id>/", views.chat_home, name="chat-detail"),
    path("api/chat/", views.chat_message, name="chat-message"),
    path("api/conversations/new/", views.new_conversation, name="chat-new"),
]
