import pandas as pd

from scripts.etl.product_master import ProductMasterAccumulator, build_product_master


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


def _sorted_records(df: pd.DataFrame) -> list[tuple[str, str | None]]:
    return sorted(zip(df["sku"], df["description"], strict=True))


def test_accumulator_matches_build_product_master_on_a_single_chunk() -> None:
    df = pd.DataFrame(
        {
            "StockCode": ["A1", "A1", "A1", "B2", "B2"],
            "Description": ["Old Name", "New Name", "New Name", "Gadget", None],
        }
    )

    accumulator = ProductMasterAccumulator()
    accumulator.add_chunk(df)

    assert _sorted_records(accumulator.build()) == _sorted_records(build_product_master(df))


def test_accumulator_gives_the_same_result_regardless_of_how_input_is_chunked() -> None:
    """The whole point of ProductMasterAccumulator is that streaming it in
    pieces must not change the result versus running build_product_master
    on the full DataFrame at once -- this is what makes it safe to use in
    place of holding the entire cleaned dataset in memory.
    """
    df = pd.DataFrame(
        {
            "StockCode": ["A1", "A1", "A1", "B2", "B2", "B2", "C3"],
            "Description": [
                "Old Name",
                "New Name",
                "New Name",
                "First Name",
                "Second Name",
                None,
                None,
            ],
        }
    )
    expected = _sorted_records(build_product_master(df))

    whole = ProductMasterAccumulator()
    whole.add_chunk(df)
    assert _sorted_records(whole.build()) == expected

    split = ProductMasterAccumulator()
    for start in range(0, len(df), 2):
        split.add_chunk(df.iloc[start : start + 2])
    assert _sorted_records(split.build()) == expected

    one_row_at_a_time = ProductMasterAccumulator()
    for i in range(len(df)):
        one_row_at_a_time.add_chunk(df.iloc[[i]])
    assert _sorted_records(one_row_at_a_time.build()) == expected


def test_accumulator_all_null_descriptions_yields_null() -> None:
    accumulator = ProductMasterAccumulator()
    accumulator.add_chunk(pd.DataFrame({"StockCode": ["A1"], "Description": [None]}))
    accumulator.add_chunk(pd.DataFrame({"StockCode": ["A1"], "Description": [None]}))

    result = accumulator.build()

    assert result.loc[result["sku"] == "A1", "description"].iloc[0] is None
