from pydantic import BaseModel

from djgent import ModelQueryTool, tool

from .models import Book


class BookAuthorSchema(BaseModel):
    id: int
    name: str


class BookSchema(BaseModel):
    id: int
    title: str
    author: BookAuthorSchema


@tool
class BookQueryTool(ModelQueryTool):
    name = "book_query"
    description = "Query demo books using a Pydantic schema"
    queryset = Book.objects.select_related("author").all()
    require_auth = False
    schema = BookSchema



@tool
def calculator(query: str) -> str:
    """
    A simple calculator tool that evaluates basic arithmetic expressions.

    Args:
        query: A string containing the arithmetic expression to evaluate.

    Returns:
        The result of the evaluated expression as a string.
    """
    try:
        # WARNING: Using eval can be dangerous in production. This is just for demo purposes.
        result = eval(query, {"__builtins__": {}})
        return str(result)
    except Exception as e:
        return f"Error evaluating expression: {e}"
