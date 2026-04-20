# MCP Integration Guide

## Overview

Djgent can load tools from Model Context Protocol (MCP) servers through
`langchain-mcp-adapters`.

At agent creation time:

- Djgent resolves your normal tool list
- Djgent calls `load_mcp_tools(mcp_servers)`
- returned MCP tools are appended to the agent's tools

This lets an agent use local or remote MCP servers alongside built-in Djgent tools.

## Installation

Install the optional MCP extra:

```bash
uv add djgent[mcp]
```

Or with pip:

```bash
pip install "djgent[mcp]"
```

## Quick Start

Pass MCP server definitions to `Agent.create(...)`:

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

response = agent.run("List the files in this project and summarize the structure.")
print(response)
```

`mcp_servers` is forwarded directly to `langchain_mcp_adapters.client.MultiServerMCPClient`.
That means the exact server config shape should match the adapter you have installed.

## How Loading Works

Djgent uses this flow internally:

```python
from djgent.runtime.mcp import load_mcp_tools

tools = load_mcp_tools(mcp_servers)
```

`load_mcp_tools(...)`:

- creates a `MultiServerMCPClient`
- prefers `client.get_tools()` when available
- falls back to `client.list_tools()`
- raises `MCPIntegrationError` if the client implementation is unsupported

## Combining MCP and Djgent Tools

You can mix MCP tools with built-in or custom Djgent tools:

```python
agent = Agent.create(
    name="workspace-assistant",
    tools=["calculator", "datetime"],
    mcp_servers={
        "filesystem": {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
        }
    },
)
```

Tool order is:

1. explicit `tools=...`
2. auto-loaded registry tools when `auto_load_tools=True`
3. MCP tools from `mcp_servers`

## Error Handling

If MCP support is not installed, Djgent raises:

```python
from djgent.runtime.mcp import MCPIntegrationError
```

Common causes:

- `langchain-mcp-adapters` is not installed
- the installed adapter client does not expose `get_tools()` or `list_tools()`
- the server definition is invalid for the adapter/client you are using

Example defensive setup:

```python
from djgent import Agent
from djgent.runtime.mcp import MCPIntegrationError

try:
    agent = Agent.create(
        name="assistant",
        mcp_servers={
            "filesystem": {
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
            }
        },
    )
except MCPIntegrationError as exc:
    print(f"MCP setup failed: {exc}")
```

## When to Use MCP

MCP is a good fit when:

- you want to reuse an existing MCP tool ecosystem
- tools should run out-of-process instead of in Django
- you need filesystem, browser, editor, or external service integrations already exposed by MCP servers

Djgent-native tools are still a better fit when:

- you need tight Django ORM access
- tool behavior depends on app-local Python code
- you want approval metadata via Djgent `Tool` subclasses

## Related Docs

- [README.md](../README.md)
- [docs/MIDDLEWARE.md](MIDDLEWARE.md)
