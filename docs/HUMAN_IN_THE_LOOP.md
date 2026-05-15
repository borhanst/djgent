# Human-in-the-Loop (HITL)

Djgent provides a first-class Human Interaction Request workflow that pauses protected agent operations for authorized reviewer approval before execution.

## Overview

When an agent attempts to run a protected tool or operation, Djgent:

1. **Pauses** the operation before execution
2. **Creates** a Human Interaction Request with safe review context
3. **Notifies** configured recipients by email
4. **Waits** for a reviewer to decide (approve, reject, edit, or cancel)
5. **Resumes** the operation based on the reviewer's decision
6. **Saves** the Final Response in the original conversation

## Configuration

### Basic Setup

```python
DJGENT = {
    "DEFAULT_LLM": "openai:gpt-4o-mini",
    "MEMORY_BACKEND": "database",  # Required for HITL
    "HUMAN_IN_THE_LOOP": {
        "REVIEWER_POLICY": {
            "mode": "admin",
            "site_owner_emails": ["owner@example.com"],
        },
        "site_owner_emails": ["owner@example.com"],
        "PROTECTED_TOOLS": {
            "send_email": {
                "reason": "Email requires owner approval.",
                "review_instructions": "Check recipient and content.",
            },
            "deploy_code": {
                "reason": "Deploy requires manager approval.",
                "review_permission": "can_deploy",
            },
        },
    },
}
```

### Global Review Permission

By default, reviewers need the `djgent.can_review_human_interaction` permission. Superusers can review all requests; staff users need the permission explicitly.

```python
# Grant to a user
user.user_permissions.add(
    Permission.objects.get(codename="can_review_human_interaction")
)
```

### Per-Tool Review Permission

Set `review_permission` in the tool's protected tools policy to require a specific permission:

```python
"PROTECTED_TOOLS": {
    "deploy_code": {
        "review_permission": "can_deploy",
    },
}
```

### Notification Recipients

Email recipients resolve in this order:

1. `human_in_the_loop.site_owner_emails` (per-request config)
2. `DJGENT["HUMAN_IN_THE_LOOP"]["site_owner_emails"]`
3. Django `ADMINS` setting

## Protecting Tools

### Via Tool Metadata

Set `requires_human_interaction = True` on your tool class:

```python
from djgent import Tool

class SendEmailTool(Tool):
    name = "send_email"
    description = "Send an email"
    requires_human_interaction = True
    approval_reason = "Email requires owner approval."

    def _run(self, to: str, subject: str = "Hello") -> str:
        return f"Email sent to {to}"
```

The existing `requires_approval = True` acts as a compatibility alias.

### Via Settings Policy

Protect any tool without modifying tool code:

```python
DJGENT = {
    "HUMAN_IN_THE_LOOP": {
        "PROTECTED_TOOLS": {
            "dangerous_tool": {
                "reason": "This tool is dangerous.",
                "review_instructions": "Check with manager first.",
                "review_permission": "can_approve_dangerous",
            },
            "simple_protected_tool": True,  # Uses default reason
        },
    },
}
```

### Custom Review Context

Override `get_review_context()` to provide safe, tool-specific information for reviewers. Do NOT include sensitive payload data:

```python
class TransferFundsTool(Tool):
    name = "transfer_funds"
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
```

## Review Surface (Django Admin)

Human Interaction Requests are reviewed in Django admin at `/admin/djgent/humaninteractionrequest/`.

### Reviewer Workflow

1. Reviewer navigates to the admin list (searchable by Public Request Reference)
2. Opens a request to see safe Review Context, operation details, and notification state
3. Selects a Decision: **Approve**, **Reject**, **Edit**, or **Cancel**
4. For reject/edit/cancel: reviewer notes are required
5. For approve: reviewer notes are optional
6. Saves the decision to resume the operation

### Key Behaviors

- **One at a time**: No bulk approve/reject actions
- **Permission enforced**: View and change require reviewer permission
- **Notes internal by default**: Reviewer notes are not shown to end users unless `notes_visible_to_user` is set
- **No conversation exposure**: Reviewers see Review Context, not original conversation content

## Public Request Reference

Every Human Interaction Request gets a unique, searchable reference like `HITL-20260515-A1B2C3D4`. This reference is:

- Shown to end users in pending-status messages (instead of internal IDs)
- Searchable in Django admin
- Included in notification emails
- Emitted in runtime events

## Resume Signal

After a successful resume, Djgent emits a `run.human_interaction_resumed` event containing:

- `request_id`: Internal request UUID
- `public_reference`: Safe reference for user-facing messages
- `status`: Final request status (`resumed`, `resume_failed`, etc.)

## Decision Handling

| Decision | Behavior |
|----------|----------|
| **Approve** | Executes the exact blocked operation, then continues the agent run |
| **Reject** | Resumes conversation and produces a Final Response without executing the operation |
| **Edit** | Executes the operation with policy-allowed reviewer changes |
| **Cancel** | Cancels the request without execution |

## Error Handling

- **Resume failures** set `resume_failed` status, preserve the Resume Payload for retry, and record the error
- **Notification failures** record the error without blocking request creation
- **Expiration** safely stops waiting without executing the protected operation

## LangGraph Integration

LangGraph-created human-in-the-loop interrupts are routed through the same shared workflow:

- Requests set `source = "langgraph_hitl"`
- Same Review Surface, notification behavior, and status transitions
- Resume continues through LangGraph checkpoint `Command` handling internally

```python
DJGENT = {
    "LANGCHAIN_MIDDLEWARE": {
        "human_in_the_loop": {
            "enabled": True,
            "interrupt_on": {
                "send_email": {
                    "allowed_decisions": ["approve", "edit", "reject"],
                    "description": "Email requires owner approval.",
                }
            },
            "site_owner_emails": ["owner@example.com"],
        }
    },
}
```

## System Checks

Djgent validates HITL configuration at startup:

| Check | ID | Description |
|-------|----|-------------|
| Missing reviewer policy | `djgent.E001` | Protected tools configured without `REVIEWER_POLICY` |
| Missing durable persistence | `djgent.E002` | Protected tools with in-memory backend |
| HITL disabled | `djgent.E003` | Protected tools with `enabled: False` |
| Missing site_owner_emails | `djgent.W001` | Warning: no email recipients configured |
| Missing auth app | `djgent.W002` | Warning: `django.contrib.auth` not installed |

Run checks with:

```bash
python manage.py check
```

## Resuming Programmatically

```python
from djgent import Agent

agent = Agent.create(
    name="support",
    memory_backend="database",
    thread_id="thread-1",
)

# Resume a reviewed request
result = agent.resume_human_interaction(request_id)
print(result.output)
```
