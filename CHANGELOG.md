# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-03-04

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
- Tool registry with auto-discovery
- Conversation memory for multi-turn interactions
- Django system checks for configuration validation
- Comprehensive documentation and examples

[0.1.0]: https://pypi.org/project/djgent/0.1.0/
