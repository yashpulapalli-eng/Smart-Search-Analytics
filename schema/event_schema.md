# ShopSense AI Search — Product Definition & Event Schema

## 1. Product Definition
**Product:** ShopSense — a mid-size e-commerce marketplace
**Feature:** AI-powered semantic search, replacing legacy exact-keyword search
**How it works technically:** Product titles/descriptions are converted into embeddings and stored in a vector database (FAISS/Chroma). When a user searches, their query is embedded and matched against the nearest product vectors — enabling matches based on meaning, not just literal keyword overlap (handles synonyms, typos, natural-language queries).
**Target users:** All shoppers using the search bar (guest + logged-in)

## 2. PM Problem Statement
Legacy keyword search returns zero results for ~15-20% of queries — typos, synonyms, or natural-language phrasing ("warm shoes for winter") that don't literally match product titles. These are searches where relevant inventory exists; we're just failing to surface it. Each zero-result search is a shopper who may abandon or buy elsewhere. AI-powered semantic search should recover a meaningful share of these lost searches.

**Decision this analysis supports:** Should we roll out AI search to 100% of traffic?

## 3. Core Metrics

| Metric | Definition |
|---|---|
| Zero-result rate (primary) | % of searches returning 0 products |
| Search success rate | % of searches followed by a result click within the same session, within 30s |
| AI Search adoption | % of treatment-group sessions that issue ≥1 search |
| CTR (search → click) | Clicks / searches |
| Conversion (search → purchase) | Purchases attributed to a search session / searches |
| Session duration | Time from first to last event in session |
| 7-day retention | % of day-0 active users returning in days 1–7 |
| DAU / WAU | Segmented by treatment/control |
| Guardrail: search latency (p50/p95) | Query submit → results rendered |
| Guardrail: reformulation rate | % of searches followed by another search within 10s |
| Guardrail: click precision | Of clicked results, % that lead to add-to-cart |

## 4. Funnel
Search issued → Non-zero results returned → Result clicked → Add to cart → Purchase

## 5. Event Schema

```
event: search_performed
  - event_id, user_id, session_id, timestamp
  - query_text, query_length
  - search_variant ("legacy" | "ai_semantic")
  - result_count (int)
  - latency_ms
  - top_result_similarity_score (float, ai_semantic only)

event: result_clicked
  - event_id, user_id, session_id, timestamp
  - search_event_id (FK)
  - product_id, result_position

event: add_to_cart
  - event_id, user_id, session_id, timestamp
  - product_id, search_event_id (FK, nullable)

event: purchase_completed
  - event_id, user_id, session_id, timestamp
  - order_id, product_ids[], revenue, search_event_id (FK, nullable)

event: session_start / session_end
  - session_id, user_id, timestamp, device_type

table: experiment_assignments
  - user_id, experiment_name, variant ("control"|"treatment"), assigned_at

table: products (vector DB / retrieval layer)
  - product_id, title, description, category, price, embedding_vector
```