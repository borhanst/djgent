from pydantic import BaseModel

from djgent import ModelQueryTool
from djgent.tools.registry import ToolRegistry

from .models import Book


class BookAuthorSchema(BaseModel):
    id: int
    name: str


class BookSchema(BaseModel):
    id: int
    title: str
    author: BookAuthorSchema


class BookQueryTool(ModelQueryTool):
    name = "book_query"
    description = "Query demo books using a Pydantic schema"
    queryset = Book.objects.select_related("author").all()
    require_auth = False
    schema = BookSchema


ToolRegistry.register(name="book_query")(BookQueryTool)
