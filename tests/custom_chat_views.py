from typing import Optional

from djgent import Agent
from djgent.chat import BaseChatView


class TestCustomChatView(BaseChatView):
    home_url_name = "home"
    embed_url_name = "embed"
    message_url_name = "message"
    new_conversation_url_name = "new"
    agent_name = "custom-chat"
    page_title = "Custom Chat"
    chat_title = "Custom Chat"
    chat_subtitle = "Custom subclass test view"
    welcome_message = "Ask the custom test agent anything."
    input_placeholder = "Message custom agent..."
    tools = ["calculator"]
    system_prompt = "You are the custom test chat agent."

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
        )
