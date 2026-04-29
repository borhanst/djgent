# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Global memory defaults through `DJGENT["MEMORY_ENABLED"]` and
  `DJGENT["MEMORY_BACKEND"]` for `Agent.create()`.
- Automatic LangGraph checkpointer configuration through
  `DJGENT["CHECKPOINTER"]`, using PostgreSQL when Django uses PostgreSQL and
  SQLite otherwise.
- DRF view tool documentation and demo support, including the featured books
  API example.
- Tests for memory settings defaults, memory override behavior, and mounted
  chat URL generation.

### Changed
- `Agent.create()` now reads memory and memory backend defaults from settings
  when those arguments are omitted.
- Example project configuration now uses database-backed memory by default.
- Package dependencies now include OpenAI LangChain and Django REST Framework
  requirements.
- Package dependencies now include LangGraph SQLite and PostgreSQL checkpoint
  savers.
- README and persistent memory docs now cover settings-backed memory behavior
  and DRF view tools.
- LangChain middleware settings now stay separate from checkpointer
  configuration.

### Fixed
- Built-in chat detail URLs no longer repeat the `chat/` segment when chat URLs
  are mounted at `/chat/`.
- Chat conversation path prefix generation now matches the mounted URL
  structure.

### Maintenance
- Formatting cleanup in agent, chat, checks, demo, and test modules.
- Minor whitespace cleanup in demo tools.

## [0.3.2] - 2026-04-22

### Fixed
- Render configured chat input placeholders in the built-in chat UI.
- Clean up package formatting and lint issues for release verification.
- Declare Python 3.10 support in package metadata and documentation.
- Document that Djgent is pronounced "DJ agent".


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
- Multi-agent helpers
- MCP tool loading support
- Django system checks for configuration validation
- Comprehensive documentation and examples

### Coming Soon
- Simple chain execution for sequential tool and agent workflows.

[0.3.2]: https://pypi.org/project/djgent/0.3.2/
[0.3.0]: https://pypi.org/project/djgent/0.3.0/
