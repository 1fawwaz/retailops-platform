import pandas as pd

from scripts.etl.categories import assign_categories, load_cluster_labels

SYNTHETIC_PRODUCTS = pd.DataFrame(
    {
        "sku": [f"S{i}" for i in range(12)],
        "description": [
            "red candle holder",
            "blue candle holder",
            "green candle holder",
            "red glass bracelet",
            "blue glass bracelet",
            "green glass bracelet",
            "vintage christmas star",
            "vintage christmas tree",
            "vintage christmas card",
            None,
            "pink heart necklace",
            "pink heart bracelet",
        ],
    }
)


def test_products_without_description_are_omitted() -> None:
    result = assign_categories(SYNTHETIC_PRODUCTS, n_clusters=3, min_df=1, max_df=1.0)

    assert "S9" not in set(result["sku"])
    assert len(result) == 11


def test_every_categorized_product_gets_a_cluster_and_label() -> None:
    cluster_labels = {0: "Alpha", 1: "Beta", 2: "Gamma"}

    result = assign_categories(
        SYNTHETIC_PRODUCTS, n_clusters=3, cluster_labels=cluster_labels, min_df=1, max_df=1.0
    )

    assert result["cluster_id"].isin([0, 1, 2]).all()
    assert result["category"].isin(["Alpha", "Beta", "Gamma"]).all()
    assert result["category"].notna().all()


def test_cluster_assignment_is_independent_of_input_row_order() -> None:
    """Regression test: KMeans' k-means++ init is sensitive to row order
    even with a fixed random_state, so assign_categories must normalize
    order internally rather than trust the caller's query order.
    """
    shuffled = SYNTHETIC_PRODUCTS.sample(frac=1, random_state=7).reset_index(drop=True)

    result_original = assign_categories(SYNTHETIC_PRODUCTS, n_clusters=3, min_df=1, max_df=1.0)
    result_shuffled = assign_categories(shuffled, n_clusters=3, min_df=1, max_df=1.0)

    original_map = dict(zip(result_original["sku"], result_original["cluster_id"], strict=True))
    shuffled_map = dict(zip(result_shuffled["sku"], result_shuffled["cluster_id"], strict=True))
    assert original_map == shuffled_map


def test_load_cluster_labels_covers_every_production_cluster() -> None:
    from scripts.etl.categories import N_CLUSTERS

    labels = load_cluster_labels()

    assert set(labels.keys()) == set(range(N_CLUSTERS))
    assert all(isinstance(name, str) and name for name in labels.values())
