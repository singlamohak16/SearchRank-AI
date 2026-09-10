"""One-page Streamlit demonstration that communicates only through FastAPI."""

from __future__ import annotations

import os
import string

import streamlit as st

from searchrank_ai.api_client import APIClient, APIClientError

_MARKDOWN_SPECIALS = frozenset(string.punctuation)


@st.cache_resource
def _client() -> APIClient:
    return APIClient(os.getenv("SEARCHRANK_API_URL", "http://127.0.0.1:8000"))


def _brands(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _markdown_text(value: str) -> str:
    """Render untrusted catalogue labels as one line of inert Markdown text."""
    one_line = value.replace("\r", " ").replace("\n", " ")
    return "".join(
        f"\\{character}" if character in _MARKDOWN_SPECIALS else character for character in one_line
    )


def _optional_number(label: str, *, default: float, maximum: float | None = None) -> float | None:
    enabled = st.checkbox(f"Use {label}")
    if not enabled:
        return None
    return st.number_input(label, min_value=0.0, max_value=maximum, value=default)


def _show_health(client: APIClient) -> None:
    try:
        health = client.health()
    except APIClientError as error:
        st.sidebar.error(str(error))
        return
    if health["status"] == "ok":
        st.sidebar.success("API ready")
    else:
        st.sidebar.warning("API partially configured")
        for component, message in health.get("errors", {}).items():
            st.sidebar.caption(f"{component}: {message}")


def _search_tab(client: APIClient) -> None:
    st.subheader("Catalogue search")
    query = st.text_input("Search terms", placeholder="Snapdragon AMOLED phone")
    first, second, third = st.columns(3)
    mode = first.selectbox("Retrieval mode", ("hybrid", "bm25", "semantic"))
    alpha = second.slider("BM25 weight", 0.0, 1.0, 0.25, 0.05)
    limit = third.number_input("Result limit", min_value=1, max_value=50, value=10)

    with st.expander("Strict filters"):
        max_price = _optional_number("maximum price (INR)", default=30_000.0)
        min_ram = _optional_number("minimum RAM (GB)", default=8.0)
        min_storage = _optional_number("minimum storage (GB)", default=128.0)
        min_rating = _optional_number("minimum rating (out of 5)", default=4.0, maximum=5.0)
        included = st.text_input("Include brands (comma-separated)")
        excluded = st.text_input("Exclude brands (comma-separated)")

    if not st.button("Search catalogue", type="primary"):
        return
    constraints = {
        "max_price_inr": max_price,
        "min_ram_gb": min_ram,
        "min_storage_gb": min_storage,
        "min_rating_5": min_rating,
        "included_brands": _brands(included),
        "excluded_brands": _brands(excluded),
    }
    try:
        response = client.search(
            {
                "query": query,
                "mode": mode,
                "alpha": alpha,
                "limit": int(limit),
                "constraints": constraints,
            }
        )
    except APIClientError as error:
        st.error(str(error))
        return

    results = response["results"]
    st.caption(f"{len(results)} result(s); strict filters were applied before ranking.")
    st.json(response["constraints"], expanded=False)
    for item in results:
        with st.container(border=True):
            st.markdown(f"### {item['rank']}. {_markdown_text(item['product_name'])}")
            st.write(
                f"{item['brand']} · ₹{item['price_inr']:,} · "
                f"{item['ram_gb']:g} GB RAM · {item['storage_gb']:g} GB storage"
            )
            rating = "Unavailable" if item["user_rating_5"] is None else item["user_rating_5"]
            st.caption(f"Rating: {rating} · Hybrid score: {item['score']:.4f}")
            st.link_button("Catalogue source", item["source_url"])


def _query_tab(client: APIClient) -> None:
    st.subheader("Ask or compare")
    request = st.text_area(
        "Natural-language request",
        placeholder="Compare Samsung and OnePlus phones under ₹30,000 by lowest price.",
    )
    context_text = st.text_area(
        "Optional conversation context",
        help="One prior message per line; at most ten lines.",
    )
    if not st.button("Run grounded workflow", type="primary"):
        return
    context = [line.strip() for line in context_text.splitlines() if line.strip()]
    try:
        response = client.query({"request": request, "conversation_context": context})
    except APIClientError as error:
        st.error(str(error))
        return

    st.markdown(response["response"])
    st.caption(f"Status: {response['status']} · Retry count: {response['retry_count']}")
    if response["constraints"] is not None:
        st.markdown("#### Extracted constraints")
        st.json(response["constraints"], expanded=False)
    with st.expander("Workflow evidence"):
        st.write("Path", " → ".join(response["workflow_path"]))
        st.write("Retrieved product IDs", response["retrieved_product_ids"])
        st.write("Tool calls", response["tool_history"])
        if response["verification"] is not None:
            st.write("Verification", response["verification"])


def main() -> None:
    st.set_page_config(page_title="SearchRank-AI", page_icon="🔎", layout="wide")
    st.title("SearchRank-AI")
    st.caption("Evidence-grounded smartphone search and comparison")
    client = _client()
    _show_health(client)
    search_tab, query_tab = st.tabs(("Search", "Ask / Compare"))
    with search_tab:
        _search_tab(client)
    with query_tab:
        _query_tab(client)


if __name__ == "__main__":
    main()
