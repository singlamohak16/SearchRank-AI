# Five-minute demonstration

This is a speaking guide, not a recording of a live sales service. Use the historical-price notice
throughout. Complete [setup](SETUP.md), check readiness, and open the website before presenting.
Never display credentials or environment/container inspection output.

## Walkthrough

1. **0:00–0:40 — Explain the problem.** “I built a smartphone catalogue assistant that combines
   search with traceable evidence. It does not fetch live prices or invent missing specifications.”
2. **0:40–1:40 — Discover.** Search for `Samsung Galaxy`, select Samsung, maximum price INR 30,000,
   minimum RAM 8 GB, minimum storage 128 GB. Inspect results and the lexical/semantic scores.
   Explain that Python enforces the filters before ranking.
3. **1:40–2:30 — Compare phones.** Add two results to the shortlist and open Compare phones.
   Point to stored price, RAM, storage, source links, and any unavailable fields. This comparison
   works without an LLM; it is not a claim about current availability or overall product quality.
4. **2:30–3:40 — Optional Ask AI.** Only with a separately configured/approved provider, submit
   `Find Samsung phones under INR 30000 with at least 8 GB RAM and 128 GB storage.` Inspect the
   interpreted constraints, tool path, citations, and verification result. This sends a real request
   to the provider. Do not promise the response will match an earlier smoke test.
5. **3:40–4:20 — Show a boundary.** Use an impossible explicit budget in Discover to show an empty
   result, then reset it. For the AI route, explain that unknown facts are withheld; do not disguise
   a quota error or failed verification as a successful answer.
6. **4:20–5:00 — Explain the evidence.** Open [results](RESULTS.md): 20 retrieval judgments,
   16 scripted agent cases, semantic recall versus hybrid top-rank trade-off, and no held-out set.

**Without AI:** skip step 4 and show the scripted evaluator's statuses/tool paths instead. Clearly
label them mock-model decisions. Search and stored-specification comparison are a complete offline
demonstration; they are not equivalent to testing live language understanding.

## Search API request

Against a running local API:

```powershell
$request = @{
  query = 'Samsung Galaxy'
  mode = 'hybrid'
  alpha = 0.25
  limit = 1
  constraints = @{
    included_brands = @('Samsung')
    max_price_inr = 30000
    min_ram_gb = 8
    min_storage_gb = 128
  }
} | ConvertTo-Json -Depth 4
Invoke-RestMethod http://127.0.0.1:8000/search `
  -Method Post -ContentType 'application/json' -Body $request
```

The following **response excerpt** was actually captured on 2026-09-18 through the FastAPI
in-process TestClient using the real cached indexes and catalogue. It was not a live HTTP/container
test; the local server port was unavailable. Other response metadata and score components are
omitted here. Small floating-point differences may occur between runtimes.

```json
{
  "query": "Samsung Galaxy",
  "mode": "hybrid",
  "alpha": 0.25,
  "results": [
    {
      "rank": 1,
      "product_id": "91mobiles:samsung-galaxy-a26-256gb",
      "product_name": "Samsung Galaxy A26 256GB",
      "brand": "Samsung",
      "price_inr": 27999,
      "ram_gb": 8.0,
      "storage_gb": 256.0,
      "user_rating_5": 3.9,
      "source_url": "https://www.91mobiles.com/samsung-galaxy-a26-256gb-price-in-india",
      "score": 0.87025453
    }
  ]
}
```

These are snapshot values, not today's offer. With ingested storage, retrieve the same evidence by
ID (encode IDs rather than concatenating arbitrary unescaped input into URLs):

```powershell
$productId = [uri]::EscapeDataString('91mobiles:samsung-galaxy-a26-256gb')
Invoke-RestMethod "http://127.0.0.1:8000/products/$productId"
```

## Agent request and failure handling

Request body for `POST /query` (sending this can call the configured provider):

```json
{
  "request": "Find Samsung phones under INR 30000 with at least 8 GB RAM and 128 GB storage.",
  "conversation_context": []
}
```

An answered response includes rendered text and structured workflow/evidence diagnostics; do not
fabricate a deterministic live answer for this guide. A historical browser smoke test on 2026-09-17
returned `answered`, five verified facts, zero retries, and no verification issues for this request.
That observation is not a new Phase 8 provider test or an accuracy benchmark.

The search-only injected service used for the 2026-09-18 example returned this actual HTTP 503 body
for `/query`. A normally assembled mock-provider app may give a more specific configuration message:

```json
{
  "error": {
    "code": "service_unavailable",
    "message": "The query service is unavailable.",
    "details": []
  }
}
```

Invalid requests return 422, absent product IDs return 404, and unavailable services/providers
return sanitized 503 responses. Use [API contracts](API_AND_UI.md) for the full schemas and limits.
