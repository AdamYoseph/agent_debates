# tests/test_search_tools.py
from unittest.mock import patch, MagicMock
from search_tools import search_web, SEARCH_TOOL_DEFINITION


def test_search_web_returns_string():
    mock_results = [
        {"title": "Toyota RAV4 Price", "body": "Costs $30,000 in Israel", "href": "https://example.com"},
        {"title": "Honda CR-V Review", "body": "Great family car", "href": "https://example2.com"},
    ]
    with patch("search_tools.DDGS") as MockDDGS:
        instance = MockDDGS.return_value.__enter__.return_value
        instance.text.return_value = mock_results
        result = search_web("best family car Israel")

    assert "Toyota RAV4 Price" in result
    assert "Costs $30,000 in Israel" in result
    assert "https://example.com" in result


def test_search_web_empty_results():
    with patch("search_tools.DDGS") as MockDDGS:
        instance = MockDDGS.return_value.__enter__.return_value
        instance.text.return_value = []
        result = search_web("something obscure")

    assert result == "No results found."


def test_search_web_handles_exception():
    with patch("search_tools.DDGS") as MockDDGS:
        instance = MockDDGS.return_value.__enter__.return_value
        instance.text.side_effect = Exception("network error")
        result = search_web("test query")

    assert result == "Search failed."


def test_search_tool_definition_structure():
    assert SEARCH_TOOL_DEFINITION["name"] == "search_web"
    assert "description" in SEARCH_TOOL_DEFINITION
    assert SEARCH_TOOL_DEFINITION["parameters"]["type"] == "object"
    assert "query" in SEARCH_TOOL_DEFINITION["parameters"]["properties"]
    assert "query" in SEARCH_TOOL_DEFINITION["parameters"]["required"]
