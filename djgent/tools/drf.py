"""DRF view-backed tools for djgent."""

from __future__ import annotations

import importlib
import json
from typing import Any, Callable, Dict, Optional, TypeVar

from django.http import HttpResponse

from djgent.tools.base import Tool

ViewType = TypeVar("ViewType", bound=type)

READ_ONLY_METHODS = {"GET", "HEAD", "OPTIONS"}
SUPPORTED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
MISSING_DRF_MESSAGE = (
    "DRF view tools require djangorestframework. Install it with "
    "`uv sync --extra drf` or `pip install djangorestframework`."
)


def _require_drf() -> tuple[Any, Any, Any]:
    """Import DRF objects lazily so base djgent imports do not require DRF."""
    try:
        views = importlib.import_module("rest_framework.views")
        viewsets = importlib.import_module("rest_framework.viewsets")
        test = importlib.import_module("rest_framework.test")
    except ImportError as exc:
        raise ImportError(MISSING_DRF_MESSAGE) from exc

    return views.APIView, viewsets.ViewSetMixin, test


class DRFViewTool(Tool):
    """Wrap a single DRF APIView or ViewSet action as a Djgent tool."""

    def __init__(
        self,
        *,
        name: str,
        description: str,
        view_cls: type,
        method: str,
        path: str,
        action: Optional[str] = None,
        risk_level: Optional[str] = None,
        requires_approval: Optional[bool] = None,
        approval_reason: str = "",
    ):
        APIView, ViewSetMixin, _ = _require_drf()

        method = method.upper()
        if method not in SUPPORTED_METHODS:
            raise ValueError(
                f"Unsupported DRF tool method '{method}'. "
                f"Supported methods: {sorted(SUPPORTED_METHODS)}"
            )
        if not issubclass(view_cls, APIView):
            raise ValueError("drf_tool can only wrap DRF APIView or ViewSet classes.")

        is_viewset = issubclass(view_cls, ViewSetMixin)
        if is_viewset and not action:
            raise ValueError("drf_tool requires an action when wrapping a DRF ViewSet.")

        default_risk = "low" if method in READ_ONLY_METHODS else "high"
        default_requires_approval = method not in READ_ONLY_METHODS

        super().__init__(
            name=name,
            description=description,
            view_cls=view_cls,
            method=method,
            path=path,
            action=action,
            risk_level=risk_level or default_risk,
            requires_approval=(
                default_requires_approval
                if requires_approval is None
                else bool(requires_approval)
            ),
            approval_reason=approval_reason,
        )
        self._is_viewset = is_viewset

    def _run(
        self,
        query_params: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        path_kwargs: Optional[Dict[str, Any]] = None,
        runtime: Any = None,
    ) -> Dict[str, Any]:
        """Execute the wrapped DRF view in-process."""
        _, _, drf_test = _require_drf()

        factory = drf_test.APIRequestFactory()
        request = self._build_request(factory, query_params=query_params, data=data)
        self._authenticate_request(request, runtime)

        view = self._build_view()
        response = view(request, **(path_kwargs or {}))
        return self._format_response(response)

    def _build_request(
        self,
        factory: Any,
        *,
        query_params: Optional[Dict[str, Any]],
        data: Optional[Any],
    ) -> Any:
        method = self.method.lower()
        request_data = query_params if self.method in READ_ONLY_METHODS else data
        request_builder = getattr(factory, method)
        if self.method in READ_ONLY_METHODS:
            return request_builder(self.path, data=request_data or {})
        return request_builder(self.path, data=request_data, format="json")

    def _authenticate_request(self, request: Any, runtime: Any = None) -> None:
        django_context = self._get_django_context(runtime)
        if django_context is None:
            return

        user = getattr(django_context, "user", None)
        if user is None:
            source_request = getattr(django_context, "request", None)
            user = getattr(source_request, "user", None)
        if user is None:
            return

        _, _, drf_test = _require_drf()
        drf_test.force_authenticate(request, user=user)

    def _build_view(self) -> Callable[..., Any]:
        if self._is_viewset:
            return self.view_cls.as_view({self.method.lower(): self.action})
        return self.view_cls.as_view()

    def _format_response(self, response: Any) -> Dict[str, Any]:
        if hasattr(response, "render") and not getattr(response, "_is_rendered", False):
            response.render()

        data: Any
        if hasattr(response, "data"):
            data = response.data
        elif isinstance(response, HttpResponse):
            data = response.content.decode(response.charset or "utf-8")
            content_type = response.headers.get("Content-Type", "")
            if "json" in content_type:
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    pass
        else:
            data = response

        status_code = getattr(response, "status_code", 200)
        return {
            "status_code": status_code,
            "data": data,
            "success": status_code < 400,
        }


def drf_tool(
    *,
    name: str,
    description: str,
    method: str,
    path: str,
    action: Optional[str] = None,
    risk_level: Optional[str] = None,
    requires_approval: Optional[bool] = None,
    approval_reason: str = "",
) -> Callable[[ViewType], ViewType]:
    """Register a DRF APIView/ViewSet endpoint as a Djgent tool."""
    from djgent.tools.registry import ToolRegistry

    def decorator(view_cls: ViewType) -> ViewType:
        tool = DRFViewTool(
            name=name,
            description=description,
            view_cls=view_cls,
            method=method,
            path=path,
            action=action,
            risk_level=risk_level,
            requires_approval=requires_approval,
            approval_reason=approval_reason,
        )
        ToolRegistry.register(name=name)(tool)
        return view_cls

    return decorator
