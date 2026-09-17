"""Offline storefront interactions: forms, persistence, comparisons and safe rendering."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from searchrank_ai.api_client import APIClient, APIClientError
from searchrank_ai.streamlit_app import _comparison_html
from searchrank_ai.ui_presentation import card_html, display_value, safe_url

APP_PATH = Path(__file__).parents[1] / "src" / "searchrank_ai" / "streamlit_app.py"


def phone(index=0):
    return {
        "product_id": f"phone-{index}",
        "product_name": f"Phone {index}",
        "brand": "Samsung",
        "price_inr": 20000 + index,
        "ram_gb": 8.0,
        "storage_gb": 128.0,
        "user_rating_5": None,
        "source_url": f"https://www.91mobiles.com/phone-{index}",
        "image_url": None,
        "processor": None,
        "rank": index + 1,
        "score": 0.5,
    }


@pytest.fixture
def client_stub(monkeypatch):
    calls = {"search": [], "query": [], "product": [], "count": 8, "fail": None}
    monkeypatch.setattr(
        APIClient,
        "health",
        lambda self: {
            "status": "ok",
            "components": {"search": True, "products": True, "query": True},
        },
    )

    def search(self, payload):
        calls["search"].append(payload)
        if calls["fail"] == "search":
            raise APIClientError("Test service unavailable")
        return {**payload, "results": [phone(i) for i in range(calls["count"])]}

    def product(self, product_id):
        calls["product"].append(product_id)
        if calls["fail"] == "product":
            raise APIClientError("Product unavailable")
        return phone(int(product_id.split("-")[-1]))

    def query(self, payload):
        calls["query"].append(payload)
        if calls["fail"] == "query":
            raise APIClientError("Gemini quota/rate limit reached. Wait; do not upgrade.")
        return {
            "response": "Verified catalogue answer.",
            "status": "answered",
            "retry_count": 0,
            "constraints": {},
            "retrieved_product_ids": ["phone-0"],
            "workflow_path": ["analyze_request", "verify_evidence"],
            "tool_history": [],
            "verification": {"passed": True, "issues": []},
        }

    monkeypatch.setattr(APIClient, "search", search)
    monkeypatch.setattr(APIClient, "product", product)
    monkeypatch.setattr(APIClient, "query", query)
    return calls


def app():
    result = AppTest.from_file(str(APP_PATH)).run(timeout=10)
    assert not result.exception
    return result


def button(page, label):
    return next(item for item in page.button if item.label == label)


def field(items, label):
    return next(item for item in items if item.label == label)


def search(page):
    page.text_input(key="search_terms").set_value("Samsung")
    button(page, "Find phones").click().run()
    assert not page.exception
    return page


def test_examples_do_not_call_search_or_llm(client_stub):
    page = app()
    button(page, "OnePlus Nord").click().run()
    assert page.text_input(key="search_terms").value == "OnePlus Nord"
    assert client_stub["search"] == client_stub["query"] == []


def test_filters_results_and_details_persist_without_resubmission(client_stub):
    page = app()
    field(page.number_input, "Budget up to (₹)").set_value(30000)
    field(page.selectbox, "Minimum RAM").set_value(8)
    field(page.selectbox, "Minimum storage").set_value(128)
    field(page.text_input, "Include brands (comma-separated)").set_value("Samsung")
    search(page)
    constraints = client_stub["search"][0]["constraints"]
    assert constraints["max_price_inr"] == 30000.0
    assert constraints["min_ram_gb"] == 8.0
    assert constraints["min_storage_gb"] == 128.0
    assert constraints["included_brands"] == ["Samsung"]
    assert len(client_stub["product"]) == 6
    page.button(key="pick_phone-0").click().run()
    assert len(client_stub["search"]) == 1
    assert len(client_stub["product"]) == 6
    assert len(page.session_state["shortlist"]) == 1
    assert page.session_state["search_response"]["query"] == "Samsung"
    assert not client_stub["query"]


def test_custom_minimums_override_presets_including_explicit_zero(client_stub):
    page = app()
    field(page.selectbox, "Minimum RAM").set_value(8)
    field(page.selectbox, "Minimum storage").set_value(128)
    field(page.selectbox, "Minimum rating").set_value(4.5)
    field(page.number_input, "Custom minimum RAM (GB)").set_value(0.0)
    field(page.number_input, "Custom minimum storage (GB)").set_value(32.0)
    field(page.number_input, "Custom minimum rating").set_value(4.2)
    search(page)
    constraints = client_stub["search"][0]["constraints"]
    assert constraints["min_ram_gb"] == 0.0
    assert constraints["min_storage_gb"] == 32.0
    assert constraints["min_rating_5"] == 4.2


@pytest.mark.parametrize("status", ["unsupported", "needs_clarification", "no_results"])
def test_non_answers_do_not_receive_verification_badge(client_stub, monkeypatch, status):
    original_query = APIClient.query

    def query(self, payload):
        return {**original_query(self, payload), "status": status}

    monkeypatch.setattr(APIClient, "query", query)
    page = app()
    field(page.text_area, "What are you looking for?").set_value("Test request")
    button(page, "Ask SearchRank").click().run()
    assert not page.exception
    assert not page.success
    assert any(status.replace("_", " ") in message.value for message in page.info)


def test_shortlist_limit_removal_and_cross_search_persistence(client_stub):
    page = search(app())
    for index in range(3):
        page.button(key=f"pick_phone-{index}").click().run()
    assert page.button(key="pick_phone-3").disabled
    assert not page.button(key="pick_phone-0").disabled
    page.button(key="remove_phone-0").click().run()
    assert not page.button(key="pick_phone-3").disabled
    search(page)
    assert set(page.session_state["shortlist"]) == {"phone-1", "phone-2"}
    button(page, "Clear shortlist").click().run()
    assert page.session_state["shortlist"] == {}
    assert not page.exception


def test_pagination_keeps_rank_and_resets_on_new_search(client_stub):
    page = search(app())
    page.selectbox(key="result_page").set_value(2).run()
    assert any(item.key == "pick_phone-6" for item in page.button)
    assert len(client_stub["search"]) == 1
    client_stub["count"] = 2
    search(page)
    assert not page.exception
    assert page.session_state["result_page"] == 1


def test_empty_error_and_blank_search_clear_stale_results(client_stub):
    page = search(app())
    client_stub["count"] = 0
    search(page)
    assert page.session_state["search_response"]["results"] == []
    client_stub["fail"] = "search"
    search(page)
    assert "Test service unavailable" in page.error[0].value
    assert "search_response" not in page.session_state
    page.text_input(key="search_terms").set_value(" ")
    button(page, "Find phones").click().run()
    assert "Enter a phone" in page.warning[0].value


def test_missing_details_preserves_search_and_comparison(client_stub):
    client_stub["fail"] = "product"
    page = search(app())
    page.button(key="pick_phone-0").click().run()
    assert not page.exception
    assert page.session_state["shortlist"]["phone-0"]["price_inr"] == 20000
    assert any("Details unavailable" in item.value for item in page.warning)


def test_ai_is_explicit_persistent_and_handles_quota_without_retry(client_stub):
    page = app()
    field(page.text_area, "What are you looking for?").set_value("Compare phones")
    button(page, "Ask SearchRank").click().run()
    assert len(client_stub["query"]) == 1
    assert any("claims checked" in message.value for message in page.success)
    button(page, "Samsung Galaxy").click().run()
    assert len(client_stub["query"]) == 1
    assert page.session_state["ai_response"]["status"] == "answered"
    client_stub["fail"] = "query"
    button(page, "Ask SearchRank").click().run()
    assert len(client_stub["query"]) == 2
    assert "quota" in page.error[0].value
    assert "ai_response" not in page.session_state


def test_too_much_context_never_calls_provider(client_stub):
    page = app()
    field(page.text_area, "What are you looking for?").set_value("Compare phones")
    field(page.text_area, "Previous messages").set_value("hello\n" * 11)
    button(page, "Ask SearchRank").click().run()
    assert not client_stub["query"]
    assert any("ten context messages" in message.value for message in page.warning)


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "http://www.91mobiles.com/a",
        "https://evil.test/a",
        "https://www.91mobiles.com.evil.test/a",
        "https://user@www.91mobiles.com/a",
        "https://www.91mobiles.com:8080/a",
        "https://www.91mobiles.com/\na",
        None,
    ],
)
def test_links_reject_untrusted_destinations(url):
    assert safe_url(url) is None
    assert safe_url(url, image=True) is None


def test_cards_and_comparison_escape_text_and_preserve_unknowns():
    item = phone()
    item["product_name"] = '<img src=x onerror="alert(1)">'
    item["processor"] = "<script>bad</script>"
    html = card_html(item, "https://evil.test/pixel")
    assert "&lt;img" in html
    assert '<img src="https://evil' not in html
    assert "not available" in html and "Not available" in html
    comparison = _comparison_html([item, phone(1)])
    assert "&lt;script&gt;" in comparison and "<script>" not in comparison
    assert display_value(None, " mAh") == "Not available"
    assert safe_url("https://www.91-img.com/pictures/phone.jpg", image=True)
    assert safe_url(item["source_url"]) == item["source_url"]
