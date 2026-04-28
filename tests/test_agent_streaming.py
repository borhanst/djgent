from __future__ import annotations

import pytest
from langchain_core.language_models.fake_chat_models import (
    FakeListChatModel,
    FakeMessagesListChatModel,
)
from langchain_core.messages import AIMessage

from djgent.agents.base import Agent
from djgent.tools.base import Tool


class BindableFakeMessagesModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


class AddOneTool(Tool):
    name = "add_one"
    description = "Add one to an integer."

    def _run(self, x: int) -> str:
        return str(x + 1)


def event_names(events: list[dict]) -> list[str]:
    return [event["event"] for event in events]


@pytest.mark.django_db
def test_agent_stream_yields_token_deltas_and_persists_final_message(settings) -> None:
    settings.DJGENT = {"AUDIT": {"ENABLED": False}}
    agent = Agent(
        name="streaming-agent",
        llm=FakeListChatModel(responses=["Hello"]),
        memory=True,
        memory_backend="memory",
    )

    events = list(agent.stream("Say hi"))

    assert event_names(events) == [
        "run.start",
        "message.delta",
        "message.delta",
        "message.delta",
        "message.delta",
        "message.delta",
        "message.complete",
        "run.end",
    ]
    assert "".join(
        event["data"]["delta"] for event in events if event["event"] == "message.delta"
    ) == "Hello"
    assert events[-2]["data"]["content"] == "Hello"
    assert agent._memory_backend.get_messages()[-2]["content"] == "Say hi"
    assert agent._memory_backend.get_messages()[-1]["content"] == "Hello"


@pytest.mark.django_db
def test_agent_stream_emits_tool_events_without_streaming_tool_output_as_delta(settings) -> None:
    settings.DJGENT = {"AUDIT": {"ENABLED": False}}
    model = BindableFakeMessagesModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "add_one",
                        "args": {"x": 1},
                        "id": "call-1",
                    }
                ],
            ),
            AIMessage(content="two"),
        ]
    )
    agent = Agent(
        name="tool-streaming-agent",
        llm=model,
        tools=[AddOneTool()],
        memory=False,
    )

    events = list(agent.stream("Use the tool"))

    assert "tool.start" in event_names(events)
    assert "tool.end" in event_names(events)
    assert [
        event["data"]["delta"] for event in events if event["event"] == "message.delta"
    ] == ["two"]
    assert events[-2]["event"] == "message.complete"
    assert events[-2]["data"]["content"] == "two"
