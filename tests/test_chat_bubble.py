from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.template import engines
from django.test import Client, RequestFactory


def _chat_settings() -> dict:
    return {
        "DEFAULT_LLM": "openai:gpt-4o-mini",
        "API_KEYS": {"OPENAI": "test-key"},
        "CHAT_UI": {
            "BUBBLE_ENABLED": True,
            "BUBBLE_TITLE": "Ask Djgent",
            "TOOLS": ["calculator", "datetime"],
        },
    }


def _render_bubble(request) -> str:
    template = engines["django"].from_string(
        "{% load djgent_chat %}{% djgent_chat_bubble %}"
    )
    return template.render({"request": request})


@pytest.mark.django_db
class TestChatBubble:
    def test_bubble_renders_when_enabled(self, settings) -> None:
        settings.ROOT_URLCONF = "tests.chat_urls"
        settings.DJGENT = _chat_settings()
        request = RequestFactory().get("/")
        request.resolver_match = SimpleNamespace(
            namespace="",
            app_name="",
            namespaces=[],
        )

        html = _render_bubble(request)

        assert "data-djgent-chat-bubble" in html
        assert 'data-src="/embed/"' in html
        assert "Ask Djgent" in html

    def test_bubble_not_rendered_on_chat_pages(self, settings) -> None:
        settings.ROOT_URLCONF = "tests.chat_urls"
        settings.DJGENT = _chat_settings()
        request = RequestFactory().get("/")
        request.resolver_match = SimpleNamespace(
            namespace="djgent_chat",
            app_name="djgent_chat",
            namespaces=["djgent_chat"],
        )

        html = _render_bubble(request)

        assert "data-djgent-chat-bubble" not in html

    def test_embed_route_uses_embed_layout(self, settings) -> None:
        settings.ROOT_URLCONF = "tests.chat_urls"
        settings.DJGENT = _chat_settings()
        client = Client()

        embed_response = client.get("/embed/")
        home_response = client.get("/")

        assert embed_response.status_code == 200
        assert b"chat-embed-shell" in embed_response.content
        assert b"app-sidebar" not in embed_response.content
        assert home_response.status_code == 200
        assert b"app-sidebar" in home_response.content
