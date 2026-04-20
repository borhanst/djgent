"""Base tool class for djgent."""

import inspect
import json
from abc import ABC, abstractmethod
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Union

from django.db.models import Model, QuerySet
from django.utils.encoding import force_str
from django.utils.functional import Promise

from djgent.serializers import (
    is_pydantic_model_class,
    serialize_with_pydantic_schema,
)
from djgent.utils.model_introspection import (
    _apply_search as model_search_util,
)
from djgent.utils.model_introspection import (
    _model_to_dict as model_to_dict_util,
)


class DjangoModelJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles Django lazy translation objects."""

    def default(self, obj):
        if isinstance(obj, Promise):
            return force_str(obj)
        return super().default(obj)


class Tool(ABC):
    """
    Abstract base class for all tools.

    Tools are functions that agents can use to interact with the world.
    Each tool must have a name, description, and implement the _run method.
    
    Supports LangChain's ToolRuntime for accessing Django context:
    
    Example:
        from langchain.tools import ToolRuntime
        
        class MyTool(Tool):
            def _run(self, arg: str, runtime: Optional[ToolRuntime] = None):
                # Get Django context
                django_ctx = self._get_django_context(runtime)
                if django_ctx and django_ctx.is_authenticated:
                    # User is logged in
                    ...
    """

    name: str
    description: str
    args_schema: Optional[dict] = None
    risk_level: str = "low"
    requires_approval: bool = False
    approval_reason: str = ""

    def __init__(self, **kwargs: Any):
        """Initialize the tool with optional configuration."""
        for key, value in kwargs.items():
            setattr(self, key, value)

    @abstractmethod
    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """
        Execute the tool.

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments (can include runtime: ToolRuntime)

        Returns:
            The result of the tool execution
        """
        pass

    def _get_django_context(self, runtime: Any = None) -> Optional[Any]:
        """
        Extract Django context from ToolRuntime.
        
        Args:
            runtime: LangChain ToolRuntime object (optional)
            
        Returns:
            DjangoContext instance or None if not available
            
        Example:
            def _run(self, query: str, runtime: Optional[ToolRuntime] = None):
                django_ctx = self._get_django_context(runtime)
                if django_ctx and django_ctx.is_authenticated:
                    user = django_ctx.user
        """
        if runtime is None:
            return None

        try:
            context = getattr(runtime, 'context', None)
            if context and isinstance(context, dict):
                return context.get("django")
        except Exception:
            pass

        return None

    def _check_authenticated(self, runtime: Any = None) -> bool:
        """
        Check if the current user is authenticated.
        
        Args:
            runtime: LangChain ToolRuntime object (optional)
            
        Returns:
            True if user is authenticated, False otherwise
        """
        django_ctx = self._get_django_context(runtime)
        if django_ctx:
            return getattr(django_ctx, 'is_authenticated', False)
        return False

    def _get_user(self, runtime: Any = None) -> Optional[Any]:
        """
        Get the current user from Django context.
        
        Args:
            runtime: LangChain ToolRuntime object (optional)
            
        Returns:
            Django User object or None if not authenticated
        """
        django_ctx = self._get_django_context(runtime)
        if django_ctx and getattr(django_ctx, 'is_authenticated', False):
            return getattr(django_ctx, 'user', None)
        return None

    def run(self, *args: Any, **kwargs: Any) -> Any:
        """
        Public method to run the tool with error handling.

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            The result of the tool execution
        """
        try:
            return self._run(*args, **kwargs)
        except Exception as e:
            from djgent.exceptions import ToolError

            raise ToolError(f"Error executing tool '{self.name}': {str(e)}") from e

    def get_tool_config(self) -> Dict[str, Any]:
        """Return metadata used by middleware and approval workflows."""
        return {
            "name": self.name,
            "risk_level": getattr(self, "risk_level", "low"),
            "requires_approval": bool(getattr(self, "requires_approval", False)),
            "reason": getattr(self, "approval_reason", ""),
        }

    def to_langchain(
        self,
        *,
        before_tool: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        after_tool: Optional[Callable[[str, Any], Any]] = None,
    ):
        """
        Convert this tool to a LangChain compatible tool.

        Returns:
            A LangChain StructuredTool instance
        """
        from langchain_core.tools import StructuredTool

        signature = inspect.signature(self._run)

        @wraps(self._run)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            bound = signature.bind_partial(*args, **kwargs)
            arguments = dict(bound.arguments)

            if before_tool:
                before_tool(self.name, arguments)

            result = self._run(*args, **kwargs)

            if after_tool:
                result = after_tool(self.name, result)

            return result

        wrapped.__signature__ = signature  # type: ignore[attr-defined]

        return StructuredTool.from_function(
            func=wrapped,
            name=self.name,
            description=self.description,
            args_schema=self.args_schema,
        )

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Allow the tool to be called directly."""
        return self.run(*args, **kwargs)


class ModelQueryTool(Tool, ABC):
    """
    Base class for creating model query tools.

    Provides a ready-to-use query interface for Django models with support for:
    - Listing objects with pagination
    - Filtering with Django-style filters
    - Getting single objects by field value (default: primary key)
    - Searching across text fields
    - Authentication-based access control
    - Dynamic queryset customization via get_queryset()

    Subclass and configure:
    ```python
    from djgent.tools.base import ModelQueryTool
    from myapp.models import Product, User

    class ProductQueryTool(ModelQueryTool):
        name = "product_query"
        description = "Query products from database"
        queryset = Product.objects.filter(active=True)
        exclude_fields = ["cost_price", "supplier_secret"]
        require_auth = False
        max_results = 100
        default_limit = 10

    # Query by slug instead of primary key
    class ProductQueryTool(ModelQueryTool):
        name = "product_query"
        queryset = Product.objects.all()
        query_field = "slug"  # Now get_by_id uses slug instead of pk

    # Or override get_queryset() for dynamic querysets:
    class UserQueryTool(ModelQueryTool):
        name = "user_query"
        description = "Query users"
        queryset = None  # Will use get_queryset()
        require_auth = True
        query_field = "username"  # Query users by username

        def get_queryset(self, runtime=None, user=None, **kwargs):
            # Dynamic queryset based on user/request
            if user and user.is_staff:
                return User.objects.all()
            return User.objects.filter(is_active=True)
    ```

    Usage:
    ```python
    tool = ProductQueryTool()

    # List objects
    tool._run(action="list", limit=20)

    # Filter objects
    tool._run(action="query", filters={"status": "active", "category": "electronics"})

    # Get by ID (uses query_field, default: "pk")
    tool._run(action="get_by_id", id=42)
    tool._run(action="get_by_id", id="product-slug", query_field="slug")  # Override

    # Search
    tool._run(action="search", search="laptop", search_fields=["name", "description"])
    ```
    """

    # ===== Configuration Class Variables =====

    # QuerySet to query (can be None if using get_queryset())
    queryset: Optional[QuerySet] = None

    # Available actions: list, query, get_by_id, search, count
    allowed_actions: List[str] = ["list", "query", "get_by_id", "search", "count"]

    # Fields to exclude from results (e.g., sensitive fields)
    exclude_fields: List[str] = []

    # Maximum results allowed
    max_results: int = 100

    # Default limit for queries
    default_limit: int = 10

    # Require authentication for all actions
    require_auth: bool = True

    # Fields to search when action="search" (None = all text fields)
    search_fields: Optional[List[str]] = None

    # Field to use for get_by_id action (default: "pk")
    query_field: str = "pk"

    # Optional schema used to shape serialized output
    schema: Optional[Any] = None

    # ===== Main Entry Point =====

    def _run(
        self,
        action: str = "list",
        filters: Optional[Dict[str, Any]] = None,
        id: Optional[Union[int, str]] = None,
        search: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
        fields: Optional[List[str]] = None,
        order_by: Optional[List[str]] = None,
        search_fields: Optional[List[str]] = None,
        query_field: Optional[str] = None,
        runtime: Optional[Any] = None,
        **kwargs: Any,
    ) -> str:
        """
        Execute the model query action.

        Args:
            action: Action to perform (list, query, get_by_id, search, count)
            filters: Django-style filters dict (e.g., {"status": "active"})
            id: Object ID (for get_by_id action)
            search: Search term (for search action)
            limit: Maximum results (default: 10, max: max_results)
            offset: Results offset for pagination
            fields: Specific fields to return (optional)
            order_by: Fields to order by (e.g., ["-created_at", "name"])
            search_fields: Fields to search (overrides class search_fields)
            query_field: Field to query by for get_by_id (default: "pk" or class query_field)
            runtime: LangChain ToolRuntime (provides Django context)
            **kwargs: Additional arguments passed to get_queryset()

        Returns:
            JSON-formatted string with results
        """
        # Validate action
        if action not in self.allowed_actions:
            return self._error_response(
                f"Invalid action '{action}'. Allowed actions: {self.allowed_actions}"
            )

        # Check authentication if required
        if self.require_auth and not self._check_authenticated(runtime):
            return self._error_response(
                "Authentication required. Please log in to access this feature."
            )

        # Get user and queryset
        user = self._get_user(runtime)
        queryset = self.get_queryset(runtime=runtime, user=user, **kwargs)

        # Enforce limits
        limit = min(limit, self.max_results)

        try:
            if action == "list":
                return self._list(
                    queryset=queryset,
                    limit=limit,
                    offset=offset,
                    fields=fields,
                    order_by=order_by,
                    runtime=runtime,
                )
            elif action == "query":
                return self._query(
                    queryset=queryset,
                    filters=filters,
                    limit=limit,
                    offset=offset,
                    fields=fields,
                    order_by=order_by,
                    runtime=runtime,
                )
            elif action == "get_by_id":
                return self._get_by_id(
                    queryset=queryset,
                    id=id,
                    fields=fields,
                    query_field=query_field,
                    runtime=runtime,
                )
            elif action == "search":
                return self._search(
                    queryset=queryset,
                    search=search,
                    limit=limit,
                    fields=fields,
                    search_fields=search_fields or self.search_fields,
                    runtime=runtime,
                )
            elif action == "count":
                return self._count(
                    queryset=queryset,
                    filters=filters,
                    runtime=runtime,
                )
        except Exception as e:
            return self._error_response(str(e))

        return self._error_response(f"Unknown action: {action}")

    # ===== Customizable Methods =====

    def get_queryset(
        self,
        runtime: Optional[Any] = None,
        user: Optional[Any] = None,
        **kwargs: Any,
    ) -> QuerySet:
        """
        Get the queryset to query.

        Override this method to customize the queryset based on the user or request.

        Args:
            runtime: LangChain ToolRuntime (contains Django context)
            user: Current user (None if anonymous)
            **kwargs: Additional arguments from _run()

        Returns:
            Django QuerySet to query

        Example:
            def get_queryset(self, runtime=None, user=None, **kwargs):
                if user and user.is_staff:
                    return MyModel.objects.all()
                return MyModel.objects.filter(public=True)
        """
        if self.queryset is not None:
            return self.queryset

        # If no queryset is set, raise an error
        raise ValueError(
            f"No queryset defined for {self.__class__.__name__}. "
            "Set the 'queryset' class variable or override 'get_queryset()'."
        )

    # ===== Action Methods =====

    def _list(
        self,
        queryset: QuerySet,
        limit: int = 10,
        offset: int = 0,
        fields: Optional[List[str]] = None,
        order_by: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> str:
        """
        List objects with pagination.

        Args:
            queryset: Base queryset
            limit: Maximum results
            offset: Results offset
            fields: Specific fields to return
            order_by: Fields to order by

        Returns:
            JSON-formatted string with results
        """
        # Apply ordering
        if order_by:
            queryset = queryset.order_by(*order_by)

        # Get total count
        total_count = queryset.count()

        # Apply pagination
        queryset = queryset[offset : offset + limit]

        # Convert to dict list
        data = self._queryset_to_dict(queryset, fields=fields)

        return self._success_response(
            action="list",
            count=len(data),
            total_count=total_count,
            limit=limit,
            offset=offset,
            data=data,
        )

    def _query(
        self,
        queryset: QuerySet,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        offset: int = 0,
        fields: Optional[List[str]] = None,
        order_by: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> str:
        """
        Filter and retrieve objects.

        Args:
            queryset: Base queryset
            filters: Django-style filters dict
            limit: Maximum results
            offset: Results offset
            fields: Specific fields to return
            order_by: Fields to order by

        Returns:
            JSON-formatted string with results
        """
        # Apply filters
        if filters:
            queryset = queryset.filter(**filters)

        # Apply ordering
        if order_by:
            queryset = queryset.order_by(*order_by)

        # Get total count
        total_count = queryset.count()

        # Apply pagination
        queryset = queryset[offset : offset + limit]

        # Convert to dict list
        data = self._queryset_to_dict(queryset, fields=fields)

        return self._success_response(
            action="query",
            count=len(data),
            total_count=total_count,
            limit=limit,
            offset=offset,
            filters=filters,
            data=data,
        )

    def _get_by_id(
        self,
        queryset: QuerySet,
        id: Optional[Union[int, str]] = None,
        fields: Optional[List[str]] = None,
        query_field: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Get a single object by field value.

        Args:
            queryset: Base queryset
            id: Object identifier (value of query_field)
            fields: Specific fields to return
            query_field: Field to query by (default: "pk" or class query_field)

        Returns:
            JSON-formatted string with object data
        """
        if id is None:
            return self._error_response("ID is required for get_by_id action")

        # Use provided query_field, or class default, or fallback to "pk"
        field = query_field or self.query_field or "pk"

        try:
            # Build the filter dynamically
            filter_kwargs = {field: id}
            obj = queryset.get(**filter_kwargs)
        except queryset.model.DoesNotExist:
            return self._error_response(
                f"Object with {field}='{id}' not found in {queryset.model.__name__}"
            )
        except Exception as e:
            return self._error_response(f"Error querying by {field}: {str(e)}")

        # Convert to dict
        data = self._model_to_dict(obj, fields=fields)

        return self._success_response(
            action="get_by_id",
            id=id,
            query_field=field,
            model=queryset.model.__name__,
            data=data,
        )

    def _search(
        self,
        queryset: QuerySet,
        search: Optional[str] = None,
        limit: int = 10,
        fields: Optional[List[str]] = None,
        search_fields: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> str:
        """
        Search across model fields.

        Args:
            queryset: Base queryset
            search: Search term
            limit: Maximum results
            fields: Specific fields to return
            search_fields: Fields to search (None = all text fields)

        Returns:
            JSON-formatted string with results
        """
        if not search:
            return self._error_response("Search term is required for search action")

        # Apply search using shared utility
        queryset = model_search_util(
            queryset, search, search_fields, queryset.model
        )

        # Get total count
        total_count = queryset.count()

        # Apply limit
        queryset = queryset[:limit]

        # Convert to dict list
        data = self._queryset_to_dict(queryset, fields=fields)

        return self._success_response(
            action="search",
            count=len(data),
            total_count=total_count,
            search_term=search,
            search_fields=search_fields,
            data=data,
        )

    def _count(
        self,
        queryset: QuerySet,
        filters: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """
        Get count of objects with optional filters.

        Args:
            queryset: Base queryset
            filters: Django-style filters dict

        Returns:
            JSON-formatted string with count
        """
        if filters:
            queryset = queryset.filter(**filters)

        return self._success_response(
            action="count",
            count=queryset.count(),
            filters=filters,
        )

    # ===== Helper Methods =====

    def _queryset_to_dict(
        self,
        queryset: QuerySet,
        fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Convert a queryset to a list of dicts."""
        return [
            self._model_to_dict(obj, fields=fields) for obj in queryset
        ]

    def _model_to_dict(
        self,
        obj: Model,
        fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Convert a model instance to a dict.

        Args:
            obj: Model instance
            fields: Specific fields to include (None = all except excluded)

        Returns:
            Dict representation of the model
        """
        if self.schema is not None:
            if not is_pydantic_model_class(self.schema):
                raise ValueError(
                    "schema must be a Pydantic BaseModel subclass. "
                    "Install pydantic and set a valid schema class."
                )

            return serialize_with_pydantic_schema(
                obj,
                self.schema,
                fields=fields,
                exclude_fields=self.exclude_fields,
            )

        return model_to_dict_util(
            obj,
            exclude_fields=self.exclude_fields,
            fields=fields,
        )

    def _success_response(self, **kwargs: Any) -> str:
        """Format a success response."""
        response = {"success": True, **kwargs}
        return json.dumps(response, indent=2, cls=DjangoModelJSONEncoder)

    def _error_response(self, error: str) -> str:
        """Format an error response."""
        return json.dumps(
            {"success": False, "error": error},
            indent=2,
            cls=DjangoModelJSONEncoder,
        )
