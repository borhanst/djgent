"""Default settings for djgent."""

DJGENT_DEFAULTS = {
    "DEFAULT_LLM": "openai:gpt-4o-mini",
    "API_KEYS": {},
    "BUILTIN_TOOLS": [
        "calculator",
        "datetime",
    ],
    "AUTO_DISCOVER_TOOLS": True,
    "MEMORY_ENABLED": True,
    "MAX_ITERATIONS": 10,
    "MODEL_QUERY_TOOL": {
        "ENABLED": True,
        "ALLOWED_MODELS": [],  # Empty list = all models allowed
        "EXCLUDED_MODELS": [],
        "MAX_RESULTS": 100,
        "DEFAULT_LIMIT": 10,
        "ALLOW_DELETE": False,
        "ALLOW_UPDATE": False,
        # Note: Sensitive fields (password, token, secret, card info, etc.) are ALWAYS excluded
        # regardless of this setting. This list adds additional exclusions.
        "EXCLUDE_FIELDS": [],
        # Optional per-model field allowlist for the generic django_model tool.
        # Example: {"blog.Post": ["id", "title", "status"]}
        "ALLOWED_FIELDS": {},
    },
    # Authentication requirements for tools
    # Define which actions require authenticated users
    "AUTH_REQUIREMENTS": {
        "django_model": {
            "require_auth_for": ["query", "get_by_id", "search"],
            "allow_anonymous": ["list_models", "get_schema"],
        },
        "django_auth": {
            "require_auth_for": ["get_user", "check_permission", "check_group"],
            "allow_anonymous": ["list_permissions", "list_groups", "check_auth"],
        },
    },
    # User fields returned by get_user action
    # Default: only basic name fields
    # Add additional fields as needed (e.g., email, is_staff, etc.)
    "USER_FIELDS": ["first_name", "last_name", "full_name"],
    # Public models - models that can be listed publicly (anonymous users)
    # Can be a list of model names or a dict with field restrictions:
    # List format: ["blog.Post", "products.Category"]
    # Dict format: {"blog.Post": ["id", "title", "content"], "products.Category": None}
    # In dict format, value is list of allowed fields or None for all fields
    # If empty or not set, NO models are shown to anonymous users
    "PUBLIC_MODELS": [],
    # Optional token pricing map used to estimate LLM costs.
    # Example:
    # "MODEL_PRICING": {
    #     "openai:gpt-4o-mini": {
    #         "input_cost_per_1m": 0.15,
    #         "output_cost_per_1m": 0.60,
    #     }
    # }
    "MODEL_PRICING": {},
    # Optional LangChain built-in middleware configuration.
    # Example:
    # "LANGCHAIN_MIDDLEWARE": {
    #     "summarization": {
    #         "enabled": True,
    #         "model": "openai:gpt-4o-mini",
    #         "trigger": ("tokens", 4000),
    #         "keep": ("messages", 20),
    #     },
    #     "model_retry": {
    #         "enabled": True,
    #         "max_retries": 3,
    #         "backoff_factor": 2.0,
    #         "initial_delay": 1.0,
    #     },
    # }
    "LANGCHAIN_MIDDLEWARE": {},
}
