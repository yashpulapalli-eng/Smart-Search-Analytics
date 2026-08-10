"""
generate_products.py
Generates a synthetic e-commerce product catalog for the ShopSense AI Search project.
Output: data/raw/products.csv
"""

import pandas as pd
import numpy as np
import random
from pathlib import Path

random.seed(42)
np.random.seed(42)

# Resolve project root relative to this file, so it works regardless of
# what directory the script is launched from (PyCharm, terminal, etc.)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = PROJECT_ROOT / "data" / "raw" / "products.csv"

# ---- Category templates: each has adjectives, nouns, and a price range ----
CATEGORIES = {
    "Footwear": {
        "adjectives": ["Waterproof", "Lightweight", "Cushioned", "Breathable", "Insulated", "Slip-on", "High-top", "Trail"],
        "nouns": ["Running Shoes", "Hiking Boots", "Sneakers", "Sandals", "Loafers", "Winter Boots", "Cleats"],
        "price_range": (25, 180),
    },
    "Outdoor & Camping": {
        "adjectives": ["Portable", "Compact", "Heavy-Duty", "Weatherproof", "Ultralight", "Insulated", "Foldable"],
        "nouns": ["Tent", "Sleeping Bag", "Backpack", "Camp Stove", "Cooler", "Hammock", "Headlamp"],
        "price_range": (15, 350),
    },
    "Home & Kitchen": {
        "adjectives": ["Non-Stick", "Stainless Steel", "Electric", "Compact", "Ceramic", "Dishwasher-Safe"],
        "nouns": ["Blender", "Cookware Set", "Air Fryer", "Coffee Maker", "Knife Set", "Mixing Bowl", "Toaster"],
        "price_range": (10, 220),
    },
    "Apparel": {
        "adjectives": ["Cozy", "Warm", "Moisture-Wicking", "Fleece-Lined", "Windproof", "Lightweight", "Soft"],
        "nouns": ["Jacket", "Hoodie", "Sweater", "Fleece Pullover", "Rain Coat", "Thermal Leggings", "Beanie"],
        "price_range": (12, 150),
    },
    "Electronics": {
        "adjectives": ["Wireless", "Noise-Cancelling", "Rechargeable", "Portable", "Bluetooth", "Compact"],
        "nouns": ["Headphones", "Speaker", "Power Bank", "Charging Cable", "Earbuds", "Smartwatch", "Webcam"],
        "price_range": (15, 300),
    },
    "Gifts & Novelty": {
        "adjectives": ["Handmade", "Personalized", "Engraved", "Rustic", "Elegant", "Minimalist"],
        "nouns": ["Mug", "Candle", "Photo Frame", "Journal", "Keychain", "Desk Ornament", "Gift Box Set"],
        "price_range": (8, 90),
    },
}

DESCRIPTION_TEMPLATES = [
    "{adj} {noun} designed for everyday use. Durable construction and reliable performance.",
    "Our best-selling {adj_lower} {noun_lower} — perfect for gifts or personal use.",
    "A {adj_lower} {noun_lower} built to last, loved by thousands of customers.",
    "Upgrade your routine with this {adj_lower} {noun_lower}, made from quality materials.",
    "This {adj_lower} {noun_lower} combines comfort, style, and function.",
]


def generate_catalog(n_products=400):
    rows = []
    for i in range(n_products):
        category = random.choice(list(CATEGORIES.keys()))
        spec = CATEGORIES[category]
        adj = random.choice(spec["adjectives"])
        noun = random.choice(spec["nouns"])
        title = f"{adj} {noun}"

        template = random.choice(DESCRIPTION_TEMPLATES)
        description = template.format(adj=adj, noun=noun, adj_lower=adj.lower(), noun_lower=noun.lower())

        price = round(np.random.uniform(*spec["price_range"]), 2)

        rows.append({
            "product_id": f"P{i+1:04d}",
            "title": title,
            "description": description,
            "category": category,
            "price": price,
        })

    df = pd.DataFrame(rows).drop_duplicates(subset="title").reset_index(drop=True)
    return df


if __name__ == "__main__":
    catalog = generate_catalog(n_products=700)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    catalog.to_csv(OUTPUT_PATH, index=False)
    print(f"Generated {len(catalog)} unique products -> {OUTPUT_PATH}")
    print(catalog.head(10))