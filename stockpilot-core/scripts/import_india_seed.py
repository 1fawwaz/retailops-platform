import csv
import os
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import psutil
except ImportError:
    import subprocess

    subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil"])
    import psutil

sys.path.append(str(Path(__file__).resolve().parent.parent))

from database import get_engine

LATEST_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "latest_india_seed"
    / "output_large_india"
)
TEMP_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "india_seed_temp"
    / "output_large_india"
)
DATA_DIR = LATEST_DIR if LATEST_DIR.exists() else TEMP_DIR
print(f"Using dataset from: {DATA_DIR}")


def p_int(val):
    if not val:
        return None
    try:
        return int(float(val))
    except Exception:
        return None


def p_float(val):
    if not val:
        return None
    try:
        return float(val)
    except Exception:
        return None


def p_bool(val):
    if not val:
        return False
    return str(val).lower() in ("true", "1", "t", "y", "yes")


def p_str(val):
    return val if val else None


def p_dt(val):
    if not val:
        return None
    if " " in val:
        try:
            return datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None
    else:
        try:
            return datetime.strptime(val, "%Y-%m-%d").date()
        except Exception:
            return None


def track_progress(generator, file_name, total_rows):
    start_time = time.time()
    last_print = start_time
    rows = 0
    process = psutil.Process(os.getpid())
    process.cpu_percent()  # initial call

    for item in generator:
        yield item
        rows += 1
        current_time = time.time()
        if current_time - last_print >= 5:
            elapsed = current_time - start_time
            rate = rows / elapsed
            mem = process.memory_info().rss / 1024 / 1024
            cpu = process.cpu_percent()
            eta = f"{int((total_rows - rows) / rate)}s" if rate > 0 else "Unknown"
            print(
                f"[{file_name}] Processed: {rows}/{total_rows} | Rate: {rate:.0f} rows/s | ETA: {eta} | Mem: {mem:.1f}MB | CPU: {cpu}%"
            )
            last_print = current_time

    print(f"[{file_name}] Completed! {rows} rows in {time.time() - start_time:.1f}s")


def get_total_lines(filename):
    with open(filename, encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f) - 1


def import_table(conn, table_name, columns, csv_file, row_mapper):
    filepath = DATA_DIR / csv_file
    total_lines = get_total_lines(filepath)

    def gen():
        with open(filepath, encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                yield row_mapper(row)

    cols_str = ", ".join(columns)
    with conn.cursor() as cur:
        with cur.copy(f"COPY {table_name} ({cols_str}) FROM STDIN") as copy:
            for row in track_progress(gen(), csv_file, total_lines):
                copy.write_row(row)
    conn.commit()

    # Validate count
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cur.fetchone()[0]
        print(f"Validated {table_name}: {count} total rows in DB.")


def import_all():
    engine = get_engine()
    raw_conn = engine.raw_connection()
    conn = raw_conn.driver_connection

    print("Terminating existing connections to stockpilot DB...", flush=True)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'stockpilot' AND pid <> pg_backend_pid();"
        )
    conn.commit()

    print("Clearing existing data (TRUNCATE CASCADE)...", flush=True)
    with conn.cursor() as cur:
        cur.execute("TRUNCATE categories CASCADE")
        cur.execute("TRUNCATE suppliers CASCADE")
        cur.execute("TRUNCATE warehouses CASCADE")
        cur.execute("TRUNCATE products CASCADE")
        cur.execute("TRUNCATE customers CASCADE")
        cur.execute("TRUNCATE promotions CASCADE")
        cur.execute(
            "ALTER TABLE stock_movements DROP CONSTRAINT IF EXISTS ck_stock_movements_movement_type CASCADE"
        )
    conn.commit()

    print("\n--- Starting Data Import ---\n")

    import_table(
        conn,
        "categories",
        [
            "id",
            "name",
            "gst_percent",
            "typical_margin_low",
            "typical_margin_high",
            "cost_range_low_inr",
            "cost_range_high_inr",
        ],
        "categories.csv",
        lambda r: (
            p_int(r["id"]),
            p_str(r["name"]),
            p_float(r["gst_percent"]),
            p_float(r["typical_margin_low"]),
            p_float(r["typical_margin_high"]),
            p_float(r["cost_range_low_inr"]),
            p_float(r["cost_range_high_inr"]),
        ),
    )

    import_table(
        conn,
        "suppliers",
        [
            "id",
            "name",
            "city",
            "state",
            "pin_code",
            "contact_person",
            "mobile",
            "contact_email",
            "gstin",
            "pan",
            "udyam_number",
            "fssai_license",
            "lead_time_days",
            "reliability_score",
            "avg_delay_days",
            "on_time_percent",
            "partial_shipment_percent",
            "cancelled_percent",
            "payment_terms",
            "credit_days",
            "moq",
            "preferred_supplier",
            "created_at",
        ],
        "suppliers.csv",
        lambda r: (
            p_int(r["id"]),
            p_str(r["name"]),
            p_str(r.get("city")),
            p_str(r.get("state")),
            p_str(r.get("pin_code")),
            p_str(r.get("contact_person")),
            p_str(r.get("mobile")),
            p_str(r.get("contact_email")),
            p_str(r.get("gstin")),
            p_str(r.get("pan")),
            p_str(r.get("udyam_number")),
            p_str(r.get("fssai_license")),
            p_int(r["lead_time_days"]),
            p_float(r["reliability_score"]),
            p_float(r.get("avg_delay_days")),
            p_float(r.get("on_time_percent")),
            p_float(r.get("partial_shipment_percent")),
            p_float(r.get("cancelled_percent")),
            p_str(r.get("payment_terms")),
            p_int(r.get("credit_days")),
            p_int(r.get("moq")),
            p_bool(r.get("preferred_supplier")),
            p_dt(r.get("created_at")) or datetime.now(),
        ),
    )

    import_table(
        conn,
        "warehouses",
        [
            "id",
            "name",
            "location",
            "state",
            "zone",
            "pin_code",
            "latitude",
            "longitude",
            "capacity_units",
        ],
        "warehouses.csv",
        lambda r: (
            p_int(r["id"]),
            p_str(r["name"]),
            p_str(r.get("location")),
            p_str(r.get("state")),
            p_str(r.get("zone")),
            p_str(r.get("pin_code")),
            p_float(r.get("latitude")),
            p_float(r.get("longitude")),
            p_int(r.get("capacity_units")),
        ),
    )

    # We need to map product_id to sku for later tables. Wait! Since we use COPY, if we map product_id -> sku, we need it in memory.
    product_id_to_sku = {}
    with open(DATA_DIR / "products.csv", encoding="utf-8", errors="replace") as f:
        for r in csv.DictReader(f):
            product_id_to_sku[r["id"]] = r["sku"]

    import_table(
        conn,
        "products",
        [
            "sku",
            "description",
            "barcode",
            "name",
            "gst_percent",
            "hsn_code",
            "shelf_life_days",
            "weight_grams",
            "reorder_quantity",
            "eoq",
            "abc_class",
            "xyz_class",
            "behavior_pattern",
            "active",
            "category_id",
            "supplier_id",
            "unit_cost",
            "sale_price",
            "reorder_point",
            "safety_stock",
            "created_at",
        ],
        "products.csv",
        lambda r: (
            p_str(r["sku"]),
            p_str(r["name"]),
            p_str(r.get("barcode")),
            p_str(r.get("name")),
            p_float(r.get("gst_percent")),
            p_str(r.get("hsn_code")),
            p_int(r.get("shelf_life_days")),
            p_float(r.get("weight_grams")),
            p_int(r.get("reorder_quantity")),
            p_int(r.get("eoq")),
            p_str(r.get("abc_class")),
            p_str(r.get("xyz_class")),
            p_str(r.get("behavior_pattern")),
            p_bool(r.get("active")),
            p_int(r.get("category_id")),
            p_int(r.get("supplier_id")),
            p_float(r.get("unit_cost_inr")),
            p_float(r.get("unit_price_inr")),
            p_int(r.get("reorder_level")),
            p_int(r.get("safety_stock")),
            p_dt(r.get("created_at")) or datetime.now(),
        ),
    )

    import_table(
        conn,
        "customers",
        [
            "id",
            "name",
            "segment",
            "city",
            "phone",
            "email",
            "preferred_category_id",
            "loyalty_score",
            "lifetime_value_inr",
            "purchase_frequency",
            "avg_basket_inr",
            "created_at",
            "country",
        ],
        "customers.csv",
        lambda r: (
            p_int(r["id"]),
            p_str(r["name"]),
            p_str(r.get("segment")),
            p_str(r.get("city")),
            p_str(r.get("phone")),
            p_str(r.get("email")),
            p_int(r.get("preferred_category_id")),
            p_float(r.get("loyalty_score")),
            p_float(r.get("lifetime_value_inr")),
            p_float(r.get("purchase_frequency")),
            p_float(r.get("avg_basket_inr")),
            p_dt(r.get("created_at")) or datetime.now(),
            "India",
        ),
    )

    import_table(
        conn,
        "promotions",
        [
            "id",
            "name",
            "promo_type",
            "category_id",
            "discount_percent",
            "start_date",
            "end_date",
            "budget_inr",
            "redemption_count",
            "sales_lift_percent",
            "status",
        ],
        "promotions.csv",
        lambda r: (
            p_int(r["id"]),
            p_str(r["name"]),
            p_str(r.get("promo_type")),
            p_int(r.get("category_id")),
            p_float(r.get("discount_percent")),
            p_dt(r.get("start_date")),
            p_dt(r.get("end_date")),
            p_float(r.get("budget_inr")),
            p_int(r.get("redemption_count")),
            p_float(r.get("sales_lift_percent")),
            p_str(r.get("status")),
        ),
    )

    import_table(
        conn,
        "inventory_batches",
        [
            "id",
            "product_sku",
            "warehouse_id",
            "batch_number",
            "manufacturing_date",
            "expiry_date",
            "quantity_on_hand",
            "status",
        ],
        "inventory_batches.csv",
        lambda r: (
            p_int(r["id"]),
            product_id_to_sku.get(r.get("product_id")),
            p_int(r.get("warehouse_id")),
            p_str(r.get("batch_number")),
            p_dt(r.get("manufacturing_date")),
            p_dt(r.get("expiry_date")),
            p_int(r.get("quantity_on_hand")) or 0,
            p_str(r.get("status")),
        ),
    )

    import_table(
        conn,
        "stock_levels",
        ["sku", "warehouse_id", "quantity_on_hand", "as_of_date"],
        "stock_levels.csv",
        lambda r: (
            product_id_to_sku.get(r.get("product_id")),
            p_int(r.get("warehouse_id")),
            p_int(r.get("quantity_on_hand")),
            p_dt(r.get("snapshot_date")) or datetime.now().date(),
        ),
    )

    import_table(
        conn,
        "stock_movements",
        [
            "sku",
            "warehouse_id",
            "movement_type",
            "quantity_delta",
            "reference",
            "movement_date",
            "provenance",
        ],
        "stock_movements.csv",
        lambda r: (
            product_id_to_sku.get(r.get("product_id")),
            p_int(r.get("warehouse_id")),
            p_str(r.get("movement_type")),
            p_int(r.get("quantity")),
            p_str(r.get("reference_id")),
            p_dt(r.get("movement_date")) or datetime.now(),
            "observed",
        ),
    )

    import_table(
        conn,
        "sales_transactions",
        [
            "id",
            "invoice",
            "sku",
            "quantity",
            "unit_price",
            "customer_id",
            "country",
            "invoice_date",
        ],
        "sales.csv",
        lambda r: (
            p_int(r["id"]),
            p_str(r["invoice_number"]),
            product_id_to_sku.get(r.get("product_id")),
            p_int(r["quantity"]),
            p_float(r["unit_price_inr"]),
            p_int(r.get("customer_id")),
            "India",
            p_dt(r["sale_date"]) or datetime.now(),
        ),
    )

    import_table(
        conn,
        "returns",
        [
            "sale_id",
            "product_sku",
            "warehouse_id",
            "quantity",
            "reason",
            "return_date",
            "refund_amount_inr",
        ],
        "returns.csv",
        lambda r: (
            p_int(r.get("sale_id")),
            product_id_to_sku.get(r.get("product_id")),
            p_int(r.get("warehouse_id")),
            p_int(r.get("quantity")),
            p_str(r.get("reason")),
            p_dt(r.get("return_date")),
            p_float(r.get("refund_amount_inr")),
        ),
    )

    import_table(
        conn,
        "inventory_adjustments",
        ["product_sku", "warehouse_id", "batch_id", "quantity", "reason", "adjustment_date"],
        "inventory_adjustments.csv",
        lambda r: (
            product_id_to_sku.get(r.get("product_id")),
            p_int(r.get("warehouse_id")),
            p_int(r.get("batch_id")),
            p_int(r.get("quantity")),
            p_str(r.get("reason")),
            p_dt(r.get("adjustment_date")),
        ),
    )

    import_table(
        conn,
        "warehouse_transfers",
        [
            "product_sku",
            "from_warehouse_id",
            "to_warehouse_id",
            "quantity",
            "transfer_date",
            "status",
        ],
        "warehouse_transfers.csv",
        lambda r: (
            product_id_to_sku.get(r.get("product_id")),
            p_int(r.get("from_warehouse_id")),
            p_int(r.get("to_warehouse_id")),
            p_int(r.get("quantity")),
            p_dt(r.get("transfer_date")),
            p_str(r.get("status")),
        ),
    )

    import_table(
        conn,
        "price_history",
        ["product_sku", "old_price_inr", "new_price_inr", "effective_date", "reason"],
        "price_history.csv",
        lambda r: (
            product_id_to_sku.get(r.get("product_id")),
            p_float(r.get("old_price_inr")),
            p_float(r.get("new_price_inr")),
            p_dt(r.get("effective_date")),
            p_str(r.get("reason")),
        ),
    )

    import_table(
        conn,
        "forecasts",
        [
            "product_sku",
            "forecast_date",
            "horizon_days",
            "predicted_demand",
            "recommended_reorder_qty",
            "confidence",
        ],
        "forecasts.csv",
        lambda r: (
            product_id_to_sku.get(r.get("product_id")),
            p_dt(r.get("forecast_date")),
            p_int(r.get("horizon_days")),
            p_float(r.get("predicted_demand")),
            p_int(r.get("recommended_reorder_qty")),
            p_float(r.get("confidence")),
        ),
    )

    print("Data imported successfully!", flush=True)
    try:
        from scripts.seed_demo_user import main as seed_demo_user

        seed_demo_user()
    except Exception as ex:
        print(f"Demo user seed notice: {ex}", flush=True)


if __name__ == "__main__":
    import_all()
