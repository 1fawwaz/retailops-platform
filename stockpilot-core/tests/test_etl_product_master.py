import pandas as pd

from scripts.etl.product_master import build_product_master


def test_one_row_per_distinct_sku() -> None:
    df = pd.DataFrame(
        {
            "StockCode": ["A1", "A1", "B2"],
            "Description": ["Widget", "Widget", "Gadget"],
        }
    )

    result = build_product_master(df)

    assert sorted(result["sku"]) == ["A1", "B2"]
    assert len(result) == 2


def test_picks_most_common_description_for_a_sku() -> None:
    df = pd.DataFrame(
        {
            "StockCode": ["A1", "A1", "A1"],
            "Description": ["Old Name", "New Name", "New Name"],
        }
    )

    result = build_product_master(df)

    assert result.loc[result["sku"] == "A1", "description"].iloc[0] == "New Name"


def test_tie_is_broken_by_first_occurrence() -> None:
    df = pd.DataFrame(
        {
            "StockCode": ["A1", "A1"],
            "Description": ["First Name", "Second Name"],
        }
    )

    result = build_product_master(df)

    assert result.loc[result["sku"] == "A1", "description"].iloc[0] == "First Name"


def test_all_null_descriptions_yields_null() -> None:
    df = pd.DataFrame(
        {
            "StockCode": ["A1", "A1"],
            "Description": [None, None],
        }
    )

    result = build_product_master(df)

    assert result.loc[result["sku"] == "A1", "description"].iloc[0] is None
