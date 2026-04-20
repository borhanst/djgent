from typing import Optional

from djgent import Agent
from djgent.chat import BaseChatView

AGENT_NAME = "example-chat"
SYSTEM_PROMPT = (
    "You are the example chat assistant for a Django demo project. "
    "Be concise, helpful, and use available tools when calculations or "
    "date/time questions come up. Use the book_query tool for questions "
    "about demo books, authors, genres, or publication years. If the runtime "
    "is not configured for a working LLM provider, explain that clearly."
)


class ExampleChatView(BaseChatView):
    session_key = "djgent_example_conversation_ids"
    template_name = "chat_ui/chat.html"
    home_url_name = "chat-home"
    message_url_name = "chat-message"
    new_conversation_url_name = "chat-new"
    page_title = "Djgent Chat Demo"
    chat_title = "Example Chat"
    chat_subtitle = "A custom chat view built by subclassing Djgent's base chat."
    agent_name = AGENT_NAME
    tools = ["calculator", "datetime"]
    system_prompt = SYSTEM_PROMPT

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


chat_home = ExampleChatView.page_view()
new_conversation = ExampleChatView.new_conversation_view()
chat_message = ExampleChatView.message_view()
