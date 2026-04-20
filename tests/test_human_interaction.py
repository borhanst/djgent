"""Tests for LangChain human-in-the-loop integration."""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

from djgent.agents.base import Agent
from djgent.models import HumanInteractionRequest
from djgent.runtime.checkpoint import DjangoCheckpointSaver
from djgent.runtime.langchain_middleware import build_langchain_middleware


class FakeInterrupt:
    def __init__(self, value):
        self.value = value


class FakeGraphOutput:
    def __init__(self, value):
        self.interrupts = [FakeInterrupt(value)]


@pytest.fixture
def hitl_settings(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.DEFAULT_FROM_EMAIL = "noreply@example.com"
    settings.DJGENT = {
        "DEFAULT_LLM": "openai:gpt-4o-mini",
        "API_KEYS": {"OPENAI": "test"},
        "LANGCHAIN_MIDDLEWARE": {
            "human_in_the_loop": {
                "enabled": True,
                "interrupt_on": {
                    "send_email": {
                        "allowed_decisions": ["approve", "edit", "reject"],
                        "description": "Email requires owner approval.",
                    }
                },
                "description_prefix": "Pending owner approval",
                "site_owner_emails": ["owner@example.com"],
            }
        },
    }
    return settings


@pytest.mark.django_db
def test_human_interrupt_creates_request_and_emails_owner(
    hitl_settings, mock_llm, monkeypatch
) -> None:
    payload = {
        "action_requests": [
            {
                "name": "send_email",
                "arguments": {"to": "customer@example.com"},
                "description": "Email requires owner approval.",
            }
        ],
        "review_configs": [
            {
                "action_name": "send_email",
                "allowed_decisions": ["approve", "edit", "reject"],
            }
        ],
    }
    monkeypatch.setattr(
        Agent,
        "_invoke_model",
        lambda self, messages, execution, **kwargs: FakeGraphOutput(payload),
    )
    agent = Agent(
        name="support",
        llm=mock_llm,
        memory=True,
        memory_backend="database",
        langchain_middleware=hitl_settings.DJGENT["LANGCHAIN_MIDDLEWARE"],
    )

    output = agent.run("Send the email")

    request = HumanInteractionRequest.objects.get()
    assert "waiting for site owner approval" in output
    assert request.status == HumanInteractionRequest.STATUS_PENDING
    assert request.action_requests[0]["name"] == "send_email"
    assert request.site_owner_emails == ["owner@example.com"]
    assert agent._last_result.state["status"] == "waiting_for_human"

    from django.core import mail

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["owner@example.com"]


def test_hitl_config_strips_djgent_only_keys(settings, monkeypatch) -> None:
    created = []

    class FakeHumanInLoop:
        def __init__(self, **kwargs):
            created.append(kwargs)

    monkeypatch.setattr(
        "djgent.runtime.langchain_middleware._load_middleware_class",
        lambda name: FakeHumanInLoop,
    )
    settings.DJGENT = {
        "LANGCHAIN_MIDDLEWARE": {
            "human_in_the_loop": {
                "enabled": True,
                "interrupt_on": {"danger": True},
                "description_prefix": "Needs owner",
                "site_owner_emails": ["owner@example.com"],
                "notify_email": True,
            }
        }
    }

    middleware, checkpointer = build_langchain_middleware()

    assert len(middleware) == 1
    assert checkpointer is None
    assert created == [
        {
            "interrupt_on": {"danger": True},
            "description_prefix": "Needs owner",
        }
    ]


@pytest.mark.django_db
def test_django_checkpoint_saver_round_trips_checkpoint() -> None:
    saver = DjangoCheckpointSaver()
    config = {"configurable": {"thread_id": "thread-1"}}
    next_config = saver.put(
        config,
        {"id": "checkpoint-1", "data": {"x": 1}},
        {"source": "test"},
        {},
    )
    saver.put_writes(
        next_config,
        [("messages", [{"role": "ai", "content": "hello"}])],
        "task-1",
    )

    item = saver.get_tuple({"configurable": {"thread_id": "thread-1"}})
    checkpoint = item.checkpoint if hasattr(item, "checkpoint") else item["checkpoint"]
    metadata = item.metadata if hasattr(item, "metadata") else item["metadata"]
    pending_writes = (
        item.pending_writes if hasattr(item, "pending_writes") else item["pending_writes"]
    )

    assert checkpoint["id"] == "checkpoint-1"
    assert metadata["source"] == "test"
    assert pending_writes[0][1] == "messages"


@pytest.mark.django_db
def test_resume_human_interaction_uses_command_and_updates_request(
    hitl_settings, mock_llm, monkeypatch
) -> None:
    request = HumanInteractionRequest.objects.create(
        agent_name="support",
        thread_id="thread-1",
        site_owner_emails=["owner@example.com"],
        action_requests=[{"name": "send_email", "arguments": {"to": "a@b.com"}}],
        review_configs=[{"action_name": "send_email"}],
    )
    captured = {}

    class FakeCommand:
        def __init__(self, resume):
            self.resume = resume

    class FakeLCGraph:
        def invoke(self, command, **kwargs):
            captured["command"] = command
            captured["kwargs"] = kwargs
            return {"messages": [], "output": "done"}

    fake_langgraph = types.ModuleType("langgraph")
    fake_langgraph_types = types.ModuleType("langgraph.types")
    fake_langgraph_types.Command = FakeCommand
    fake_langchain = types.ModuleType("langchain")
    fake_langchain_agents = types.ModuleType("langchain.agents")
    fake_langchain_agents.create_agent = lambda **kwargs: FakeLCGraph()
    monkeypatch.setitem(sys.modules, "langgraph", fake_langgraph)
    monkeypatch.setitem(sys.modules, "langgraph.types", fake_langgraph_types)
    monkeypatch.setitem(sys.modules, "langchain", fake_langchain)
    monkeypatch.setitem(sys.modules, "langchain.agents", fake_langchain_agents)
    monkeypatch.setattr(
        Agent,
        "_build_langchain_runtime",
        lambda self: ([], SimpleNamespace()),
    )

    agent = Agent(
        name="support",
        llm=mock_llm,
        memory=False,
        langchain_middleware=hitl_settings.DJGENT["LANGCHAIN_MIDDLEWARE"],
        thread_id="thread-1",
    )
    result = agent.resume_human_interaction(request.id)

    request.refresh_from_db()
    assert result.output == "done"
    assert request.status == HumanInteractionRequest.STATUS_RESUMED
    assert captured["command"].resume == {"decisions": [{"type": "approve"}]}
    assert captured["kwargs"]["config"]["configurable"]["thread_id"] == "thread-1"
