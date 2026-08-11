"""
generate_dashboard.py
Queries the live shopsense.db + reruns significance tests, then writes a
fresh dashboard/index.html with current numbers injected.

Re-run this any time the underlying data changes:
    python src/analysis/generate_dashboard.py
"""

import sqlite3
import json
import numpy as np
import pandas as pd
from scipy import stats
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "processed" / "shopsense.db"
TEMPLATE_PATH = PROJECT_ROOT / "dashboard" / "template.html"
OUTPUT_PATH = PROJECT_ROOT / "dashboard" / "index.html"
JSON_OUT_PATH = PROJECT_ROOT / "data" / "processed" / "dashboard_data.json"

ALPHA = 0.05


def two_proportion_z_test(success_a, n_a, success_b, n_b):
    p_a, p_b = success_a / n_a, success_b / n_b
    se_diff = np.sqrt(p_a * (1 - p_a) / n_a + p_b * (1 - p_b) / n_b)
    p_pool = (success_a + success_b) / (n_a + n_b)
    se_pool = np.sqrt(p_pool * (1 - p_pool) * (1 / n_a + 1 / n_b))
    z = (p_b - p_a) / se_pool if se_pool > 0 else 0
    p_value = 2 * (1 - stats.norm.cdf(abs(z)))
    diff = p_b - p_a
    return {
        "control": float(p_a), "treatment": float(p_b), "diff": float(diff),
        "lo": float(diff - 1.96 * se_diff), "hi": float(diff + 1.96 * se_diff),
        "p": float(p_value), "sig": bool(p_value < ALPHA),
    }


def welch_t_test(sample_a, sample_b):
    t_stat, p_value = stats.ttest_ind(sample_b, sample_a, equal_var=False)
    mean_a, mean_b = np.mean(sample_a), np.mean(sample_b)
    se_diff = np.sqrt(np.var(sample_a, ddof=1) / len(sample_a) + np.var(sample_b, ddof=1) / len(sample_b))
    diff = mean_b - mean_a
    return {
        "control": float(mean_a), "treatment": float(mean_b), "diff": float(diff),
        "lo": float(diff - 1.96 * se_diff), "hi": float(diff + 1.96 * se_diff),
        "p": float(p_value), "sig": bool(p_value < ALPHA),
    }


def fmt_p(p):
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def build_dashboard_data():
    conn = sqlite3.connect(DB_PATH)

    searches = pd.read_sql_query("""
        SELECT se.*, ea.variant FROM search_events se
        JOIN experiment_assignments ea ON se.user_id = ea.user_id
    """, conn)
    clicks = pd.read_sql_query("""
        SELECT se.event_id, ea.variant, CASE WHEN ce.event_id IS NOT NULL THEN 1 ELSE 0 END AS clicked
        FROM search_events se
        JOIN experiment_assignments ea ON se.user_id = ea.user_id
        LEFT JOIN click_events ce ON ce.search_event_id = se.event_id
    """, conn)
    carts = pd.read_sql_query("""
        SELECT se.event_id, ea.variant,
               CASE WHEN ce.event_id IS NOT NULL THEN 1 ELSE 0 END AS clicked,
               CASE WHEN ae.event_id IS NOT NULL THEN 1 ELSE 0 END AS carted,
               CASE WHEN pe.event_id IS NOT NULL THEN 1 ELSE 0 END AS purchased
        FROM search_events se
        JOIN experiment_assignments ea ON se.user_id = ea.user_id
        LEFT JOIN click_events ce ON ce.search_event_id = se.event_id
        LEFT JOIN cart_events ae ON ae.search_event_id = se.event_id
        LEFT JOIN purchase_events pe ON pe.search_event_id = se.event_id
    """, conn)
    revenue_by_search = pd.read_sql_query("""
        SELECT se.event_id, ea.variant, COALESCE(pe.revenue, 0) AS revenue
        FROM search_events se
        JOIN experiment_assignments ea ON se.user_id = ea.user_id
        LEFT JOIN purchase_events pe ON pe.search_event_id = se.event_id
    """, conn)
    dau_raw = pd.read_sql_query("""
        SELECT ea.variant, DATE(se.timestamp) AS d, COUNT(DISTINCT se.user_id) AS dau
        FROM search_events se
        JOIN experiment_assignments ea ON se.user_id = ea.user_id
        GROUP BY ea.variant, d ORDER BY d
    """, conn)
    latency = pd.read_sql_query("""
        SELECT ea.variant, AVG(se.latency_ms) AS avg_latency
        FROM search_events se JOIN experiment_assignments ea ON se.user_id = ea.user_id
        GROUP BY ea.variant
    """, conn)

    conn.close()

    control = searches[searches["variant"] == "control"]
    treatment = searches[searches["variant"] == "treatment"]

    # --- Zero-result rate ---
    zr = two_proportion_z_test(
        (control["result_count"] == 0).sum(), len(control),
        (treatment["result_count"] == 0).sum(), len(treatment),
    )

    # --- CTR ---
    c_click = clicks[clicks["variant"] == "control"]
    t_click = clicks[clicks["variant"] == "treatment"]
    ctr = two_proportion_z_test(c_click["clicked"].sum(), len(c_click), t_click["clicked"].sum(), len(t_click))

    # --- Search -> Purchase ---
    c_all = carts[carts["variant"] == "control"]
    t_all = carts[carts["variant"] == "treatment"]
    conv = two_proportion_z_test(c_all["purchased"].sum(), len(c_all), t_all["purchased"].sum(), len(t_all))

    # --- Revenue per search ---
    rev_a = revenue_by_search[revenue_by_search["variant"] == "control"]["revenue"].values
    rev_b = revenue_by_search[revenue_by_search["variant"] == "treatment"]["revenue"].values
    rev = welch_t_test(rev_a, rev_b)

    # --- Funnel (click/cart/purchase rates as % of prior step) ---
    def funnel_stats(df):
        clicked = df["clicked"].sum()
        carted = df["carted"].sum()
        purchased = df["purchased"].sum()
        n = len(df)
        return {
            "click_rate": 100 * clicked / n if n else 0,
            "cart_rate": 100 * carted / clicked if clicked else 0,
            "purchase_rate": 100 * purchased / carted if carted else 0,
        }
    f_c, f_t = funnel_stats(c_all), funnel_stats(t_all)

    # --- DAU series (aligned by date) ---
    all_days = sorted(dau_raw["d"].unique())
    dau_control = [int(dau_raw[(dau_raw["d"] == d) & (dau_raw["variant"] == "control")]["dau"].sum()) for d in all_days]
    dau_treatment = [int(dau_raw[(dau_raw["d"] == d) & (dau_raw["variant"] == "treatment")]["dau"].sum()) for d in all_days]

    # --- Guardrails: latency + 7-day retention ---
    lat_c = float(latency[latency["variant"] == "control"]["avg_latency"].iloc[0]) if not latency.empty else 0.0
    lat_t = float(latency[latency["variant"] == "treatment"]["avg_latency"].iloc[0]) if not latency.empty else 0.0

    conn = sqlite3.connect(DB_PATH)
    retention = pd.read_sql_query("""
        WITH first_activity AS (
            SELECT user_id, MIN(DATE(timestamp)) AS day0 FROM search_events GROUP BY user_id
        ), retained AS (
            SELECT fa.user_id, MAX(CASE WHEN DATE(se.timestamp) > fa.day0
                     AND DATE(se.timestamp) <= DATE(fa.day0, '+7 days') THEN 1 ELSE 0 END) AS ret7
            FROM first_activity fa JOIN search_events se ON se.user_id = fa.user_id
            GROUP BY fa.user_id
        )
        SELECT ea.variant, 100.0*SUM(r.ret7)/COUNT(*) AS ret_pct
        FROM retained r JOIN experiment_assignments ea ON r.user_id = ea.user_id
        GROUP BY ea.variant
    """, conn)
    conn.close()
    ret_c = float(retention[retention["variant"] == "control"]["ret_pct"].iloc[0]) if not retention.empty else 0.0
    ret_t = float(retention[retention["variant"] == "treatment"]["ret_pct"].iloc[0]) if not retention.empty else 0.0

    # --- Verdict ---
    primary_sig_positive = bool(zr["sig"] and ctr["sig"] and conv["sig"] and ctr["diff"] > 0 and conv["diff"] > 0)
    verdict = "RECOMMEND SHIP" if primary_sig_positive else "NEEDS MORE DATA"

    def delta_class(diff, higher_is_better=True):
        if diff == 0:
            return "flat"
        positive = diff > 0 if higher_is_better else diff < 0
        return "up" if positive else "flat"

    dashboard_data = {
        "meta": {
            "users": len(searches["user_id"].unique()),
            "searches": len(searches),
            "date_range": f"{all_days[0]} to {all_days[-1]}" if all_days else "N/A",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
        "verdict": verdict,
        "kpis": [
            {"name": "Zero-Result Rate", "control": f"{zr['control']*100:.2f}%", "treatment": f"{zr['treatment']*100:.2f}%",
             "delta": f"{zr['diff']*100:+.1f}pp", "deltaClass": delta_class(zr["diff"], higher_is_better=False)},
            {"name": "Click-Through Rate", "control": f"{ctr['control']*100:.2f}%", "treatment": f"{ctr['treatment']*100:.2f}%",
             "delta": f"{ctr['diff']*100:+.1f}pp", "deltaClass": delta_class(ctr["diff"])},
            {"name": "Search → Purchase", "control": f"{conv['control']*100:.2f}%", "treatment": f"{conv['treatment']*100:.2f}%",
             "delta": f"{conv['diff']*100:+.1f}pp", "deltaClass": delta_class(conv["diff"])},
            {"name": "Revenue / Search", "control": f"${rev['control']:.2f}", "treatment": f"${rev['treatment']:.2f}",
             "delta": f"{'+' if rev['diff']>=0 else ''}{rev['diff']:.2f} {'(n.s.)' if not rev['sig'] else ''}",
             "deltaClass": "up" if rev["sig"] and rev["diff"] > 0 else "flat"},
        ],
        "funnel": [
            {"label": "Click Rate", "control": round(f_c["click_rate"], 2), "treatment": round(f_t["click_rate"], 2)},
            {"label": "Cart Add Rate", "control": round(f_c["cart_rate"], 2), "treatment": round(f_t["cart_rate"], 2)},
            {"label": "Purchase Rate", "control": round(f_c["purchase_rate"], 2), "treatment": round(f_t["purchase_rate"], 2)},
        ],
        "significance": [
            {"name": "Zero-Result Rate", "sub": "lower is better · pct pts", "diff": zr["diff"]*100, "lo": zr["lo"]*100, "hi": zr["hi"]*100,
             "p": fmt_p(zr["p"]), "sig": zr["sig"], "scaleMax": max(4, abs(zr["hi"]*100)*1.4)},
            {"name": "Click-Through Rate", "sub": "higher is better · pct pts", "diff": ctr["diff"]*100, "lo": ctr["lo"]*100, "hi": ctr["hi"]*100,
             "p": fmt_p(ctr["p"]), "sig": ctr["sig"], "scaleMax": max(4, abs(ctr["hi"]*100)*1.4)},
            {"name": "Search → Purchase", "sub": "higher is better · pct pts", "diff": conv["diff"]*100, "lo": conv["lo"]*100, "hi": conv["hi"]*100,
             "p": fmt_p(conv["p"]), "sig": conv["sig"], "scaleMax": max(4, abs(conv["hi"]*100)*1.4)},
            {"name": "Revenue / Search", "sub": "higher is better · dollars", "diff": rev["diff"], "lo": rev["lo"], "hi": rev["hi"],
             "p": fmt_p(rev["p"]), "sig": rev["sig"], "scaleMax": max(4, abs(rev["hi"])*1.4)},
        ],
        "dau": {"days": all_days, "control": dau_control, "treatment": dau_treatment},
        "guardrails": [
            {"title": "Search Latency (avg)",
             "control": {"n": f"{lat_c:.0f}ms", "l": "CH.A control"},
             "treatment": {"n": f"{lat_t:.0f}ms", "l": f"CH.B treatment ({lat_t-lat_c:+.0f}ms)"}},
            {"title": "7-Day Retention",
             "control": {"n": f"{ret_c:.1f}%", "l": "CH.A control"},
             "treatment": {"n": f"{ret_t:.1f}%", "l": f"CH.B treatment ({ret_t-ret_c:+.1f}pp)"}},
        ],
        "footer": {
            "method": f"{len(searches['user_id'].unique())} users randomly split 50/50, control (legacy keyword search) vs. "
                      f"treatment (AI semantic search via FAISS + sentence-transformers). {len(all_days)}-day simulation, "
                      f"{len(searches)} total searches. Two-proportion z-test for rate metrics, Welch's t-test for revenue. α = 0.05.",
            "caveat": f"Revenue-per-search lift is {'statistically significant' if rev['sig'] else 'directionally positive but not statistically significant'} "
                      f"(p = {fmt_p(rev['p'])}) at current sample size. Ship recommendation rests on zero-result rate, CTR, and conversion.",
        },
    }
    return dashboard_data


def render_dashboard():
    data = build_dashboard_data()

    JSON_OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT_PATH.write_text(json.dumps(data, indent=2))
    print(f"Saved raw dashboard data -> {JSON_OUT_PATH}")

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    final_html = template.replace("__DASHBOARD_DATA__", json.dumps(data))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(final_html, encoding="utf-8")
    print(f"Dashboard generated -> {OUTPUT_PATH}")
    print(f"\nVerdict: {data['verdict']}")
    print(f"Users: {data['meta']['users']} | Searches: {data['meta']['searches']}")


if __name__ == "__main__":
    render_dashboard()