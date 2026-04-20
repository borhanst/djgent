"""Tests for audit logging integration with agent runtime."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage

from djgent.agents.base import Agent
from djgent.exceptions import AgentError, RateLimitError
from djgent.models import AuditLog
from djgent.runtime import ApprovalRequiredError, AuditMiddleware
from djgent.runtime.middleware import apply_after_tool, apply_before_tool


@pytest.mark.django_db
class TestAuditIntegration:
    def test_agent_run_creates_audit_log(
        self, agent_kwargs: dict, mock_llm: MagicMock
    ) -> None:
        mock_llm.invoke.return_value = AIMessage(content="Test response")
        agent = Agent(llm=mock_llm, **agent_kwargs)

        output = agent.run("Hello")

        assert output == "Test response"
        log = AuditLog.objects.get(event_type="agent_run")
        assert log.agent_name == "test_agent"
        assert log.level == "info"
        assert log.details["input"] == "Hello"
        assert log.details["output"] == "Test response"
        assert log.duration_ms is not None

    def test_failed_agent_run_creates_error_audit_log(
        self, agent_kwargs: dict, mock_llm: MagicMock
    ) -> None:
        mock_llm.invoke.side_effect = RuntimeError("model exploded")
        agent = Agent(llm=mock_llm, **agent_kwargs)

        with pytest.raises(AgentError):
            agent.run("Hello")

        log = AuditLog.objects.get(event_type="agent_run")
        assert log.agent_name == "test_agent"
        assert log.level == "error"
        assert "model exploded" in log.error
        assert log.details["input"] == "Hello"
        assert log.details["output"] is None

    def test_tool_execution_creates_redacted_audit_log(
        self, agent_kwargs: dict, mock_llm: MagicMock, monkeypatch
    ) -> None:
        @dataclass
        class RuntimeLike:
            lock: object = field(default_factory=threading.Lock)

        def fake_invoke_model(self, messages, execution, **kwargs):
            arguments = {
                "query": "hello",
                "api_key": "secret",
                "runtime": RuntimeLike(),
            }
            apply_before_tool(self._middleware, execution, "lookup", arguments)
            apply_after_tool(
                self._middleware,
                execution,
                "lookup",
                {"answer": "world"},
            )
            return MagicMock(content="Done")

        monkeypatch.setattr(Agent, "_invoke_model", fake_invoke_model)
        agent = Agent(llm=mock_llm, **agent_kwargs)

        agent.run("Use a tool")

        log = AuditLog.objects.get(event_type="tool_execution")
        assert log.agent_name == "test_agent"
        assert log.tool_name == "lookup"
        assert "RuntimeLike" in log.details["arguments"]["runtime"]
        assert {
            key: value
            for key, value in log.details["arguments"].items()
            if key != "runtime"
        } == {
            "query": "hello",
            "api_key": "***REDACTED***",
        }
        assert log.details["result_type"] == "dict"
        assert "result" not in log.details

    def test_approval_interruption_creates_audit_log(
        self, agent_kwargs: dict, mock_llm: MagicMock, monkeypatch
    ) -> None:
        def fake_invoke_model(self, messages, execution, **kwargs):
            raise ApprovalRequiredError(
                tool_name="danger",
                arguments={"token": "secret"},
                reason="Needs approval",
                thread_id=execution.thread_id,
            )

        monkeypatch.setattr(Agent, "_invoke_model", fake_invoke_model)
        agent = Agent(llm=mock_llm, **agent_kwargs)

        result = agent.run("Do risky thing")

        assert result == "Needs approval"
        log = AuditLog.objects.get(event_type="tool_approval")
        assert log.agent_name == "test_agent"
        assert log.tool_name == "danger"
        assert log.details["approved"] is False
        assert log.details["reason"] == "Needs approval"
        assert log.details["arguments"]["token"] == "***REDACTED***"

    def test_audit_disabled_prevents_automatic_logs(
        self, settings, agent_kwargs: dict, mock_llm: MagicMock
    ) -> None:
        settings.DJGENT = {
            "AUDIT": {
                "ENABLED": False,
            }
        }
        agent = Agent(llm=mock_llm, **agent_kwargs)

        agent.run("Hello")

        assert AuditLog.objects.count() == 0

    def test_manual_audit_middleware_works_when_auto_disabled(
        self, settings, agent_kwargs: dict, mock_llm: MagicMock
    ) -> None:
        settings.DJGENT = {
            "AUDIT": {
                "ENABLED": True,
                "AUTO_MIDDLEWARE": False,
            }
        }
        agent_kwargs["middleware"] = [AuditMiddleware()]
        agent = Agent(llm=mock_llm, **agent_kwargs)

        agent.run("Hello")

        assert AuditLog.objects.filter(event_type="agent_run").count() == 1

    def test_manual_audit_middleware_is_not_duplicated(
        self, agent_kwargs: dict, mock_llm: MagicMock
    ) -> None:
        agent_kwargs["middleware"] = [AuditMiddleware()]
        agent = Agent(llm=mock_llm, **agent_kwargs)

        agent.run("Hello")

        assert AuditLog.objects.filter(event_type="agent_run").count() == 1

    def test_rate_limit_error_creates_rate_limit_audit_log(
        self, agent_kwargs: dict, mock_llm: MagicMock
    ) -> None:
        class BlockingMiddleware:
            def before_run(self, execution):
                raise RateLimitError("Rate limit exceeded", limit_type="minute")

            def after_run(self, execution, output):
                return output

            def before_tool(self, execution, tool_name, arguments):
                return None

            def after_tool(self, execution, tool_name, result):
                return result

        agent_kwargs["middleware"] = [BlockingMiddleware()]
        agent = Agent(llm=mock_llm, **agent_kwargs)

        with pytest.raises(RateLimitError):
            agent.run("Hello")

        rate_log = AuditLog.objects.get(event_type="rate_limit_exceeded")
        assert rate_log.agent_name == "test_agent"
        assert rate_log.details["limit_type"] == "minute"
        assert AuditLog.objects.filter(
            event_type="agent_run", level="error"
        ).exists()
