# ShopSense AI Search — Case Study & Ship Recommendation

**Author:** SRIYASHVEER PULAPALLI
**Date:** August 2026
**Status:** Experiment complete 

---

## 1. Background

ShopSense's current product search only works through exact keyword matching — a query has to literally share words with a product's title or description to return anything. Digging into the legacy system's performance showed that about **1 out of every 40 searches came back with zero results**, and in nearly all of those cases, relevant products actually existed in the catalog. The search engine simply couldn't bridge the gap between how people naturally phrase things and how products happen to be labeled — a misspelling, a synonym, or a request like "warm shoes for winter" failing to match a listing titled "Insulated Boots."

Every one of those failed searches represents a shopper who might just leave, quietly, without buying anything — and possibly go straight to a competitor. It's a loss that rarely shows up cleanly in standard dashboards, since all you see is a session ending, not *why* it ended.

**The question this analysis was built to answer:** is it worth rolling AI-powered semantic search out to every user?

---

## 2. What Was Built

The proposed fix replaces keyword search with a semantic search engine:

- Every product's title and description gets converted into a vector embedding, using `sentence-transformers` running entirely locally
- Those embeddings live in a FAISS index, which allows retrieval based on *meaning* rather than exact word overlap — so typos, synonyms, and conversational phrasing can still surface the right products
- Architecturally, this is a retrieval-only slice of a RAG pipeline — no generative component, which keeps things fast, predictable, and easy to reason about

---

## 3. How the Experiment Was Run

- **Design:** Randomized A/B test
- **Sample:** 800 users, split 50/50 at the user level
  - **Control group:** old keyword search
  - **Treatment group:** new AI semantic search
- **Window:** 14 days, June 1 through June 14, 2026
- **Volume:** 5,678 searches total (2,902 in control, 2,776 in treatment)
- **Main metric:** zero-result rate
- **Supporting metrics:** click-through rate, search-to-purchase conversion, revenue per search
- **Guardrails watched:** search latency, 7-day retention

---

## 4. What the Data Showed

| Metric | Control | Treatment | Change | p-value | Statistically real? |
|---|---|---|---|---|---|
| Zero-result rate | 2.48% | 0.00% | −2.48pp | <0.001 | ✅ Yes |
| Click-through rate | 43.76% | 52.05% | +8.29pp | <0.001 | ✅ Yes |
| Search → Purchase | 12.20% | 16.46% | +4.26pp | <0.001 | ✅ Yes |
| Revenue per search | $18.58 | $19.17 | +$0.59 | 0.706 | ❌ No |

**Guardrail checks:**
| Metric | Control | Treatment | Notes |
|---|---|---|---|
| Avg. search latency | 90ms | 179ms | +99ms slower — a genuine cost worth watching, not a red flag |
| 7-day retention | 90.93% | 90.16% | −0.77pp — essentially no difference |

The full statistical work — z-tests, Welch's t-test, confidence intervals — lives in `experiment/ab_significance_test.py`, with additional detail in `PROGRESS.md`.

---

## 5. Making Sense of the Numbers

**The core story is strong: AI search clearly improves the search experience and what happens afterward.** People in the treatment group were meaningfully more likely to click something worth clicking (a roughly 19% relative jump in CTR) and meaningfully more likely to actually buy (about a 35% relative lift in conversion). And the zero-result problem — the whole reason this project exists — essentially disappeared for treatment users.

**Revenue is a different story, and it's worth explaining rather than glossing over.** A $0.59 average increase sounds promising, but the confidence interval spans from roughly −$2.47 to +$3.65 — wide enough that we can't rule out this being noise. That's not surprising once you consider how revenue behaves as a metric: most searches generate zero dollars, and the ones that do convert vary wildly (an $8 candle versus a $350 tent), so detecting a small shift in the *average* takes either a much bigger sample or a longer test. **This reflects a limitation in the data, not a weakness in the underlying case for AI search** — every metric that measures actual user behavior, rather than dollar-value noise, moved clearly in the right direction.

**The latency increase is real but doesn't appear to be costing anything measurable.** The added ~100ms is worth keeping an eye on post-launch, especially since real infrastructure conditions could stretch that gap further, but it didn't translate into any visible retention drop here.

---

## 6. The Call

### ✅ Ship AI semantic search to all traffic.

The main hypothesis — that semantic search meaningfully cuts down zero-result searches and improves what happens after someone searches — holds up with strong statistical backing (p < 0.001 across all three behavioral metrics). Nothing about this recommendation depends on the revenue number panning out; the case is solid without it.

**How I'd suggest rolling it out:**
1. Launch to 100% of traffic, but keep tracking revenue per search closely — at full volume, the sample size grows fast enough that the revenue question could likely be resolved within a few weeks.
2. Keep an eye on latency in production, particularly for mobile or slower connections, since the simulated gap here may understate what happens under real load.
3. Re-check zero-result rate and CTR on a monthly basis post-launch, since search quality can quietly degrade as the catalog grows and changes.

---

## 7. What This Analysis Doesn't Cover

Worth stating plainly rather than leaving out:

- **Adoption wasn't a useful metric here**, since every simulated session included at least one search by design — so "adoption" came out at 100% for both groups regardless. A real measurement of adoption would need sessions where users browse without ever searching.
- **Search success rate ended up mathematically identical to CTR** in this dataset, because every simulated click happened well within the 30-second success window. In a live product, these two numbers would likely diverge and should be tracked as distinct signals.
- **The underlying data is simulated**, not pulled from real traffic — the probabilities behind clicks, cart adds, and purchases were built on reasonable assumptions rather than measured real-world behavior. That said, the *process* — the schema design, the SQL work, the significance testing — is exactly what would carry over to a live rollout; it's the specific numbers that are illustrative rather than observed.
- **Revenue's high variance is baked into the metric itself**, not a flaw in how the experiment was run. A logical next step would be either a larger sample or a variance-reduction approach like CUPED to actually settle the revenue question.

---

## 8. What This Project Is Meant to Show

- The ability to frame a product problem around a specific, measurable metric instead of a vague feature idea
- A complete analytics build: schema design → synthetic data → SQL → statistical testing → a live dashboard
- Real experimentation discipline — proper randomization, the right significance tests, confidence intervals — not just comparing two numbers and calling it a day
- Judgment that doesn't overreach: shipping based on genuinely strong evidence while being upfront about what's still unresolved
- A working, if lightweight, RAG/retrieval implementation (FAISS + sentence-transformers) alongside the analytics work, which speaks to AI engineering skills as much as product or data analysis ones

---

*The complete technical write-up, including every bug encountered during the build and how each was diagnosed, is in `PROGRESS.md`. The live dashboard lives at `dashboard/index.html`.*