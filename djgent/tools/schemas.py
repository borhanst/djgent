"""Pydantic schemas for tool input validation."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator


# ============================================================
# Base Tool Schemas
# ============================================================


class ToolExecutionContext(BaseModel):
    """Context for tool execution."""
    agent_name: str = Field(description="Name of the agent executing the tool")
    thread_id: str = Field(description="Thread ID for the conversation")
    user_id: Optional[int] = Field(default=None, description="ID of the user")
    session_id: Optional[str] = Field(default=None, description="Session ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class ToolExecutionInput(BaseModel):
    """Base input for tool execution."""
    tool_name: str = Field(description="Name of the tool to execute")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    context: Optional[ToolExecutionContext] = Field(default=None, description="Execution context")


# ============================================================
# Retrieval Tool Schemas
# ============================================================


class KnowledgeRetrievalInput(BaseModel):
    """Input schema for knowledge retrieval tool."""
    query: str = Field(min_length=1, max_length=1000, description="Search query")
    limit: int = Field(default=5, ge=1, le=50, description="Maximum number of results")
    namespace: str = Field(default="default", description="Knowledge namespace to search")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Optional filters")

    @field_validator('query')
    @classmethod
    def query_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Query cannot be empty or whitespace only")
        return v.strip()


class KnowledgeIngestInput(BaseModel):
    """Input schema for knowledge ingestion tool."""
    title: str = Field(min_length=1, max_length=500, description="Document title")
    content: str = Field(min_length=1, max_length=100000, description="Document content")
    namespace: str = Field(default="default", description="Knowledge namespace")
    source: str = Field(default="", description="Source of the document")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")

    @field_validator('title')
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Title cannot be empty or whitespace only")
        return v.strip()


# ============================================================
# Built-in Tool Schemas
# ============================================================


class CalculatorInput(BaseModel):
    """Input schema for calculator tool."""
    expression: str = Field(min_length=1, max_length=500, description="Mathematical expression")

    @field_validator('expression')
    @classmethod
    def validate_expression(cls, v: str) -> str:
        v = v.strip()
        # Basic validation for safe characters
        allowed = set('0123456789+-*/.() %')
        if not all(c in allowed or c.isspace() for c in v):
            raise ValueError("Expression contains invalid characters")
        return v


class SearchInput(BaseModel):
    """Input schema for search tool."""
    query: str = Field(min_length=1, max_length=500, description="Search query")
    num_results: int = Field(default=5, ge=1, le=20, description="Number of results")
    source: Optional[str] = Field(default=None, description="Search source")


class WeatherInput(BaseModel):
    """Input schema for weather tool."""
    location: str = Field(min_length=1, max_length=200, description="Location for weather")
    units: str = Field(default="metric", description="Temperature units (metric/imperial)")
    
    @field_validator('units')
    @classmethod
    def validate_units(cls, v: str) -> str:
        if v not in ('metric', 'imperial'):
            raise ValueError("Units must be 'metric' or 'imperial'")
        return v


class DatetimeInput(BaseModel):
    """Input schema for datetime tool."""
    timezone: Optional[str] = Field(default=None, description="Timezone (IANA format)")
    format: Optional[str] = Field(default=None, description="Output format")


class HttpRequestInput(BaseModel):
    """Input schema for HTTP request tool."""
    url: str = Field(description="URL to request")
    method: str = Field(default="GET", description="HTTP method")
    headers: Optional[Dict[str, str]] = Field(default=None, description="HTTP headers")
    body: Optional[Any] = Field(default=None, description="Request body")
    timeout: int = Field(default=30, ge=1, le=300, description="Request timeout in seconds")

    @field_validator('method')
    @classmethod
    def validate_method(cls, v: str) -> str:
        allowed = {'GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'}
        if v.upper() not in allowed:
            raise ValueError(f"Method must be one of {allowed}")
        return v.upper()

    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(('http://', 'https://')):
            raise ValueError("URL must start with http:// or https://")
        return v


# ============================================================
# Django Model Tool Schemas
# ============================================================


class DjangoModelQueryInput(BaseModel):
    """Input schema for Django model query tool."""
    model_name: str = Field(description="Django model name")
    operation: str = Field(description="Operation: create, read, update, delete, list")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Query filters")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Data for create/update")
    limit: Optional[int] = Field(default=None, ge=1, le=1000, description="Result limit")
    order_by: Optional[List[str]] = Field(default=None, description="Order by fields")

    @field_validator('operation')
    @classmethod
    def validate_operation(cls, v: str) -> str:
        allowed = {'create', 'read', 'update', 'delete', 'list'}
        if v.lower() not in allowed:
            raise ValueError(f"Operation must be one of {allowed}")
        return v.lower()


class DjangoAuthInput(BaseModel):
    """Input schema for Django auth tool."""
    operation: str = Field(description="Auth operation")
    username: Optional[str] = Field(default=None, description="Username")
    email: Optional[str] = Field(default=None, description="Email address")
    password: Optional[str] = Field(default=None, description="Password")
    user_data: Optional[Dict[str, Any]] = Field(default=None, description="User data for creation")

    @field_validator('operation')
    @classmethod
    def validate_operation(cls, v: str) -> str:
        allowed = {'login', 'logout', 'check', 'create_user', 'change_password'}
        if v.lower() not in allowed:
            raise ValueError(f"Operation must be one of {allowed}")
        return v.lower()


# ============================================================
# Memory Tool Schemas
# ============================================================


class MemoryStoreInput(BaseModel):
    """Input schema for memory store tool."""
    operation: str = Field(description="Operation: store, retrieve, search, delete")
    key: str = Field(min_length=1, max_length=200, description="Memory key")
    value: Optional[Any] = Field(default=None, description="Value to store")
    namespace: str = Field(default="default", description="Memory namespace")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Search filters")

    @field_validator('operation')
    @classmethod
    def validate_operation(cls, v: str) -> str:
        allowed = {'store', 'retrieve', 'search', 'delete', 'list'}
        if v.lower() not in allowed:
            raise ValueError(f"Operation must be one of {allowed}")
        return v.lower()


# ============================================================
# Agent Execution Schemas
# ============================================================


class AgentRunInput(BaseModel):
    """Input schema for agent run."""
    message: str = Field(min_length=1, description="Input message to agent")
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")
    stream: bool = Field(default=False, description="Enable streaming")


class AgentConfigInput(BaseModel):
    """Input schema for agent configuration."""
    name: str = Field(min_length=1, max_length=100, description="Agent name")
    llm_provider: str = Field(description="LLM provider name")
    llm_model: Optional[str] = Field(default=None, description="LLM model name")
    tools: List[str] = Field(default_factory=list, description="Tool names")
    system_prompt: Optional[str] = Field(default=None, description="System prompt")
    memory_enabled: bool = Field(default=True, description="Enable memory")
    middleware: List[str] = Field(default_factory=list, description="Middleware names")


# ============================================================
# Validation Utilities
# ============================================================


def validate_tool_input(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate tool input against known schemas.
    
    Args:
        tool_name: Name of the tool
        arguments: Tool arguments to validate
        
    Returns:
        Validated arguments
        
    Raises:
        ValueError: If validation fails
    """
    schema_map = {
        "knowledge_retrieval": KnowledgeRetrievalInput,
        "knowledge_ingest": KnowledgeIngestInput,
        "calculator": CalculatorInput,
        "search": SearchInput,
        "weather": WeatherInput,
        "datetime": DatetimeInput,
        "http_request": HttpRequestInput,
        "django_model": DjangoModelQueryInput,
        "django_auth": DjangoAuthInput,
        "memory_store": MemoryStoreInput,
    }
    
    schema_class = schema_map.get(tool_name)
    if schema_class:
        validated = schema_class(**arguments)
        return validated.model_dump()
    
    # Return unchanged if no schema found
    return arguments
