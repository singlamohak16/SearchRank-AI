"""Shopping-style local catalogue UI. Data and AI requests still go through FastAPI."""

from __future__ import annotations

import os
import string
from html import escape
from math import ceil

import streamlit as st

from searchrank_ai.api_client import APIClient, APIClientError
from searchrank_ai.ui_presentation import STYLE, card_html, display_value, safe_url

_MARKDOWN_SPECIALS = frozenset(string.punctuation)
_EXAMPLES = {
    "Samsung Galaxy": "Samsung Galaxy",
    "OnePlus Nord": "OnePlus Nord",
    "AMOLED + Snapdragon": "AMOLED Snapdragon",
}
_COMPARISON_FIELDS = (
    ("price_inr", "Catalogue price (INR)", ""),
    ("ram_gb", "RAM", " GB"),
    ("storage_gb", "Storage", " GB"),
    ("user_rating_5", "User rating", " / 5"),
    ("processor", "Processor", ""),
    ("battery_mah", "Battery", " mAh"),
    ("charging", "Charging", ""),
    ("display_inches", "Display size", " inches"),
    ("display_type", "Display type", ""),
    ("rear_camera", "Rear camera", ""),
    ("front_camera", "Front camera", ""),
)


@st.cache_resource
def _client() -> APIClient:
    return APIClient(os.getenv("SEARCHRANK_API_URL", "http://127.0.0.1:8000"))


def _brands(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _markdown_text(value: str) -> str:
    one_line = value.replace("\r", " ").replace("\n", " ")
    return "".join(f"\\{c}" if c in _MARKDOWN_SPECIALS else c for c in one_line)


def _empty(title: str, description: str) -> None:
    st.html(f'<div class="sr-empty"><h3>{escape(title)}</h3><p>{escape(description)}</p></div>')


def _prefill(query: str) -> None:
    st.session_state["search_terms"] = query


def _toggle_shortlist(item: dict) -> None:
    selected = st.session_state.setdefault("shortlist", {})
    if item["product_id"] in selected:
        del selected[item["product_id"]]
    elif len(selected) < 3:
        selected[item["product_id"]] = item


def _clear_shortlist() -> None:
    st.session_state["shortlist"] = {}


def _health(client: APIClient) -> dict:
    try:
        result = client.health()
    except APIClientError:
        st.warning("The catalogue service is offline. Start the local API, then refresh this page.")
        return {"components": {"search": False, "products": False, "query": False}}
    if not result["components"].get("search"):
        st.warning("Search is not ready yet. Check the catalogue and index setup.")
    return result


def _details(client: APIClient, product_id: str) -> dict | None:
    cache = st.session_state.setdefault("product_details", {})
    if product_id not in cache:
        try:
            cache[product_id] = client.product(product_id)
        except APIClientError:
            return None
    return cache[product_id]


def _source(item: dict) -> None:
    url = safe_url(item.get("source_url"))
    if url:
        st.link_button("View catalogue source ↗", url, use_container_width=True)
    else:
        st.caption("Source link unavailable")


def _search_form(ready: bool) -> tuple[bool, dict]:
    with st.form("phone_search"):
        query = st.text_input(
            "Search phones", key="search_terms", placeholder="Try a phone, brand or specification…"
        )
        price_col, ram_col, storage_col, rating_col = st.columns(4)
        price = price_col.number_input(
            "Budget up to (₹)",
            min_value=0,
            value=0,
            step=5000,
            help="0 means no price limit. Prices are catalogue snapshots.",
        )
        ram = ram_col.selectbox(
            "Minimum RAM",
            (0, 4, 6, 8, 12, 16),
            format_func=lambda n: "Any RAM" if n == 0 else f"{n} GB",
        )
        storage = storage_col.selectbox(
            "Minimum storage",
            (0, 64, 128, 256, 512, 1024),
            format_func=lambda n: "Any storage" if n == 0 else f"{n} GB",
        )
        rating = rating_col.selectbox(
            "Minimum rating",
            (0.0, 3.0, 3.5, 4.0, 4.5),
            format_func=lambda n: "Any rating" if n == 0 else f"{n:g} / 5",
        )
        with st.expander("Brands & search settings"):
            st.caption(
                "Need a different minimum? Optional custom values override the presets above."
            )
            custom_ram = st.number_input("Custom minimum RAM (GB)", min_value=0.0, value=None)
            custom_storage = st.number_input(
                "Custom minimum storage (GB)", min_value=0.0, value=None
            )
            custom_rating = st.number_input(
                "Custom minimum rating", min_value=0.0, max_value=5.0, value=None
            )
            included = st.text_input(
                "Include brands (comma-separated)", placeholder="Samsung, OnePlus"
            )
            excluded = st.text_input("Exclude brands (comma-separated)")
            mode = st.selectbox("Retrieval mode", ("hybrid", "bm25", "semantic"))
            alpha = st.slider("BM25 weight", 0.0, 1.0, 0.25, 0.05)
            limit = st.selectbox("Maximum results", (6, 12, 24, 50), index=1)
        submitted = st.form_submit_button(
            "Find phones", type="primary", disabled=not ready, use_container_width=True
        )
    return submitted, {
        "query": query.strip(),
        "mode": mode,
        "alpha": alpha,
        "limit": limit,
        "constraints": {
            "max_price_inr": float(price) if price else None,
            "min_ram_gb": custom_ram if custom_ram is not None else float(ram) if ram else None,
            "min_storage_gb": (
                custom_storage
                if custom_storage is not None
                else float(storage)
                if storage
                else None
            ),
            "min_rating_5": custom_rating
            if custom_rating is not None
            else rating
            if rating
            else None,
            "included_brands": _brands(included),
            "excluded_brands": _brands(excluded),
        },
    }


def _search_tab(client: APIClient, health: dict) -> None:
    for column, (label, query) in zip(st.columns(3), _EXAMPLES.items(), strict=True):
        column.button(
            label,
            key=f"example_{label}",
            on_click=_prefill,
            args=(query,),
            use_container_width=True,
        )
    submitted, payload = _search_form(health["components"].get("search", False))
    if submitted:
        st.session_state.pop("search_response", None)
        st.session_state["result_page"] = 1
        if not payload["query"]:
            st.warning("Enter a phone, brand or specification to start your search.")
        else:
            try:
                with st.spinner("Finding phones that match your filters…"):
                    st.session_state["search_response"] = client.search(payload)
                selected = st.session_state["shortlist"]
                st.session_state["product_details"] = {
                    k: v for k, v in st.session_state["product_details"].items() if k in selected
                }
            except APIClientError as error:
                st.error(f"Search could not finish. {error}")
    response = st.session_state.get("search_response")
    if response is None:
        _empty(
            "Your next phone starts here.",
            "Choose an example or search above. "
            "Add up to three phones to compare their specifications.",
        )
        return
    results = response["results"]
    st.subheader(f"{len(results)} phones found")
    st.caption(
        f"Results for “{response['query']}” · ordered by relevance · submitted filters applied"
    )
    with st.expander("Applied filters & ranking details"):
        st.json(response["constraints"], expanded=False)
        st.caption(f"Method: {response['mode']} · BM25 weight: {response['alpha']}")
    if not results:
        _empty(
            "No phones match this search.",
            "Try a broader term or adjust the filters, then search again. "
            "Your limits are never relaxed automatically.",
        )
        return
    pages = ceil(len(results) / 6)
    page = (
        st.selectbox(
            "Results page",
            range(1, pages + 1),
            key="result_page",
            format_func=lambda n: f"Page {n} of {pages}",
        )
        if pages > 1
        else 1
    )
    visible = results[(page - 1) * 6 : page * 6]
    for offset in range(0, len(visible), 3):
        for column, item in zip(st.columns(3), visible[offset : offset + 3], strict=False):
            with column, st.container(border=True):
                detail = (
                    _details(client, item["product_id"])
                    if health["components"].get("products")
                    else None
                )
                st.html(card_html(item, detail.get("image_url") if detail else None))
                selected = item["product_id"] in st.session_state["shortlist"]
                st.button(
                    "Remove from compare" if selected else "Add to compare",
                    key=f"pick_{item['product_id']}",
                    on_click=_toggle_shortlist,
                    args=(item,),
                    disabled=not selected and len(st.session_state["shortlist"]) >= 3,
                    use_container_width=True,
                    type="primary" if selected else "secondary",
                )
                _source(item)
    st.caption(
        "Catalogue records, not current stock or live prices. Images belong to their source."
    )


def _comparison_html(products: list[dict]) -> str:
    headers = "".join(f'<th scope="col">{escape(p["product_name"])}</th>' for p in products)
    rows = []
    for field, label, suffix in _COMPARISON_FIELDS:
        values = "".join(
            f"<td>{escape(display_value(p.get(field), suffix))}</td>" for p in products
        )
        rows.append(f'<tr><th scope="row">{escape(label)}</th>{values}</tr>')
    return (
        '<div class="sr-compare-wrap" role="region" '
        'aria-label="Phone comparison table" tabindex="0">'
        '<table class="sr-compare">'
        "<caption>Catalogue specifications · not an AI recommendation</caption>"
        f'<thead><tr><th scope="col">Specification</th>{headers}</tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def _compare_tab(client: APIClient) -> None:
    selected = st.session_state["shortlist"]
    st.subheader(f"Your shortlist · {len(selected)} / 3")
    st.caption("Compare stored specifications side by side. Missing values stay missing.")
    if not selected:
        _empty(
            "A little comparison goes a long way.",
            "Add two or three phones from Discover. "
            "Your shortlist stays while you try another search.",
        )
        return
    st.button("Clear shortlist", on_click=_clear_shortlist)
    products = []
    for column, summary in zip(st.columns(len(selected)), selected.values(), strict=True):
        with column:
            st.markdown(f"**{_markdown_text(summary['product_name'])}**")
            st.button(
                "Remove",
                key=f"remove_{summary['product_id']}",
                on_click=_toggle_shortlist,
                args=(summary,),
            )
            _source(summary)
        detail = _details(client, summary["product_id"])
        if detail is None:
            st.warning(
                f"Details unavailable for {_markdown_text(summary['product_name'])}. "
                "Showing basic search information; other specifications remain unavailable."
            )
        products.append(detail or summary)
    if len(products) < 2:
        st.info("Add one more phone in Discover to compare.")
    st.html(_comparison_html(products))
    st.caption(
        "No overall winner is implied. Ratings have no review counts; equal values remain equal."
    )


def _query_tab(client: APIClient, health: dict) -> None:
    st.subheader("Tell us what matters to you.")
    st.caption("Ask in your own words. Product claims are checked against catalogue evidence.")
    if not health["components"].get("query"):
        st.info("AI assistance is unavailable. Catalogue search can still work independently.")
    st.caption(
        "Example: Compare Samsung phones under ₹30,000 with 8 GB RAM "
        "by lowest price and highest rating."
    )
    with st.form("ask_ai"):
        request = st.text_area(
            "What are you looking for?",
            max_chars=2000,
            placeholder="Compare Samsung and OnePlus phones under ₹30,000…",
        )
        with st.expander("Add conversation context (optional)"):
            context = st.text_area(
                "Previous messages", help="One message per line; up to ten lines."
            )
        st.caption(
            "Questions and context go to the configured AI provider. "
            "Do not include private information."
        )
        submitted = st.form_submit_button(
            "Ask SearchRank", type="primary", disabled=not health["components"].get("query", False)
        )
    if submitted:
        st.session_state.pop("ai_response", None)
        messages = [line.strip() for line in context.splitlines() if line.strip()]
        if not request.strip():
            st.warning("Describe the phones or comparison you want.")
        elif len(messages) > 10 or any(len(line) > 2000 for line in messages):
            st.warning("Use at most ten context messages, with no more than 2,000 characters each.")
        else:
            try:
                with st.spinner("Searching the catalogue and checking the evidence…"):
                    st.session_state["ai_response"] = client.query(
                        {"request": request.strip(), "conversation_context": messages}
                    )
                    st.session_state["ai_request"] = request.strip()
            except APIClientError as error:
                st.error(f"AI assistance could not finish. {error}")
    response = st.session_state.get("ai_response")
    if not response:
        return
    st.caption(f"Answer to: {st.session_state['ai_request']}")
    verification = response.get("verification")
    if response["status"] == "answered" and verification and verification.get("passed"):
        st.success("Product claims checked against catalogue evidence")
    else:
        st.info(f"Request status: {response['status'].replace('_', ' ')}")
    st.markdown(response["response"])
    with st.expander("Sources, filters & workflow evidence"):
        st.caption(f"Status: {response['status']} · Retry count: {response['retry_count']}")
        st.write("Applied constraints", response["constraints"])
        st.write("Retrieved product IDs", response["retrieved_product_ids"])
        st.write("Path", " → ".join(response["workflow_path"]))
        st.write("Tool calls", response["tool_history"])
        st.write("Verification", verification)


def main() -> None:
    st.set_page_config(
        page_title="SearchRank-AI · Find your next phone", page_icon="🔎", layout="wide"
    )
    st.html(STYLE)
    for key in ("shortlist", "product_details"):
        st.session_state.setdefault(key, {})
    st.html(
        '<div class="sr-masthead"><div class="sr-logo">SearchRank<span>AI</span></div>'
        '<div class="sr-edition">Smartphone catalogue<br>Search. Compare. Decide.</div></div>'
        '<div class="sr-eyebrow">LESS GUESSWORK. MORE EVIDENCE.</div>'
    )
    st.title("Find your next phone.")
    st.html(
        '<div class="sr-intro">Explore the specs. Set your limits. Find the phones that fit.</div>'
    )
    client = _client()
    health = _health(client)
    discover, compare, ask = st.tabs(("Discover", "Compare phones", "Ask AI"))
    with discover:
        _search_tab(client, health)
    with compare:
        _compare_tab(client)
    with ask:
        _query_tab(client, health)
    st.html(
        '<div class="sr-footer">SearchRank-AI · An evidence-grounded portfolio project. '
        "Catalogue prices and specifications are historical snapshots, not live offers.</div>"
    )


if __name__ == "__main__":
    main()
