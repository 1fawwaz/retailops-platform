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

   **Deliberately kept** despite looking similar at a glance: `PADS` (19 rows, one
   consistent description "PADS TO MATCH ALL CUSHIONS", a real near-free bundled
   item) and `DCGSSGIRL` / `DCGSLBOY` / `DCGSSBOY` / `DCGSLGIRL` (real merchandise —
   "BOYS/GIRLS PARTY BAG" — despite some rows having a missing or placeholder
   description).

Measured counts (via `scripts/run_etl.py`, cascading -- each filter applies to
whatever survived the previous one):

| Step | Rows dropped | Rows remaining |
|---|---|---|
| Raw | -- | 1,067,371 |
| Drop cancellations | 19,494 | 1,047,877 |
| Drop non-positive quantity | 3,457 | 1,044,420 |
| Drop null StockCode | 0 | 1,044,420 |
| Drop test rows | 15 | 1,044,405 |
| Drop admin codes | 4,588 | 1,039,817 |

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
occurrence in the data, for determinism). Result: **4,972 distinct products** --
fewer than the raw file's 5,305 distinct StockCodes, because 333 SKUs vanish
entirely during cleaning (13 admin codes, 2 test codes, and 318 more that turned
out to have *only* cancelled or non-positive-quantity rows in the entire dataset
-- spot-checked directly: e.g. SKU `85105` has exactly one raw row, `Quantity=-3`,
no cancellation prefix, no description. A SKU with zero valid sales has no place
in a product master built from real transactions).

## #category-clustering

TODO — added when step (c) lands.

## #cost-price

TODO — added when step (d) lands.

## #supplier-assignment

TODO — added when step (e) lands.

## #stock-ledger

TODO — added when step (f) lands.

## #reorder-point

TODO — added when step (g) lands.
