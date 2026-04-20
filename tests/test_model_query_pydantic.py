import json

import pytest
from pydantic import BaseModel

from demo_app.models import Author, Book
from djgent.tools.base import ModelQueryTool


class AuthorSchema(BaseModel):
    id: int
    name: str


class BookSchema(BaseModel):
    id: int
    title: str
    author: AuthorSchema


class BookQueryTool(ModelQueryTool):
    name = "book_query"
    description = "Query books"
    queryset = Book.objects.all()
    require_auth = False
    schema = BookSchema


@pytest.fixture
def author(db):
    return Author.objects.create(name="Octavia Butler", country="US")


@pytest.fixture
def books(db, author):
    return [
        Book.objects.create(
            title="Kindred",
            genre="Sci-Fi",
            published_year=1979,
            author=author,
            is_featured=True,
        ),
        Book.objects.create(
            title="Parable of the Sower",
            genre="Sci-Fi",
            published_year=1993,
            author=author,
            is_featured=False,
        ),
    ]


@pytest.mark.django_db
def test_get_by_id_uses_declared_pydantic_fields(author, books):
    payload = json.loads(BookQueryTool()._run(action="get_by_id", id=books[0].pk))

    assert payload["success"] is True
    assert payload["data"] == {
        "id": books[0].pk,
        "title": "Kindred",
        "author": {
            "id": author.pk,
            "name": "Octavia Butler",
        },
    }


@pytest.mark.django_db
def test_runtime_fields_intersect_pydantic_fields(author, books):
    payload = json.loads(BookQueryTool()._run(action="list", fields=["title"], limit=10))

    assert payload["success"] is True
    assert payload["data"] == [
        {"title": "Kindred"},
        {"title": "Parable of the Sower"},
    ]
