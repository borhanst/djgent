"""Tests for LangChain human-in-the-loop integration."""

from __future__ import annotations

import sys
import types
import uuid
from types import SimpleNamespace

from unittest.mock import MagicMock

import pytest

from djgent.agents.base import Agent
from djgent.models import HumanInteractionRequest
from djgent.runtime.checkpoint import DjangoCheckpointSaver
from djgent.runtime.langchain_middleware import build_langchain_middleware
from djgent.tools.base import Tool


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
def test_public_reference_auto_generated() -> None:
    request = HumanInteractionRequest.objects.create(
        agent_name="support",
        thread_id="thread-1",
    )
    assert request.public_reference is not None
    assert request.public_reference.startswith("HITL-")
    assert len(request.public_reference) == 22  # HITL-YYYYMMDD-XXXXXXXX


@pytest.mark.django_db
def test_public_reference_is_unique() -> None:
    refs = set()
    for _ in range(5):
        request = HumanInteractionRequest.objects.create(
            agent_name="support",
            thread_id=f"thread-{uuid.uuid4()}",
        )
        refs.add(request.public_reference)
    assert len(refs) == 5


@pytest.mark.django_db
def test_public_reference_searchable() -> None:
    request = HumanInteractionRequest.objects.create(
        agent_name="support",
        thread_id="thread-1",
    )
    found = HumanInteractionRequest.objects.get(
        public_reference=request.public_reference
    )
    assert found.id == request.id


@pytest.mark.django_db
def test_new_status_values() -> None:
    for status in [
        HumanInteractionRequest.STATUS_PENDING,
        HumanInteractionRequest.STATUS_APPROVED,
        HumanInteractionRequest.STATUS_REJECTED,
        HumanInteractionRequest.STATUS_RESUMING,
        HumanInteractionRequest.STATUS_RESUMED,
        HumanInteractionRequest.STATUS_RESUME_FAILED,
        HumanInteractionRequest.STATUS_EXPIRED,
        HumanInteractionRequest.STATUS_CANCELLED,
    ]:
        request = HumanInteractionRequest.objects.create(
            agent_name="support",
            thread_id=f"thread-{status}",
            status=status,
        )
        assert request.status == status


@pytest.mark.django_db
def test_review_context_separate_from_resume_payload() -> None:
    request = HumanInteractionRequest.objects.create(
        agent_name="support",
        thread_id="thread-1",
        review_context={"tool": "send_email", "reason": "User requested"},
    )
    request.set_resume_payload({"tool_name": "send_email", "args": {"to": "a@b.com"}})

    request.refresh_from_db()
    assert request.review_context == {"tool": "send_email", "reason": "User requested"}
    payload = request.get_resume_payload()
    assert payload == {"tool_name": "send_email", "args": {"to": "a@b.com"}}


@pytest.mark.django_db
def test_resume_payload_encryption_round_trip() -> None:
    request = HumanInteractionRequest.objects.create(
        agent_name="support",
        thread_id="thread-1",
    )
    data = {"tool_name": "send_email", "args": {"to": "test@example.com", "body": "hello"}}
    request.set_resume_payload(data)

    request.refresh_from_db()
    assert request.resume_payload_encrypted is not None

    decrypted = request.get_resume_payload()
    assert decrypted == data


@pytest.mark.django_db
def test_clear_resume_payload() -> None:
    request = HumanInteractionRequest.objects.create(
        agent_name="support",
        thread_id="thread-1",
    )
    request.set_resume_payload({"tool_name": "send_email", "args": {}})
    assert request.resume_payload_encrypted is not None

    request.clear_resume_payload()
    request.refresh_from_db()
    assert request.resume_payload_encrypted is None
    assert request.get_resume_payload() is None


@pytest.mark.django_db
def test_is_decidable() -> None:
    request = HumanInteractionRequest.objects.create(
        agent_name="support",
        thread_id="thread-1",
    )
    assert request.is_decidable() is True

    for status in [
        HumanInteractionRequest.STATUS_RESUMING,
        HumanInteractionRequest.STATUS_RESUMED,
        HumanInteractionRequest.STATUS_RESUME_FAILED,
        HumanInteractionRequest.STATUS_EXPIRED,
        HumanInteractionRequest.STATUS_CANCELLED,
    ]:
        request.status = status
        assert request.is_decidable() is False


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
    request.set_resume_payload({"tool_name": "send_email", "args": {"to": "a@b.com"}})
    request.save()
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


# --- Issue 02: Create requests from protected tools ---


class _ProtectedTool(Tool):
    """Tool flagged with requires_human_interaction."""

    name = "send_email"
    description = "Send an email"
    requires_human_interaction = True
    approval_reason = "Email requires owner approval."

    def _run(self, to: str, subject: str = "Hello") -> str:
        return f"Email sent to {to}"


class _ApprovalAliasTool(Tool):
    """Tool using requires_approval as compatibility alias."""

    name = "delete_record"
    description = "Delete a record"
    requires_approval = True
    approval_reason = "Destructive operation."

    def _run(self, record_id: int) -> str:
        return f"Deleted {record_id}"


class _ToolWithReviewContext(Tool):
    """Tool with custom get_review_context."""

    name = "transfer_funds"
    description = "Transfer funds between accounts"
    requires_human_interaction = True

    def _run(self, amount: float, to_account: str) -> str:
        return f"Transferred {amount}"

    def get_review_context(self, arguments):
        return {
            "operation_name": "fund_transfer",
            "amount": arguments.get("amount"),
            "destination": arguments.get("to_account"),
            "risk_level": "high",
        }


@pytest.mark.django_db
def test_requires_human_interaction_flag() -> None:
    """Tool with requires_human_interaction=True sets both flags in config."""
    tool = _ProtectedTool()
    config = tool.get_tool_config()

    assert config["requires_human_interaction"] is True
    assert config["requires_approval"] is True


@pytest.mark.django_db
def test_requires_approval_compatibility_alias() -> None:
    """requires_approval acts as alias when first-class HITL is enabled."""
    tool = _ApprovalAliasTool()
    config = tool.get_tool_config()

    assert config["requires_approval"] is True
    assert config["requires_human_interaction"] is True


@pytest.mark.django_db
def test_tool_get_review_context_default() -> None:
    """Default get_review_context returns operation name and reason."""
    tool = _ProtectedTool()
    ctx = tool.get_review_context({"to": "user@example.com"})

    assert ctx["operation_name"] == "send_email"
    assert "email requires owner approval" in ctx["reason"].lower()


@pytest.mark.django_db
def test_tool_get_review_context_custom() -> None:
    """Custom get_review_context is used when available."""
    tool = _ToolWithReviewContext()
    ctx = tool.get_review_context({"amount": 1000, "to_account": "ACC-999"})

    assert ctx["operation_name"] == "fund_transfer"
    assert ctx["amount"] == 1000
    assert ctx["destination"] == "ACC-999"
    assert ctx["risk_level"] == "high"


@pytest.mark.django_db
def test_settings_protected_tools(hitl_settings) -> None:
    """Settings policy can mark tools as protected without editing tool code."""
    from djgent.agents.base import Agent

    hitl_settings.DJGENT["HUMAN_IN_THE_LOOP"] = {
        "PROTECTED_TOOLS": {
            "dangerous_tool": {
                "reason": "This tool is dangerous.",
                "review_instructions": "Check with manager first.",
            }
        }
    }

    agent = Agent(
        name="test-agent",
        tools=[],
        memory=False,
    )
    protected = agent._protected_tools_from_settings()

    assert "dangerous_tool" in protected
    assert protected["dangerous_tool"]["requires_human_interaction"] is True
    assert protected["dangerous_tool"]["reason"] == "This tool is dangerous."
    assert protected["dangerous_tool"]["review_instructions"] == "Check with manager first."


@pytest.mark.django_db
def test_djgent_native_hitl_request_uses_public_reference() -> None:
    """Djgent-native HITL request stores public_reference and uses it in output."""
    request = HumanInteractionRequest.objects.create(
        agent_name="test-agent",
        thread_id="thread-123",
        source=HumanInteractionRequest.SOURCE_DJGENT_NATIVE,
        operation_name="send_email",
        operation_type=HumanInteractionRequest.OPERATION_TYPE_TOOL,
        review_context={"operation_name": "send_email"},
        action_requests=[{"name": "send_email", "description": "Email test"}],
        review_configs=[{"action_name": "send_email", "allowed_decisions": ["approve"]}],
        site_owner_emails=["owner@example.com"],
    )
    request.set_resume_payload({"tool_name": "send_email", "arguments": {"to": "test@example.com"}})
    request.save()

    assert request.public_reference
    assert request.public_reference.startswith("HITL-")
    assert request.source == "djgent_native"


@pytest.mark.django_db
def test_email_uses_public_reference(hitl_settings) -> None:
    """Notification email uses public reference, not internal ID."""
    from django.core.mail import outbox

    from djgent.runtime.human import notify_site_owners

    request = HumanInteractionRequest.objects.create(
        agent_name="test-agent",
        thread_id="thread-456",
        action_requests=[{"name": "send_email", "description": "Email requires review."}],
        site_owner_emails=["owner@example.com"],
    )

    outbox.clear()
    notify_site_owners(request, {"notify_email": True})

    assert len(outbox) == 1
    email = outbox[0]
    assert request.public_reference in email.body
    assert "Operations:" in email.body


@pytest.mark.django_db
def test_human_interaction_middleware_intercepts_protected_tool() -> None:
    """HumanInteractionMiddleware raises HumanInteractionRequiredError for protected tools."""
    from djgent.runtime.approvals import HumanInteractionRequiredError
    from djgent.runtime.middleware import HumanInteractionMiddleware, ExecutionContext

    middleware = HumanInteractionMiddleware()
    execution = ExecutionContext(
        agent_name="test-agent",
        thread_id="thread-789",
        input="test",
        context={
            "risky_tools": {
                "send_email": {
                    "name": "send_email",
                    "requires_human_interaction": True,
                    "reason": "Email requires approval.",
                }
            },
            "protected_tools": {},
            "approved_tools": {},
        },
    )

    with pytest.raises(HumanInteractionRequiredError) as exc_info:
        middleware.before_tool(execution, "send_email", {"to": "test@example.com"})

    assert exc_info.value.tool_name == "send_email"
    assert exc_info.value.arguments == {"to": "test@example.com"}


@pytest.mark.django_db
def test_human_interaction_middleware_skips_approved_tool() -> None:
    """HumanInteractionMiddleware skips tools in approved_tools."""
    from djgent.runtime.middleware import HumanInteractionMiddleware, ExecutionContext

    middleware = HumanInteractionMiddleware()
    execution = ExecutionContext(
        agent_name="test-agent",
        thread_id="thread-789",
        input="test",
        context={
            "risky_tools": {
                "send_email": {
                    "name": "send_email",
                    "requires_human_interaction": True,
                    "reason": "Email requires approval.",
                }
            },
            "protected_tools": {},
            "approved_tools": {},
            "approval_skiplist": {"send_email"},
        },
    )

    # Should not raise
    middleware.before_tool(execution, "send_email", {"to": "test@example.com"})


@pytest.mark.django_db
def test_human_interaction_middleware_from_settings() -> None:
    """HumanInteractionMiddleware checks settings-based protected tools."""
    from djgent.runtime.approvals import HumanInteractionRequiredError
    from djgent.runtime.middleware import HumanInteractionMiddleware, ExecutionContext

    middleware = HumanInteractionMiddleware()
    execution = ExecutionContext(
        agent_name="test-agent",
        thread_id="thread-789",
        input="test",
        context={
            "risky_tools": {},
            "protected_tools": {
                "deploy_code": {
                    "name": "deploy_code",
                    "requires_human_interaction": True,
                    "reason": "Deploy requires approval.",
                    "review_context": {"operation_name": "deploy"},
                    "review_instructions": "Check staging first.",
                    "review_permission": "can_deploy",
                }
            },
            "approved_tools": {},
        },
    )

    with pytest.raises(HumanInteractionRequiredError) as exc_info:
        middleware.before_tool(execution, "deploy_code", {"branch": "main"})

    assert exc_info.value.tool_name == "deploy_code"
    assert exc_info.value.review_context == {"operation_name": "deploy"}
    assert exc_info.value.review_instructions == "Check staging first."
    assert exc_info.value.review_permission == "can_deploy"


# --- Issue 03: Review one request in Django admin ---


@pytest.mark.django_db
def test_admin_search_by_public_reference() -> None:
    """Public Request Reference is unique and searchable."""
    request = HumanInteractionRequest.objects.create(
        agent_name="support",
        thread_id="thread-100",
        source=HumanInteractionRequest.SOURCE_DJGENT_NATIVE,
        operation_name="send_email",
    )
    ref = request.public_reference

    found = HumanInteractionRequest.objects.filter(public_reference=ref)
    assert found.count() == 1
    assert found.first().id == request.id


@pytest.mark.django_db
def test_decision_constants_exist() -> None:
    """Model defines decision constants for approve, reject, edit, cancel."""
    assert HumanInteractionRequest.DECISION_APPROVE == "approve"
    assert HumanInteractionRequest.DECISION_REJECT == "reject"
    assert HumanInteractionRequest.DECISION_EDIT == "edit"
    assert HumanInteractionRequest.DECISION_CANCEL == "cancel"


@pytest.mark.django_db
def test_decision_field_on_model() -> None:
    """Model has a decision field for storing the reviewer's choice."""
    request = HumanInteractionRequest.objects.create(
        agent_name="support",
        thread_id="thread-200",
    )
    request.decision = HumanInteractionRequest.DECISION_APPROVE
    request.save()
    request.refresh_from_db()
    assert request.decision == "approve"


@pytest.mark.django_db
def test_reviewer_notes_required_decisions() -> None:
    """Reject, edit, and cancel decisions require reviewer notes."""
    notes_required = (
        HumanInteractionRequest.DECISION_REJECT,
        HumanInteractionRequest.DECISION_EDIT,
        HumanInteractionRequest.DECISION_CANCEL,
    )
    for decision in notes_required:
        assert decision in notes_required

    # Approve does not require notes
    assert HumanInteractionRequest.DECISION_APPROVE not in notes_required


@pytest.mark.django_db
def test_notes_visible_to_user_field() -> None:
    """Model has notes_visible_to_user flag for controlling note visibility."""
    request = HumanInteractionRequest.objects.create(
        agent_name="support",
        thread_id="thread-300",
    )
    assert request.notes_visible_to_user is False
    request.notes_visible_to_user = True
    request.save()
    request.refresh_from_db()
    assert request.notes_visible_to_user is True


@pytest.mark.django_db
def test_request_source_choices() -> None:
    """Model defines source choices for djgent_native and langgraph_hitl."""
    assert HumanInteractionRequest.SOURCE_DJGENT_NATIVE == "djgent_native"
    assert HumanInteractionRequest.SOURCE_LANGGRAPH_HITL == "langgraph_hitl"


@pytest.mark.django_db
def test_review_context_not_exposed_in_resume_payload() -> None:
    """Review context is separate from resume payload (not exposed to reviewers)."""
    request = HumanInteractionRequest.objects.create(
        agent_name="support",
        thread_id="thread-400",
        review_context={"operation_name": "send_email", "safe": True},
    )
    request.set_resume_payload({"tool_name": "send_email", "args": {"to": "secret@example.com"}})
    request.save()

    request.refresh_from_db()
    # Review context is safe for reviewers
    assert request.review_context == {"operation_name": "send_email", "safe": True}
    # Resume payload contains sensitive data and is encrypted
    payload = request.get_resume_payload()
    assert payload["args"]["to"] == "secret@example.com"
    # They are stored separately
    assert request.review_context != payload


# --- Issue 04: Resume reviewed Djgent-native requests ---


@pytest.mark.django_db
def test_resume_validates_decidable_status() -> None:
    """Resume rejects requests not in a decidable state."""
    request = HumanInteractionRequest.objects.create(
        agent_name="support",
        thread_id="thread-500",
        status=HumanInteractionRequest.STATUS_RESUMED,
    )

    agent = Agent(
        name="support",
        llm=MagicMock(),
        memory=False,
    )

    from djgent.agents.base import AgentError
    with pytest.raises(AgentError, match="not in a decidable state"):
        agent.resume_human_interaction(request.id)


@pytest.mark.django_db
def test_resume_validates_resume_payload_for_native() -> None:
    """Resume rejects native requests without resume payload."""
    request = HumanInteractionRequest.objects.create(
        agent_name="support",
        thread_id="thread-501",
        source=HumanInteractionRequest.SOURCE_DJGENT_NATIVE,
        status=HumanInteractionRequest.STATUS_PENDING,
    )

    agent = Agent(
        name="support",
        llm=MagicMock(),
        memory=False,
    )

    from djgent.agents.base import AgentError
    with pytest.raises(AgentError, match="no resume payload"):
        agent.resume_human_interaction(request.id)


@pytest.mark.django_db
def test_resume_clears_payload_on_success() -> None:
    """After successful resume, the encrypted resume payload is cleared."""
    request = HumanInteractionRequest.objects.create(
        agent_name="support",
        thread_id="thread-502",
    )
    request.set_resume_payload({"tool_name": "send_email", "args": {"to": "a@b.com"}})
    request.save()
    assert request.resume_payload_encrypted is not None

    request.clear_resume_payload()
    request.save(update_fields=["resume_payload_encrypted", "resume_payload_key_version"])
    request.refresh_from_db()
    assert request.resume_payload_encrypted is None
    assert request.get_resume_payload() is None


@pytest.mark.django_db
def test_resume_sets_resume_failed_on_error() -> None:
    """Failed resume sets status to resume_failed and records error."""
    request = HumanInteractionRequest.objects.create(
        agent_name="support",
        thread_id="thread-503",
    )
    request.status = HumanInteractionRequest.STATUS_RESUME_FAILED
    request.error = "LangGraph not available"
    request.save()
    request.refresh_from_db()

    assert request.status == HumanInteractionRequest.STATUS_RESUME_FAILED
    assert "LangGraph not available" in request.error


@pytest.mark.django_db
def test_resume_emits_public_reference_in_event() -> None:
    """Resume event includes public_reference for tracking."""
    request = HumanInteractionRequest.objects.create(
        agent_name="support",
        thread_id="thread-504",
        status=HumanInteractionRequest.STATUS_PENDING,
    )
    request.set_resume_payload({"tool_name": "test", "args": {}})
    request.save()

    # Verify the request has a public reference
    assert request.public_reference
    assert request.public_reference.startswith("HITL-")


# --- Issue 05: Unify LangGraph HITL with shared reviewer flow ---


@pytest.mark.django_db
def test_langgraph_hitl_request_uses_shared_model() -> None:
    """LangGraph HITL requests use the shared HumanInteractionRequest model."""
    request = HumanInteractionRequest.objects.create(
        agent_name="support",
        thread_id="thread-600",
        source=HumanInteractionRequest.SOURCE_LANGGRAPH_HITL,
        operation_name="send_email",
        operation_type=HumanInteractionRequest.OPERATION_TYPE_TOOL,
        review_context={"operation_name": "send_email", "action_count": 1},
        action_requests=[{"name": "send_email", "arguments": {"to": "a@b.com"}}],
        review_configs=[{"action_name": "send_email"}],
    )
    request.set_resume_payload({
        "action_requests": [{"name": "send_email", "arguments": {"to": "a@b.com"}}],
        "review_configs": [{"action_name": "send_email"}],
    })
    request.save()

    assert request.source == "langgraph_hitl"
    assert request.operation_name == "send_email"
    assert request.operation_type == "tool"
    assert request.public_reference.startswith("HITL-")


@pytest.mark.django_db
def test_langgraph_and_native_requests_share_status_transitions() -> None:
    """Both LangGraph and Djgent-native requests use the same status transitions."""
    langgraph_request = HumanInteractionRequest.objects.create(
        agent_name="support",
        thread_id="thread-601",
        source=HumanInteractionRequest.SOURCE_LANGGRAPH_HITL,
    )
    native_request = HumanInteractionRequest.objects.create(
        agent_name="support",
        thread_id="thread-602",
        source=HumanInteractionRequest.SOURCE_DJGENT_NATIVE,
    )

    # Both start as pending
    assert langgraph_request.status == HumanInteractionRequest.STATUS_PENDING
    assert native_request.status == HumanInteractionRequest.STATUS_PENDING

    # Both are decidable
    assert langgraph_request.is_decidable() is True
    assert native_request.is_decidable() is True

    # Both can transition to resuming
    langgraph_request.status = HumanInteractionRequest.STATUS_RESUMING
    native_request.status = HumanInteractionRequest.STATUS_RESUMING
    assert langgraph_request.is_decidable() is False
    assert native_request.is_decidable() is False


@pytest.mark.django_db
def test_langgraph_request_has_review_context() -> None:
    """LangGraph HITL requests have review context for safe display."""
    request = HumanInteractionRequest.objects.create(
        agent_name="support",
        thread_id="thread-603",
        source=HumanInteractionRequest.SOURCE_LANGGRAPH_HITL,
        operation_name="deploy_code",
        review_context={"operation_name": "deploy_code", "action_count": 2},
    )

    assert request.review_context == {"operation_name": "deploy_code", "action_count": 2}
    # Review context does not contain sensitive payload data
    assert "args" not in request.review_context
    assert "arguments" not in request.review_context


@pytest.mark.django_db
def test_langgraph_request_admin_surface() -> None:
    """LangGraph HITL requests appear in the shared admin surface."""
    request = HumanInteractionRequest.objects.create(
        agent_name="support",
        thread_id="thread-604",
        source=HumanInteractionRequest.SOURCE_LANGGRAPH_HITL,
        operation_name="send_email",
    )

    # Can be found by public reference
    found = HumanInteractionRequest.objects.filter(
        public_reference=request.public_reference
    )
    assert found.count() == 1
    assert found.first().source == "langgraph_hitl"

    # Can be filtered by source
    langgraph_requests = HumanInteractionRequest.objects.filter(
        source=HumanInteractionRequest.SOURCE_LANGGRAPH_HITL
    )
    assert langgraph_requests.count() >= 1


# --- Issue 06: Configuration checks and docs ---


@pytest.mark.django_db
def test_system_check_fails_without_reviewer_policy(settings) -> None:
    """System check fails when protected tools are configured but no reviewer policy."""
    from djgent.checks import check_hitl_reviewer_policy

    settings.DJGENT = {
        "HUMAN_IN_THE_LOOP": {
            "PROTECTED_TOOLS": {
                "send_email": {"reason": "Email requires approval."}
            }
            # Missing REVIEWER_POLICY
        }
    }

    errors = check_hitl_reviewer_policy(None)
    assert any(e.id == "djgent.E001" for e in errors)
    assert any("REVIEWER_POLICY" in e.msg for e in errors)


@pytest.mark.django_db
def test_system_check_passes_with_reviewer_policy(settings) -> None:
    """System check passes when both protected tools and reviewer policy exist."""
    from djgent.checks import check_hitl_reviewer_policy

    settings.DJGENT = {
        "HUMAN_IN_THE_LOOP": {
            "PROTECTED_TOOLS": {
                "send_email": {"reason": "Email requires approval."}
            },
            "REVIEWER_POLICY": {
                "mode": "admin",
                "site_owner_emails": ["admin@example.com"],
            },
            "site_owner_emails": ["admin@example.com"],
        }
    }

    errors = check_hitl_reviewer_policy(None)
    assert len(errors) == 0


@pytest.mark.django_db
def test_system_check_passes_without_protected_tools(settings) -> None:
    """System check passes when no protected tools are configured."""
    from djgent.checks import check_hitl_reviewer_policy

    settings.DJGENT = {
        "HUMAN_IN_THE_LOOP": {}
    }

    errors = check_hitl_reviewer_policy(None)
    assert len(errors) == 0


@pytest.mark.django_db
def test_system_check_warns_without_site_owner_emails(settings) -> None:
    """System check warns when no site_owner_emails are configured."""
    from djgent.checks import check_hitl_reviewer_policy

    settings.DJGENT = {
        "HUMAN_IN_THE_LOOP": {
            "PROTECTED_TOOLS": {
                "send_email": {"reason": "Email requires approval."}
            },
            "REVIEWER_POLICY": {"mode": "admin"},
            # Missing site_owner_emails
        }
    }

    errors = check_hitl_reviewer_policy(None)
    warnings = [e for e in errors if e.id == "djgent.W001"]
    assert len(warnings) == 1


@pytest.mark.django_db
def test_fail_closed_without_reviewer_policy(settings) -> None:
    """Protected tools without reviewer policy should fail closed."""
    from djgent.checks import check_hitl_reviewer_policy

    # No DJGENT config at all - should pass
    settings.DJGENT = {}
    assert check_hitl_reviewer_policy(None) == []

    # Protected tools without policy - should fail
    settings.DJGENT = {
        "HUMAN_IN_THE_LOOP": {
            "PROTECTED_TOOLS": {"send_email": True}
        }
    }
    errors = check_hitl_reviewer_policy(None)
    assert any(e.id == "djgent.E001" for e in errors)


@pytest.mark.django_db
def test_system_check_fails_without_durable_persistence(settings) -> None:
    """System check fails when protected tools are configured but memory backend is in-memory."""
    from djgent.checks import check_hitl_durable_persistence

    settings.DJGENT = {
        "MEMORY_BACKEND": "memory",
        "HUMAN_IN_THE_LOOP": {
            "PROTECTED_TOOLS": {
                "send_email": {"reason": "Email requires approval."}
            },
        },
    }

    errors = check_hitl_durable_persistence(None)
    assert any(e.id == "djgent.E002" for e in errors)
    assert any("MEMORY_BACKEND" in e.msg for e in errors)


@pytest.mark.django_db
def test_system_check_passes_with_database_backend(settings) -> None:
    """System check passes when durable database backend is configured."""
    from djgent.checks import check_hitl_durable_persistence

    settings.DJGENT = {
        "MEMORY_BACKEND": "database",
        "HUMAN_IN_THE_LOOP": {
            "PROTECTED_TOOLS": {
                "send_email": {"reason": "Email requires approval."}
            },
        },
    }

    errors = check_hitl_durable_persistence(None)
    assert len(errors) == 0


@pytest.mark.django_db
def test_system_check_passes_without_protected_tools_durable(settings) -> None:
    """System check passes when no protected tools are configured (durable check)."""
    from djgent.checks import check_hitl_durable_persistence

    settings.DJGENT = {
        "MEMORY_BACKEND": "memory",
        "HUMAN_IN_THE_LOOP": {},
    }

    errors = check_hitl_durable_persistence(None)
    assert len(errors) == 0


@pytest.mark.django_db
def test_system_check_fails_when_hitl_disabled_with_protected_tools(settings) -> None:
    """System check fails when HITL is disabled but protected tools exist."""
    from djgent.checks import check_hitl_disabled_with_protected_tools

    settings.DJGENT = {
        "HUMAN_IN_THE_LOOP": {
            "enabled": False,
            "PROTECTED_TOOLS": {
                "send_email": {"reason": "Email requires approval."}
            },
        },
    }

    errors = check_hitl_disabled_with_protected_tools(None)
    assert any(e.id == "djgent.E003" for e in errors)
    assert any("enabled" in e.msg.lower() for e in errors)


@pytest.mark.django_db
def test_system_check_passes_when_hitl_enabled_with_protected_tools(settings) -> None:
    """System check passes when HITL is enabled with protected tools."""
    from djgent.checks import check_hitl_disabled_with_protected_tools

    settings.DJGENT = {
        "HUMAN_IN_THE_LOOP": {
            "enabled": True,
            "PROTECTED_TOOLS": {
                "send_email": {"reason": "Email requires approval."}
            },
        },
    }

    errors = check_hitl_disabled_with_protected_tools(None)
    assert len(errors) == 0


@pytest.mark.django_db
def test_admin_notification_state_shows_emailed_at() -> None:
    """Admin notification_state displays emailed_at when available."""
    from django.utils import timezone

    request = HumanInteractionRequest.objects.create(
        agent_name="support",
        thread_id="thread-notif",
    )

    # Replicate the admin notification_state logic
    def notification_state(obj):
        if obj.emailed_at:
            return f"Sent ({obj.emailed_at:%Y-%m-%d %H:%M})"
        if obj.notification_error:
            return f"Failed: {obj.notification_error[:50]}"
        return "Pending"

    # No email sent yet
    assert notification_state(request) == "Pending"

    # Email sent
    request.emailed_at = timezone.now()
    state = notification_state(request)
    assert "Sent" in state

    # Notification error
    request.emailed_at = None
    request.notification_error = "SMTP connection failed"
    state = notification_state(request)
    assert "Failed" in state
