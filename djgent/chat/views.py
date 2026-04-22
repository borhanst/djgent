import json
from abc import ABC, abstractmethod
from typing import Any, Optional

from django.conf import settings
from django.db import models
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_GET, require_POST

from djgent import Agent
from djgent.models import Conversation
from djgent.utils.agent_runner import run_agent_with_request

SESSION_KEY = "djgent_chat_conversation_ids"
DEFAULT_SYSTEM_PROMPT = (
    "You are the built-in Djgent chat assistant. Be concise, helpful, and "
    "use available tools when calculations, dates, or project-specific tasks "
    "benefit from them. If the runtime is not configured for a working LLM "
    "provider, explain that clearly."
)


def _chat_settings() -> dict[str, Any]:
    return ConfiguredChatView().get_settings()


class BaseChatView(ABC):
    """Reusable chat backend that handles persistence and anonymous sessions.

    This is an abstract base class. Subclasses **must** implement
    :meth:`build_agent` to provide an agent instance.  For a ready-to-use
    implementation that reads settings from ``DJGENT["CHAT_UI"]``, see
    :class:`ConfiguredChatView`.
    """

    session_key = SESSION_KEY
    template_name = "djgent/chat.html"
    embed_template_name = "djgent/chat_embed.html"
    home_url_name = "home"
    embed_url_name = "embed"
    message_url_name = "message"
    new_conversation_url_name = "new"
    conversation_path_segment = "chat/"
    page_title = "Djgent Chat"
    chat_title = "Djgent Chat"
    chat_subtitle = "A built-in chat surface for Djgent agents with persistent conversations."
    welcome_message = (
        "Start with a question. Conversation history is stored with Djgent's "
        "database memory backend."
    )
    input_placeholder = "Message Djgent..."
    system_prompt = DEFAULT_SYSTEM_PROMPT
    tools = ["calculator", "datetime"]
    auto_load_tools = True
    agent_name = "djgent-chat"

    # Pagination / display limits
    max_session_conversations = 20  # tracked in session
    max_sidebar_conversations = 12  # shown in sidebar
    message_preview_length = 90  # chars for conversation preview
    default_conversation_name_length = 60  # chars

    @classmethod
    def page_view(cls):
        @require_GET
        def view(request, conversation_id: Optional[str] = None):
            return cls().render_page(request, conversation_id=conversation_id)

        return view

    @classmethod
    def embed_view(cls):
        @require_GET
        @xframe_options_sameorigin
        def view(request, conversation_id: Optional[str] = None):
            return cls().render_embed(request, conversation_id=conversation_id)

        return view

    @classmethod
    def message_view(cls):
        @require_POST
        def view(request):
            return cls().post_message(request)

        return view

    @classmethod
    def new_conversation_view(cls):
        @require_POST
        def view(request):
            return cls().reset_conversation(request)

        return view

    def get_settings(self) -> dict[str, Any]:
        return {}

    def get_agent_name(self) -> str:
        return self.agent_name

    def get_page_title(self) -> str:
        return self.page_title

    def get_chat_title(self) -> str:
        return self.chat_title

    def get_chat_subtitle(self) -> str:
        return self.chat_subtitle

    def get_welcome_message(self) -> str:
        return self.welcome_message

    def get_input_placeholder(self) -> str:
        return self.input_placeholder

    def get_tool_names(self) -> list[str]:
        return list(self.tools)

    def get_auto_load_tools(self) -> bool:
        return bool(self.auto_load_tools)

    def get_template_name(self) -> str:
        return self.template_name

    def get_embed_template_name(self) -> str:
        return self.embed_template_name

    def get_system_prompt(self) -> str:
        return self.system_prompt

    def get_session_key(self) -> str:
        return self.session_key

    def get_route_name(self, request, url_name: str) -> str:
        namespace = getattr(getattr(request, "resolver_match", None), "namespace", "")
        return f"{namespace}:{url_name}" if namespace else url_name

    def get_home_url(self, request) -> str:
        return reverse(self.get_route_name(request, self.home_url_name))

    def get_embed_url(self, request) -> str:
        return reverse(self.get_route_name(request, self.embed_url_name))

    def get_message_url(self, request) -> str:
        return reverse(self.get_route_name(request, self.message_url_name))

    def get_new_conversation_url(self, request) -> str:
        return reverse(self.get_route_name(request, self.new_conversation_url_name))

    def get_conversation_path_prefix(self, request, *, embed: bool = False) -> str:
        if embed:
            return self.get_embed_url(request)
        return f"{self.get_home_url(request)}{self.conversation_path_segment}"

    def get_active_user(self, request) -> Optional[Any]:
        user = getattr(request, "user", None)
        return user if user and user.is_authenticated else None

    def get_provider_status(self) -> dict[str, Any]:
        djgent_settings = getattr(settings, "DJGENT", {}) or {}
        provider_string = djgent_settings.get("DEFAULT_LLM", "")
        provider = provider_string.split(":", 1)[0].lower() if provider_string else ""
        api_keys = djgent_settings.get("API_KEYS", {}) or {}

        if provider == "ollama":
            return {
                "provider": provider_string,
                "configured": True,
                "message": (
                    "Configured for Ollama. Make sure the Ollama server is " "running locally."
                ),
            }

        provider_key_map = {
            "openai": "OPENAI",
            "anthropic": "ANTHROPIC",
            "google": "GOOGLE",
            "gemini": "GOOGLE",
            "groq": "GROQ",
            "openrouter": "OPENROUTER",
            "azure_openai": "OPENAI",
        }
        key_name = provider_key_map.get(provider)
        has_key = bool(key_name and api_keys.get(key_name))

        if has_key:
            return {
                "provider": provider_string,
                "configured": True,
                "message": f"Configured for {provider_string}.",
            }

        return {
            "provider": provider_string or "unset",
            "configured": False,
            "message": (
                f"Set a valid API key for {provider_string or 'your provider'} "
                "or switch DJGENT_DEFAULT_LLM to a reachable local Ollama model."
            ),
        }

    def get_session_conversation_ids(self, request) -> list[str]:
        return list(request.session.get(self.get_session_key(), []))

    def save_session_conversation_ids(self, request, conversation_ids: list[str]) -> None:
        request.session[self.get_session_key()] = conversation_ids
        request.session.modified = True

    def track_conversation(self, request, conversation_id: str) -> None:
        conversation_ids = self.get_session_conversation_ids(request)
        if conversation_id in conversation_ids:
            conversation_ids.remove(conversation_id)
        conversation_ids.insert(0, conversation_id)
        self.save_session_conversation_ids(
            request, conversation_ids[: self.max_session_conversations]
        )

    def get_conversation_queryset(self, request) -> models.QuerySet:
        user = self.get_active_user(request)
        queryset = Conversation.objects.filter(agent_name=self.get_agent_name()).order_by(
            "-updated_at"
        )

        if user:
            return queryset.filter(user=user)

        conversation_ids = self.get_session_conversation_ids(request)
        if not conversation_ids:
            return queryset.none()
        return queryset.filter(user__isnull=True, id__in=conversation_ids)

    def get_conversation_or_404(self, request, conversation_id: str) -> Conversation:
        conversation = self.get_conversation_queryset(request).filter(id=conversation_id).first()
        if not conversation:
            raise Http404("Conversation not found.")
        return conversation

    def serialize_conversation(self, conversation: Conversation) -> dict[str, Any]:
        last_message = conversation.messages.order_by("-created_at").first()
        return {
            "id": str(conversation.id),
            "name": conversation.name or "Untitled chat",
            "updated_at": conversation.updated_at.isoformat(),
            "message_count": conversation.message_count,
            "preview": (
                last_message.content[: self.message_preview_length]
                if last_message
                else "Start a new conversation."
            ),
        }

    def serialize_messages(self, conversation: Optional[Conversation]) -> list[dict[str, Any]]:
        if not conversation:
            return []

        return [
            {
                "id": message.id,
                "role": message.role,
                "content": message.content,
                "created_at": message.created_at.isoformat(),
            }
            for message in conversation.messages.all()
        ]

    @abstractmethod
    def build_agent(self, request, conversation_id: Optional[str] = None) -> Agent:
        """Return an Agent instance for handling chat messages."""

    def maybe_name_conversation(self, conversation: Conversation, prompt: str) -> None:
        if conversation.name:
            return
        conversation.name = (
            prompt.strip()[: self.default_conversation_name_length] or "Untitled chat"
        )
        conversation.save(update_fields=["name", "updated_at"])

    def get_page_context(
        self,
        request,
        conversation_id: Optional[str] = None,
        *,
        embed: bool = False,
    ) -> dict[str, Any]:
        selected_conversation = None
        if conversation_id:
            selected_conversation = self.get_conversation_or_404(request, conversation_id)

        conversations = [
            self.serialize_conversation(item)
            for item in self.get_conversation_queryset(request)[: self.max_sidebar_conversations]
        ]
        tools = self.get_tool_names()

        return {
            "page_title": self.get_page_title(),
            "chat_title": self.get_chat_title(),
            "chat_subtitle": self.get_chat_subtitle(),
            "welcome_message": self.get_welcome_message(),
            "input_placeholder": self.get_input_placeholder(),
            "tool_names": ", ".join(tools) or "none",
            "conversations": conversations,
            "selected_conversation": (
                self.serialize_conversation(selected_conversation)
                if selected_conversation
                else None
            ),
            "initial_messages": self.serialize_messages(selected_conversation),
            "provider_status": self.get_provider_status(),
            "chat_api_url": self.get_message_url(request),
            "new_chat_url": self.get_new_conversation_url(request),
            "chat_base_url": self.get_home_url(request),
            "conversation_path_prefix": self.get_conversation_path_prefix(request, embed=embed),
            "history_updates_enabled": not embed,
            "is_embed": embed,
        }

    def render_page(self, request, conversation_id: Optional[str] = None) -> Any:
        return render(
            request,
            self.get_template_name(),
            self.get_page_context(request, conversation_id=conversation_id),
        )

    def render_embed(self, request, conversation_id: Optional[str] = None) -> Any:
        return render(
            request,
            self.get_embed_template_name(),
            self.get_page_context(
                request,
                conversation_id=conversation_id,
                embed=True,
            ),
        )

    def reset_conversation(self, request) -> JsonResponse:
        """Clear the session's conversation tracking and redirect to home."""
        conversation_ids = self.get_session_conversation_ids(request)
        if conversation_ids:
            conversation_ids.clear()
            self.save_session_conversation_ids(request, conversation_ids)

        return JsonResponse({"ok": True, "redirect_url": self.get_home_url(request)})

    def post_message(self, request) -> JsonResponse:
        provider_status = self.get_provider_status()
        if not provider_status["configured"]:
            return JsonResponse(
                {"ok": False, "error": provider_status["message"]},
                status=400,
            )

        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse(
                {"ok": False, "error": "Invalid JSON payload."},
                status=400,
            )

        message = (payload.get("message") or "").strip()
        conversation_id = payload.get("conversation_id") or None
        if not message:
            return JsonResponse(
                {"ok": False, "error": "Message is required."},
                status=400,
            )

        if conversation_id:
            self.get_conversation_or_404(request, conversation_id)

        try:
            agent = self.build_agent(request, conversation_id=conversation_id)
            result = run_agent_with_request(agent, request, message)
        except Exception as exc:
            return JsonResponse({"ok": False, "error": str(exc)}, status=500)

        new_conversation_id = agent.get_conversation_id()
        conversation = (
            Conversation.objects.filter(
                id=new_conversation_id,
                agent_name=self.get_agent_name(),
            ).first()
            if new_conversation_id
            else None
        )
        if conversation:
            self.maybe_name_conversation(conversation, message)
            self.track_conversation(request, str(conversation.id))

        conversations = [
            self.serialize_conversation(item)
            for item in self.get_conversation_queryset(request)[: self.max_sidebar_conversations]
        ]

        return JsonResponse(
            {
                "ok": True,
                "conversation_id": new_conversation_id,
                "message": {
                    "role": "ai",
                    "content": result.get("output", ""),
                },
                "conversations": conversations,
            }
        )


class ConfiguredChatView(BaseChatView):
    """Built-in chat view that reads settings from DJGENT.CHAT_UI."""

    def get_settings(self) -> dict[str, Any]:
        djgent_settings = getattr(settings, "DJGENT", {}) or {}
        chat_settings = djgent_settings.get("CHAT_UI", {}) or {}
        title = chat_settings.get("TITLE", self.chat_title)
        return {
            "agent_name": chat_settings.get("AGENT_NAME", self.agent_name),
            "page_title": chat_settings.get("PAGE_TITLE", title),
            "title": title,
            "subtitle": chat_settings.get("SUBTITLE", self.chat_subtitle),
            "system_prompt": chat_settings.get("SYSTEM_PROMPT", BaseChatView.system_prompt),
            "tools": list(chat_settings.get("TOOLS", self.tools)),
            "auto_load_tools": chat_settings.get("AUTO_LOAD_TOOLS", self.auto_load_tools),
            "welcome_message": chat_settings.get("WELCOME_MESSAGE", self.welcome_message),
            "input_placeholder": chat_settings.get("INPUT_PLACEHOLDER", self.input_placeholder),
            "bubble_enabled": chat_settings.get("BUBBLE_ENABLED", False),
            "bubble_title": chat_settings.get("BUBBLE_TITLE", "Ask Djgent"),
            "bubble_label": chat_settings.get("BUBBLE_LABEL", "Open Djgent chat"),
            "bubble_position": chat_settings.get("BUBBLE_POSITION", "bottom-right"),
            "bubble_panel_width": chat_settings.get("BUBBLE_PANEL_WIDTH", "420px"),
            "bubble_panel_mobile_height": chat_settings.get(
                "BUBBLE_PANEL_MOBILE_HEIGHT",
                "78vh",
            ),
        }

    def get_agent_name(self) -> str:
        return self.get_settings()["agent_name"]

    def get_page_title(self) -> str:
        return self.get_settings()["page_title"]

    def get_chat_title(self) -> str:
        return self.get_settings()["title"]

    def get_chat_subtitle(self) -> str:
        return self.get_settings()["subtitle"]

    def get_welcome_message(self) -> str:
        return self.get_settings()["welcome_message"]

    def get_input_placeholder(self) -> str:
        return self.get_settings()["input_placeholder"]

    def get_tool_names(self) -> list[str]:
        return self.get_settings()["tools"]

    def get_auto_load_tools(self) -> bool:
        return bool(self.get_settings()["auto_load_tools"])

    def get_system_prompt(self) -> str:
        return self.get_settings()["system_prompt"]

    def build_agent(self, request, conversation_id: Optional[str] = None) -> Agent:
        return Agent.create(
            name=self.get_agent_name(),
            tools=self.get_tool_names(),
            memory=True,
            memory_backend="database",
            conversation_id=conversation_id,
            conversation_name="",
            user=self.get_active_user(request),
            system_prompt=self.get_system_prompt(),
            auto_load_tools=self.get_auto_load_tools(),
        )


chat_home = ConfiguredChatView.page_view()
chat_embed = ConfiguredChatView.embed_view()
new_conversation = ConfiguredChatView.new_conversation_view()
chat_message = ConfiguredChatView.message_view()
