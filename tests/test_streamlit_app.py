"""A small render smoke test for the transport-only Streamlit page."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from searchrank_ai.api_client import APIClient, APIClientError
from searchrank_ai.streamlit_app import _markdown_text


def test_catalogue_labels_are_escaped_before_markdown_rendering() -> None:
    value = "Phone [bad](https://evil.example)\n![pixel](https://evil.example/pixel.png)"

    escaped = _markdown_text(value)

    assert "\n" not in escaped
    assert "[bad](" not in escaped
    assert "![pixel](" not in escaped
    assert "\\[bad\\]\\(https\\:\\/\\/evil\\.example\\)" in escaped


def test_streamlit_page_renders_search_and_query_tabs(monkeypatch) -> None:
    monkeypatch.setenv("SEARCHRANK_API_URL", "http://127.0.0.1:1")

    def offline_health(self):
        raise APIClientError("Test service offline")

    # Cached clients survive AppTest instances: never depend on a real local service.
    monkeypatch.setattr(APIClient, "health", offline_health)
    app_path = Path(__file__).parents[1] / "src" / "searchrank_ai" / "streamlit_app.py"

    app = AppTest.from_file(str(app_path)).run(timeout=10)

    assert not app.exception
    assert app.title[0].value == "Find your next phone."
    assert [tab.label for tab in app.tabs] == ["Discover", "Compare phones", "Ask AI"]
    assert {button.label for button in app.button} == {
        "Samsung Galaxy",
        "OnePlus Nord",
        "AMOLED + Snapdragon",
        "Find phones",
        "Ask SearchRank",
    }
    assert next(button for button in app.button if button.label == "Find phones").disabled
    assert next(button for button in app.button if button.label == "Ask SearchRank").disabled
