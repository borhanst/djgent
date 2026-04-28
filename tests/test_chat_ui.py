from __future__ import annotations

import re
from pathlib import Path
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

        response = client.get("/chat/")

        assert response.status_code == 200
        assert b"Test Chat" in response.content
        assert b"New conversation" in response.content

    def test_configured_input_placeholder_renders(self, settings) -> None:
        self._configure(settings)
        settings.DJGENT["CHAT_UI"]["INPUT_PLACEHOLDER"] = "Ask the release assistant"
        client = Client()

        response = client.get("/chat/")

        assert response.status_code == 200
        assert b'placeholder="Ask the release assistant"' in response.content

    def test_post_message_creates_conversation(self, settings) -> None:
        self._configure(settings)
        client = Client()
        conversation = Conversation.objects.create(
            agent_name="djgent-chat",
            name="",
        )

        with patch("djgent.chat.views.ConfiguredChatView.build_agent") as build_agent:
            build_agent.return_value.get_conversation_id.return_value = str(conversation.id)

            with patch("djgent.chat.views.run_agent_with_request") as runner:
                runner.return_value = {"output": "Hello from Djgent"}

                response = client.post(
                    "/chat/api/chat/",
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

    def test_post_message_can_stream_response_events(self, settings) -> None:
        self._configure(settings)
        client = Client()
        conversation = Conversation.objects.create(
            agent_name="djgent-chat",
            name="",
        )

        with patch("djgent.chat.views.ConfiguredChatView.build_agent") as build_agent:
            build_agent.return_value.get_conversation_id.return_value = str(conversation.id)

            with patch("djgent.chat.views.stream_agent_with_request") as streamer:
                streamer.return_value = [
                    {
                        "event": "run.start",
                        "data": {"thread_id": str(conversation.id)},
                    },
                    {
                        "event": "message.delta",
                        "data": {"delta": "Hello "},
                    },
                    {
                        "event": "message.delta",
                        "data": {"delta": "from stream"},
                    },
                    {
                        "event": "message.complete",
                        "data": {"content": "Hello from stream"},
                    },
                    {
                        "event": "run.end",
                        "data": {"output": "Hello from stream"},
                    },
                ]

                response = client.post(
                    "/chat/api/chat/",
                    data='{"message":"Hello","stream":true}',
                    content_type="application/json",
                )
                body = b"".join(response.streaming_content).decode("utf-8")

        assert response.status_code == 200
        assert response["Content-Type"] == "text/event-stream"
        assert "event: run.start" in body
        assert "event: message.delta" in body
        assert '"delta": "Hello "' in body
        assert '"delta": "from stream"' in body
        assert "event: message.complete" in body
        assert '"content": "Hello from stream"' in body
        assert "event: run.end" in body
        assert '"conversation_id"' in body
        assert body.count('"role": "ai"') == 0

        conversation = Conversation.objects.get(
            id=conversation.id,
            agent_name="djgent-chat",
        )
        assert conversation.name == "Hello"

    def test_streaming_new_conversation_detail_is_accessible(self, settings) -> None:
        self._configure(settings)
        client = Client()

        with patch("djgent.chat.views.ConfiguredChatView.build_agent") as build_agent:
            def build_agent_for_conversation(request, conversation_id=None):
                agent = build_agent.return_value
                agent.get_conversation_id.return_value = conversation_id
                return agent

            build_agent.side_effect = build_agent_for_conversation

            with patch("djgent.chat.views.stream_agent_with_request") as streamer:
                streamer.return_value = [
                    {
                        "event": "message.complete",
                        "data": {"content": "Hello from stream"},
                    },
                ]

                response = client.post(
                    "/chat/api/chat/",
                    data='{"message":"Hello","stream":true}',
                    content_type="application/json",
                )
                body = b"".join(response.streaming_content).decode("utf-8")

        assert response.status_code == 200
        conversation = Conversation.objects.get(agent_name="djgent-chat")
        assert f'"conversation_id": "{conversation.id}"' in body

        detail_response = client.get(f"/chat/{conversation.id}/")

        assert detail_response.status_code == 200

    def test_stream_message_validation_errors_use_sse(self, settings) -> None:
        self._configure(settings)
        client = Client()

        response = client.post(
            "/chat/api/chat/",
            data='{"message":""}',
            content_type="application/json",
            HTTP_ACCEPT="text/event-stream",
        )

        assert response.status_code == 400
        assert response["Content-Type"] == "text/event-stream"
        body = b"".join(response.streaming_content).decode("utf-8")
        assert "event: error" in body
        assert '"error": "Message is required."' in body

    def test_stream_message_provider_errors_use_sse(self, settings) -> None:
        self._configure(settings)
        settings.DJGENT["API_KEYS"] = {"OPENAI": ""}
        client = Client()

        response = client.post(
            "/chat/api/chat/",
            data='{"message":"Hello","stream":true}',
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response["Content-Type"] == "text/event-stream"
        body = b"".join(response.streaming_content).decode("utf-8")
        assert "event: error" in body
        assert '"ok": false' in body

    def test_streaming_can_be_disabled_in_chat_settings(self, settings) -> None:
        self._configure(settings)
        settings.DJGENT["CHAT_UI"]["STREAMING"] = False
        client = Client()
        conversation = Conversation.objects.create(
            agent_name="djgent-chat",
            name="",
        )

        with patch("djgent.chat.views.ConfiguredChatView.build_agent") as build_agent:
            build_agent.return_value.get_conversation_id.return_value = str(conversation.id)

            with patch("djgent.chat.views.run_agent_with_request") as runner:
                runner.return_value = {"output": "Hello without stream"}

                response = client.post(
                    "/chat/api/chat/",
                    data='{"message":"Hello","stream":true}',
                    content_type="application/json",
                    HTTP_ACCEPT="text/event-stream",
                )

        assert response.status_code == 200
        assert response["Content-Type"] == "application/json"
        assert response.json()["message"]["content"] == "Hello without stream"

    def test_streaming_setting_is_exposed_to_templates(self, settings) -> None:
        self._configure(settings)
        settings.DJGENT["CHAT_UI"]["STREAMING"] = False
        client = Client()

        response = client.get("/chat/")

        assert response.status_code == 200
        assert b"streamingEnabled: false" in response.content
        assert b'id="stream-status"' not in response.content

    def test_new_conversation_creates_blank_conversation(self, settings) -> None:
        self._configure(settings)
        client = Client()

        response = client.post("/chat/api/conversations/new/")

        assert response.status_code == 200
        data = response.json()
        conversation = Conversation.objects.get(
            id=data["conversation_id"],
            agent_name="djgent-chat",
        )
        assert conversation.name == ""
        assert data["redirect_url"] == f"/chat/{conversation.id}/"

    def test_anonymous_user_can_only_access_session_conversation(self, settings) -> None:
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

    def test_anonymous_user_can_adopt_existing_conversation_without_session(
        self, settings
    ) -> None:
        self._configure(settings)
        client = Client()
        conversation = Conversation.objects.create(
            agent_name="djgent-chat",
            user=None,
            name="Recovered conversation",
        )

        response = client.get(f"/chat/{conversation.id}/")

        assert response.status_code == 200
        assert str(conversation.id) in client.session["djgent_chat_conversation_ids"]

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

        home_response = client.get("/chat/")
        own_response = client.get(f"/chat/{own_conversation.id}/")
        other_response = client.get(f"/chat/{other_conversation.id}/")

        assert home_response.status_code == 200
        assert b"My conversation" in home_response.content
        assert b"Other conversation" not in home_response.content
        assert own_response.status_code == 200
        assert other_response.status_code == 404

    def test_configured_chat_auto_loads_registered_tools_by_default(self, settings) -> None:
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

    def test_configured_chat_streaming_defaults_to_enabled(self, settings) -> None:
        self._configure(settings)

        assert ConfiguredChatView().get_streaming_enabled() is True

    def test_configured_chat_can_disable_streaming(self, settings) -> None:
        self._configure(settings)
        settings.DJGENT["CHAT_UI"]["STREAMING"] = False

        assert ConfiguredChatView().get_streaming_enabled() is False


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

        with patch("tests.custom_chat_views.TestCustomChatView.build_agent") as build_agent:
            build_agent.return_value.get_conversation_id.return_value = str(conversation.id)

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

    def test_post_message_can_stream_for_subclass_view(self, settings) -> None:
        self._configure(settings)
        client = Client()
        conversation = Conversation.objects.create(
            agent_name="custom-chat",
            name="",
        )

        with patch("tests.custom_chat_views.TestCustomChatView.build_agent") as build_agent:
            build_agent.return_value.get_conversation_id.return_value = str(conversation.id)

            with patch("djgent.chat.views.stream_agent_with_request") as streamer:
                streamer.return_value = [
                    {"event": "message.delta", "data": {"delta": "Custom "}},
                    {"event": "message.delta", "data": {"delta": "stream"}},
                    {
                        "event": "message.complete",
                        "data": {"content": "Custom stream"},
                    },
                ]

                response = client.post(
                    "/api/chat/",
                    data='{"message":"Hello","stream":true}',
                    content_type="application/json",
                )
                body = b"".join(response.streaming_content).decode("utf-8")

        assert response.status_code == 200
        assert response["Content-Type"] == "text/event-stream"
        assert "event: message.delta" in body
        assert '"delta": "Custom "' in body
        assert '"delta": "stream"' in body
        assert "event: run.end" in body
        assert '"content": "Custom stream"' in body
        assert body.count('"role": "ai"') == 0

    def test_embed_view_works_for_subclass(self, settings) -> None:
        self._configure(settings)
        client = Client()

        response = client.get("/embed/")

        assert response.status_code == 200
        assert b"chat-embed-shell" in response.content

    def test_new_conversation_endpoint_creates_and_redirects_to_detail(
        self, settings
    ) -> None:
        self._configure(settings)
        client = Client()

        response = client.post("/api/conversations/new/")

        assert response.status_code == 200
        data = response.json()
        conversation = Conversation.objects.get(
            id=data["conversation_id"],
            agent_name="custom-chat",
        )
        assert conversation.name == ""
        assert data["conversation"]["name"] == "Untitled chat"
        assert data["redirect_url"] == f"/chat/{conversation.id}/"

        session = client.session
        assert str(conversation.id) in session["djgent_chat_conversation_ids"]

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


class TestExampleChatUiAssets:
    def test_example_template_exposes_streaming_config(self) -> None:
        template = Path("example/chat_ui/templates/chat_ui/chat.html").read_text()

        assert "streamingEnabled" in template
        assert "streaming_enabled|yesno" in template

    def test_example_javascript_consumes_streaming_events(self) -> None:
        script = Path("example/chat_ui/static/chat_ui/chat.js").read_text()

        assert "function postStream" in script
        assert '"Accept": "text/event-stream"' in script
        assert 'eventType === "message.delta"' in script
        assert 'eventType === "run.end"' in script

    @pytest.mark.parametrize(
        "script_path",
        [
            "djgent/chat/static/djgent/chat.js",
            "example/chat_ui/static/chat_ui/chat.js",
        ],
    )
    def test_stream_finalization_updates_existing_ai_message(self, script_path: str) -> None:
        script = Path(script_path).read_text()
        match = re.search(
            r"function finishAssistantDraft\(content\) \{(?P<body>.*?)\n\}",
            script,
            re.DOTALL,
        )
        assert match is not None
        body = match.group("body")

        assert 'lastMessage && lastMessage.role === "ai"' in body
        assert 'lastMessage.role === "ai" && lastMessage.isStreaming' not in body
