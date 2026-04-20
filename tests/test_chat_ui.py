from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from djgent.chat.views import ConfiguredChatView
from djgent.models import Conversation


@pytest.mark.django_db
class TestBuiltInChatUi:
    def _configure(self, settings) -> None:
        settings.ROOT_URLCONF = "tests.chat_urls"
        settings.DJGENT = {
            "DEFAULT_LLM": "openai:gpt-4o-mini",
            "API_KEYS": {"OPENAI": "test-key"},
            "CHAT_UI": {
                "TITLE": "Test Chat",
                "TOOLS": ["calculator", "datetime"],
            },
        }

    def test_home_renders(self, settings) -> None:
        self._configure(settings)
        client = Client()

        response = client.get("/")

        assert response.status_code == 200
        assert b"Test Chat" in response.content
        assert b"New conversation" in response.content

    def test_post_message_creates_conversation(self, settings) -> None:
        self._configure(settings)
        client = Client()
        conversation = Conversation.objects.create(
            agent_name="djgent-chat",
            name="",
        )

        with patch("djgent.chat.views.ConfiguredChatView.build_agent") as build_agent:
            build_agent.return_value.get_conversation_id.return_value = str(
                conversation.id
            )

            with patch("djgent.chat.views.run_agent_with_request") as runner:
                runner.return_value = {"output": "Hello from Djgent"}

                response = client.post(
                    "/api/chat/",
                    data='{"message":"Hello"}',
                    content_type="application/json",
                )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["message"]["content"] == "Hello from Djgent"

        conversation = Conversation.objects.get(
            id=data["conversation_id"],
            agent_name="djgent-chat",
        )
        assert conversation.name == "Hello"

    def test_anonymous_user_can_only_access_session_conversation(
        self, settings
    ) -> None:
        self._configure(settings)
        client = Client()
        own_conversation = Conversation.objects.create(
            agent_name="djgent-chat",
            user=None,
            name="Own conversation",
        )
        other_conversation = Conversation.objects.create(
            agent_name="djgent-chat",
            user=None,
            name="Other conversation",
        )

        session = client.session
        session["djgent_chat_conversation_ids"] = [str(own_conversation.id)]
        session.save()

        own_response = client.get(f"/chat/{own_conversation.id}/")
        other_response = client.get(f"/chat/{other_conversation.id}/")

        assert own_response.status_code == 200
        assert other_response.status_code == 404

    def test_authenticated_user_only_sees_own_conversations(self, settings) -> None:
        self._configure(settings)
        client = Client()
        user_model = get_user_model()
        current_user = user_model.objects.create_user(
            username="chat-user",
            password="test-pass",
        )
        other_user = user_model.objects.create_user(
            username="other-user",
            password="test-pass",
        )
        own_conversation = Conversation.objects.create(
            agent_name="djgent-chat",
            user=current_user,
            name="My conversation",
        )
        other_conversation = Conversation.objects.create(
            agent_name="djgent-chat",
            user=other_user,
            name="Other conversation",
        )

        client.force_login(current_user)

        home_response = client.get("/")
        own_response = client.get(f"/chat/{own_conversation.id}/")
        other_response = client.get(f"/chat/{other_conversation.id}/")

        assert home_response.status_code == 200
        assert b"My conversation" in home_response.content
        assert b"Other conversation" not in home_response.content
        assert own_response.status_code == 200
        assert other_response.status_code == 404

    def test_configured_chat_auto_loads_registered_tools_by_default(
        self, settings
    ) -> None:
        self._configure(settings)
        request = Client().get("/").wsgi_request

        with patch("djgent.chat.views.Agent.create") as create:
            ConfiguredChatView().build_agent(request)

        assert create.call_args.kwargs["tools"] == ["calculator", "datetime"]
        assert create.call_args.kwargs["auto_load_tools"] is True

    def test_configured_chat_can_disable_auto_load_tools(self, settings) -> None:
        self._configure(settings)
        settings.DJGENT["CHAT_UI"]["AUTO_LOAD_TOOLS"] = False
        request = Client().get("/").wsgi_request

        with patch("djgent.chat.views.Agent.create") as create:
            ConfiguredChatView().build_agent(request)

        assert create.call_args.kwargs["auto_load_tools"] is False


@pytest.mark.django_db
class TestCustomChatView:
    def _configure(self, settings) -> None:
        settings.ROOT_URLCONF = "tests.custom_root_urls"
        settings.DJGENT = {
            "DEFAULT_LLM": "openai:gpt-4o-mini",
            "API_KEYS": {"OPENAI": "test-key"},
        }

    def test_home_renders(self, settings) -> None:
        self._configure(settings)
        client = Client()
        Conversation.objects.create(agent_name="custom-chat", name="Visible")
        Conversation.objects.create(agent_name="other-chat", name="Hidden")

        response = client.get("/")

        assert response.status_code == 200
        assert b"Custom Chat" in response.content
        assert b"Custom subclass test view" in response.content
        assert b"Visible" not in response.content
        assert b"Hidden" not in response.content

    def test_post_message_uses_subclass_agent(self, settings) -> None:
        self._configure(settings)
        client = Client()
        conversation = Conversation.objects.create(
            agent_name="custom-chat",
            name="",
        )

        with patch(
            "tests.custom_chat_views.TestCustomChatView.build_agent"
        ) as build_agent:
            build_agent.return_value.get_conversation_id.return_value = str(
                conversation.id
            )

            with patch("djgent.chat.views.run_agent_with_request") as runner:
                runner.return_value = {"output": "Hello from custom chat"}

                response = client.post(
                    "/api/chat/",
                    data='{"message":"Hello"}',
                    content_type="application/json",
                )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["message"]["content"] == "Hello from custom chat"

        conversation = Conversation.objects.get(
            id=data["conversation_id"],
            agent_name="custom-chat",
        )
        assert conversation.name == "Hello"

    def test_embed_view_works_for_subclass(self, settings) -> None:
        self._configure(settings)
        client = Client()

        response = client.get("/embed/")

        assert response.status_code == 200
        assert b"chat-embed-shell" in response.content

    def test_new_conversation_endpoint_uses_custom_home_url(self, settings) -> None:
        self._configure(settings)
        client = Client()

        response = client.post("/api/conversations/new/")

        assert response.status_code == 200
        assert response.json()["redirect_url"] == "/"

    def test_custom_view_anonymous_access_is_session_scoped(self, settings) -> None:
        self._configure(settings)
        client = Client()
        own_conversation = Conversation.objects.create(
            agent_name="custom-chat",
            user=None,
            name="Session conversation",
        )
        other_conversation = Conversation.objects.create(
            agent_name="custom-chat",
            user=None,
            name="Other session conversation",
        )

        session = client.session
        session["djgent_chat_conversation_ids"] = [str(own_conversation.id)]
        session.save()

        own_response = client.get(f"/chat/{own_conversation.id}/")
        other_response = client.get(f"/chat/{other_conversation.id}/")

        assert own_response.status_code == 200
        assert other_response.status_code == 404
