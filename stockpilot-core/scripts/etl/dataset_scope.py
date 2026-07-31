"""Optional scope-limiting for resource-constrained deployments.

See docs/data-derivation.md#demo-dataset-scope. Disabled (full dataset) by
default -- only takes effect when ETL_MAX_TRANSACTIONS is set.
"""

from __future__ import annotations

import pandas as pd


class SkuVolumeCounter:
    """Tracks per-SKU transaction counts across streamed chunks, so the
    top-N-by-volume SKUs can be selected after a single streaming pass
    without holding the full transaction log in memory -- state is bounded
    by the number of distinct SKUs (thousands), not row count (millions).
    """

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def add_chunk(self, chunk: pd.DataFrame) -> None:
        for sku in chunk["StockCode"]:
            key = str(sku)
            self._counts[key] = self._counts.get(key, 0) + 1

    def top_skus_by_target_volume(self, target_transaction_count: int) -> set[str]:
        """Greedily keep whole SKUs, ranked by transaction count descending,
        until their cumulative count reaches target_transaction_count.

        Keeping each selected SKU's full transaction history (rather than
        truncating the date range across all SKUs) preserves that SKU's
        complete seasonal pattern and forecasting signal, and keeps the
        stock ledger's daily granularity intact -- only the number of
        distinct products covered shrinks, not the richness of each one
        that's kept.
        """
        if target_transaction_count <= 0:
            return set()
        ranked = sorted(self._counts.items(), key=lambda item: (-item[1], item[0]))
        selected: set[str] = set()
        cumulative = 0
        for sku, count in ranked:
            if cumulative >= target_transaction_count:
                break
            selected.add(sku)
            cumulative += count
        return selected
