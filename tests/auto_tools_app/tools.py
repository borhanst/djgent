from djgent import tool
from djgent.tools.base import Tool


class AutoDiscoveredTool(Tool):
    name = "auto_discovered_tool"
    description = "Auto-discovered class tool"

    def _run(self) -> str:
        return "auto"


class DuplicateTool(Tool):
    name = "duplicate_tool"
    description = "Should not replace manual registration"

    def _run(self) -> str:
        return "auto duplicate"


class NoNameTool(Tool):
    description = "Tool subclass without a name should be ignored"

    def _run(self) -> str:
        return "ignored"


class NotATool:
    name = "not_a_tool"


@tool(name="decorated_auto_function")
def decorated_function() -> str:
    """Decorated function tool."""
    return "decorated"
