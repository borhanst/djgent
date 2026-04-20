"""Agent runner helpers for integrating Django requests with LangChain agents."""

from typing import Any, Dict, Optional

from django.http import HttpRequest

from djgent.utils.django_context import DjangoContext


def run_agent_with_request(
    agent: Any,
    request: HttpRequest,
    input: str,
    context: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Run a LangChain agent with Django request context.
    
    This helper injects the Django request and user information into the
    LangChain ToolRuntime context, allowing tools to access request.user
    for authentication checks.
    
    Args:
        agent: LangChain AgentExecutor or compiled graph
        request: Django HttpRequest object
        input: User input message
        context: Additional context to merge with Django context
        **kwargs: Additional arguments passed to agent.invoke()
        
    Returns:
        Agent response dictionary
        
    Example:
        In a Django view:
        
        from djgent.utils.agent_runner import run_agent_with_request
        from django.http import JsonResponse
        from django.contrib.auth.decorators import login_required
        
        @login_required
        def agent_chat(request):
            agent = Agent.create(name="assistant", auto_load_tools=True)
            response = run_agent_with_request(
                agent, 
                request, 
                request.POST.get('message', '')
            )
            return JsonResponse(response)
            
        For anonymous access (limited functionality):
        
        def public_chat(request):
            agent = Agent.create(name="assistant", auto_load_tools=True)
            response = run_agent_with_request(
                agent, 
                request, 
                request.POST.get('message', '')
            )
            # Anonymous users can use: list_models, get_schema, list_permissions
            # Anonymous users cannot: query data, get_user details
            return JsonResponse(response)
    """
    # Build Django context from request
    django_ctx = DjangoContext.from_request(request)
    
    # Prepare context for agent
    agent_context = {"django": django_ctx}
    
    # Merge with additional context
    if context:
        agent_context.update(context)
    
    # Build messages for agent
    from langchain_core.messages import HumanMessage
    
    messages = [HumanMessage(content=input)]
    
    # Invoke agent with context
    result = agent.invoke(
        {"messages": messages},
        context=agent_context,
        **kwargs
    )
    
    return result


def run_tool_with_request(
    tool: Any,
    request: HttpRequest,
    action: str,
    **kwargs: Any,
) -> Any:
    """
    Run a tool directly with Django request context.
    
    This is useful when you want to call a specific tool without
    going through an agent.
    
    Args:
        tool: Tool instance (e.g., DjangoModelQueryTool)
        request: Django HttpRequest object
        action: Tool action to execute
        **kwargs: Additional arguments for the tool
        
    Returns:
        Tool result
        
    Example:
        from djgent.tools.registry import ToolRegistry
        from djgent.utils.agent_runner import run_tool_with_request
        
        tool = ToolRegistry.get_tool_instance("django_model")
        
        # Anonymous user - can list models
        result = run_tool_with_request(tool, request, action="list_models")
        
        # Authenticated user - can query data
        result = run_tool_with_request(tool, request, action="query", model="auth.User")
    """
    # Build Django context from request
    django_ctx = DjangoContext.from_request(request)
    
    # Create a minimal runtime-like context
    class SimpleRuntime:
        def __init__(self, context):
            self.context = context
    
    runtime = SimpleRuntime(context={"django": django_ctx})
    
    # Call tool with runtime
    return tool._run(action=action, runtime=runtime, **kwargs)


def check_user_access(request: HttpRequest, required_action: str, tool_name: str) -> bool:
    """
    Check if the current user has access to a specific tool action.
    
    Args:
        request: Django HttpRequest object
        required_action: The action being requested
        tool_name: The tool name (e.g., "django_model", "django_auth")
        
    Returns:
        True if user has access, False otherwise
        
    Example:
        if not check_user_access(request, "query", "django_model"):
            return JsonResponse({"error": "Authentication required"})
    """
    from django.conf import settings
    
    user = getattr(request, 'user', None)
    is_authenticated = user.is_authenticated if user else False
    
    # If user is authenticated, allow all actions
    if is_authenticated:
        return True
    
    # Check auth requirements from settings
    djgent_settings = getattr(settings, "DJGENT", {})
    auth_requirements = djgent_settings.get("AUTH_REQUIREMENTS", {})
    tool_config = auth_requirements.get(tool_name, {})
    
    # Check if action is in allow_anonymous list
    allow_anonymous = tool_config.get("allow_anonymous", [])
    if required_action in allow_anonymous:
        return True
    
    # Check if action is in require_auth list
    require_auth = tool_config.get("require_auth_for", [])
    if required_action in require_auth:
        return False
    
    # Default: allow anonymous (backward compatibility)
    return True
