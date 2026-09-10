"""
seed_completion.py
==================
Completes Phase 1 seeding:
1. Receives approved POs (fixes the line_id/quantity payload issue)
2. Creates remaining Sales Orders to reach 500 target
3. Prints final audit summary
"""

import json
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = os.environ.get("BASE_URL", "https://retail-hta8.onrender.com").rstrip("/")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@retailops.local")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ProductionPassword123!")


class APIClient:
    def __init__(self) -> None:
        self.token: str = ""
        self._login()

    def _login(self) -> None:
        body = urllib.parse.urlencode(
            {"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        ).encode()
        req = urllib.request.Request(
            f"{BASE_URL}/auth/login",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        for attempt in range(5):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read())
                    self.token = data["access_token"]
                    print(f"[AUTH] Logged in as {ADMIN_EMAIL}")
                    return
            except Exception as e:
                print(f"[AUTH] Login attempt {attempt + 1} failed: {e}")
                time.sleep(3 * (attempt + 1))
        print("[AUTH] FATAL: could not log in")
        sys.exit(1)

    def _request(self, method: str, path: str, body: dict | None = None, retries: int = 3):
        url = f"{BASE_URL}{path}"
        data = json.dumps(body).encode() if body is not None else None
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        for attempt in range(retries):
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                err_body = e.read().decode()[:300]
                if e.code == 401:
                    print(f"[{method} {path}] 401 - refreshing token...")
                    self._login()
                    continue
                print(f"[{method} {path}] HTTP {e.code}: {err_body}")
                if e.code in (409, 422):
                    return None
                time.sleep(2 * (attempt + 1))
            except Exception as e:
                print(f"[{method} {path}] Error: {e}")
                time.sleep(2 * (attempt + 1))
        return None

    def get(self, path: str):
        return self._request("GET", path)

    def post(self, path: str, body: dict):
        return self._request("POST", path, body)


def receive_approved_pos(client: APIClient) -> None:
    """Receive POs that are in 'approved' status using correct line_id/quantity payload."""
    print("\n" + "=" * 70)
    print("STEP 1: RECEIVING APPROVED PURCHASE ORDERS")
    print("=" * 70)

    all_pos = client.get("/purchase-orders?limit=1000") or []
    approved_pos = [po for po in all_pos if po.get("status") == "approved"]
    print(f"-> Found {len(approved_pos)} POs in 'approved' status ready for receiving")

    if not approved_pos:
        print("-> No approved POs to receive. Checking for submitted POs to approve first...")
        submitted_pos = [po for po in all_pos if po.get("status") == "submitted"]
        print(f"-> Found {len(submitted_pos)} submitted POs to approve")
        for po in submitted_pos[:100]:  # Approve up to 100
            client.post(f"/purchase-orders/{po['id']}/approve", {})
        # Re-fetch
        all_pos = client.get("/purchase-orders?limit=1000") or []
        approved_pos = [po for po in all_pos if po.get("status") == "approved"]
        print(f"-> Now {len(approved_pos)} POs in 'approved' status")

    received_count = 0
    failed_count = 0

    for po in approved_pos:
        po_id = po["id"]
        # Fetch full PO to get lines with IDs
        full_po = client.get(f"/purchase-orders/{po_id}")
        if not full_po or "lines" not in full_po:
            failed_count += 1
            continue

        # Build correct receive payload with line_id and quantity
        receive_lines = []
        for line in full_po["lines"]:
            receive_lines.append(
                {
                    "line_id": line["id"],
                    "quantity": line["quantity_ordered"],
                    "over_receipt_confirmed": False,
                }
            )

        if not receive_lines:
            continue

        result = client.post(f"/purchase-orders/{po_id}/receive", {"lines": receive_lines})
        if result:
            received_count += 1
        else:
            failed_count += 1

        if received_count % 20 == 0 and received_count > 0:
            print(f"   Received {received_count} POs so far...")

    print(f"-> PO Receiving complete: {received_count} received, {failed_count} failed")


def advance_draft_pos(client: APIClient) -> None:
    """Move draft POs through submit → approve lifecycle to create realistic mix."""
    print("\n" + "=" * 70)
    print("STEP 2: ADVANCING DRAFT PO LIFECYCLE")
    print("=" * 70)

    all_pos = client.get("/purchase-orders?limit=1000") or []
    draft_pos = [po for po in all_pos if po.get("status") == "draft"]
    print(f"-> Found {len(draft_pos)} draft POs")

    # Submit 70% of drafts
    to_submit = draft_pos[: int(len(draft_pos) * 0.7)]
    submitted = 0
    for po in to_submit:
        result = client.post(f"/purchase-orders/{po['id']}/submit", {})
        if result:
            submitted += 1
    print(f"-> Submitted {submitted} POs")

    # Approve 50% of submitted
    all_pos = client.get("/purchase-orders?limit=1000") or []
    submitted_pos = [po for po in all_pos if po.get("status") == "submitted"]
    to_approve = submitted_pos[: int(len(submitted_pos) * 0.5)]
    approved = 0
    for po in to_approve:
        result = client.post(f"/purchase-orders/{po['id']}/approve", {})
        if result:
            approved += 1
    print(f"-> Approved {approved} POs")

    # Receive 60% of approved
    all_pos = client.get("/purchase-orders?limit=1000") or []
    approved_pos = [po for po in all_pos if po.get("status") == "approved"]
    to_receive = approved_pos[: int(len(approved_pos) * 0.6)]
    received = 0
    for po in to_receive:
        full_po = client.get(f"/purchase-orders/{po['id']}")
        if not full_po or "lines" not in full_po:
            continue
        receive_lines = [
            {
                "line_id": line["id"],
                "quantity": line["quantity_ordered"],
                "over_receipt_confirmed": False,
            }
            for line in full_po["lines"]
        ]
        if receive_lines:
            result = client.post(f"/purchase-orders/{po['id']}/receive", {"lines": receive_lines})
            if result:
                received += 1
    print(f"-> Received {received} POs")


def create_remaining_sales_orders(client: APIClient) -> None:
    """Create remaining Sales Orders to reach 500 target."""
    print("\n" + "=" * 70)
    print("STEP 3: CREATING REMAINING SALES ORDERS")
    print("=" * 70)

    existing_sos = client.get("/sales-orders?limit=1000") or []
    current_count = len(existing_sos)
    needed = max(0, 500 - current_count)
    print(f"-> Current SOs: {current_count}, need {needed} more")

    if needed == 0:
        print("-> Sales Order target already met!")
        return

    # Get product SKUs and customer/warehouse IDs
    products = client.get("/products?limit=1000") or []
    customers = client.get("/customers?limit=1000") or []
    warehouses = client.get("/warehouses") or []

    all_skus = [p["sku"] for p in products]
    cust_ids = [c["id"] for c in customers]
    wh_ids = [w["id"] for w in warehouses]

    if not all_skus or not cust_ids or not wh_ids:
        print("-> ERROR: Missing products, customers, or warehouses for SO creation")
        return

    def create_single_so(i: int):
        c_id = random.choice(cust_ids)
        w_id = random.choice(wh_ids)
        lines = []
        for _ in range(random.randint(1, 4)):
            sku = random.choice(all_skus)
            lines.append(
                {
                    "sku": sku,
                    "quantity": random.randint(5, 40),
                    "unit_price": round(random.uniform(30.0, 500.0), 2),
                }
            )
        so_payload = {
            "customer_id": c_id,
            "warehouse_id": w_id,
            "lines": lines,
        }
        so = client.post("/sales-orders", so_payload)
        if not so:
            return None
        so_id = so["id"]
        # Advance lifecycle: ~80% confirmed, ~50% fulfilled
        advance = random.random()
        if advance > 0.2:
            conf = client.post(f"/sales-orders/{so_id}/confirm", {})
            if conf:
                # Try to get invoice and record payment
                inv = client.get(f"/sales-orders/{so_id}/invoice")
                if inv and isinstance(inv, dict):
                    inv_id = inv.get("id")
                    total = float(inv.get("total_amount", 0.0))
                    if inv_id and total > 0:
                        pay_method = random.choice(
                            ["Bank Transfer (NEFT/RTGS)", "UPI Corporate", "Commercial Credit"]
                        )
                        client.post(
                            f"/invoices/{inv_id}/payments", {"amount": total, "method": pay_method}
                        )
                if advance > 0.45:
                    client.post(f"/sales-orders/{so_id}/fulfill", {})
        return so_id

    created = 0
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(create_single_so, i) for i in range(needed)]
        for f in as_completed(futures):
            res = f.result()
            if res:
                created += 1
                if created % 10 == 0:
                    print(f"   Created {created}/{needed} SOs...")

    print(f"-> Created {created} new Sales Orders")


def print_final_audit(client: APIClient) -> None:
    """Print final audit counts."""
    print("\n" + "=" * 70)
    print("FINAL SEEDING AUDIT SUMMARY")
    print("=" * 70)

    final_prods = client.get("/products?limit=1000") or []
    final_whs = client.get("/warehouses") or []
    final_supps = client.get("/suppliers") or []
    final_custs = client.get("/customers?limit=1000") or []
    final_pos = client.get("/purchase-orders?limit=1000") or []
    final_sos = client.get("/sales-orders?limit=1000") or []

    # PO status breakdown
    po_statuses = {}
    for po in final_pos:
        s = po.get("status", "unknown")
        po_statuses[s] = po_statuses.get(s, 0) + 1

    # SO status breakdown
    so_statuses = {}
    for so in final_sos:
        s = so.get("status", "unknown")
        so_statuses[s] = so_statuses.get(s, 0) + 1

    print(
        f"Products:         {len(final_prods):>5} (Target: >= 100)  {'✓' if len(final_prods) >= 100 else '✗'}"
    )
    print(
        f"Warehouses:       {len(final_whs):>5} (Target: >= 5)    {'✓' if len(final_whs) >= 5 else '✗'}"
    )
    print(
        f"Suppliers:        {len(final_supps):>5} (Target: >= 30)   {'✓' if len(final_supps) >= 30 else '✗'}"
    )
    print(
        f"Customers:        {len(final_custs):>5} (Target: >= 250)  {'✓' if len(final_custs) >= 250 else '✗'}"
    )
    print(
        f"Purchase Orders:  {len(final_pos):>5} (Target: >= 300)  {'✓' if len(final_pos) >= 300 else '✗'}"
    )
    print(
        f"Sales Orders:     {len(final_sos):>5} (Target: >= 500)  {'✓' if len(final_sos) >= 500 else '✗'}"
    )
    print()
    print("PO Status Breakdown:")
    for s, c in sorted(po_statuses.items()):
        print(f"  {s:>20}: {c}")
    print("SO Status Breakdown:")
    for s, c in sorted(so_statuses.items()):
        print(f"  {s:>20}: {c}")
    print("=" * 70)
    print("PHASE 1 SEEDING COMPLETION DONE!")


def main() -> None:
    client = APIClient()

    # Step 1: Advance draft POs through lifecycle
    advance_draft_pos(client)

    # Step 2: Receive approved POs with correct payload
    receive_approved_pos(client)

    # Step 3: Create remaining Sales Orders
    create_remaining_sales_orders(client)

    # Final audit
    print_final_audit(client)


if __name__ == "__main__":
    main()
