# Multi-Agent Systems Guide

## Overview

Djgent supports multi-agent systems using the **Subagents pattern** from LangChain. This pattern enables coordinating multiple specialized agents to tackle complex workflows.

In the Subagents pattern:
- A **main agent** (coordinator) manages the workflow
- **Subagents** are specialized workers invoked as tools by the main agent
- Each subagent has its own context, tools, and system prompt
- Context is isolated between subagents for better efficiency

## When to Use Multi-Agent

Multi-agent systems are particularly valuable when:

| Scenario | Description |
|----------|-------------|
| **Too many tools** | A single agent has too many tools and makes poor decisions about which to use |
| **Specialized knowledge** | Tasks require domain-specific context with extensive prompts |
| **Sequential constraints** | Need to enforce workflow steps that unlock capabilities after conditions are met |
| **Distributed development** | Different teams need to develop/maintain components independently |
| **Parallelization** | Want to spawn specialized workers for concurrent subtask execution |

### When NOT to Use Multi-Agent

- Simple tasks that a single agent with proper tools can handle
- When latency is critical and overhead outweighs benefits
- When context requirements are minimal

## Quick Start

### Using `Agent.create_multi()` (Recommended)

The easiest way to create a multi-agent system is using the `Agent.create_multi()` factory method:

```python
from djgent import Agent

# Create multi-agent team with agent configurations
team = Agent.create_multi(
    name="customer-support",
    agents=[
        {
            "name": "tech-agent",
            "role": "Technical support for Django and Python",
            "system_prompt": "You handle technical questions about Django and Python.",
            "tools": ["django_model", "calculator"],
        },
        {
            "name": "billing-agent",
            "role": "Billing and payment questions",
            "system_prompt": "You handle billing and payment questions.",
            "tools": ["django_model"],
        },
    ],
)

# Run the team
response = team.run("I was charged twice for my subscription")
print(response)  # billing-agent handles this
```

### Basic Multi-Agent Team (Manual)

Alternatively, create agents manually and pass to `MultiAgent`:

```python
from djgent import Agent, MultiAgent

# Create specialized agents
tech_agent = Agent.create(
    name="tech-agent",
    system_prompt="You handle technical questions about Django and Python.",
    tools=["django_model", "calculator"],
)

billing_agent = Agent.create(
    name="billing-agent",
    system_prompt="You handle billing and payment questions.",
    tools=["django_model"],
)

# Create multi-agent team
team = MultiAgent(
    name="customer-support",
    subagents=[tech_agent, billing_agent],
)

# Run the team
response = team.run("I was charged twice for my subscription")
print(response)  # billing-agent handles this
```

### With Role Descriptions

Provide explicit role descriptions for better routing:

```python
team = MultiAgent(
    name="support-team",
    subagents=[
        (tech_agent, "Technical support for Django, Python, and API issues"),
        (billing_agent, "Billing, payments, refunds, and subscriptions"),
        (general_agent, "General FAQs, account info, and inquiries"),
    ],
    verbose=True,  # Enable logging
)

response = team.run("How do I fix a database error?")
```

### With Custom Main Agent

Provide your own coordinator agent:

```python
# Create custom main agent
coordinator = Agent.create(
    name="coordinator",
    system_prompt="""You are a support coordinator.
    - For technical questions: invoke tech-agent
    - For billing questions: invoke billing-agent
    - For general questions: invoke general-agent
    Always route to the appropriate specialist.""",
)

team = MultiAgent(
    name="support-team",
    subagents=[tech_agent, billing_agent, general_agent],
    main_agent=coordinator,
)
```

## API Reference

### `Agent.create_multi()` Factory Method

```python
@classmethod
def create_multi(
    cls,
    name: str,
    agents: Optional[List[Dict[str, Any]]] = None,
    main_agent_config: Optional[Dict[str, Any]] = None,
    memory: bool = True,
    memory_backend: str = "memory",
    verbose: bool = False,
    **kwargs: Any,
) -> "MultiAgent":
    """
    Factory method to create a multi-agent system.
    
    Args:
        name: Team name
        agents: List of agent configurations, each containing:
            - name: str (agent name)
            - role: str (specialization/role description for routing)
            - tools: Optional[List] (tool names or instances)
            - system_prompt: Optional[str] (specialized system prompt)
            - llm_provider: Optional[str] (override provider)
            - memory: bool (enable memory for this subagent)
        main_agent_config: Configuration for the main coordinator agent:
            - system_prompt: Optional[str] (routing instructions)
            - tools: Optional[List] (additional tools)
            - llm_provider: Optional[str]
        memory: Enable conversation memory for main agent
        memory_backend: Backend type ("memory" or "database")
        verbose: Enable detailed logging
        **kwargs: Additional MultiAgent settings
        
    Returns:
        MultiAgent instance
        
    Example:
        team = Agent.create_multi(
            name="customer-support",
            agents=[
                {
                    "name": "tech-agent",
                    "role": "Technical support for Django and Python",
                    "system_prompt": "You handle technical questions.",
                    "tools": ["django_model"],
                },
                {
                    "name": "billing-agent",
                    "role": "Billing and payment questions",
                    "system_prompt": "You handle billing questions.",
                    "tools": ["django_model"],
                },
            ],
            verbose=True,
        )
        response = team.run("I was charged twice")
    """
```

### MultiAgent Class

```python
class MultiAgent:
    def __init__(
        self,
        name: str,
        subagents: Optional[List[Union[Agent, Tuple[Agent, str]]]] = None,
        main_agent: Optional[Agent] = None,
        main_agent_config: Optional[Dict[str, Any]] = None,
        memory: bool = True,
        memory_backend: str = "memory",
        verbose: bool = False,
    ):
        """
        Initialize multi-agent coordinator.
        
        Args:
            name: Team name
            subagents: List of Agent instances or (Agent, role_description) tuples
            main_agent: Optional custom main/coordination agent
            main_agent_config: Config for auto-created main agent:
                - system_prompt: str
                - tools: List
                - llm_provider: Optional[str]
            memory: Enable conversation memory for main agent
            memory_backend: Backend type ("memory" or "database")
            verbose: Enable detailed logging
        """
```

### Methods

#### `add_subagent(agent, role=None)`

Add a subagent to the team:

```python
tech_agent = Agent.create(name="tech-agent", tools=["django_model"])
team.add_subagent(tech_agent, role="Technical support specialist")
```

#### `remove_subagent(agent_name)`

Remove a subagent from the team:

```python
team.remove_subagent("tech-agent")
```

#### `get_subagent(name)`

Get a subagent by name:

```python
tech = team.get_subagent("tech-agent")
```

#### `list_subagents()`

List all subagents with their roles:

```python
for subagent in team.list_subagents():
    print(f"{subagent['name']}: {subagent['role']}")
```

#### `run(input, **kwargs)`

Execute the multi-agent system:

```python
response = team.run("I was charged twice")
```

#### `run_parallel(input, subagent_names=None)`

Run input through multiple subagents in parallel:

```python
responses = team.run_parallel(
    "What do you know about Django?",
    subagent_names=["tech-agent", "general-agent"]
)

for name, response in responses.items():
    print(f"{name}: {response}")
```

#### `get_conversation_id()`

Get the current conversation ID:

```python
conv_id = team.get_conversation_id()
```

#### `get_conversation_info()`

Get conversation metadata:

```python
info = team.get_conversation_info()
if info:
    print(f"Messages: {info['message_count']}")
```

#### `clear_memory()`

Clear conversation history for all agents:

```python
team.clear_memory()
```

## Usage Examples

### Example 1: Customer Support Team

```python
from djgent import Agent, MultiAgent

# Create specialized support agents
tech_agent = Agent.create(
    name="tech-agent",
    system_prompt="You are a technical support specialist for Django and Python. Help users debug code, fix errors, and understand frameworks.",
    tools=["django_model", "calculator"],
    memory=True,
)

billing_agent = Agent.create(
    name="billing-agent",
    system_prompt="You are a billing specialist. Help users with payments, refunds, subscriptions, and invoices.",
    tools=["django_model"],
    memory=True,
)

shipping_agent = Agent.create(
    name="shipping-agent",
    system_prompt="You handle shipping, delivery, and order tracking questions.",
    tools=["django_model"],
    memory=True,
)

# Create multi-agent team
team = MultiAgent(
    name="customer-support",
    subagents=[
        (tech_agent, "Technical support for Django, Python, and code debugging"),
        (billing_agent, "Billing, payments, refunds, and subscription management"),
        (shipping_agent, "Shipping, delivery tracking, and order status"),
    ],
    memory_backend="database",
    verbose=True,
)

# Process customer requests
response = team.run("My order hasn't arrived yet")
print(response)  # shipping-agent handles this

response = team.run("I need help with a Django error")
print(response)  # tech-agent handles this
```

### Example 2: Research Team

```python
from djgent import Agent, MultiAgent

# Create research specialists
data_analyst = Agent.create(
    name="data-analyst",
    system_prompt="You analyze data and statistics. Use the calculator tool for computations.",
    tools=["calculator"],
)

writer = Agent.create(
    name="writer",
    system_prompt="You write clear, well-structured reports and summaries.",
)

reviewer = Agent.create(
    name="reviewer",
    system_prompt="You review content for accuracy and clarity.",
)

# Create research team
team = MultiAgent(
    name="research-team",
    subagents=[
        (data_analyst, "Data analysis and statistical computations"),
        (writer, "Report writing and content creation"),
        (reviewer, "Content review and quality assurance"),
    ],
)

# Complex research query
response = team.run(
    "Analyze the sales data: 1500 units at $25 each, with 15% growth. Write a summary."
)
print(response)
```

### Example 3: Dynamic Subagent Management

```python
from djgent import Agent, MultiAgent

# Create team without initial subagents
team = MultiAgent(name="dynamic-team")

# Add subagents dynamically
tech = Agent.create(name="tech", tools=["django_model"])
team.add_subagent(tech, role="Technical support")

billing = Agent.create(name="billing", tools=["django_model"])
team.add_subagent(billing, role="Billing support")

# Process requests
response = team.run("Help me with Django")

# Remove a subagent
team.remove_subagent("billing")

# List remaining subagents
print(team.list_subagents())
```

### Example 4: Parallel Execution

```python
from djgent import Agent, MultiAgent

# Create specialized agents
python_expert = Agent.create(
    name="python-expert",
    system_prompt="You are a Python expert.",
)

django_expert = Agent.create(
    name="django-expert",
    system_prompt="You are a Django expert.",
)

js_expert = Agent.create(
    name="js-expert",
    system_prompt="You are a JavaScript expert.",
)

team = MultiAgent(
    name="dev-team",
    subagents=[python_expert, django_expert, js_expert],
)

# Get opinions from all experts in parallel
responses = team.run_parallel(
    "What are the best practices for web development?"
)

for name, response in responses.items():
    print(f"\n{name}:")
    print(response)
```

### Example 5: Persistent Memory

```python
from djgent import Agent, MultiAgent

# Create team with database-backed memory
team = MultiAgent(
    name="support-team",
    subagents=[tech_agent, billing_agent],
    memory_backend="database",
)

# Process conversation
response = team.run("I have a billing question")
conv_id = team.get_conversation_id()

# Resume conversation later
team2 = MultiAgent(
    name="support-team",
    subagents=[tech_agent, billing_agent],
    memory_backend="database",
)
# Note: Main agent will have the conversation history
```

## Performance Considerations

### Model Calls

| Scenario | Model Calls | Notes |
|----------|-------------|-------|
| **One-shot request** | ~4 calls | Main agent + subagent invocation |
| **Repeat request** | ~8 calls (4+4) | Subagents are stateless—each invocation is fresh |
| **Multi-domain request** | ~5 calls | Can invoke subagents in parallel |

### Optimization Tips

1. **Use parallel execution** for multi-domain queries:
   ```python
   responses = team.run_parallel("query")
   ```

2. **Minimize subagent count**—only include necessary specialists

3. **Use specific role descriptions** to improve routing accuracy

4. **Enable verbose mode** during development to understand routing:
   ```python
   team = MultiAgent(..., verbose=True)
   ```

## Best Practices

### 1. Clear Role Descriptions

Provide specific, distinct role descriptions for each subagent:

```python
# Good
team = MultiAgent(
    name="support",
    subagents=[
        (tech_agent, "Technical support for Django, Python, and API debugging"),
        (billing_agent, "Billing, payments, refunds, and subscription issues"),
    ],
)

# Bad - too vague
team = MultiAgent(
    name="support",
    subagents=[
        (tech_agent, "Helps users"),
        (billing_agent, "Answers questions"),
    ],
)
```

### 2. Specialized System Prompts

Give each subagent a focused system prompt:

```python
tech_agent = Agent.create(
    name="tech-agent",
    system_prompt="You are a technical support specialist. Focus on debugging code, explaining errors, and providing code examples. Do not handle billing questions.",
)
```

### 3. Context Isolation

Leverage context isolation for efficiency:

```python
# Each subagent only sees its relevant context
tech_agent = Agent.create(
    name="tech-agent",
    system_prompt="You have access to Django model documentation...",  # 2000 tokens
    tools=["django_model"],
)
```

### 4. Main Agent Customization

For complex workflows, provide a custom main agent:

```python
coordinator = Agent.create(
    name="coordinator",
    system_prompt="""You coordinate a support team.
    
    Routing rules:
    1. If user mentions error/bug/code → tech-agent
    2. If user mentions payment/billing/refund → billing-agent
    3. If user mentions shipping/delivery → shipping-agent
    
    Always confirm which specialist you're invoking.""",
)

team = MultiAgent(
    name="support",
    subagents=[tech_agent, billing_agent, shipping_agent],
    main_agent=coordinator,
)
```

## Pattern Comparison

| Pattern | Distributed Dev | Parallelization | Multi-hop | Direct User Interaction |
|---------|----------------|-----------------|-----------|------------------------|
| **Subagents** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

**Subagents pattern is best for:**
- Teams developing agents independently
- Tasks requiring parallel execution
- Multi-step workflows needing multiple specialists
- Direct user interaction scenarios

## Troubleshooting

### Main Agent Not Routing Correctly

**Problem:** Main agent invokes wrong subagent or doesn't invoke any.

**Solutions:**
1. Improve role descriptions to be more specific
2. Add explicit routing instructions in main agent's system prompt
3. Enable verbose mode to see routing decisions
4. Test with simpler queries first

```python
team = MultiAgent(
    name="support",
    subagents=[
        (tech_agent, "EXCLUSIVELY technical questions about code and debugging"),
    ],
    main_agent_config={
        "system_prompt": "ONLY invoke tech-agent for code-related questions.",
    },
    verbose=True,
)
```

### Subagent Not Found

**Problem:** `AgentError: Tool 'x_subagent' not found`

**Solutions:**
1. Verify subagent was added: `print(team.list_subagents())`
2. Check agent name matches: `team.get_subagent("name")`
3. Ensure subagent was added before calling `run()`

### Memory Not Persisting

**Problem:** Conversation history lost between runs.

**Solutions:**
1. Use `memory_backend="database"` instead of default `"memory"`
2. Save conversation ID: `conv_id = team.get_conversation_id()`
3. Resume with same ID: Pass `conversation_id=conv_id` to main agent config

## Related Documentation

- [Agent Guide](../README.md#agent) - Single agent creation and usage
- [ModelQueryTool Guide](MODEL_QUERY_TOOL.md) - Creating database query tools
- [Persistent Memory Guide](PERSISTENT_MEMORY.md) - Conversation storage and management
