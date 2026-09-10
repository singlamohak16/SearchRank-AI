"""A small render smoke test for the transport-only Streamlit page."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_page_renders_search_and_query_tabs(monkeypatch) -> None:
    monkeypatch.setenv("SEARCHRANK_API_URL", "http://127.0.0.1:1")
    app_path = Path(__file__).parents[1] / "src" / "searchrank_ai" / "streamlit_app.py"

    app = AppTest.from_file(str(app_path)).run(timeout=10)

    assert not app.exception
    assert app.title[0].value == "SearchRank-AI"
    assert [tab.label for tab in app.tabs] == ["Search", "Ask / Compare"]
    assert {button.label for button in app.button} == {
        "Search catalogue",
        "Run grounded workflow",
    }
