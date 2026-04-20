"""Web search tool using LangChain's DuckDuckGo integration."""

from typing import Any

from djgent.tools.base import Tool


class SearchTool(Tool):
    """
    Search the web using LangChain's DuckDuckGo integration.

    Free, no API key required. Returns real search results.
    Based on: https://docs.langchain.com/oss/python/integrations/tools/ddg
    """

    name = "search"
    description = "Search the web using DuckDuckGo. Use this tool for weather information, current events, news, recent information, facts about people/places/things, or any information you don't know or need to verify."

    def __init__(self, **kwargs: Any):
        """Initialize the search tool with LangChain's DuckDuckGoSearchResults."""
        super().__init__(**kwargs)
        self._search = None

    def _get_search_tool(self):
        """Lazy load the LangChain search tool."""
        if self._search is None:
            try:
                from langchain_community.tools import DuckDuckGoSearchResults

                self._search = DuckDuckGoSearchResults(output_format="list")
            except ImportError:
                raise ImportError(
                    "langchain-community package not installed. "
                    "Run: pip install langchain-community duckduckgo-search"
                )
        return self._search

    def _run(
        self,
        query: str,
    ) -> str:
        """
        Search the web using DuckDuckGo via LangChain.

        Args:
            query: The search query

        Returns:
            Formatted search results with title, URL, and snippet
        """
        try:
            search_tool = self._get_search_tool()
            results = search_tool.invoke(query)
            if not results:
                return f"No results found for '{query}'. Try a different search term."

            # Format results (LangChain returns list of dicts)
            if isinstance(results, list):
                formatted = []
                for i, result in enumerate(results, 1):
                    title = result.get("title", "No title")
                    url = result.get("link", result.get("url", "No URL"))
                    snippet = result.get(
                        "snippet", result.get("body", "No description")
                    )
                    formatted.append(
                        f"{i}. {title}\n   URL: {url}\n   {snippet}"
                    )
                return f"Search results for '{query}':\n\n" + "\n\n".join(
                    formatted
                )
            else:
                # Fallback for string results
                return f"Search results for '{query}':\n{results}"

        except ImportError as e:
            return str(e)
        except Exception as e:
            return f"Search error: {str(e)}"
