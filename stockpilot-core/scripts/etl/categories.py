"""Step (c): TF-IDF + KMeans categories, hand-labelled.

See docs/data-derivation.md#category-clustering for the silhouette-score
comparison behind N_CLUSTERS and the reasoning behind each label.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer

from scripts.etl.random_seed import RANDOM_SEED

N_CLUSTERS = 11
MAPPING_PATH = Path(__file__).resolve().parent / "category_mapping.json"

TFIDF_MIN_DF = 3
TFIDF_MAX_DF = 0.5


def load_cluster_labels() -> dict[int, str]:
    with MAPPING_PATH.open() as f:
        raw = json.load(f)
    return {int(cluster_id): label for cluster_id, label in raw.items()}


def assign_categories(
    product_df: pd.DataFrame,
    *,
    n_clusters: int = N_CLUSTERS,
    cluster_labels: dict[int, str] | None = None,
    min_df: int = TFIDF_MIN_DF,
    max_df: float = TFIDF_MAX_DF,
) -> pd.DataFrame:
    """product_df needs columns sku, description.

    Returns sku, cluster_id, category for products with a non-null
    description. Products with no description are omitted -- their
    category_id stays null, since there's no text to cluster on.

    n_clusters/cluster_labels/min_df/max_df default to the production
    values but are overridable so this is testable against small
    synthetic datasets (KMeans needs n_samples >= n_clusters, and a
    tiny corpus can't satisfy min_df=3).

    Sorts by sku internally: KMeans' k-means++ initialization is
    sensitive to input row order even with a fixed random_state, so
    reproducibility (and matching the row order used to hand-label
    category_mapping.json) can't depend on the caller happening to
    query in sku order.
    """
    labelled = product_df.dropna(subset=["description"]).sort_values("sku").reset_index(drop=True)

    vectorizer = TfidfVectorizer(stop_words="english", min_df=min_df, max_df=max_df)
    tfidf_matrix = vectorizer.fit_transform(labelled["description"])

    kmeans = KMeans(n_clusters=n_clusters, random_state=RANDOM_SEED, n_init=10)
    labelled["cluster_id"] = kmeans.fit_predict(tfidf_matrix)

    labels = cluster_labels if cluster_labels is not None else load_cluster_labels()
    labelled["category"] = labelled["cluster_id"].map(labels)

    return labelled[["sku", "cluster_id", "category"]]
