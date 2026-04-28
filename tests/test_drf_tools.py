"""Tests for DRF view-backed tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from djgent.tools.base import Tool
from djgent.tools.registry import ToolRegistry

drf = pytest.importorskip("rest_framework")

from rest_framework.response import Response  # noqa: E402
from rest_framework.views import APIView  # noqa: E402
from rest_framework.viewsets import ViewSet  # noqa: E402


@pytest.fixture
def isolated_tool_registry():
    """Temporarily isolate ToolRegistry state."""
    original_tools = ToolRegistry._tools.copy()
    original_sources = ToolRegistry._sources.copy()
    original_discovered = ToolRegistry._discovered
    ToolRegistry.clear()
    try:
        yield
    finally:
        ToolRegistry._tools = original_tools
        ToolRegistry._sources = original_sources
        ToolRegistry._discovered = original_discovered


def test_drf_tool_registers_api_view_tool(isolated_tool_registry) -> None:
    from djgent.tools.drf import drf_tool

    @drf_tool(
        name="echo_api",
        description="Echo through DRF.",
        method="GET",
        path="/api/echo/",
    )
    class EchoView(APIView):
        def get(self, request):
            return Response({"query": request.query_params.get("q")})

    tool = ToolRegistry.get_tool_instance("echo_api")

    assert isinstance(tool, Tool)
    assert tool.name == "echo_api"
    assert tool.description == "Echo through DRF."
    assert tool.run(query_params={"q": "django"}) == {
        "status_code": 200,
        "data": {"query": "django"},
        "success": True,
    }


def test_drf_tool_registers_viewset_action(isolated_tool_registry) -> None:
    from djgent.tools.drf import drf_tool

    @drf_tool(
        name="book_detail_api",
        description="Fetch a book through DRF.",
        method="GET",
        path="/api/books/{pk}/",
        action="retrieve",
    )
    class BookViewSet(ViewSet):
        def retrieve(self, request, pk=None):
            return Response({"pk": pk})

    tool = ToolRegistry.get_tool_instance("book_detail_api")

    assert tool.run(path_kwargs={"pk": "42"}) == {
        "status_code": 200,
        "data": {"pk": "42"},
        "success": True,
    }


def test_drf_tool_forwards_runtime_user(isolated_tool_registry) -> None:
    from djgent.tools.drf import drf_tool

    @drf_tool(
        name="current_user_api",
        description="Return current user.",
        method="GET",
        path="/api/me/",
    )
    class CurrentUserView(APIView):
        def get(self, request):
            return Response({"username": request.user.username})

    @dataclass
    class User:
        username: str = "agent-user"
        is_authenticated: bool = True

    @dataclass
    class DjangoContext:
        user: User
        is_authenticated: bool = True
        request: Any = None

    @dataclass
    class Runtime:
        context: dict[str, Any]

    runtime = Runtime(context={"django": DjangoContext(user=User())})

    tool = ToolRegistry.get_tool_instance("current_user_api")

    assert tool.run(runtime=runtime)["data"] == {"username": "agent-user"}


def test_drf_tool_non_read_methods_default_to_approval(isolated_tool_registry) -> None:
    from djgent.tools.drf import drf_tool

    @drf_tool(
        name="create_book_api",
        description="Create a book through DRF.",
        method="POST",
        path="/api/books/",
    )
    class CreateBookView(APIView):
        def post(self, request):
            return Response(request.data, status=201)

    tool = ToolRegistry.get_tool_instance("create_book_api")

    assert tool.risk_level == "high"
    assert tool.requires_approval is True
    assert tool.run(data={"title": "Django"}) == {
        "status_code": 201,
        "data": {"title": "Django"},
        "success": True,
    }


def test_drf_tool_requires_viewset_action(isolated_tool_registry) -> None:
    from djgent.tools.drf import drf_tool

    with pytest.raises(ValueError, match="action"):

        @drf_tool(
            name="missing_action_api",
            description="Invalid viewset config.",
            method="GET",
            path="/api/books/",
        )
        class InvalidViewSet(ViewSet):
            def list(self, request):
                return Response([])


def test_drf_tool_reports_missing_dependency(monkeypatch) -> None:
    import djgent.tools.drf as drf_tools

    def fake_import_module(name):
        if name == "rest_framework" or name.startswith("rest_framework."):
            raise ImportError("No module named rest_framework")
        return drf_tools.importlib.import_module(name)

    monkeypatch.setattr(drf_tools.importlib, "import_module", fake_import_module)

    with pytest.raises(ImportError, match="djangorestframework"):
        drf_tools._require_drf()
