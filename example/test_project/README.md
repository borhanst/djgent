# Test Project

Small Django project for exercising the local `djgent` package.

## Setup

Create an environment and install the package in editable mode with Django:

```bash
cd example
uv venv
source .venv/bin/activate
uv pip install -e "..[dev]"
cp .env.example .env
```

## Run

```bash
cd example
python manage.py migrate
python manage.py seed_demo_data
python manage.py check
python manage.py runserver
```

Open `http://127.0.0.1:8000/` for the demo page with the site-wide chat bubble, or `http://127.0.0.1:8000/chat/` for the full chat UI.

The example project also includes `example/chat_ui/views.py`, which shows how to
build a custom chat endpoint by subclassing `djgent.chat.BaseChatView` instead of
rewriting the chat persistence logic.

By default the example uses `ollama:llama3.2`. If you prefer a hosted provider, set `DJGENT_DEFAULT_LLM` and the matching API key in `example/.env`.

## Smoke test

Open a Django shell:

```bash
cd example
python manage.py shell
```

Then run:

```python
from djgent.tools.builtin import DjangoModelQueryTool
from djgent.tools.registry import ToolRegistry

tool = DjangoModelQueryTool()
print(tool._run(action="list_models"))
print(tool._run(action="get_schema", model="demo_app.Book"))

book_tool = ToolRegistry.get_tool_instance("book_query")
print(book_tool._run(action="list"))
print(book_tool._run(action="get_by_id", id=1))
```

The `book_query` example tool is defined in `example/demo_app/tools.py` and uses:

```python
class BookQueryTool(ModelQueryTool):
    queryset = Book.objects.select_related("author").all()
    require_auth = False
    schema = BookSchema
```

Only the fields declared on `BookSchema` are returned.
