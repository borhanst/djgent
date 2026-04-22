import logging

from django.apps import AppConfig
from django.conf import settings

logger = logging.getLogger(__name__)


class DjgentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "djgent"
    verbose_name = "Djgent Agent Framework"

    # Mapping of tool names to their classes
    BUILTIN_TOOL_CLASSES = {}

    def ready(self):
        """Initialize djgent when Django starts."""
        from djgent.tools.registry import ToolRegistry
        from djgent.utils.public_models import PublicModelRegistry

        # Register admin models
        self._register_admin()

        # Auto-discover public model registrations
        PublicModelRegistry.auto_discover()

        # Build the tool mapping
        self._build_builtin_tool_mapping()

        # Register built-in tools based on BUILTIN_TOOLS setting
        self._register_builtin_tools()

        # Register Django model query tool if enabled
        self._register_model_query_tool()

        # Register Django auth tool (always registered)
        self._register_django_auth_tool()

        # Auto-discover tools if enabled
        if getattr(settings, "DJGENT", {}).get("AUTO_DISCOVER_TOOLS", True):
            ToolRegistry.auto_discover()

    def _register_admin(self):
        """Register Django admin models."""
        try:
            from djgent import admin as djgent_admin  # noqa: F401
        except ImportError:
            pass  # Admin not available
        except Exception as e:
            logger.debug(f"Could not register admin: {e}")

    def _build_builtin_tool_mapping(self):
        """Build mapping of tool names to their classes."""
        from djgent.tools.builtin import (
            CalculatorTool,
            DateTimeTool,
            DjangoAuthTool,
            DjangoModelQueryTool,
            HTTPTool,
            KnowledgeIngestTool,
            MemoryStoreTool,
            RetrievalTool,
            SearchTool,
            WeatherTool,
        )

        self.BUILTIN_TOOL_CLASSES = {
            "calculator": CalculatorTool,
            "datetime": DateTimeTool,
            "http": HTTPTool,
            "search": SearchTool,
            "weather": WeatherTool,
            "model_query": DjangoModelQueryTool,
            "django_auth": DjangoAuthTool,
            "memory_store": MemoryStoreTool,
            "knowledge_retrieval": RetrievalTool,
            "knowledge_ingest": KnowledgeIngestTool,
        }

    def _register_builtin_tools(self):
        """Register built-in tools based on BUILTIN_TOOLS setting."""
        from djgent.tools.registry import ToolRegistry

        # Get BUILTIN_TOOLS from settings, with default fallback
        djgent_settings = getattr(settings, "DJGENT", {})
        builtin_tools = djgent_settings.get("BUILTIN_TOOLS", ["calculator", "datetime"])

        # Register each tool specified in BUILTIN_TOOLS
        for tool_name in builtin_tools:
            if tool_name in self.BUILTIN_TOOL_CLASSES:
                if not ToolRegistry.has_tool(tool_name):
                    tool_class = self.BUILTIN_TOOL_CLASSES[tool_name]
                    ToolRegistry.register(name=tool_name)(tool_class)
                    logger.debug(f"Registered built-in tool: {tool_name}")
            else:
                logger.warning(
                    f"Unknown tool '{tool_name}' in BUILTIN_TOOLS setting. "
                    f"Available tools: {list(self.BUILTIN_TOOL_CLASSES.keys())}"
                )

    def _register_model_query_tool(self):
        """Register Django model query tool if enabled."""
        from djgent.tools.builtin import DjangoModelQueryTool
        from djgent.tools.registry import ToolRegistry

        # Get MODEL_QUERY_TOOL config
        djgent_settings = getattr(settings, "DJGENT", {})
        model_query_config = djgent_settings.get("MODEL_QUERY_TOOL", {})

        # Check if enabled (default: True)
        if not model_query_config.get("ENABLED", True):
            logger.debug("Django model query tool is disabled")
            return

        # Register if not already registered
        if not ToolRegistry.has_tool("django_model"):
            ToolRegistry.register(name="django_model")(DjangoModelQueryTool)
            logger.debug("Registered django_model tool")

    def _register_django_auth_tool(self):
        """Register Django auth tool (always registered)."""
        from djgent.tools.builtin import DjangoAuthTool
        from djgent.tools.registry import ToolRegistry

        # Register if not already registered
        if not ToolRegistry.has_tool("django_auth"):
            ToolRegistry.register(name="django_auth")(DjangoAuthTool)
            logger.debug("Registered django_auth tool")
