# Smart Search Analytics

A product analytics and experimentation platform built to test whether AI-powered semantic search actually improves the shopping experience on an e-commerce site. The project covers the full pipeline: event tracking design, a working embedding/vector-search engine, SQL-based analysis, a properly randomized A/B test with statistical significance testing, a live dashboard, and a final write-up with a ship/no-ship recommendation.

> A quick note on naming: this repo is called `Smart-Search-Analytics`, but the case study inside it is framed around a made-up online retailer, **ShopSense** — invented purely to give the analysis a concrete setting to work through, the way a business-school case study might use a fictional company name. The repo title reflects what the project does; ShopSense is just the pretend storefront the analysis is built around.

---

## The Problem Being Investigated

ShopSense's existing search only matches exact keywords, and roughly 1 out of every 40 searches comes back empty — not because the store lacks the product, but because the search engine can't handle a typo, a synonym, or a query phrased in plain language instead of matching product-listing text word-for-word. The project sets out to answer a concrete business question: **is it worth replacing that search system with an AI-driven version across all traffic?**

**Short answer: yes** — the reasoning and evidence are laid out in full in [`case_study/case_study.md`](./case_study/case_study.md).

---

## Repository Layout

| Folder | What's in it |
|---|---|
| `schema/` | Product framing, event definitions, and the metrics tracked (Day 1) |
| `src/data_generation/` | Scripts that build the synthetic product catalog and simulate user/session/search behavior (Day 2) |
| `src/embeddings/` | The embedding pipeline and FAISS-based vector search — this is the actual retrieval engine behind "AI search" |
| `src/sql/` | Database loading script plus the core SQL queries used for analysis (Day 3) |
| `src/analysis/` | Python scripts that run the SQL analytics and regenerate the dashboard |
| `experiment/` | The formal A/B significance testing — z-tests, t-tests, confidence intervals (Day 6) |
| `dashboard/` | A live HTML dashboard that pulls current numbers straight from the database each time it's rebuilt |
| `case_study/` | The final decision memo (Day 7) |
| `PROGRESS.md` | A running log of the build, including the actual bugs hit and how they were resolved |

---

## Tools Used

- **Analysis:** Python (pandas, numpy), SQLite
- **Retrieval / AI layer:** `sentence-transformers` for local embeddings (no external API needed) plus FAISS for similarity search — a stripped-down, retrieval-only version of a RAG setup
- **Stats:** scipy — two-proportion z-tests, Welch's t-test, 95% confidence intervals
- **Dashboard:** plain HTML/CSS/JS, rebuilt from live SQL and statistical results each time it runs

---

## Headline Findings

| Metric | Legacy Search | AI Search | p-value | Significant? |
|---|---|---|---|---|
| Zero-result rate | 2.48% | 0.00% | <0.001 | ✅ |
| Click-through rate | 43.76% | 52.05% | <0.001 | ✅ |
| Search → Purchase conversion | 12.20% | 16.46% | <0.001 | ✅ |
| Revenue per search | $18.58 | $19.17 | 0.706 | ❌ (not conclusive) |

The full reasoning behind these numbers, plus an honest look at what the analysis doesn't prove, is in [`case_study/case_study.md`](./case_study/case_study.md).

---

## Running It Yourself

```bash
git clone https://github.com/yashpulapalli-eng/Smart-Search-Analytics.git
cd Smart-Search-Analytics
python -m venv venv
source venv/Scripts/activate   # Git Bash on Windows
pip install -r requirements.txt

# Build the pipeline in order
python src/data_generation/generate_products.py
python src/embeddings/build_embeddings.py
python src/data_generation/generate_events.py
python src/sql/load_to_sqlite.py

# Run the analysis
python src/analysis/run_analytics.py
python experiment/ab_significance_test.py

# Rebuild the dashboard
python src/analysis/generate_dashboard.py
```

Once that's done, just open `dashboard/index.html` in a browser — nothing else needs to be running.

---

## Why I Built This

This started as a way to demonstrate product analytics and experimentation skills — problem framing, metric design, proper A/B testing, and applied retrieval/AI work — relevant to product management, data analysis, and AI engineering roles alike. `PROGRESS.md` has the unfiltered build log, including real bugs that came up along the way (a data-integrity issue with duplicate IDs, a couple of path-resolution mistakes, an encoding bug) — working through those is as much a part of the story as the final numbers.