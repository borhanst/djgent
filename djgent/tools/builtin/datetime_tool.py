"""Date and time utility tool."""

from datetime import datetime
from typing import Optional, Union

from djgent.tools.base import Tool


class DateTimeTool(Tool):
    """
    Get current date/time information and perform date calculations.

    Can get current date/time, format dates, and calculate date differences.
    """

    name = "datetime"
    description = "Get current date/time, format dates, or calculate date differences."

    def _run(
        self,
        action: str = "now",
        format: Optional[str] = None,
        date1: Optional[str] = None,
        date2: Optional[str] = None,
    ) -> str:
        """
        Perform date/time operations.

        Args:
            action: One of 'now', 'format', 'diff'
            format: Date format string (for 'format' action)
            date1: First date string (for 'diff' action)
            date2: Second date string (for 'diff' action)

        Returns:
            The result of the date/time operation
        """
        try:
            if action == "now":
                now = datetime.now()
                if format:
                    return now.strftime(format)
                return now.isoformat()

            elif action == "format":
                if not date1:
                    return "Error: date1 is required for format action"
                dt = datetime.fromisoformat(date1)
                fmt = format or "%Y-%m-%d %H:%M:%S"
                return dt.strftime(fmt)

            elif action == "diff":
                if not date1 or not date2:
                    return "Error: date1 and date2 are required for diff action"
                dt1 = datetime.fromisoformat(date1)
                dt2 = datetime.fromisoformat(date2)
                diff = dt2 - dt1
                return f"{diff.days} days, {diff.seconds} seconds"

            else:
                return f"Error: Unknown action '{action}'. Use 'now', 'format', or 'diff'."

        except Exception as e:
            return f"Error: {str(e)}"
