# Data derivation

Online Retail II (UCI, CC BY 4.0) has no cost price, stock levels, suppliers, or
categories. This document is the audit trail for everything `scripts/run_etl.py`
derives to fill those gaps, and for how the raw transaction log is cleaned before
any of that derivation happens. Every derived column in the schema carries a SQL
comment pointing at a section here (see `stockpilot-core/models/`).

All randomised steps use a single fixed seed (`RANDOM_SEED = 42`, `scripts/etl/random_seed.py`)
via `numpy.random.default_rng`, drawn from in the same order on every run, so the
whole pipeline is reproducible from an empty database.

## Cleaning

Applied in `scripts/etl/clean.py`, in this order, against the raw 1,067,371-row
transaction log:

1. **Drop cancellations** — `Invoice` starts with `'C'`.
2. **Drop non-positive quantities** — `Quantity <= 0`.
3. **Drop null StockCodes** — `StockCode` is null (0 rows in this dataset; kept as an
   explicit step because the spec requires it and a future data refresh might not be
   this clean).
4. **Drop test rows** — `StockCode` is `TEST001` or `TEST002` (both have the literal
   description "This is a test product."), or `Description` (trimmed, case-insensitive)
   equals exactly `"test"` (two rows on otherwise-real SKUs `22355`/`22823` — clearly
   a data-entry artifact, not a real transaction).
5. **Drop non-merchandise administrative line items.** Distinct-`StockCode`
   inspection of the raw file turned up codes that are financial/administrative
   entries embedded in the same transaction log as real sales, not products:

   | StockCode | Description | Why excluded |
   |---|---|---|
   | `POST` | POSTAGE | Shipping charge |
   | `DOT` | DOTCOM POSTAGE | Shipping charge |
   | `D` | Discount | Discount line |
   | `M` / `m` | Manual | Manual/ad-hoc charge |
   | `ADJUST` | Adjustment by \<name\> on \<date\> | Inventory/account adjustment |
   | `S` | SAMPLES | Free samples, not sold merchandise |
   | `B` | Adjust bad debt | Financial write-off (price ranges into the tens of thousands, positive and negative) |
   | `AMAZONFEE` | AMAZON FEE | Marketplace fee |
   | `CRUK` | CRUK Commission | Charity commission |
   | `C2` | CARRIAGE | Shipping charge |
   | `BANK CHARGES` | Bank Charges | Financial charge |
   | `GIFT` | (null) | Single anomalous row, no real description, zero price |
   | `22016` | Dotcomgiftshop Gift Voucher £100.00 | Gift voucher, not merchandise (found retroactively -- see below) |
   | `23595` | adjustment | Its only row; 100% administrative (found retroactively) |
   | `35600A` | Found by jackie | Its only row; 100% administrative (found retroactively) |

   Plus the whole **`gift_0001_*` StockCode family** (Dotcomgiftshop Gift Voucher,
   denominations £10-£90) is dropped by prefix match (`StockCode` starts with
   `gift_`, case-insensitive) rather than by exact code, since some of its rows
   have a null or garbled `Description` (e.g. "to push order througha s stock was")
   that a text-based filter wouldn't catch.

   **Deliberately kept** despite looking similar at a glance: `PADS` (19 rows, one
   consistent description "PADS TO MATCH ALL CUSHIONS", a real near-free bundled
   item) and `DCGSSGIRL` / `DCGSLBOY` / `DCGSSBOY` / `DCGSLGIRL` (real merchandise —
   "BOYS/GIRLS PARTY BAG" — despite some rows having a missing or placeholder
   description).

   **Retroactive correction:** `22016`, `23595`, `35600A`, and the `gift_0001_*`
   family were *not* caught by the original step (a) pass -- they surfaced while
   sanity-checking step (d)'s derived `unit_cost`, where 14 products came out to
   `unit_cost = 0.00`. Most of those were genuinely near-free items consistent
   with their observed prices (e.g. `PADS`), but a few were gift vouchers and
   pure administrative notes that never belonged in the product catalog at all.
   Confirmed each was 100% non-merchandise before excluding it (e.g. `23595` and
   `35600A` each have exactly one cleaned row, and that row's description is the
   administrative note, not a product name) rather than pattern-matching on
   description text alone, which risked dropping real transactions that merely
   had an occasional bad description on an otherwise-legitimate SKU (e.g. dozens
   of real product codes have a stray "amazon" or "adjustment" row alongside many
   rows with a real description -- `product_master.py`'s most-common-description
   logic already handles that correctly by picking the real description as the
   mode, so those rows were deliberately left alone).

Measured counts (via `scripts/run_etl.py`, cascading -- each filter applies to
whatever survived the previous one; includes the retroactive correction above):

| Step | Rows dropped | Rows remaining |
|---|---|---|
| Raw | -- | 1,067,371 |
| Drop cancellations | 19,494 | 1,047,877 |
| Drop non-positive quantity | 3,457 | 1,044,420 |
| Drop null StockCode | 0 | 1,044,420 |
| Drop test rows | 15 | 1,044,405 |
| Drop admin codes (incl. retroactive fixes) | 4,692 | 1,039,713 |

**Note on write ordering:** step (a) itself only cleans the data in memory and
reports counts — it does not write to the database yet. `sales_transactions.sku`
has a foreign key to `products.sku`, so transactions can't be inserted before the
products they reference exist. Step (b) (product master) therefore inserts both
`products` and the cleaned `sales_transactions` rows together, since they're
coupled by that constraint; splitting them across two commits would mean either
committing code that can't run yet, or committing with the constraint dropped,
which is worse. This is a write-ordering detail, not a deviation from what step
(a)/(b) each conceptually produce.

## Product master

`scripts/etl/product_master.py` groups the cleaned transaction log by `StockCode`
and picks each SKU's most common non-null `Description` (ties broken by first
occurrence in the data, for determinism). Result: **4,960 distinct products**
(after the retroactive cleaning correction below; originally 4,972) -- fewer
than the raw file's 5,305 distinct StockCodes, because SKUs vanish entirely
during cleaning: admin/gift-voucher codes, test codes, and SKUs that turned out
to have *only* cancelled or non-positive-quantity rows in the entire dataset --
spot-checked directly: e.g. SKU `85105` has exactly one raw row, `Quantity=-3`,
no cancellation prefix, no description. A SKU with zero valid sales has no place
in a product master built from real transactions.

## #category-clustering

`scripts/etl/categories.py` assigns each product a category via TF-IDF + KMeans
over `products.description`, entirely `provenance="derived"` -- nothing here
comes from the source dataset.

**Method:** TF-IDF vectorize descriptions (`stop_words="english"`, `min_df=3`,
`max_df=0.5` -- standard preprocessing thresholds, not business values) over the
4,908 products that have a non-null description (64 have none and are left
uncategorized -- there's no text to cluster on). KMeans with `random_state=42`
(the single seed in `scripts/etl/random_seed.py`) and `n_init=10`.

**Choosing k:** the spec calls for 8-12 clusters. Compared silhouette scores
across the full range on the real data:

| k | silhouette |
|---|---|
| 8 | 0.0192 |
| 9 | 0.0208 |
| 10 | 0.0231 |
| **11** | **0.0243** (chosen) |
| 12 | 0.0231 |

Honest caveat: these are all low absolute scores. Retail product descriptions are
short, and TF-IDF over them produces a high-dimensional sparse space where
KMeans clusters overlap heavily -- this is a real characteristic of the data, not
a bug. k=11 is the best of a weak field, not a clean separation. One large
"general" cluster acting as a catch-all for items without strong distinguishing
vocabulary is expected, and a random sample of categorized products confirms
occasional imprecise-looking assignments (e.g. a glass bracelet landing in
"Heart-Themed Decor") alongside mostly sensible ones. This is disclosed here
rather than presented as more precise than it is.

**Hand-labelling:** for k=11, inspected each cluster's top TF-IDF terms (by
centroid weight) and 8 sample descriptions, then picked a label a human would
recognize. The mapping is committed as its own file,
`scripts/etl/category_mapping.json`, separate from the clustering code, so the
one-time manual labelling decision is auditable without reading Python:

| Cluster | Label | Size |
|---|---|---|
| 0 | General Home & Gifts | 2,635 |
| 1 | Bags & Totes | 446 |
| 2 | Metal Signs & Decor | 118 |
| 3 | Pink-Themed Gifts & Decor | 431 |
| 4 | Christmas & Vintage Decor | 183 |
| 5 | Assorted Packs & Novelties | 251 |
| 6 | Artificial Flowers & Jewelry | 130 |
| 7 | Candle Holders & Greeting Cards | 167 |
| 8 | Glassware & Glass Decor | 228 |
| 9 | Heart-Themed Decor | 199 |
| 10 | Gift Sets & Bundles | 120 |

**Reproducibility pitfall caught and fixed:** KMeans' k-means++ initialization is
sensitive to input row order even with a fixed `random_state` -- the first
version of `step_c_categories()` queried products without `ORDER BY sku`, which
gave a *different* (and visibly wrong-looking: one cluster absorbing 2,810 of
4,908 products with clearly mismatched labels) clustering than the one used to
write the mapping above. Fixed by querying `ORDER BY sku` *and* having
`assign_categories()` sort by `sku` internally, so correctness doesn't depend on
every caller remembering to order the query. Covered by
`test_cluster_assignment_is_independent_of_input_row_order`.

## #cost-price

`scripts/etl/cost_price.py` computes `products.unit_cost` (`provenance="derived"`,
descends from `observed` sale prices via a `derived` margin, so stays `derived`
per the "never upgrade provenance" rule):

```
unit_cost(sku) = median(unit_price observed for sku across sales_transactions)
                 x margin_factor(category of sku)
```

**margin_factor** is sampled **once per category** (not per SKU) from
`Uniform(0.55, 0.80)`, using the single seeded `Generator`
(`scripts/etl/random_seed.create_rng()`) threaded through the whole pipeline run
-- categories are iterated in ascending `category_id` order so the draw sequence,
and therefore the result, is fully determined by `RANDOM_SEED`.

**Coverage:** a product only gets a `unit_cost` if it has *both* a category (a
margin_factor basis, from step c) and at least one sales transaction (a price to
apply it to). Products with neither are left with `unit_cost = null` rather than
given an invented fallback -- there's no real derivation basis for them, and
`Product.unit_cost` is nullable precisely for this reason. Measured: 4,898 of
4,960 products got a `unit_cost` (the other 62 have no description, so no
category, from step c).

**Honest residual:** 9 products come out to `unit_cost = 0.00` because their
*entire* observed transaction history has `unit_price = 0` (median of all-zero
prices is zero). Spot-checked each one directly -- all are real, named products
(e.g. "CERAMIC CAKE TEAPOT WITH CHERRY", "CRYSTAL DRAGONFLY PHONE CHARM", `PADS`)
that were apparently always given away free or heavily discounted to zero in
every recorded transaction, not administrative artifacts (those were removed in
the cleaning correction above). `unit_cost = 0` is the mathematically correct
output of the documented formula given that input, not a bug, so this is
disclosed rather than patched with an arbitrary floor.

## #supplier-assignment

`scripts/etl/suppliers.py` invents a supplier roster and assigns exactly one
supplier to every product. Entirely `provenance="derived"` -- this dataset has
no real supplier data at all.

**Roster:** 15 suppliers (spec range: 12-20), named plainly `Supplier 01`
through `Supplier 15` -- not invented company names, so nothing here could be
mistaken for a real business. Each gets, drawn from the shared seeded
`Generator` in roster order:
- `lead_time_days`: `randint(3, 21)` inclusive (the spec's exact range).
- `reliability_score`: `Uniform(0.85, 0.99)` -- the spec doesn't give a range
  for this one; chosen to read as a plausible on-time-delivery rate for a
  business that's actually still operating (a supplier below ~85% reliability
  wouldn't stay a supplier long).

**Assignment:** every product gets exactly one supplier, chosen uniformly at
random from the roster (`randint(0, 15)` per SKU, SKUs sorted first for the
same input-order-independence reason as `assign_categories` -- see
`test_assign_suppliers_is_independent_of_input_order`).

## #stock-ledger

TODO — added when step (f) lands.

## #reorder-point

TODO — added when step (g) lands.
