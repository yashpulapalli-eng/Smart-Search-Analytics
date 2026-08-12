# ShopSense AI Search — Product Case Study & Ship Recommendation

**Author:** Sriyashveer Pulapalli
**Date:** August 2026
**Status:** Experiment complete 

---

## 1. The Problem

ShopSense's legacy product search relies on exact keyword matching: a query only returns results if its words literally appear in a product's title or description. Analysis of the legacy system showed roughly **1 in every 40 searches returned zero results** — not because relevant inventory didn't exist, but because the search engine couldn't understand typos, synonyms, or natural-language phrasing (e.g., "warm shoes for winter" failing to match a product titled "Insulated Boots").

Every zero-result search is a shopper who may abandon the session or buy from a competitor. This is a silent, compounding revenue leak — invisible in most dashboards because it shows up as "the user just left," not as an identifiable failure event.

**The decision this analysis supports:** should ShopSense roll out AI-powered semantic search to 100% of traffic?

---

## 2. The Solution

We built and tested an AI semantic search engine as a replacement for legacy keyword search:

- Product titles and descriptions are converted into vector embeddings (`sentence-transformers`, `all-MiniLM-L6-v2`, run locally)
- A FAISS vector index enables retrieval by *meaning*, not literal word overlap — so queries with typos, synonyms, or natural-language phrasing can still surface relevant products
- This is a lightweight RAG-style (Retrieval-Augmented Generation) architecture: retrieval only, no generative component, keeping it fast and interpretable

---

## 3. Experiment Design

- **Method:** Randomized controlled A/B test
- **Population:** 800 users, randomly split 50/50 at the user level
  - **Control:** legacy keyword search
  - **Treatment:** AI semantic search
- **Duration:** 14 days, June 1–14, 2026
- **Sample size:** 5,678 total searches (2,902 control / 2,776 treatment)
- **Primary metric:** zero-result rate
- **Secondary metrics:** click-through rate, search→purchase conversion, revenue per search
- **Guardrail metrics:** search latency, 7-day retention

---

## 4. Results

| Metric | Control | Treatment | Absolute Lift | p-value | Significant? |
|---|---|---|---|---|---|
| Zero-result rate | 2.48% | 0.00% | −2.48pp | <0.001 | ✅ Yes |
| Click-through rate | 43.76% | 52.05% | +8.29pp | <0.001 | ✅ Yes |
| Search → Purchase conversion | 12.20% | 16.46% | +4.26pp | <0.001 | ✅ Yes |
| Revenue per search | $18.58 | $19.17 | +$0.59 | 0.706 | ❌ No |

**Guardrails:**
| Metric | Control | Treatment | Note |
|---|---|---|---|
| Avg. search latency | 90ms | 179ms | +99ms — real cost, not a guardrail failure |
| 7-day retention | 90.93% | 90.16% | −0.77pp — not meaningfully different |

Full statistical methodology (two-proportion z-tests, Welch's t-test, 95% confidence intervals) is documented in `experiment/ab_significance_test.py` and `PROGRESS.md`.

---

## 5. Interpretation

**AI search produces a statistically robust improvement in search quality and downstream conversion.** Users assigned to AI search were significantly more likely to find something worth clicking (+19% relative CTR lift) and significantly more likely to complete a purchase (+35% relative conversion lift). The zero-result problem — the entire premise of this project — was effectively eliminated in the treatment group.

**Revenue per search is directionally positive but not proven.** A $0.59 average lift sounds real, but the confidence interval (−$2.47 to +$3.65) is wide enough that we cannot distinguish this from noise at the current sample size. This is expected: revenue is a high-variance metric (most searches generate $0; a few generate hundreds of dollars), so detecting a small average shift requires either a much larger sample or a longer test window. **This is a data limitation, not evidence against AI search** — every metric that actually measures user behavior (not downstream dollar variance) moved decisively in the right direction.

**Latency increased, but not to a level that shows up in retention.** The +99ms latency cost is real and should be monitored, but it did not translate into a measurable drop in 7-day retention. Worth continued observation post-launch, particularly on slower connections/devices.

---

## 6. Recommendation

### ✅ Ship AI semantic search to 100% of traffic.

The core hypothesis — that semantic retrieval reduces zero-result searches and improves downstream engagement — is validated with high statistical confidence (p < 0.001 on all three primary/secondary behavioral metrics). The business case does not depend on the unproven revenue claim; it stands on its own from the search-quality and conversion evidence alone.

**Recommended rollout approach:**
1. Ship to 100% of traffic, but continue instrumenting revenue-per-search post-launch — with full traffic volume, statistical power will be much higher, and we can re-test the revenue hypothesis with a larger sample within 2-3 weeks.
2. Monitor latency in production, especially on mobile/lower-end devices, since the simulated +99ms gap could be larger under real infrastructure load.
3. Re-run the zero-result rate and CTR analysis monthly post-launch as a regression check — semantic search quality can drift as the product catalog grows.

---

## 7. Limitations of This Analysis

Being upfront about these matters more than pretending they don't exist:

- **Adoption metric was not meaningful in this simulation.** Every simulated session included at least one search by construction, so "AI search adoption" was trivially 100% for both groups. A real-world adoption metric would need sessions that don't involve search at all.
- **Search success rate was mathematically redundant with CTR** in this dataset, since simulated clicks always occurred within the 30-second success window. In production, this metric would diverge meaningfully from CTR and is worth tracking separately.
- **This is simulated data**, not live production traffic — user behavior probabilities (click/cart/purchase rates as a function of similarity score) were modeled based on reasonable assumptions, not measured real-world elasticities. The *methodology* (event schema, SQL analysis, significance testing) is directly production-transferable; the specific numbers are illustrative of a plausible, well-reasoned scenario.
- **Revenue variance is inherent to the metric**, not a flaw in the experiment — a follow-up analysis with either a larger sample or a variance-reduction technique (e.g., CUPED) would be the natural next step to resolve it.

---

## 8. What This Project Demonstrates

- Product problem framing tied to a measurable, defensible metric (zero-result rate)
- End-to-end instrumentation: event schema design → synthetic data generation → SQL analytics → Python statistical testing → live dashboard
- Real experimentation rigor: proper control/treatment randomization, two-proportion z-tests, Welch's t-test, confidence intervals — not just "eyeballing the numbers"
- Calibrated judgment: shipping on strong evidence while being explicit about what remains unproven, rather than overclaiming a clean sweep
- A lightweight RAG/vector-search technical implementation (FAISS + sentence-transformers), directly relevant to AI Engineering roles alongside the PM/DA analysis

---

*Full technical documentation, bug fixes encountered, and debugging methodology available in `PROGRESS.md`. Live dashboard: `dashboard/index.html`.*
