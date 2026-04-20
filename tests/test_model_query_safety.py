import json
from dataclasses import dataclass
from typing import Any, Optional

import pytest
from pydantic import BaseModel

from demo_app.models import Author, Book
from djgent.tools.base import ModelQueryTool
from djgent.tools.builtin import DjangoModelQueryTool
from djgent.tools.schemas import DjangoModelQueryInput, validate_tool_input


@dataclass
class MockUser:
    id: int = 1
    username: str = "agent-user"
    is_authenticated: bool = True


@dataclass
class MockDjangoContext:
    user: MockUser
    is_authenticated: bool = True
    request: Optional[Any] = None


class MockRuntime:
    context = {"django": MockDjangoContext(user=MockUser())}


class BookQueryTool(ModelQueryTool):
    name = "book_query"
    description = "Query books"
    queryset = Book.objects.all()
    require_auth = False


class AuthorSchema(BaseModel):
    id: int
    name: str


class BookSchema(BaseModel):
    id: int
    title: str
    author: AuthorSchema


class EfficientBookQueryTool(ModelQueryTool):
    name = "efficient_book_query"
    description = "Query books with authors"
    queryset = Book.objects.all()
    require_auth = False
    schema = BookSchema
    select_related = ["author"]


@pytest.fixture
def author(db):
    return Author.objects.create(name="Ursula Le Guin", country="US")


@pytest.fixture
def books(db, author):
    return [
        Book.objects.create(
            title="A Wizard of Earthsea",
            genre="Fantasy",
            published_year=1968,
            author=author,
            is_featured=True,
        ),
        Book.objects.create(
            title="The Dispossessed",
            genre="Sci-Fi",
            published_year=1974,
            author=author,
            is_featured=False,
        ),
        Book.objects.create(
            title="The Left Hand of Darkness",
            genre="Sci-Fi",
            published_year=1969,
            author=author,
            is_featured=True,
        ),
    ]


def payload(result: str) -> dict:
    return json.loads(result)


def test_django_model_schema_matches_tool_arguments():
    data = validate_tool_input(
        "django_model",
        {
            "action": "query",
            "model": "demo_app.Book",
            "filters": {"title__icontains": "earthsea"},
            "id": 1,
            "search": "earth",
            "limit": 5,
            "offset": 0,
            "fields": ["id", "title"],
            "order_by": ["title"],
            "search_fields": ["title"],
            "query_field": "id",
            "include_total": False,
            "app": "demo_app",
        },
    )

    assert set(data) >= {
        "action",
        "model",
        "filters",
        "id",
        "search",
        "limit",
        "offset",
        "fields",
        "order_by",
        "search_fields",
        "query_field",
        "include_total",
        "app",
    }
    assert DjangoModelQueryInput(action="list_models").action == "list_models"


@pytest.mark.django_db
def test_rejects_unknown_filter_field(books):
    result = payload(
        BookQueryTool()._run(action="query", filters={"missing": "value"})
    )

    assert result["success"] is False
    assert "Unknown field 'missing'" in result["error"]


@pytest.mark.django_db
def test_rejects_unsafe_lookup_and_relation_traversal(books):
    unsafe_lookup = payload(
        BookQueryTool()._run(action="query", filters={"title__regex": ".*"})
    )
    relation_traversal = payload(
        BookQueryTool()._run(action="query", filters={"author__name": "Ursula"})
    )

    assert unsafe_lookup["success"] is False
    assert "Invalid filter 'title__regex'" in unsafe_lookup["error"]
    assert relation_traversal["success"] is False
    assert "Invalid filter 'author__name'" in relation_traversal["error"]


@pytest.mark.django_db
def test_accepts_safe_filters_order_fields_and_search(books):
    query = payload(
        BookQueryTool()._run(
            action="query",
            filters={"title__icontains": "the"},
            fields=["title", "published_year"],
            order_by=["-published_year"],
        )
    )
    search = payload(
        BookQueryTool()._run(
            action="search",
            search="earthsea",
            fields=["title"],
            search_fields=["title"],
        )
    )

    assert query["success"] is True
    assert [item["title"] for item in query["data"]] == [
        "The Dispossessed",
        "The Left Hand of Darkness",
    ]
    assert search["success"] is True
    assert search["data"] == [{"title": "A Wizard of Earthsea"}]


@pytest.mark.django_db
def test_generic_tool_applies_config_limits_and_offset(settings, books):
    settings.DJGENT = {
        "MODEL_QUERY_TOOL": {
            "ALLOWED_MODELS": ["demo_app.Book"],
            "EXCLUDED_MODELS": [],
            "MAX_RESULTS": 1,
            "DEFAULT_LIMIT": 2,
            "EXCLUDE_FIELDS": [],
        }
    }

    result = payload(
        DjangoModelQueryTool()._run(
            action="list",
            model="demo_app.Book",
            limit=50,
            offset=-99,
            runtime=MockRuntime(),
        )
    )

    assert result["success"] is True
    assert result["limit"] == 1
    assert result["offset"] == 0
    assert result["count"] == 1


@pytest.mark.django_db
def test_generic_tool_allowed_fields_hide_other_fields(settings, books):
    settings.DJGENT = {
        "MODEL_QUERY_TOOL": {
            "ALLOWED_MODELS": ["demo_app.Book"],
            "EXCLUDED_MODELS": [],
            "ALLOWED_FIELDS": {"demo_app.Book": ["id", "title"]},
            "EXCLUDE_FIELDS": [],
        }
    }

    result = payload(
        DjangoModelQueryTool()._run(
            action="list",
            model="demo_app.Book",
            runtime=MockRuntime(),
        )
    )

    assert result["success"] is True
    assert set(result["data"][0]) == {"id", "title"}


@pytest.mark.django_db
def test_select_related_tool_serializes_nested_schema_without_n_plus_one(
    books, django_assert_num_queries
):
    with django_assert_num_queries(1):
        result = payload(
            EfficientBookQueryTool()._run(action="list", include_total=False)
        )

    assert result["success"] is True
    assert result["data"][0]["author"] == {
        "id": books[0].author_id,
        "name": "Ursula Le Guin",
    }
