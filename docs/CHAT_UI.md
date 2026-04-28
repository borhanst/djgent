# Chat UI

Djgent ships with a built-in chat UI and a reusable `BaseChatView` for projects
that want the same chat behavior with a custom agent.

## Built-In Chat App

Mount the default chat UI:

```python
# settings.py
DJGENT = {
    "DEFAULT_LLM": "openai:gpt-4o-mini",
    "API_KEYS": {
        "OPENAI": os.environ.get("OPENAI_API_KEY", ""),
    },
    "CHAT_UI": {
        "TITLE": "Support Copilot",
        "TOOLS": ["calculator", "datetime", "search"],
        "AUTO_LOAD_TOOLS": True,
        "STREAMING": True,
        "SYSTEM_PROMPT": "You are the support assistant for our product.",
        "BUBBLE_ENABLED": True,
        "BUBBLE_TITLE": "Ask Support",
    },
}
```

```python
# urls.py
from django.urls import include, path

urlpatterns = [
    path("ai/", include("djgent.chat.urls")),
]
```

This keeps Djgent's default templates, conversation history, anonymous session
support, and embed/bubble flow.

## Custom Chat Views

Use `BaseChatView` when you want to provide your own agent but keep the shared
chat functionality:

- authenticated users see their own conversations for that agent
- unauthenticated users can also chat, with conversations scoped to their session
- message posting, conversation naming, persistence, and embed rendering are
  already handled

### Minimal subclass

```python
from typing import Optional

from djgent import Agent
from djgent.chat import BaseChatView


class SupportChatView(BaseChatView):
    agent_name = "support-chat"
    detail_url_name = "detail"
    page_title = "Support Chat"
    chat_title = "Support Chat"
    chat_subtitle = "Chat with the support agent."
    tools = ["calculator", "datetime", "search"]
    auto_load_tools = True
    system_prompt = "You are the support assistant for our SaaS product."

    def build_agent(
        self, request, conversation_id: Optional[str] = None
    ) -> Agent:
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
```

`AUTO_LOAD_TOOLS` defaults to `True` for chat views, so tools registered with
`@tool` or app `tools.py` auto-discovery are available to the chat agent without
listing every tool in `CHAT_UI["TOOLS"]`. Set it to `False` when you want only
the explicit `TOOLS` list.

### URL registration

```python
from django.urls import path

from .views import SupportChatView

urlpatterns = [
    path("", SupportChatView.page_view(), name="home"),
    path("chat/<uuid:conversation_id>/", SupportChatView.page_view(), name="detail"),
    path("embed/", SupportChatView.embed_view(), name="embed"),
    path("embed/<uuid:conversation_id>/", SupportChatView.embed_view(), name="embed-detail"),
    path("api/chat/", SupportChatView.message_view(), name="message"),
    path("api/conversations/new/", SupportChatView.new_conversation_view(), name="new"),
]
```

## What `BaseChatView` Provides

- `page_view()` for the main chat page
- `embed_view()` for iframe/embed mode
- `message_view()` for posting messages
- `new_conversation_view()` for creating a blank conversation and returning its
  detail-page redirect URL
- conversation access control for authenticated and anonymous users
- database-backed conversation history using the agent name returned by
  `get_agent_name()`

## Streaming Responses

`message_view()` keeps the normal JSON response by default. To receive
server-sent events instead, send `stream: true` in the JSON body or set
`Accept: text/event-stream`:

```javascript
const response = await fetch("/ai/api/chat/", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  },
  body: JSON.stringify({
    message: "Summarize this conversation",
    conversation_id: currentConversationId,
    stream: true,
  }),
});
```

The stream emits:

- `run.start` when the agent run begins
- `message.delta` for incremental assistant text
- `message.complete` for the final assistant message
- `tool.start` and `tool.end` for tool runtime events
- `run.end` with conversation id and sidebar conversation metadata
- `error` for validation, provider, or execution failures

Streaming is enabled by default for `ConfiguredChatView`. Disable it with:

```python
DJGENT = {
    "CHAT_UI": {
        "STREAMING": False,
    },
}
```

When disabled, stream requests fall back to the normal JSON response and the
built-in browser UI uses non-streaming posts.

## Subclass Contract

Required:

- implement `build_agent(request, conversation_id=None)`

Optional overrides:

- `get_agent_name()`
- `detail_url_name`
- `get_page_title()`
- `get_chat_title()`
- `get_chat_subtitle()`
- `get_welcome_message()`
- `get_input_placeholder()`
- `get_tool_names()`
- `get_template_name()`
- `get_embed_template_name()`

Class attributes with the same names can be used for the common cases.

## Built-In vs Custom

- Use `ConfiguredChatView` and `djgent.chat.urls` when one settings-backed agent
  is enough.
- Use `BaseChatView` when your Django app wants to define its own agent in Python
  without rebuilding chat persistence and request handling.
