import numpy as np

from scripts.etl.suppliers import (
    LEAD_TIME_DAYS_HIGH,
    LEAD_TIME_DAYS_LOW,
    RELIABILITY_SCORE_HIGH,
    RELIABILITY_SCORE_LOW,
    assign_suppliers,
    generate_supplier_roster,
)


def test_generate_supplier_roster_has_requested_count_and_ranges() -> None:
    rng = np.random.default_rng(1)

    roster = generate_supplier_roster(rng, n_suppliers=15)

    assert len(roster) == 15
    assert list(roster["name"]) == [f"Supplier {i:02d}" for i in range(1, 16)]
    assert roster["lead_time_days"].between(LEAD_TIME_DAYS_LOW, LEAD_TIME_DAYS_HIGH).all()
    assert roster["reliability_score"].between(RELIABILITY_SCORE_LOW, RELIABILITY_SCORE_HIGH).all()


def test_generate_supplier_roster_is_deterministic_given_same_seed() -> None:
    roster_a = generate_supplier_roster(np.random.default_rng(42), n_suppliers=5)
    roster_b = generate_supplier_roster(np.random.default_rng(42), n_suppliers=5)

    assert roster_a.equals(roster_b)


def test_assign_suppliers_gives_every_sku_a_valid_supplier_index() -> None:
    rng = np.random.default_rng(3)
    skus = [f"SKU{i}" for i in range(20)]

    assignment = assign_suppliers(skus, n_suppliers=5, rng=rng)

    assert set(assignment.keys()) == set(skus)
    assert all(0 <= index < 5 for index in assignment.values())


def test_assign_suppliers_is_independent_of_input_order() -> None:
    skus = ["B1", "A1", "C1"]
    shuffled = ["C1", "A1", "B1"]

    assignment_a = assign_suppliers(skus, n_suppliers=4, rng=np.random.default_rng(9))
    assignment_b = assign_suppliers(shuffled, n_suppliers=4, rng=np.random.default_rng(9))

    assert assignment_a == assignment_b
