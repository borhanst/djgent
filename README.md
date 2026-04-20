# Djgent

**Django AI Agent Framework** - Build AI agents with LangChain integration in Django applications.

[![PyPI](https://img.shields.io/pypi/v/djgent.svg)](https://test.pypi.org/simple/ djgent)
[![GitHub](https://img.shields.io/github/license/borhanst/djgent)](https://github.com/borhanst/djgent/blob/main/LICENSE)
[![Python Support](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Django Support](https://img.shields.io/badge/Django-5.2+-green.svg)](https://www.djangoproject.com/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

## Features

- 🤖 **Easy Agent Creation** - Create AI agents with minimal configuration
- 💬 **Built-In Chat UI** - Mount a polished chat app with persistent conversations
- 🔌 **Multi-LLM Support** - OpenAI, Anthropic, Google Gemini, Groq, Ollama, OpenRouter
- 🛠️ **Tool System** - Built-in tools + custom tools with `@tool` decorator or `ModelQueryTool` base class
- 🧠 **Conversation Memory** - In-memory or database-backed persistent memory
- 🔄 **Durable Execution** - Thread-aware state with resumable runs and approval checkpoints
- 🧱 **Middleware Stack** - Dynamic prompts, summarization, output guardrails, and tool approvals
- ✅ **Structured Output** - Validate agent responses against Pydantic or dataclass schemas
- 🌊 **Streaming + Async APIs** - `stream`, `astream`, `arun`, and `ainvoke`
- 🧠 **Long-Term Memory** - Persist reusable facts across conversations
- 📚 **Retrieval / Knowledge Base** - Ingest and search project knowledge documents
- 🔌 **MCP Integration** - Load tools from MCP servers when adapters are installed
- 🔍 **Auto-Discovery** - Automatically discover and register tools from Django apps
- ✅ **System Checks** - Built-in Django system checks for configuration validation
- 🗄️ **Model Query Tools** - Easy database querying with `ModelQueryTool` base class
- 💾 **Persistent Storage** - Django models for conversation history with admin interface
- 🛡️ **Rate Limiting** - Protect agents from abuse with configurable rate limits
- 📋 **Audit Logging** - Track all agent operations with persistent audit logs
- 💨 **Response Caching** - Cache LLM responses to reduce costs and latency
- ⛓️ **Chains** - Sequential execution of tools and agents
- 🔎 **Input Validation** - Pydantic-based validation for all tool inputs

## Documentation

Core guides:

- [Chat UI](docs/CHAT_UI.md) - Built-in chat, reusable base chat views, and anonymous session behavior
- [Persistence Memory](docs/PERSISTENT_MEMORY.md) - Conversation persistence and history management
- [Model Query Tool](docs/MODEL_QUERY_TOOL.md) - Building safe model-backed tools
- [Multi Agent](docs/MULTI_AGENT.md) - Coordinating multiple specialized agents
- [Middleware](docs/MIDDLEWARE.md) - Runtime middleware, approvals, and LangChain middleware config
- [MCP](docs/MCP.md) - Loading tools from MCP servers

## Installation

### Using uv (Recommended)

```bash
uv add djgent
```

### Using pip

```bash
pip install djgent
```

### From GitHub (Latest)

```bash
# Using uv
uv add git+https://github.com/borhanst/djgent.git

# Using pip
pip install git+https://github.com/borhanst/djgent.git
```

### Optional Dependencies

Install specific provider support:

```bash
# Using uv
uv add djgent[google]
uv add djgent[openai]
uv add djgent[anthropic]
uv add djgent[groq]
uv add djgent[ollama]
uv add djgent[search]
uv add djgent[http]
uv add djgent[mcp]
uv add djgent[all]  # All providers

# Using pip
pip install djgent[google]
pip install djgent[openai]
pip install djgent[anthropic]
pip install djgent[groq]
pip install djgent[ollama]
pip install djgent[search]
pip install djgent[http]
pip install djgent[mcp]
pip install djgent[all]
```

## Quick Start

### 1. Add to INSTALLED_APPS

In your Django `settings.py`:

```python
INSTALLED_APPS = [
    # ...
    'djgent',
]
```

### 2. Configure Djgent

```python
import os
from dotenv import load_dotenv

load_dotenv()

DJGENT = {
    "DEFAULT_LLM": "google:gemini-2.5-flash",  # or "openai:gpt-4o-mini", "anthropic:claude-3-5-sonnet-20241022"
    "API_KEYS": {
        "GOOGLE": os.environ.get("GOOGLE_API_KEY", ""),
        "OPENAI": os.environ.get("OPENAI_API_KEY", ""),
        "ANTHROPIC": os.environ.get("ANTHROPIC_API_KEY", ""),
        "GROQ": os.environ.get("GROQ_API_KEY", ""),
    },
    "BUILTIN_TOOLS": ["calculator", "datetime", "search"],
    "AUTO_DISCOVER_TOOLS": True,
    "MEMORY_ENABLED": True,
}
```

### 3. Create an Agent

```python
from djgent import Agent

# Create an agent with auto-loaded tools
agent = Agent.create(
    name="assistant",
    auto_load_tools=True,
    memory=True,
)

# Run the agent
response = agent.run("What is 25 * 47 + 100?")
print(response)  # Uses calculator tool automatically
```

### 3.5 Built-In Chat UI

Djgent includes a reusable chat app you can mount directly in your Django project.

```python
# settings.py
INSTALLED_APPS = [
    # ...
    "djgent",
    "djgent.chat",
]

DJGENT = {
    "DEFAULT_LLM": "openai:gpt-4o-mini",
    "API_KEYS": {
        "OPENAI": os.environ.get("OPENAI_API_KEY", ""),
    },
    "CHAT_UI": {
        "TITLE": "Support Copilot",
        "TOOLS": ["calculator", "datetime", "search"],
        "AUTO_LOAD_TOOLS": True,
        "SYSTEM_PROMPT": "You are the support assistant for our product.",
        "BUBBLE_ENABLED": True,
        "BUBBLE_TITLE": "Ask Support",
    },
}
```

```python
# urls.py
from django.urls import include, path

urlpatterns = [
    path("ai/", include("djgent.chat.urls")),
]
```

Add the site-wide bubble to your base template:

```django
{% load djgent_chat %}
...
{% djgent_chat_bubble %}
```

This gives you a modern browser chat view with conversation history, anonymous session tracking, database-backed persistence, and an opt-in slide-out chat bubble for normal app pages. The bubble is not auto-injected into Django admin.

If you want the same chat behavior with your own agent, subclass `BaseChatView`:

```python
from typing import Optional

from djgent import Agent
from djgent.chat import BaseChatView


class SupportChatView(BaseChatView):
    agent_name = "support-chat"
    chat_title = "Support Chat"
    system_prompt = "You are the support assistant for our product."
    tools = ["calculator", "datetime", "search"]
    auto_load_tools = True

    def build_agent(
        self, request, conversation_id: Optional[str] = None
    ) -> Agent:
        return Agent.create(
            name=self.get_agent_name(),
            tools=self.get_tool_names(),
            memory=True,
            memory_backend="database",
            conversation_id=conversation_id,
            conversation_name="",
            user=self.get_active_user(request),
            system_prompt=self.get_system_prompt(),
            auto_load_tools=self.get_auto_load_tools(),
        )
```

Chat views auto-load registered tools by default. A tool registered with
`@tool` or app `tools.py` auto-discovery is available to the chat agent without
adding its name to `CHAT_UI["TOOLS"]`; set
`AUTO_LOAD_TOOLS=False` for explicit-only tool lists.

Register it with:

```python
urlpatterns = [
    path("", SupportChatView.page_view(), name="home"),
    path("chat/<uuid:conversation_id>/", SupportChatView.page_view(), name="detail"),
    path("embed/", SupportChatView.embed_view(), name="embed"),
    path("embed/<uuid:conversation_id>/", SupportChatView.embed_view(), name="embed-detail"),
    path("api/chat/", SupportChatView.message_view(), name="message"),
    path("api/conversations/new/", SupportChatView.new_conversation_view(), name="new"),
]
```

See [Chat UI](docs/CHAT_UI.md) for the full subclassing guide.

### 4. Create Custom Tools

```python
from djgent import Tool, tool

@tool
def get_weather(city: str) -> str:
    """Get current weather for a city."""
    # Your weather API logic here
    return f"Weather in {city}: Sunny, 25°C"

@tool(name="greet", description="Greet someone by name")
def greet_person(name: str) -> str:
    """Greet a person."""
    return f"Hello, {name}!"

@tool
class EchoTool(Tool):
    name = "echo"
    description = "Echo a message"

    def _run(self, message: str) -> str:
        return message
```

Djgent auto-discovers tools from each installed app's `tools.py` when
`DJGENT["AUTO_DISCOVER_TOOLS"]` is `True` (default). Function tools decorated
with `@tool` self-register during import, and `Tool` subclasses with a `name`
are registered automatically.

### 5. Create Model Query Tools (New!)

Easily query your Django models with the `ModelQueryTool` base class:

```python
from djgent import ModelQueryTool
from products.models import Product

class ProductQueryTool(ModelQueryTool):
    name = "product_query"
    description = "Query products from database"
    queryset = Product.objects.filter(active=True)
    exclude_fields = ["cost_price"]  # Hide sensitive fields
    require_auth = False  # Public access

# Use with an agent
agent = Agent.create(
    name="shopping-assistant",
    tools=[ProductQueryTool()],
)

# Query actions: list, query, get_by_id, search, count
response = agent.run("Show me laptops under $1000")
```

Override `get_queryset()` for dynamic, user-based access:

```python
from django.contrib.auth import get_user_model
User = get_user_model()

class UserQueryTool(ModelQueryTool):
    name = "user_query"
    require_auth = True
    
    def get_queryset(self, runtime=None, user=None, **kwargs):
        if user and user.is_staff:
            return User.objects.all()  # Staff see all
        return User.objects.filter(id=user.id) if user else User.objects.none()
```

Query by different fields (e.g., slug, username):

```python
class ProductQueryTool(ModelQueryTool):
    name = "product_query"
    queryset = Product.objects.all()
    query_field = "slug"  # Query by slug instead of pk

# Now you can query by slug
tool._run(action="get_by_id", id="my-product-slug")

# Or override per-query
tool._run(action="get_by_id", id="my-product", query_field="sku")
```

## Usage Examples

### Basic Agent

```python
from djgent import Agent

agent = Agent.create(
    name="helper",
    tools=["calculator", "datetime"],
    memory=True,
)

response = agent.run("What's 15% of 250?")
print(response)
```

### Agent with Custom System Prompt

```python
agent = Agent.create(
    name="coding-assistant",
    auto_load_tools=True,
    system_prompt="""You are an expert Python developer.
    Help users with coding questions.
    Use tools when you need to calculate or search for information.""",
)

response = agent.run("How do I read a JSON file in Python?")
```

### Switching LLM Providers

```python
# Use OpenAI instead of default
agent = Agent.create(
    name="assistant",
    llm_provider="openai",  # Override default provider
    auto_load_tools=True,
)

# Use Anthropic
agent = Agent.create(
    name="assistant",
    llm_provider="anthropic",
)

# Use Groq (fast!)
agent = Agent.create(
    name="assistant",
    llm_provider="groq",
)
```

### Using Tools Directly

```python
from djgent.tools.registry import ToolRegistry

# Get a tool instance
calculator = ToolRegistry.get_tool_instance("calculator")
result = calculator.run("2 + 2 * 5")
print(result)  # 12
```

### Persistent Conversation Memory (New!)

Save conversation history to the database:

```python
from djgent import Agent

# Database-backed persistent storage
agent = Agent.create(
    name="assistant",
    memory_backend="database",  # Use database instead of in-memory
    user=request.user,  # Associate with user (optional)
)

response = agent.run("Hello!")

# Get conversation ID to resume later
conv_id = agent.get_conversation_id()

# Resume existing conversation
agent = Agent.create(
    name="assistant",
    memory_backend="database",
    conversation_id=conv_id,  # Resume this conversation
)
```

Manage conversations via CLI:

```bash
# List conversations
python manage.py djgent_list_conversations --user=admin

# Export conversation
python manage.py djgent_export_conversation --id=<uuid> --output=chat.json

# Clear old conversations
python manage.py djgent_clear_conversations --days=30
```

See [docs/PERSISTENT_MEMORY.md](docs/PERSISTENT_MEMORY.md) for full documentation.

### Runtime Middleware

Djgent always includes three runtime middleware components by default:

- `DynamicPromptMiddleware` injects a saved summary and optional prompt context
- `ToolApprovalMiddleware` blocks risky tools until they are approved
- `OutputGuardrailMiddleware` replaces empty model output with a fallback response

You can add your own middleware on top of that stack:

```python
from djgent import Agent
from djgent.runtime import AgentMiddleware, ExecutionContext


class MetricsMiddleware(AgentMiddleware):
    def before_run(self, execution: ExecutionContext) -> None:
        execution.metadata["request_source"] = "chat-ui"
        execution.emit("run.started", input=execution.input)

    def after_run(self, execution: ExecutionContext, output: str) -> str:
        execution.emit("run.completed", output=output)
        return output


agent = Agent.create(
    name="assistant",
    auto_load_tools=True,
    middleware=[MetricsMiddleware()],
)

response = agent.run(
    "Summarize our last exchange",
    context={"prompt_context": "Respond in 3 bullet points."},
)
```

Mark custom tools as approval-gated by setting `requires_approval = True`:

```python
from djgent import Agent, Tool


class DeleteRecordTool(Tool):
    name = "delete_record"
    description = "Delete a record from the database."
    requires_approval = True
    approval_reason = "Deleting data is irreversible."

    def _run(self, record_id: int) -> str:
        return f"Deleted record {record_id}"


agent = Agent.create(name="ops", tools=[DeleteRecordTool()])

message = agent.run("Delete record 42")
state = agent.get_thread_state()

print(message)
print(state["paused_tool_name"])
print(state["paused_tool_arguments"])

agent.approve_pending_tool()
message = agent.run("Delete record 42")
print(message)
```

You can also enable LangChain's built-in middleware through `langchain_middleware`:

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

See [docs/MIDDLEWARE.md](docs/MIDDLEWARE.md) for the full guide.

### MCP Tool Loading

Load external tools from Model Context Protocol servers with the optional MCP extra:

```bash
uv add djgent[mcp]
```

```python
from djgent import Agent

agent = Agent.create(
    name="assistant",
    auto_load_tools=True,
    mcp_servers={
        "filesystem": {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
        }
    },
)
```

`djgent` forwards `mcp_servers` directly to `langchain_mcp_adapters` and adds the
returned MCP tools to the agent's tool list.

See [docs/MCP.md](docs/MCP.md) for installation notes, loading behavior, and error handling.

### Rate Limiting (New!)

Protect your agents from abuse with configurable rate limits:

```python
from djgent import Agent
from djgent.runtime import RateLimitMiddleware

# Create rate limiter with custom limits
limiter = RateLimitMiddleware(
    requests_per_minute=30,
    requests_per_hour=500,
    requests_per_day=5000,
    burst_size=10,
)

# Add to agent
agent = Agent.create(
    name="assistant",
    middleware=[limiter],
    auto_load_tools=True,
)

# The middleware automatically tracks requests per user/IP
response = agent.run("Hello!")
```

### Audit Logging (New!)

Track all agent operations with persistent audit logs:

```python
from djgent.audit import AuditLogger, AuditEventType, AuditLevel

# Create audit logger
audit_logger = AuditLogger()

# Log an event
audit_logger.log(
    event_type=AuditEventType.AGENT_RUN,
    level=AuditLevel.INFO,
    agent_name="assistant",
    user_id=1,
    message="User asked about weather",
    metadata={"query": "weather in Dhaka"},
)

# Query audit logs
from djgent.models import AuditLog
logs = AuditLog.objects.filter(agent_name="assistant")
```

### Response Caching (New!)

Cache LLM responses to reduce costs and improve latency:

```python
from djgent.cache import ResponseCache, CacheMiddleware

# Create cache with TTL (in seconds)
cache = ResponseCache(
    default_ttl=3600,  # 1 hour
    max_size=1000,
)

# Or use middleware for automatic caching
cache_middleware = CacheMiddleware(
    ttl=1800,  # 30 minutes
    enabled=True,
)

# Add to agent
agent = Agent.create(
    name="assistant",
    middleware=[cache_middleware],
    auto_load_tools=True,
)

# Same prompts will hit cache
response1 = agent.run("What is Python?")
response2 = agent.run("What is Python?")  # Cached!
```

### Pydantic Input Validation (New!)

Validate tool inputs with Pydantic schemas:

```python
from djgent.tools.schemas import (
    validate_tool_input,
    ToolExecutionInput,
    KnowledgeRetrievalInput,
)
from pydantic import ValidationError

# Validate tool execution input
try:
    validated = validate_tool_input(
        ToolExecutionInput,
        tool_name="search",
        arguments={"query": "Django"},
    )
except ValidationError as e:
    print(f"Validation failed: {e}")

# Use built-in schemas for tools
knowledge_input = KnowledgeRetrievalInput(
    query="How to create agents",
    limit=10,
    namespace="docs",
)
```

### Chains (New!)

Execute multiple steps sequentially:

```python
from djgent.chains import Chain

# Define steps
def step1(data):
    return f"Step 1: {data}"

def step2(data):
    return f"Step 2: {data}"

def step3(data):
    return f"Step 3: {data}"

# Create and execute chain
chain = Chain()
chain.add(step1).add(step2).add(step3)

result = chain.execute("hello")
# Result: "Step 3: Step 2: Step 1: hello"
```

## Built-in Tools

| Tool | Description |
|------|-------------|
| `calculator` | Mathematical calculations (+, -, *, /, **, %) |
| `datetime` | Get current date/time, format dates, calculate differences |
| `search` | Web search using DuckDuckGo (no API key needed) |
| `http` | Make HTTP requests to APIs |
| `weather` | Get weather information (requires API key) |
| `django_model` | Read-only generic Django model queries for admin/debug workflows |
| `django_auth` | Check user authentication, permissions, and groups |

### Model Query Tools

Create custom database query tools easily with `ModelQueryTool`:

```python
from djgent import ModelQueryTool

class MyModelQueryTool(ModelQueryTool):
    name = "my_model_query"
    queryset = MyModel.objects.select_related("owner").all()
    exclude_fields = ["sensitive_field"]
    allowed_fields = ["id", "name", "status", "owner"]
    require_auth = False  # Public access
```

**Actions:** `list`, `query`, `get_by_id`, `search`, `count`

Model query tools validate requested fields, filters, ordering, search fields, and `query_field` before ORM execution. Prefer app-specific `ModelQueryTool` classes over the generic `django_model` tool for production user-facing agents.

See [docs/MODEL_QUERY_TOOL.md](docs/MODEL_QUERY_TOOL.md) for full documentation.

## Supported LLM Providers

| Provider | Models | API Key |
|----------|--------|---------|
| Google Gemini | gemini-2.5-flash, gemini-pro | `GOOGLE_API_KEY` |
| OpenAI | gpt-4o-mini, gpt-4, gpt-3.5-turbo | `OPENAI_API_KEY` |
| Anthropic | claude-3-5-sonnet, claude-3-opus | `ANTHROPIC_API_KEY` |
| Groq | llama-3.3-70b, mixtral-8x7b | `GROQ_API_KEY` |
| Ollama | llama3.2, mistral, custom | None (local) |
| OpenRouter | Various models | `OPENROUTER_API_KEY` |

## Configuration Checks

Run Django's system checks to verify your configuration:

```bash
python manage.py check
```

Or programmatically:

```python
from djgent.utils.checks import print_djent_checks

if print_djent_checks():
    print("✅ All checks passed!")
```

## API Reference

### Agent

```python
from djgent import Agent

agent = Agent.create(
    name: str,                    # Agent name
    tools: List[str] = None,      # List of tool names
    memory: bool = True,          # Enable conversation memory
    system_prompt: str = None,    # System prompt
    auto_load_tools: bool = False,# Auto-load all registered tools
    llm_provider: str = None,     # Override default LLM provider
    middleware: List = None,      # Middleware list (rate limiting, caching, etc.)
    memory_backend: str = None,   # "database" or "memory"
    response_schema: type = None, # Optional structured output schema
    mcp_servers: dict = None,     # Optional MCP server definitions
    langchain_middleware: dict = None,  # LangChain built-in middleware config
    checkpointer: Any = None,     # Optional LangGraph/LangChain checkpointer
    thread_id: str = None,        # Override durable thread identifier
)

# Run the agent
response = agent.run("Your message here")

# Clear conversation history
agent.clear_memory()

# Get conversation history
history = agent.get_history()
```

### Tool Decorator

```python
from djgent import tool

@tool
def my_tool(arg1: str, arg2: int = 10) -> str:
    """Tool description. First line is used as the description."""
    return f"Result: {arg1} * {arg2}"

@tool(name="custom_name", description="Custom description")
def another_tool(value: str) -> str:
    """Full docstring can be multi-line."""
    return value.upper()
```

### Tool Class

```python
from djgent import Tool, tool

@tool
class MyCustomTool(Tool):
    name = "my_tool"
    description = "Does something useful"

    def _run(self, input: str) -> str:
        return f"Processed: {input}"
```

Place this class in an installed app's `tools.py`. `@tool` registers functions
and `Tool` subclasses during import. Without the decorator, Djgent can still
auto-register `Tool` subclasses from `name = "my_tool"` when
`AUTO_DISCOVER_TOOLS` is enabled. Manual `ToolRegistry.register(...)` also still
works and wins over duplicate auto-discovery.

### ModelQueryTool Class

Create database query tools easily:

```python
from djgent import ModelQueryTool
from myapp.models import MyModel

class MyModelQueryTool(ModelQueryTool):
    name = "my_model_query"
    description = "Query my models"
    queryset = MyModel.objects.select_related("owner").all()
    exclude_fields = ["password", "secret"]  # Hide sensitive fields
    allowed_fields = ["id", "name", "status", "owner"]
    require_auth = False  # Public access
    max_results = 100
    query_field = "pk"  # Field to query by (default: "pk")

# Usage with agent
agent = Agent.create(
    name="assistant",
    tools=[MyModelQueryTool()],
)

# Or use directly
tool = MyModelQueryTool()
tool._run(action="list", limit=10)
tool._run(action="list", include_total=False)  # Skip total_count query
tool._run(action="query", filters={"status": "active"})
tool._run(action="get_by_id", id=42)  # Query by pk
tool._run(action="get_by_id", id="my-slug", query_field="slug")  # Query by slug
tool._run(action="search", search="keyword")
tool._run(action="count", filters={"status": "active"})
```

Override `get_queryset()` for dynamic access control:

```python
class UserQueryTool(ModelQueryTool):
    name = "user_query"
    require_auth = True
    query_field = "username"  # Query by username instead of id
    
    def get_queryset(self, runtime=None, user=None, **kwargs):
        # runtime contains Django context
        # user is the current user (None if anonymous)
        if user and user.is_staff:
            return User.objects.all()
        return User.objects.filter(is_active=True) if user else User.objects.none()
```

### Rate Limiting API

```python
from djgent.runtime import RateLimitMiddleware

# Create rate limiter
limiter = RateLimitMiddleware(
    requests_per_minute: int = 60,
    requests_per_hour: int = 1000,
    requests_per_day: int = 10000,
    burst_size: int = 10,
    enabled: bool = True,
)

# Add to agent
agent = Agent.create(
    name="assistant",
    middleware=[limiter],
)
```

### Audit Logging API

```python
# Import directly from module
from djgent.audit import (
    AuditLogger,
    AuditEventType,
    AuditLevel,
    AuditEvent,
)

# Create logger
audit_logger = AuditLogger()

# Log events
audit_logger.log(
    event_type: AuditEventType,
    level: AuditLevel,
    agent_name: str,
    user_id: Optional[int],
    message: str,
    metadata: Dict[str, Any] = {},
)

# Query logs
from djgent.models import AuditLog
AuditLog.objects.filter(agent_name="assistant")
```

### Response Caching API

```python
# Import directly from module
from djgent.cache import ResponseCache, CacheMiddleware

# Create cache
cache = ResponseCache(
    default_ttl: int = 3600,
    max_size: int = 1000,
)

# Get cached response
cached = cache.get("cache_key")

# Set cache
cache.set("cache_key", "response", ttl=3600)

# Use middleware
cache_middleware = CacheMiddleware(
    ttl: int = 3600,
    enabled: bool = True,
)

agent = Agent.create(
    name="assistant",
    middleware=[cache_middleware],
)
```

### Pydantic Schemas API

```python
from djgent.tools.schemas import (
    # Validation
    validate_tool_input,
    
    # Base schemas
    ToolExecutionContext,
    ToolExecutionInput,
    
    # Tool-specific schemas
    KnowledgeRetrievalInput,
    KnowledgeIngestInput,
    SearchInput,
    CalculatorInput,
    WeatherInput,
    HttpRequestInput,
    DjangoModelQueryInput,
    DjangoAuthInput,
    MemoryStoreInput,
)

# Validate input
validated = validate_tool_input(ToolExecutionInput, **data)
```

### Chains API

```python
from djgent.chains import Chain

# Create chain
chain = Chain()

# Add steps
chain.add(step_callable)
chain.add(another_step)

# Execute
result = chain.execute(input_data)

# Chain methods
len(chain)          # Get number of steps
chain.clear()        # Clear all steps
```

## Project Structure

```
djgent/
├── agents/
│   └── base.py          # Agent class with persistent memory support
├── tools/
│   ├── base.py          # Tool base class + ModelQueryTool
│   ├── decorators.py    # @tool decorator
│   ├── registry.py      # ToolRegistry
│   ├── schemas.py      # Pydantic schemas for input validation
│   └── builtin/         # Built-in tools
│       ├── calculator.py
│       ├── datetime_tool.py
│       ├── django_model.py  # Django model query tool
│       ├── django_auth.py   # Django auth tool
│       ├── http_tool.py
│       ├── search.py
│       └── weather.py
├── llm/
│   ├── providers.py     # LLM provider management
│   └── config.py        # LLM configuration
├── memory/              # Persistent memory module
│   ├── __init__.py
│   ├── base.py          # BaseMemory ABC
│   ├── backends.py      # DatabaseMemory, InMemoryMemory
│   └── utils.py         # Utility functions
├── management/
│   └── commands/        # Management commands
│       ├── djgent_create_conversation.py
│       ├── djgent_list_conversations.py
│       ├── djgent_export_conversation.py
│       └── djgent_clear_conversations.py
├── migrations/          # Database migrations
├── runtime/             # Runtime components
│   ├── rate_limit.py    # Rate limiting middleware
│   ├── schemas.py       # Runtime schemas
│   ├── middleware.py    # Agent middleware
│   └── state.py         # Execution state
├── retrieval/           # Knowledge retrieval
│   ├── base.py
│   └── tools.py
├── utils/
│   ├── checks.py        # Django system checks
│   ├── helpers.py       # Utility functions
│   └── public_models.py # Public model registration
├── audit.py             # Audit logging
├── cache.py             # Response caching
├── chains.py            # Chain execution
├── models.py            # Conversation, Message, AuditLog models
├── admin.py             # Django admin configuration
├── exceptions.py        # Custom exceptions
└── settings.py          # Default settings
```

## Development

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/borhanst/djgent.git
cd djgent

# Install with dev dependencies using uv
uv sync --extra dev

# Run tests
uv run pytest

# Format code
uv run black djgent/

# Lint code
uv run ruff check djgent/
```

### Building the Package

```bash
# Build distribution using uv
uv build

# The built files will be in dist/
# - djgent-<version>-py3-none-any.whl
# - djgent-<version>.tar.gz
```

### Publishing to PyPI

```bash
# Publish using uv
uv publish --token pypi-YOUR-API-TOKEN

# Or publish to TestPyPI first
uv publish --token pypi-YOUR-TOKEN --url https://test.pypi.org/legacy/
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Changelog

### 0.3.0 (2026-03-14)
- Added rate limiting with `RateLimitMiddleware`
- Added audit logging with `AuditLogger` and `AuditLog` model
- Added response caching with `ResponseCache` and `CacheMiddleware`
- Added Pydantic input validation schemas in `djgent.tools.schemas`
- Added `Chain` class for sequential tool/agent execution
- Added runtime schemas (`StreamEvent`, `ApprovalRequest`, `AgentResult`)
- Restructured audit, cache, chains to single files (audit.py, cache.py, chains.py)
- Added tests for agent, tools, and memory modules
- Fixed various bug fixes and improvements

### 0.2.0 (2026-03-06)
- Added persistent conversation memory with Django models
- Added `Conversation` and `Message` models for chat history
- Added database-backed memory backend (`DatabaseMemory`)
- Updated `Agent` class with `memory_backend` parameter
- Added conversation management commands:
  - `djgent_list_conversations` - List conversations
  - `djgent_create_conversation` - Create new conversation
  - `djgent_export_conversation` - Export conversation to JSON
  - `djgent_clear_conversations` - Clear old conversations
- Added Django admin interface for conversations
- Added memory utility functions (`get_conversation`, `create_conversation`, etc.)
- Added `ModelQueryTool` base class for easy database querying
- Added `get_queryset()` method for dynamic queryset customization
- Updated `DjangoModelQueryTool` to use new `ModelQueryTool` base
- Added `django_auth` tool for authentication checks
- Added public model registration for anonymous access
- Enhanced authentication support with `runtime` parameter

### 0.0.3 (2026-03-04)
- Initial release
- Agent creation with LangChain integration
- Multi-LLM provider support
- Built-in tools (calculator, datetime, search, HTTP, weather)
- Custom tool creation with @tool decorator
- Tool auto-discovery
- Conversation memory
- Django system checks

## Links

- [GitHub](https://github.com/borhanst/djgent)
- [Issues](https://github.com/borhanst/djgent/issues)
- [LangChain Documentation](https://python.langchain.com/)
- [Django Documentation](https://docs.djangoproject.com/)
- [uv - Fast Python package installer](https://github.com/astral-sh/uv)
