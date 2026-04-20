# ModelQueryTool Guide

## Overview

`ModelQueryTool` is a base class that provides a ready-to-use query interface for Django models. It supports:

- **Listing objects** with pagination
- **Filtering** with Django-style filters
- **Getting single objects** by ID
- **Searching** across text fields
- **Counting** objects with optional filters
- **Authentication-based access control**
- **Dynamic queryset customization** via `get_queryset()`

## Installation

```python
from djgent import ModelQueryTool
```

## Basic Usage

### Simple Model Query Tool

```python
from djgent import ModelQueryTool
from myapp.models import Product

class ProductQueryTool(ModelQueryTool):
    name = "product_query"
    description = "Query products from database"
    queryset = Product.objects.filter(active=True)
    exclude_fields = ["cost_price", "supplier_secret"]
    require_auth = False  # Public access
    max_results = 100
    default_limit = 10
```

### Query by Different Fields

By default, `get_by_id` queries by primary key (`pk`). You can change this:

```python
# Query by slug instead of pk
class ProductQueryTool(ModelQueryTool):
    name = "product_query"
    queryset = Product.objects.all()
    query_field = "slug"  # Now queries use slug field

# Usage
tool = ProductQueryTool()
tool._run(action="get_by_id", id="my-product-slug")  # Queries by slug

# Or override per-query
tool._run(action="get_by_id", id="SKU-123", query_field="sku")
```

### Usage Examples

```python
from myapp.tools import ProductQueryTool

tool = ProductQueryTool()

# List objects
result = tool._run(action="list", limit=20, offset=0)
# Returns: {"success": true, "count": 20, "total_count": 150, "data": [...]}

# Filter objects
result = tool._run(
    action="query",
    filters={"category": "electronics", "price__lt": 1000}
)
# Returns: {"success": true, "count": 10, "data": [...]}

# Get by ID
result = tool._run(action="get_by_id", id=42)
# Returns: {"success": true, "id": 42, "data": {...}}

# Search
result = tool._run(
    action="search",
    search="laptop",
    search_fields=["name", "description"]
)
# Returns: {"success": true, "count": 5, "search_term": "laptop", "data": [...]}

# Count
result = tool._run(
    action="count",
    filters={"category": "electronics"}
)
# Returns: {"success": true, "count": 45}
```

## Advanced Usage

### Dynamic Queryset with `get_queryset()`

Override `get_queryset()` to customize the queryset based on the user or request:

```python
from djgent import ModelQueryTool
from django.contrib.auth import get_user_model

User = get_user_model()

class UserQueryTool(ModelQueryTool):
    name = "user_query"
    description = "Query users with role-based access"
    require_auth = True

    def get_queryset(self, runtime=None, user=None, **kwargs):
        """Customize queryset based on user role."""
        if user and user.is_staff:
            # Staff see all users
            return User.objects.all()
        elif user and user.groups.filter(name="HR").exists():
            # HR sees active users only
            return User.objects.filter(is_active=True)
        else:
            # Regular users see only themselves
            return User.objects.filter(id=user.id) if user else User.objects.none()
```

### Context-Aware Queryset

```python
from djgent import ModelQueryTool
from orders.models import Order

class OrderQueryTool(ModelQueryTool):
    name = "order_query"
    description = "Query orders"
    require_auth = True

    def get_queryset(self, runtime=None, user=None, **kwargs):
        """Show users only their own orders."""
        if not user:
            return Order.objects.none()

        # Regular users see only their orders
        if not user.is_staff:
            return Order.objects.filter(customer=user)

        # Staff sees all orders
        return Order.objects.all()
```

### Multiple Query Tools for Different Models

```python
from djgent import ModelQueryTool, tool
from blog.models import Post, Category
from products.models import Product, Category as ProductCategory

# Blog tools
class PostQueryTool(ModelQueryTool):
    name = "post_query"
    description = "Query blog posts"
    queryset = Post.objects.filter(status="published")
    exclude_fields = ["admin_notes", "draft_content"]
    require_auth = False

class CategoryQueryTool(ModelQueryTool):
    name = "category_query"
    description = "Query blog categories"
    queryset = Category.objects.all()
    require_auth = False

# Product tools
class ProductQueryTool(ModelQueryTool):
    name = "product_query"
    description = "Query products"
    queryset = Product.objects.filter(active=True)
    exclude_fields = ["cost_price", "supplier_info"]
    require_auth = False

# Register tools
post_query = tool(PostQueryTool)
category_query = tool(CategoryQueryTool)
product_query = tool(ProductQueryTool)
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `queryset` | `QuerySet` | `None` | Base queryset to query |
| `allowed_actions` | `List[str]` | `["list", "query", "get_by_id", "search", "count"]` | Available actions |
| `exclude_fields` | `List[str]` | `[]` | Fields to exclude from results |
| `max_results` | `int` | `100` | Maximum results allowed |
| `default_limit` | `int` | `10` | Default limit for queries |
| `require_auth` | `bool` | `True` | Require authentication for all actions |
| `search_fields` | `List[str]` | `None` | Default fields to search |
| `query_field` | `str` | `"pk"` | Field to query by for `get_by_id` action |

## Action Parameters

### `list` - List objects with pagination

```python
tool._run(
    action="list",
    limit=10,          # Max results
    offset=0,          # Pagination offset
    fields=None,       # Specific fields to return
    order_by=None,     # Order by fields (e.g., ["-created_at"])
)
```

### `query` - Filter objects

```python
tool._run(
    action="query",
    filters={"status": "active"},  # Django-style filters
    limit=10,
    offset=0,
    fields=None,
    order_by=["-created_at"],
)
```

### `get_by_id` - Get single object by field value

```python
tool._run(
    action="get_by_id",
    id=42,              # Object identifier (value of query_field)
    fields=None,        # Specific fields to return
    query_field=None,   # Field to query by (default: class query_field or "pk")
)

# Examples:
# Query by primary key (default)
tool._run(action="get_by_id", id=42)

# Query by slug (set class query_field)
class ProductQueryTool(ModelQueryTool):
    query_field = "slug"

tool._run(action="get_by_id", id="my-product-slug")

# Override query_field per query
tool._run(action="get_by_id", id="SKU-123", query_field="sku")
```

### `search` - Search across fields

```python
tool._run(
    action="search",
    search="django",                # Search term
    limit=10,
    fields=None,
    search_fields=["name", "description"],  # Fields to search
)
```

### `count` - Count objects

```python
tool._run(
    action="count",
    filters={"status": "active"},  # Optional filters
)
```

## Response Format

### Success Response

```json
{
  "success": true,
  "action": "query",
  "count": 10,
  "total_count": 150,
  "limit": 10,
  "offset": 0,
  "filters": {"status": "active"},
  "data": [
    {"id": 1, "name": "Item 1", ...},
    {"id": 2, "name": "Item 2", ...}
  ]
}
```

### Error Response

```json
{
  "success": false,
  "error": "Authentication required. Please log in to access this feature."
}
```

## Integration with Agents

```python
from djgent import Agent, ModelQueryTool
from products.models import Product

# Create a product query tool
class ProductQueryTool(ModelQueryTool):
    name = "product_query"
    description = "Query products from the database"
    queryset = Product.objects.filter(active=True)
    require_auth = False

# Create agent with the tool
agent = Agent.create(
    name="shopping-assistant",
    tools=[ProductQueryTool()],
    system_prompt="You are a shopping assistant. Help users find products.",
)

# Use the agent
response = agent.run("Show me laptops under $1000")
```

## DjangoModelQueryTool

The built-in `DjangoModelQueryTool` uses `ModelQueryTool` as its base class and provides dynamic model selection:

```python
from djgent.tools.builtin import DjangoModelQueryTool

tool = DjangoModelQueryTool()

# List all models
tool._run(action="list_models")

# Get schema for a model
tool._run(action="get_schema", model="blog.Post")

# Query a specific model
tool._run(
    action="query",
    model="blog.Post",
    filters={"status": "published"}
)

# Get by ID
tool._run(action="get_by_id", model="products.Product", id=42)

# Search
tool._run(
    action="search",
    model="blog.Post",
    search="django"
)
```

## Best Practices

1. **Always exclude sensitive fields**: Use `exclude_fields` to hide passwords, tokens, etc.

2. **Use `require_auth` appropriately**: Set to `False` only for public data.

3. **Override `get_queryset()` for dynamic access**: Implement role-based filtering.

4. **Set reasonable limits**: Prevent large result sets with `max_results`.

5. **Provide clear descriptions**: Help the agent understand when to use your tool.

## Troubleshooting

### "No queryset defined" error

Set the `queryset` class variable or override `get_queryset()`:

```python
class MyTool(ModelQueryTool):
    queryset = MyModel.objects.all()  # Set queryset
```

### "Authentication required" error

Set `require_auth = False` for public access or ensure the user is authenticated.

### Empty results

Check that:
- The queryset is correct
- Filters match existing data
- The user has access to the data (if using `get_queryset()` with user-based filtering)
