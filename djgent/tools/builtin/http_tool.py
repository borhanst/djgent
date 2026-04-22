"""HTTP tool for making API calls."""

from typing import Any, Dict, Optional

import httpx

from djgent.tools.base import Tool


class HTTPTool(Tool):
    """
    Make HTTP requests to APIs and web services.

    Supports GET, POST, PUT, DELETE, and PATCH methods with headers and body.
    """

    name = "http"
    description = "Make HTTP requests (GET, POST, PUT, DELETE, PATCH) to APIs and web services."
    risk_level = "high"
    requires_approval = True
    approval_reason = "HTTP requests can access external systems and send data."

    def _run(
        self,
        method: str = "GET",
        url: str = "",
        headers: Optional[Dict[str, str]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """
        Make an HTTP request.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, PATCH)
            url: The URL to request
            headers: Optional headers dictionary
            json_body: Optional JSON body for POST/PUT/PATCH
            timeout: Request timeout in seconds

        Returns:
            Dictionary with status_code, headers, and body
        """
        try:
            method = method.upper()
            with httpx.Client(timeout=timeout) as client:
                kwargs: Dict[str, Any] = {"headers": headers or {}}
                if json_body:
                    kwargs["json"] = json_body

                response = client.request(method, url, **kwargs)

                return {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response.text,
                    "success": response.status_code < 400,
                }

        except httpx.TimeoutException:
            return {"error": f"Request timed out after {timeout} seconds"}
        except httpx.RequestError as e:
            return {"error": f"Request failed: {str(e)}"}
        except Exception as e:
            return {"error": f"Error: {str(e)}"}
