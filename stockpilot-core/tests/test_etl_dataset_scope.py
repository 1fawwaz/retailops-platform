import pandas as pd

from scripts.etl.dataset_scope import SkuVolumeCounter


def _chunk(skus: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"StockCode": skus})


def test_zero_target_keeps_nothing() -> None:
    counter = SkuVolumeCounter()
    counter.add_chunk(_chunk(["A1", "A1", "B2"]))

    assert counter.top_skus_by_target_volume(0) == set()


def test_keeps_highest_volume_skus_first() -> None:
    counter = SkuVolumeCounter()
    counter.add_chunk(_chunk(["A1"] * 5 + ["B2"] * 3 + ["C3"] * 1))

    # target 5 is satisfied by A1 alone (5 >= 5), so only A1 is kept
    assert counter.top_skus_by_target_volume(5) == {"A1"}
    # target 6 needs A1 (5) + the next-highest SKU B2 (3) to reach >= 6
    assert counter.top_skus_by_target_volume(6) == {"A1", "B2"}
    # target 9 needs all three SKUs (5+3+1=9)
    assert counter.top_skus_by_target_volume(9) == {"A1", "B2", "C3"}


def test_target_larger_than_total_keeps_everything() -> None:
    counter = SkuVolumeCounter()
    counter.add_chunk(_chunk(["A1", "A1", "B2"]))

    assert counter.top_skus_by_target_volume(1_000_000) == {"A1", "B2"}


def test_result_is_independent_of_chunking() -> None:
    skus = ["A1"] * 5 + ["B2"] * 3 + ["C3"] * 1 + ["D4"] * 4

    whole = SkuVolumeCounter()
    whole.add_chunk(_chunk(skus))

    split = SkuVolumeCounter()
    for start in range(0, len(skus), 3):
        split.add_chunk(_chunk(skus[start : start + 3]))

    assert whole.top_skus_by_target_volume(7) == split.top_skus_by_target_volume(7)


def test_ties_broken_deterministically_by_sku_name() -> None:
    counter = SkuVolumeCounter()
    counter.add_chunk(_chunk(["B2", "A1"]))  # both count 1, tie

    # target 1 is satisfied by whichever tied SKU sorts first: "A1" < "B2"
    assert counter.top_skus_by_target_volume(1) == {"A1"}
