# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added
- First-class Human Interaction Request model with encrypted Resume Payload, Public Request Reference, Review Context, and reviewer/decision metadata
- Protected tool workflow: `requires_human_interaction` flag pauses tools before execution and creates pending requests
- Settings-based tool protection via `DJGENT["HUMAN_IN_THE_LOOP"]["PROTECTED_TOOLS"]` without editing tool code
- Django admin Review Surface with per-request decision, permission enforcement, reviewer notes, and search by Public Request Reference
- Djgent-native resume flow: approve executes blocked operation, reject produces Final Response without execution, edit applies reviewer changes
- Decision/resume locking prevents double-execution under concurrent reviewer actions
- Resume failure handling preserves Resume Payload for retry and records error
- LangGraph HITL requests routed through shared reviewer flow with `source = "langgraph_hitl"`
- Notification email with safe summary and authenticated admin link; failure recorded without blocking request creation
- Django system checks for missing reviewer policy (E001), missing durable persistence (E002), and disabled HITL with protected tools (E003)
- Human-in-the-loop documentation covering configuration, protected tools, admin review, resume, and LangGraph integration

## [0.3.0] - 2026-04-20

### Added
- Initial release of djgent
- Agent creation with LangChain/LangGraph integration
- Multi-LLM provider support:
  - Google Gemini
  - OpenAI (GPT-4, GPT-3.5-turbo)
  - Anthropic (Claude 3 family)
  - Groq (fast inference)
  - Ollama (local models)
  - OpenRouter (unified API)
- Built-in tools:
  - Calculator (safe mathematical expressions)
  - DateTime (current time, formatting, date differences)
  - Search (DuckDuckGo web search)
  - HTTP (make API requests)
  - Weather (weather information)
- Custom tool creation with `@tool` decorator
- Tool registry with auto-discovery and Django app tool loading
- Conversation memory with in-memory and database-backed storage
- Built-in chat UI with persistent conversations and reusable chat views
- Long-term memory and retrieval/knowledge-base tools
- Runtime middleware, approvals, streaming events, and rate limiting
- Audit logging, response caching, usage tracking, and admin integration
- `ModelQueryTool` for safe model-backed database querying
- Pydantic input validation and structured output support
- Multi-agent helpers and simple chain execution
- MCP tool loading support
- Django system checks for configuration validation
- Comprehensive documentation and examples

[0.3.0]: https://pypi.org/project/djgent/0.3.0/
