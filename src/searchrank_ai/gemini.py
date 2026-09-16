"""Opt-in Gemini REST adapter; no paid fallback, automatic retries, or extra SDK."""

from __future__ import annotations

import json
from copy import deepcopy
from http.client import HTTPException
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from searchrank_ai.llm import ProviderUnavailableError, StructuredJSONProvider

# Explicitly reviewed free-tier candidate, not an assurance about account billing.
SUPPORTED_MODELS = frozenset({"gemini-3.1-flash-lite"})
MAX_RESPONSE_BYTES = 1_000_000


def _unique_winner(evidence: list[dict[str, Any]], field: str, direction: str) -> str | None:
    """A tie or missing value cannot support a sole winner across retrieved products."""
    values = {product["product_id"]: product.get(field) for product in evidence}
    if len(values) < 2 or any(
        not isinstance(value, (int, float)) or isinstance(value, bool) for value in values.values()
    ):
        return None
    target = min(values.values()) if direction == "lower" else max(values.values())
    winners = [product_id for product_id, value in values.items() if value == target]
    return winners[0] if len(winners) == 1 else None


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not forward the authentication header to another endpoint.
        return None


class GeminiProvider(StructuredJSONProvider):
    """Keep the existing evidence contract while using Gemini structured output."""

    def __init__(self, model: str, api_key: str, *, opener: Any = None) -> None:
        if model.strip() not in SUPPORTED_MODELS:
            raise ValueError("Gemini model is not in the reviewed free-tier model allowlist")
        if not api_key.strip() or any(not 33 <= ord(char) <= 126 for char in api_key.strip()):
            raise ValueError("Gemini requires GEMINI_API_KEY")
        self.model = model.strip()
        self._api_key = api_key.strip()
        self._opener = opener if opener is not None else build_opener(_NoRedirect())

    def _request_json(
        self, operation: str, instructions: str, payload: dict[str, Any], schema: dict[str, Any]
    ) -> dict[str, Any]:
        schema = deepcopy(schema)
        if operation == "request_analysis":
            schema["properties"]["comparison_criteria"]["items"]["enum"] = list(
                payload["comparison_rules"]
            )
            instructions += (
                " comparison_criteria must contain exact comparison_rules keys, not field names"
                " or invented codes. If a requested criterion is unsupported, ask a clarification"
                " question naming it or mark the request unsupported. Never substitute another"
                " criterion. For example, lowest price maps to 'lowest price', not price_inr_lower."
            )
        if operation == "grounded_answer_draft":
            comparisons = schema["properties"]["comparisons"]
            evidence = payload["catalogue_data"]
            if evidence:
                ids = [product["product_id"] for product in evidence]
                citation_schema = {
                    "anyOf": [
                        {
                            "type": "object",
                            "properties": {
                                "product_id": {"type": "string", "enum": [product["product_id"]]},
                                "source_url": {"type": "string", "enum": [product["source_url"]]},
                            },
                            "required": ["product_id", "source_url"],
                            "additionalProperties": False,
                        }
                        for product in evidence
                    ]
                }
                facts = schema["properties"]["facts"]["items"]["properties"]
                facts["product_id"]["enum"] = ids
                facts["citation"] = citation_schema
                comparison_properties = comparisons["items"]["properties"]
                comparison_properties["product_ids"]["items"]["enum"] = ids
                comparison_properties["preferred_product_id"]["enum"] = ids
                comparison_properties["citations"]["items"] = citation_schema
                schema["properties"]["unavailable_information"]["items"]["properties"][
                    "product_id"
                ]["enum"] = ids
            criteria = payload["comparison_criteria"]
            if payload["request_type"] == "compare" and criteria:
                variants = []
                comparison_notes = []
                for criterion in criteria:
                    item = deepcopy(comparisons["items"])
                    properties = item["properties"]
                    properties["criterion"]["enum"] = [criterion]
                    rule = payload["comparison_rules"].get(criterion.strip().casefold())
                    if rule is not None:
                        properties["field"]["enum"] = [rule[0]]
                        if rule[1] is not None:
                            properties["preference"]["enum"] = [rule[1]]
                            if evidence:
                                winner = _unique_winner(evidence, rule[0], rule[1])
                                if winner is None:
                                    comparison_notes.append(
                                        f"{criterion}: no sole winner across retrieved products. "
                                        f"Report every product's {rule[0]} as facts "
                                        "(or unavailable if missing); do not emit a comparison "
                                        "for this criterion."
                                    )
                                    continue
                                properties["preferred_product_id"]["enum"] = [winner]
                    variants.append(item)
                if variants:
                    comparisons["items"] = {"anyOf": variants}
                else:
                    comparisons["maxItems"] = 0
                payload = {**payload, "comparison_notes": comparison_notes}
            else:
                comparisons["maxItems"] = 0
            instructions += (
                " Copy criterion strings exactly from comparison_criteria, without paraphrasing."
                " For search requests return an empty comparisons array."
                " Each fact's citation.product_id must equal that fact's product_id."
                " Each comparison must cite EVERY product in its product_ids, exactly once,"
                " with no extra products. Five compared IDs require five citations, not two."
                " Copy each cited product's exact source_url from catalogue_data."
                " Only propose a preferred product when its numeric value uniquely wins;"
                " for ties report the factual values without inventing a winner."
                " Follow comparison_notes. Compare the full retrieved group, not a subset"
                " selected to hide a tie."
                " Keep facts concise: for comparisons report product names and the requested"
                " comparison fields only; for searches report name, price, RAM, storage,"
                " and rating when available. Do not repeat every catalogue field."
            )
        body = {
            "systemInstruction": {"parts": [{"text": instructions}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": json.dumps(payload, ensure_ascii=False, default=str)}],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": schema,
                "temperature": 0,
                "candidateCount": 1,
                "maxOutputTokens": 4000,
                "thinkingConfig": {"thinkingLevel": "minimal"},
            },
        }
        request = Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": self._api_key},
            method="POST",
        )
        try:
            with self._opener.open(request, timeout=25) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as error:
            status = error.code
            error.close()
            messages = {
                429: "Gemini quota/rate limit reached. Wait and check AI Studio; do not upgrade.",
                401: "Gemini authentication failed. Check the locally saved key.",
                403: "Gemini access denied. Check key permissions and regional availability.",
                404: "The configured Gemini model is unavailable for this API/project.",
            }
            raise ProviderUnavailableError(
                messages.get(
                    status,
                    f"Gemini rejected {operation} (HTTP {status}). No retry was attempted.",
                )
            ) from None
        except (URLError, OSError, HTTPException):
            raise ProviderUnavailableError("Gemini could not be reached or timed out.") from None
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ProviderUnavailableError("Gemini returned an oversized response.")
        try:
            envelope = json.loads(raw)
            if envelope.get("promptFeedback", {}).get("blockReason"):
                raise ValueError
            candidate = envelope["candidates"][0]
            if candidate.get("finishReason") != "STOP":
                raise ValueError
            parts = candidate["content"]["parts"]
            text = "".join(part["text"] for part in parts if not part.get("thought", False))
            result = json.loads(text)
            if not isinstance(result, dict):
                raise ValueError
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            raise ProviderUnavailableError(
                "Gemini returned a blocked, incomplete, or invalid structured response."
            ) from None
        return result
