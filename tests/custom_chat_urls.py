from django.urls import path

from tests.custom_chat_views import TestCustomChatView

app_name = "custom_chat"

urlpatterns = [
    path("", TestCustomChatView.page_view(), name="home"),
    path("chat/<uuid:conversation_id>/", TestCustomChatView.page_view(), name="detail"),
    path("embed/", TestCustomChatView.embed_view(), name="embed"),
    path(
        "embed/<uuid:conversation_id>/",
        TestCustomChatView.embed_view(),
        name="embed-detail",
    ),
    path("api/chat/", TestCustomChatView.message_view(), name="message"),
    path(
        "api/conversations/new/",
        TestCustomChatView.new_conversation_view(),
        name="new",
    ),
]
