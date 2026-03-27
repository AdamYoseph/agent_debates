# search_tools.py
from ddgs import DDGS


def search_web(query: str, max_results: int = 5) -> str:
    """Run a DuckDuckGo text search and return formatted results."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return "No results found."
        lines = []
        for r in results:
            lines.append(f"{r['title']} | {r['body']} | {r['href']}")
        return "\n".join(lines)
    except Exception as e:
        print(f"[search_web] Search failed: {e}")
        return "Search failed."


def pre_search(topic: str) -> str:
    """Run targeted searches before the debate starts. Returns a research brief."""
    queries = [
        f"{topic} price Israel 2025",
        f"{topic} insurance cost Israel",
        f"{topic} reliability rating",
        f"best family car Israel 2025 recommendations",
        f"{topic} fuel economy",
        f"{topic} maintenance cost",
    ]
    sections = ["## RESEARCH BRIEF\n"]
    for query in queries:
        result = search_web(query, max_results=3)
        sections.append(f"### {query}\n{result}\n")
    return "\n".join(sections)


SEARCH_TOOL_DEFINITION = {
    "name": "search_web",
    "description": (
        "Search the web for current information about car prices, insurance rates, "
        "reliability ratings, and other relevant data. Use this when you need specific "
        "facts or figures to support your argument."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query, e.g. 'Toyota RAV4 price Israel 2025'",
            },
            "max_results": {
                "type": "integer",
                "description": "Number of results to return (default 5)",
            },
        },
        "required": ["query"],
    },
}
