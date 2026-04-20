# Runtime Middleware Guide

The built-in chat app in `djgent.chat` uses the same `Agent` runtime described here, so these middleware hooks and LangChain middleware settings apply to the packaged UI too.

## Overview

Djgent applies a runtime middleware stack around each agent run and each tool call.
Middleware can:

- add prompt context before the model runs
- block risky tools until they are approved
- normalize or transform model output
- emit execution events or attach metadata

Every `Agent` includes these built-in middleware classes by default:

- `DynamicPromptMiddleware`
- `ToolApprovalMiddleware`
- `OutputGuardrailMiddleware`

Custom middleware passed to `Agent.create(..., middleware=[...])` runs after those defaults.

## Execution Context

Middleware hooks receive an `ExecutionContext` object:

```python
from djgent.runtime import ExecutionContext
```

Important fields:

- `agent_name`: current agent name
- `thread_id`: durable execution thread id
- `input`: user input for this run
- `context`: per-run context passed to `agent.run(..., context={...})`
- `state`: durable state loaded from the `StateStore`
- `events`: collected `StreamEvent` objects
- `metadata`: mutable scratch space for middleware

You can add events from middleware with:

```python
execution.emit("custom.event", value="example")
```

## Built-In Middleware

### DynamicPromptMiddleware

Builds an extra system prompt from execution state and per-run context.

Current behavior:

- adds `execution.state["summary"]` when present
- adds `context["prompt_context"]` when present
- stores the final prompt block in `execution.metadata["dynamic_prompt"]`

Example:

```python
agent.run(
    "Answer briefly",
    context={"prompt_context": "Use exactly 3 bullet points."},
)
```

### ToolApprovalMiddleware

Interrupts execution before a risky tool call unless that tool has already been approved for the active thread.

It uses:

- `execution.context["risky_tools"]`: tool config indexed by name
- `execution.context["approved_tools"]`: approved tool names for the thread

Risky tools are discovered from Djgent `Tool` instances whose config returns:

- `requires_approval = True`
- optional `approval_reason`

When approval is required, Djgent raises `ApprovalRequiredError` internally, stores the pending tool in durable state, and returns an interrupted result instead of crashing the run.

### OutputGuardrailMiddleware

Normalizes blank output from the model.

If the final text is empty or whitespace:

- returns `context["empty_output_fallback"]` when provided
- otherwise returns `"I processed your request."`
- emits a `guardrail.empty_output` event

## Writing Custom Middleware

Subclass `AgentMiddleware` and override any hooks you need:

```python
from djgent.runtime import AgentMiddleware, ExecutionContext


class AuditTrailMiddleware(AgentMiddleware):
    def before_run(self, execution: ExecutionContext) -> None:
        execution.emit("run.started", input=execution.input)
        execution.metadata["source"] = execution.context.get("source", "unknown")

    def after_run(self, execution: ExecutionContext, output: str) -> str:
        execution.emit("run.finished", output=output)
        return output

    def before_tool(self, execution: ExecutionContext, tool_name: str, arguments: dict) -> None:
        execution.emit("tool.before", tool=tool_name, arguments=arguments)

    def after_tool(self, execution: ExecutionContext, tool_name: str, result):
        execution.emit("tool.after", tool=tool_name)
        return result
```

Attach it to an agent:

```python
from djgent import Agent

agent = Agent.create(
    name="assistant",
    auto_load_tools=True,
    middleware=[AuditTrailMiddleware()],
)
```

## Tool Approval Flow

Mark a tool as risky:

```python
from djgent import Tool


class DeleteUserTool(Tool):
    name = "delete_user"
    description = "Delete a user account."
    requires_approval = True
    approval_reason = "Deleting accounts is irreversible."

    def _run(self, user_id: int) -> str:
        return f"Deleted user {user_id}"
```

Use it with an agent:

```python
from djgent import Agent

agent = Agent.create(
    name="ops",
    tools=[DeleteUserTool()],
    thread_id="ops-thread-1",
)

message = agent.run("Delete user 42")
state = agent.get_thread_state()

print(message)
print(state["status"])
```

Inspect and approve the pending tool:

```python
state = agent.get_thread_state()
print(state["paused_tool_name"])
print(state["paused_tool_arguments"])

agent.approve_pending_tool()

# Retry the original intent after approval
message = agent.run("Delete user 42")
print(message)
```

Notes:

- approvals are stored in the durable thread state
- pass `thread_id` explicitly when approval and retry happen in different processes
- `approve_pending_tool(tool_name=...)` validates the expected tool name before approving it

## LangChain Built-In Middleware

Djgent can also instantiate LangChain's built-in middleware via `langchain_middleware`.
Supported sections currently map to:

- `summarization`
- `model_retry`
- `tool_retry`
- `model_fallback`
- `model_call_limit`
- `tool_call_limit`
- `tool_selector`
- `context_editing`

Example:

```python
agent = Agent.create(
    name="assistant",
    auto_load_tools=True,
    langchain_middleware={
        "summarization": True,
        "tool_retry": True,
    },
)
```

Djgent merges `langchain_middleware` from:

1. `DJGENT["LANGCHAIN_MIDDLEWARE"]` in Django settings
2. per-agent `langchain_middleware` overrides

If you configure `human_in_the_loop`, Djgent currently raises a configuration error because that flow is not wired into the runtime yet.

## Tips

- Keep middleware side effects small and deterministic.
- Prefer storing temporary values in `execution.metadata`.
- Use `execution.context` for per-request inputs coming from your application.
- Return transformed output/results from `after_run` and `after_tool` rather than mutating unrelated state.
- If middleware depends on persistence, keep `thread_id` stable across retries and resumes.
