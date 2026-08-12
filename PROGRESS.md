# ShopSense AI Search — Build Log

## Day 1: Defining the Product and the Data Model
**The framing:** rather than building a generic "AI search demo," the project centers on a real, defensible business problem — ShopSense's legacy keyword search fails on roughly 15-20% of queries, returning zero results even when relevant products exist. The whole project is structured around answering one specific question: *should ShopSense ship AI search to everyone?*

**What came out of this day:**
- A product definition, a problem statement written the way a PM would frame it, and a clear decision the analysis needs to support
- A table of the metrics that actually matter here — zero-result rate, CTR, conversion, retention, DAU/WAU, plus guardrails
- The funnel: Search → Results → Click → Cart → Purchase
- A full event schema covering every action worth tracking (searches, clicks, cart adds, purchases, sessions, experiment assignments, the products table)

**File:** `schema/event_schema.md`

---

## Day 2: Building the Catalog, the Retrieval Engine, and the Synthetic Data

**Product catalog** (`src/data_generation/generate_products.py`)
Generated 255 distinct fake products spread across six categories — footwear, outdoor gear, kitchen items, apparel, electronics, and gifts.
*Bug hit:* the script originally assumed it would always run from the project's root folder, using a plain relative path like `"data/raw/products.csv"`. That broke the moment it got run from a different working directory (which happens by default in PyCharm). Fixed it by resolving all paths relative to the script's own file location instead of assuming a fixed starting point.

**Embedding and vector search setup** (`src/embeddings/build_embeddings.py`)
Uses `sentence-transformers` (specifically `all-MiniLM-L6-v2`, which runs entirely on your machine — no API key needed) to turn each product's title and description into an embedding. Those embeddings get indexed with FAISS, enabling real cosine-similarity search. This module also exposes the `semantic_search()` function that the event simulator calls later.
Testing it with a handful of sample queries confirmed it works well on broad, typo-heavy, or loosely worded searches ("cozy warm gift for hiking" correctly pulled up sweaters, jackets, and boots). It also surfaced a real, worth-noting limitation: queries that fall between visually similar categories — like searching for a coffee maker when blenders and mixing bowls are also nearby in the embedding space — rank a bit weaker, likely because the product descriptions aren't detailed enough to fully separate them. That's a legitimate finding about the system's limits, not something broken.

**Simulating user behavior** (`src/data_generation/generate_events.py`)
Simulates 800 users split evenly into control (legacy search) and treatment (AI search) over a two-week window. Legacy search works via naive keyword overlap — which is exactly what creates the zero-result problem by design. AI search runs through the actual FAISS retrieval built above. Click, cart, and purchase behavior are all weighted by how relevant the search results actually were, so the simulated data reflects a real pattern: better results lead to better outcomes, not just fewer empty searches.
*Bug hit, and a more interesting one:* search event IDs were originally built from just the user, the day, and the session — with no way to distinguish multiple searches happening within that same session. Since a session could easily contain 2-3 searches, this caused duplicate IDs, which then silently collapsed rows whenever `COUNT(DISTINCT ...)` got used in SQL, and worse, caused a join fan-out that inflated total revenue when purchases matched against duplicate search rows. Fixed by tagging every event ID with a per-search index, making search, click, cart, and purchase IDs all genuinely unique. Regenerated the dataset afterward.

**Getting everything into a database** (`src/sql/load_to_sqlite.py`)
Pulls all the generated CSVs into one SQLite database, with indexes added on the columns used for joins, so the SQL work in the next step runs cleanly.

---

## Day 3: The SQL Layer
**File:** `src/sql/analytics_queries.sql`, run through `src/analysis/run_analytics.py`

Ten queries in total, covering zero-result rate, CTR, the full funnel (broken down step by step), AI search adoption, DAU, WAU, 7-day retention, search success rate, latency, and revenue per search — every one of them split by control vs. treatment.

*Bug hit:* not in the SQL itself, but in the Python script that runs it — the logic meant to split the file into labeled query blocks was mistakenly treating any block that opened with a comment line as "empty" and skipping it entirely, which silently dropped two queries (zero-result rate and retention) from the printed output. Once the parsing logic was corrected, all ten queries ran and displayed properly.

**What came out of it, once the earlier data bug was fixed:**
| Metric | Control | Treatment |
|---|---|---|
| Zero-result rate | 2.48% | 0.00% |
| CTR | 43.76% | 52.05% |
| Search → Purchase | 12.20% | 16.46% |
| Revenue / search | $18.58 | $19.17 |
| Avg latency | 90ms | 179ms |
| 7-day retention | 90.93% | 90.16% |

---

## Day 4 + Day 6 (done together): Testing Whether the Difference Is Real
**File:** `experiment/ab_significance_test.py`

Ran two-proportion z-tests on zero-result rate, CTR, and search-to-purchase conversion, plus a Welch's t-test on revenue per search — each with a 95% confidence interval attached.

*Bug hit:* a path-resolution mistake, similar in spirit to the Day 2 one but the opposite direction — the script copied a `parents[2]` path calculation from other scripts that live two folders deep, but this one only lives one folder deep (`experiment/`), so it ended up climbing one level too high and looking for the database outside the actual project folder. Fixed by adjusting it to `parents[1]`.

**What it found:**
| Metric | p-value | Real, or just noise? |
|---|---|---|
| Zero-result rate | <0.001 | ✅ Real |
| CTR | <0.001 | ✅ Real |
| Search → Purchase | <0.001 | ✅ Real |
| Revenue per search | 0.706 | ❌ Can't tell — too much noise |

**What it means:** AI search produces a clear, statistically solid improvement in search quality and conversion. Revenue moved in the right direction but not by an amount we can confidently call "real" yet — which makes sense given how variable purchase amounts are, and is an honest finding rather than something to smooth over.

---

## Patterns Worth Remembering for Next Time
1. **Don't hardcode relative paths.** Always resolve them relative to the script's own location, and double-check that `parents[N]` actually matches how deep the script sits.
2. **Red squiggles in an IDE aren't the same as a broken program.** PyCharm can't always trace things like a runtime `sys.path` change, so it'll flag something as "unresolved" even when the code runs perfectly. Trust what actually happens when you run it (`exit code 0`) over what the editor guesses.
3. **Non-unique IDs break things quietly, not loudly.** `COUNT(DISTINCT ...)` and joins on a key that isn't actually unique won't throw an error — they'll just give you a wrong number that looks plausible. Cross-checking totals between independent queries is what caught this here.
4. **A warning isn't a failure.** Only a full traceback ending in a raised exception and a non-zero exit code actually means something broke.

---

## What's Left
- **Day 5:** an interactive dashboard pulling together everything above
- **Day 7:** the final write-up — the actual case for shipping (or not)