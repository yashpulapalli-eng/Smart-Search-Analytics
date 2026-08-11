"""
ab_significance_test.py
Runs formal statistical significance tests comparing control (legacy search)
vs treatment (AI semantic search) on the core experiment metrics.
 
Proportion metrics (zero-result rate, CTR, search->purchase conversion):
    Two-proportion z-test + 95% confidence interval on the difference
Continuous metric (revenue per search):
    Welch's t-test (does not assume equal variance) + 95% CI
 
Output: printed report + data/processed/ab_test_results.csv
"""

import sqlite3
import pandas as pd
import numpy as np
from scipy import stats
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "processed" / "shopsense.db"
OUT_PATH = PROJECT_ROOT / "data" / "processed" / "ab_test_results.csv"

ALPHA = 0.05  # significance threshold


def two_proportion_z_test(success_a, n_a, success_b, n_b, label_a="control", label_b="treatment"):
    """
    Two-proportion z-test. Tests whether the conversion rate differs
    significantly between group A (control) and group B (treatment).
    """
    p_a = success_a / n_a
    p_b = success_b / n_b
    p_pool = (success_a + success_b) / (n_a + n_b)

    se_pool = np.sqrt(p_pool * (1 - p_pool) * (1 / n_a + 1 / n_b))
    z = (p_b - p_a) / se_pool
    p_value = 2 * (1 - stats.norm.cdf(abs(z)))  # two-tailed

    # 95% CI on the difference (using unpooled SE, standard for CI construction)
    se_diff = np.sqrt(p_a * (1 - p_a) / n_a + p_b * (1 - p_b) / n_b)
    diff = p_b - p_a
    ci_low = diff - 1.96 * se_diff
    ci_high = diff + 1.96 * se_diff

    return {
        f"{label_a}_rate_pct": round(p_a * 100, 3),
        f"{label_b}_rate_pct": round(p_b * 100, 3),
        "absolute_diff_pct_pts": round(diff * 100, 3),
        "relative_lift_pct": round((diff / p_a) * 100, 2) if p_a > 0 else float("inf"),
        "z_statistic": round(z, 3),
        "p_value": round(p_value, 5),
        "significant_at_5pct": p_value < ALPHA,
        "ci_95_low_pct_pts": round(ci_low * 100, 3),
        "ci_95_high_pct_pts": round(ci_high * 100, 3),
    }


def welch_t_test(sample_a, sample_b, label_a="control", label_b="treatment"):
    """Welch's t-test for a continuous metric (does not assume equal variances)."""
    t_stat, p_value = stats.ttest_ind(sample_b, sample_a, equal_var=False)

    mean_a, mean_b = np.mean(sample_a), np.mean(sample_b)
    se_diff = np.sqrt(np.var(sample_a, ddof=1) / len(sample_a) + np.var(sample_b, ddof=1) / len(sample_b))
    diff = mean_b - mean_a
    ci_low = diff - 1.96 * se_diff
    ci_high = diff + 1.96 * se_diff

    return {
        f"{label_a}_mean": round(mean_a, 3),
        f"{label_b}_mean": round(mean_b, 3),
        "absolute_diff": round(diff, 3),
        "relative_lift_pct": round((diff / mean_a) * 100, 2) if mean_a != 0 else float("inf"),
        "t_statistic": round(t_stat, 3),
        "p_value": round(p_value, 5),
        "significant_at_5pct": p_value < ALPHA,
        "ci_95_low": round(ci_low, 3),
        "ci_95_high": round(ci_high, 3),
    }


def run_all_tests():
    conn = sqlite3.connect(DB_PATH)

    searches = pd.read_sql_query("""
        SELECT se.*, ea.variant
        FROM search_events se
        JOIN experiment_assignments ea ON se.user_id = ea.user_id
    """, conn)

    purchases = pd.read_sql_query("""
        SELECT pe.*, ea.variant
        FROM purchase_events pe
        JOIN experiment_assignments ea ON pe.user_id = ea.user_id
    """, conn)

    conn.close()

    control = searches[searches["variant"] == "control"]
    treatment = searches[searches["variant"] == "treatment"]

    results = {}

    # --- Test 1: Zero-result rate ---
    print("=" * 90)
    print("TEST 1: ZERO-RESULT RATE (lower is better)")
    print("=" * 90)
    zr_a = (control["result_count"] == 0).sum()
    zr_b = (treatment["result_count"] == 0).sum()
    res = two_proportion_z_test(zr_a, len(control), zr_b, len(treatment))
    results["zero_result_rate"] = res
    for k, v in res.items():
        print(f"  {k}: {v}")

    # --- Test 2: CTR ---
    print("\n" + "=" * 90)
    print("TEST 2: CLICK-THROUGH RATE (higher is better)")
    print("=" * 90)
    conn = sqlite3.connect(DB_PATH)
    clicks = pd.read_sql_query("""
        SELECT se.event_id, se.user_id, ea.variant,
               CASE WHEN ce.event_id IS NOT NULL THEN 1 ELSE 0 END AS clicked
        FROM search_events se
        JOIN experiment_assignments ea ON se.user_id = ea.user_id
        LEFT JOIN click_events ce ON ce.search_event_id = se.event_id
    """, conn)
    conn.close()

    ctr_a = clicks[clicks["variant"] == "control"]["clicked"].sum()
    ctr_b = clicks[clicks["variant"] == "treatment"]["clicked"].sum()
    n_ctr_a = (clicks["variant"] == "control").sum()
    n_ctr_b = (clicks["variant"] == "treatment").sum()
    res = two_proportion_z_test(ctr_a, n_ctr_a, ctr_b, n_ctr_b)
    results["ctr"] = res
    for k, v in res.items():
        print(f"  {k}: {v}")

    # --- Test 3: Search -> Purchase conversion ---
    print("\n" + "=" * 90)
    print("TEST 3: SEARCH -> PURCHASE CONVERSION (higher is better)")
    print("=" * 90)
    purch_a = purchases[purchases["variant"] == "control"]["user_id"].count()
    purch_b = purchases[purchases["variant"] == "treatment"]["user_id"].count()
    res = two_proportion_z_test(purch_a, len(control), purch_b, len(treatment))
    results["search_to_purchase"] = res
    for k, v in res.items():
        print(f"  {k}: {v}")

    # --- Test 4: Revenue per search (continuous, Welch's t-test) ---
    print("\n" + "=" * 90)
    print("TEST 4: REVENUE PER SEARCH (higher is better)")
    print("=" * 90)
    # Build a per-search revenue array (0 for searches with no purchase) so the
    # t-test reflects revenue generated per search opportunity, not just per purchase
    rev_by_search = pd.read_sql_query("""
        SELECT se.event_id, ea.variant, COALESCE(pe.revenue, 0) AS revenue
        FROM search_events se
        JOIN experiment_assignments ea ON se.user_id = ea.user_id
        LEFT JOIN purchase_events pe ON pe.search_event_id = se.event_id
    """, sqlite3.connect(DB_PATH))

    rev_a = rev_by_search[rev_by_search["variant"] == "control"]["revenue"].values
    rev_b = rev_by_search[rev_by_search["variant"] == "treatment"]["revenue"].values
    res = welch_t_test(rev_a, rev_b)
    results["revenue_per_search"] = res
    for k, v in res.items():
        print(f"  {k}: {v}")

    # --- Save summary ---
    summary_rows = []
    for metric, res in results.items():
        summary_rows.append({"metric": metric, **res})
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(OUT_PATH, index=False)

    print("\n" + "=" * 90)
    print("OVERALL VERDICT")
    print("=" * 90)
    for metric, res in results.items():
        verdict = "SIGNIFICANT ✅" if res["significant_at_5pct"] else "NOT significant ❌"
        print(f"  {metric}: {verdict} (p = {res['p_value']})")

    print(f"\nSaved full results -> {OUT_PATH}")


if __name__ == "__main__":
    run_all_tests()

