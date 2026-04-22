"""
djgent - Django AI Agent Framework

Build AI agents with LangChain integration in Django applications.

Features:
    - Easy agent creation with LangChain/LangGraph integration
    - Multi-LLM support (OpenAI, Anthropic, Google, Groq, Ollama)
    - Built-in tools (calculator, datetime, search, HTTP, weather)
    - Custom tool creation with @tool decorator
    - Conversation memory (in-memory and database-backed)
    - Auto-discovery of tools from Django apps
    - Public model registration for anonymous access
    - Rate limiting middleware
    - Audit logging
    - Response caching
    - Pydantic input validation

Example:
    >>> from djgent import Agent
    >>> agent = Agent.create(name="assistant", auto_load_tools=True)
    >>> response = agent.run("What is 25 * 47?")
    >>> print(response)

For more information, see: https://github.com/borhanst/djgent
"""

__version__ = "0.3.1"
__author__ = "Borhan"
__author_email__ = "mdborhan.st@gmail.com"
__license__ = "MIT"
__url__ = "https://github.com/borhanst/djgent"
__description__ = "Django AI Agent Framework - Build AI agents with LangChain integration"

from djgent.agents.base import Agent

# Audit module - import directly when needed:
# from djgent.audit import AuditLogger, audit_logger
# Cache module - import directly when needed:
# from djgent.cache import CacheMiddleware, ResponseCache
from djgent.exceptions import (
    AgentError,
    ConfigurationError,
    DjgentError,
    LLMError,
    MemoryError,
    RateLimitError,
    RegistryError,
    ToolError,
    ValidationError,
)
from djgent.memory import (
    create_conversation,
    delete_conversation,
    get_all_conversations,
    get_conversation,
    get_memory_backend,
)
from djgent.memory.store import memory_store
from djgent.retrieval import (
    BaseRetriever,
    DjangoKnowledgeRetriever,
    KnowledgeIngestTool,
    RetrievalTool,
)
from djgent.runtime import (
    AgentMiddleware,
    AgentResult,
    ApprovalRequest,
    ExecutionContext,
    RateLimitMiddleware,
    StreamEvent,
)
from djgent.tools.base import ModelQueryTool, Tool
from djgent.tools.decorators import register_tool, tool
from djgent.tools.registry import ToolRegistry
from djgent.tools.schemas import (
    AgentRunInput,
    CalculatorInput,
    DjangoAuthInput,
    DjangoModelQueryInput,
    HttpRequestInput,
    KnowledgeIngestInput,
    KnowledgeRetrievalInput,
    MemoryStoreInput,
    SearchInput,
    ToolExecutionInput,
    WeatherInput,
    validate_tool_input,
)
from djgent.utils.public_models import (
    PublicModelRegistry,
    get_public_model_fields,
    get_public_models,
    register_public_model,
)

__all__ = [
    # Agent
    "Agent",
    "AgentMiddleware",
    "AgentResult",
    # Cache available via: from djgent.cache import CacheMiddleware, ResponseCache
    # Exceptions
    "AgentError",
    "ConfigurationError",
    "DjgentError",
    "LLMError",
    "MemoryError",
    "RateLimitError",
    "RegistryError",
    "ToolError",
    "ValidationError",
    # Retrieval
    "BaseRetriever",
    "DjangoKnowledgeRetriever",
    "KnowledgeIngestTool",
    "RetrievalTool",
    # Runtime
    "ApprovalRequest",
    "ExecutionContext",
    "RateLimitMiddleware",
    "StreamEvent",
    # Tools
    "Tool",
    "ModelQueryTool",
    "ToolRegistry",
    "register_tool",
    "tool",
    # Schemas
    "AgentRunInput",
    "CalculatorInput",
    "DjangoAuthInput",
    "DjangoModelQueryInput",
    "HttpRequestInput",
    "KnowledgeIngestInput",
    "KnowledgeRetrievalInput",
    "MemoryStoreInput",
    "SearchInput",
    "ToolExecutionInput",
    "validate_tool_input",
    "WeatherInput",
    # Public Models
    "register_public_model",
    "get_public_models",
    "get_public_model_fields",
    "PublicModelRegistry",
    # Memory
    "get_memory_backend",
    "get_conversation",
    "create_conversation",
    "delete_conversation",
    "get_all_conversations",
    "memory_store",
    "__version__",
]
