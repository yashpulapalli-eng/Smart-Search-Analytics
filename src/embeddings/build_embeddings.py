"""
build_embeddings.py
Builds a semantic search engine over the product catalog:
1. Loads data/raw/products.csv
2. Generates embeddings for each product (title + description) using a local model
3. Builds a FAISS vector index for fast similarity search
4. Saves the index + product lookup table to data/processed/
5. Provides a semantic_search() function to test/query it

No API key required — uses sentence-transformers running locally.
"""

import pandas as pd
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRODUCTS_CSV = PROJECT_ROOT / "data" / "raw" / "products.csv"
INDEX_PATH = PROJECT_ROOT / "data" / "processed" / "product_index.faiss"
LOOKUP_PATH = PROJECT_ROOT / "data" / "processed" / "product_lookup.csv"

MODEL_NAME = "all-MiniLM-L6-v2"  # small, fast, good quality — runs locally, ~80MB download


def build_index():
    print(f"Loading products from {PRODUCTS_CSV} ...")
    products = pd.read_csv(PRODUCTS_CSV)

    print(f"Loading embedding model '{MODEL_NAME}' (first run downloads it, ~80MB)...")
    model = SentenceTransformer(MODEL_NAME)

    # Combine title + description so the embedding captures full meaning
    text_to_embed = (products["title"] + ". " + products["description"]).tolist()

    print(f"Generating embeddings for {len(text_to_embed)} products...")
    embeddings = model.encode(text_to_embed, show_progress_bar=True, normalize_embeddings=True)
    embeddings = np.array(embeddings).astype("float32")

    # Build FAISS index (inner product on normalized vectors = cosine similarity)
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)

    # Save index and lookup table
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(INDEX_PATH))
    products.to_csv(LOOKUP_PATH, index=False)

    print(f"Saved FAISS index -> {INDEX_PATH}")
    print(f"Saved product lookup -> {LOOKUP_PATH}")
    print(f"Embedding dimension: {dimension}, total vectors: {index.ntotal}")

    return index, products, model


def load_index():
    """Load a previously built index + lookup table + model (for reuse in other scripts)."""
    index = faiss.read_index(str(INDEX_PATH))
    products = pd.read_csv(LOOKUP_PATH)
    model = SentenceTransformer(MODEL_NAME)
    return index, products, model


def semantic_search(query, index, products, model, top_k=5):
    """Search the vector index with a natural-language query and return top_k matches."""
    query_vec = model.encode([query], normalize_embeddings=True).astype("float32")
    similarities, indices = index.search(query_vec, top_k)

    results = products.iloc[indices[0]].copy()
    results["similarity_score"] = similarities[0]
    return results[["product_id", "title", "category", "price", "similarity_score"]]


if __name__ == "__main__":
    index, products, model = build_index()

    # Quick sanity-check queries to prove semantic matching works
    test_queries = [
        "cozy warm gift for someone who loves hiking",
        "somthing to make cofee in the morning",  # deliberate typo to test robustness
        "shoes for running in the rain",
    ]

    print("\n--- Sanity check: semantic search test queries ---")
    for q in test_queries:
        print(f"\nQuery: '{q}'")
        results = semantic_search(q, index, products, model, top_k=5)
        print(results.to_string(index=False))
