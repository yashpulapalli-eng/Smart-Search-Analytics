"""
generate_events.py
Simulates realistic user behavior for the ShopSense A/B test:
- Legacy search (control): naive keyword overlap, high zero-result rate
- AI search (treatment): semantic retrieval via FAISS, low zero-result rate

Generates: users, sessions, search_performed, result_clicked, add_to_cart,
purchase_completed, and experiment_assignments tables.

Output: CSVs in data/processed/
"""

import pandas as pd
import numpy as np
import random
from pathlib import Path
from datetime import datetime, timedelta
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT / "src" / "embeddings"))

from build_embeddings import load_index, semantic_search  # noqa: E402

random.seed(7)
np.random.seed(7)

N_USERS = 800
SIM_DAYS = 14
START_DATE = datetime(2026, 6, 1)
DAILY_ACTIVE_PROB = 0.30

# Natural-language-ish query templates, mixing clean and messy queries
QUERY_TEMPLATES = [
    "{adj} {noun}", "{noun}", "cheap {noun}", "best {noun} for {occasion}",
    "{adj} {noun} for {occasion}", "gift {noun}", "{noun} under 50 dollars",
    "somthing for {occasion}", "{noun} {adj_typo}",
]
OCCASIONS = ["hiking", "winter", "my mom", "the office", "travel", "gym", "camping", "a gift", "rain"]


def load_products():
    products = pd.read_csv(PROJECT_ROOT / "data" / "raw" / "products.csv")
    return products


def make_typo(word):
    """Randomly introduce a simple typo into a word."""
    if len(word) < 4:
        return word
    i = random.randint(1, len(word) - 2)
    return word[:i] + word[i + 1] + word[i] + word[i + 2:]  # swap two adjacent letters


def generate_query(products):
    """Generate a plausible, sometimes-messy search query from product vocabulary."""
    row = products.sample(1).iloc[0]
    words = row["title"].split()
    adj = words[0] if len(words) > 1 else random.choice(["nice", "good"])
    noun = " ".join(words[1:]) if len(words) > 1 else words[0]
    occasion = random.choice(OCCASIONS)

    template = random.choice(QUERY_TEMPLATES)
    query = template.format(
        adj=adj.lower(), noun=noun.lower(), occasion=occasion,
        adj_typo=make_typo(adj.lower())
    )

    # 20% chance of injecting a typo into the whole query
    if random.random() < 0.2:
        parts = query.split()
        idx = random.randint(0, len(parts) - 1)
        parts[idx] = make_typo(parts[idx])
        query = " ".join(parts)

    return query.strip()


def legacy_search(query, products, max_results=10):
    """Naive keyword-overlap search: returns products where any query word
    appears in the title or description. Simulates a dumb legacy search engine."""
    query_words = set(query.lower().split())
    matches = []
    for _, row in products.iterrows():
        text = (row["title"] + " " + row["description"]).lower()
        text_words = set(text.split())
        if query_words & text_words:  # any overlap
            matches.append(row)
    if not matches:
        return pd.DataFrame(columns=products.columns.tolist() + ["similarity_score"])
    result_df = pd.DataFrame(matches).head(max_results).copy()
    result_df["similarity_score"] = np.random.uniform(0.3, 0.6, size=len(result_df))  # legacy has no real relevance score
    return result_df


def simulate_user_search(user_id, variant, products, index, model, day_offset, session_id):
    query = generate_query(products)
    t0 = START_DATE + timedelta(days=day_offset, hours=random.randint(7, 22), minutes=random.randint(0, 59))

    if variant == "ai_semantic":
        results = semantic_search(query, index, products, model, top_k=8)
        latency_ms = np.random.normal(180, 30)  # AI slightly slower (embedding + retrieval)
    else:
        results = legacy_search(query, products, max_results=8)
        latency_ms = np.random.normal(90, 20)  # legacy is faster but dumber

    latency_ms = max(20, latency_ms)
    result_count = len(results)
    top_sim = results["similarity_score"].max() if result_count > 0 else 0.0

    search_event = {
        "event_id": f"S{user_id}_{day_offset}_{session_id}",
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": t0,
        "query_text": query,
        "query_length": len(query.split()),
        "search_variant": variant,
        "result_count": result_count,
        "latency_ms": round(latency_ms, 1),
        "top_result_similarity_score": round(top_sim, 4) if result_count > 0 else None,
    }

    events = {"search": search_event, "click": None, "cart": None, "purchase": None}

    if result_count == 0:
        return events

    # Click probability increases with similarity score (better results -> more clicks)
    click_prob = 0.15 + 0.55 * top_sim  # ranges ~0.15 (bad results) to ~0.7 (great results)
    if random.random() < click_prob:
        clicked_row = results.iloc[0] if random.random() < 0.6 else results.sample(1).iloc[0]
        position = int(results.index.get_loc(clicked_row.name)) + 1 if clicked_row.name in results.index else 1

        click_time = t0 + timedelta(seconds=random.randint(3, 25))
        events["click"] = {
            "event_id": f"C{user_id}_{day_offset}_{session_id}",
            "user_id": user_id,
            "session_id": session_id,
            "timestamp": click_time,
            "search_event_id": search_event["event_id"],
            "product_id": clicked_row["product_id"],
            "result_position": position,
        }

        # Add-to-cart probability also scales with relevance
        cart_prob = 0.25 + 0.4 * top_sim
        if random.random() < cart_prob:
            cart_time = click_time + timedelta(seconds=random.randint(5, 40))
            events["cart"] = {
                "event_id": f"A{user_id}_{day_offset}_{session_id}",
                "user_id": user_id,
                "session_id": session_id,
                "timestamp": cart_time,
                "product_id": clicked_row["product_id"],
                "search_event_id": search_event["event_id"],
            }

            # Purchase probability
            purchase_prob = 0.35 + 0.35 * top_sim
            if random.random() < purchase_prob:
                purchase_time = cart_time + timedelta(minutes=random.randint(1, 20))
                events["purchase"] = {
                    "event_id": f"P{user_id}_{day_offset}_{session_id}",
                    "user_id": user_id,
                    "session_id": session_id,
                    "timestamp": purchase_time,
                    "order_id": f"O{user_id}_{day_offset}_{session_id}",
                    "product_ids": clicked_row["product_id"],
                    "revenue": float(clicked_row["price"]),
                    "search_event_id": search_event["event_id"],
                }

    return events


def generate_dataset():
    products = load_products()
    print("Loading FAISS index for AI search simulation...")
    index, indexed_products, model = load_index()

    # Assign users to control/treatment (50/50 split)
    user_ids = [f"U{i:05d}" for i in range(1, N_USERS + 1)]
    assignments = []
    for uid in user_ids:
        variant = random.choice(["legacy", "ai_semantic"])
        assignments.append({
            "user_id": uid,
            "experiment_name": "ai_search_v1",
            "variant": "control" if variant == "legacy" else "treatment",
            "assigned_at": START_DATE,
        })
    assignments_df = pd.DataFrame(assignments)
    user_variant_map = dict(zip(assignments_df["user_id"],
                                 np.where(assignments_df["variant"] == "treatment", "ai_semantic", "legacy")))

    searches, clicks, carts, purchases, sessions = [], [], [], [], []

    print(f"Simulating {SIM_DAYS} days of activity for {N_USERS} users...")
    for day in range(SIM_DAYS):
        # Not all users are active every day (with some daily variance)
        active_users = [u for u in user_ids if random.random() < DAILY_ACTIVE_PROB]

        for uid in active_users:
            variant = user_variant_map[uid]
            n_sessions = np.random.choice([1, 2], p=[0.85, 0.15])

            for s in range(n_sessions):
                session_id = f"SESS_{uid}_{day}_{s}"
                device = random.choices(["mobile", "desktop", "tablet"], weights=[0.6, 0.35, 0.05])[0]
                session_start = START_DATE + timedelta(days=day, hours=random.randint(7, 22))
                sessions.append({
                    "session_id": session_id, "user_id": uid,
                    "timestamp": session_start, "device_type": device,
                })

                n_searches = np.random.choice([1, 2, 3], p=[0.6, 0.3, 0.1])
                for _ in range(n_searches):
                    result = simulate_user_search(uid, variant, products, index, model, day, session_id)
                    searches.append(result["search"])
                    if result["click"]:
                        clicks.append(result["click"])
                    if result["cart"]:
                        carts.append(result["cart"])
                    if result["purchase"]:
                        purchases.append(result["purchase"])

        if (day + 1) % 5 == 0:
            print(f"  Day {day + 1}/{SIM_DAYS} done — {len(searches)} searches so far")

    out_dir = PROJECT_ROOT / "data" / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(searches).to_csv(out_dir / "search_events.csv", index=False)
    pd.DataFrame(clicks).to_csv(out_dir / "click_events.csv", index=False)
    pd.DataFrame(carts).to_csv(out_dir / "cart_events.csv", index=False)
    pd.DataFrame(purchases).to_csv(out_dir / "purchase_events.csv", index=False)
    pd.DataFrame(sessions).to_csv(out_dir / "sessions.csv", index=False)
    assignments_df.to_csv(out_dir / "experiment_assignments.csv", index=False)

    print("\n--- Dataset generation complete ---")
    print(f"Searches:    {len(searches)}")
    print(f"Clicks:      {len(clicks)}")
    print(f"Cart adds:   {len(carts)}")
    print(f"Purchases:   {len(purchases)}")
    print(f"Sessions:    {len(sessions)}")
    print(f"Saved to: {out_dir}")


if __name__ == "__main__":
    generate_dataset()

