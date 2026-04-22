"""Optional MCP integration helpers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class MCPIntegrationError(RuntimeError):
    """Raised when optional MCP support is not available."""


def load_mcp_tools(
    servers: Dict[str, Dict[str, Any]],
    *,
    client_class: Optional[Any] = None,
) -> List[Any]:
    """
    Load tools from MCP servers when langchain-mcp-adapters is installed.
    """
    client_class = client_class or _resolve_client_class()
    client = client_class(servers)

    if hasattr(client, "get_tools"):
        tools = client.get_tools()
    elif hasattr(client, "list_tools"):
        tools = client.list_tools()
    else:
        raise MCPIntegrationError("Unsupported MCP client implementation.")

    return list(tools)


def _resolve_client_class() -> Any:
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except Exception as exc:
        raise MCPIntegrationError(
            "Install 'langchain-mcp-adapters' to enable MCP tool loading."
        ) from exc

    return MultiServerMCPClient
