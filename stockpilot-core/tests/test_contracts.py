"""Fails if any endpoint's response shape has drifted from the frozen
contract in contracts/stockpilot-api/versions/v1.json (Stage 1 Task 6).

This is what stops the agent silently breaking when the environment
changes: if a response model's fields change, this test fails until
someone deliberately runs scripts/export_contracts.py, reviews the diff,
and commits the new frozen version -- not silently.
"""

import json
from pathlib import Path

from api.main import app
from scripts.export_contracts import extract_endpoint_schemas

CONTRACTS_DIR = Path(__file__).resolve().parent.parent.parent / "contracts" / "stockpilot-api"
FROZEN_VERSION_PATH = CONTRACTS_DIR / "versions" / "v1.json"
SCHEMAS_DIR = CONTRACTS_DIR / "schemas"


def test_frozen_contract_file_exists() -> None:
    assert FROZEN_VERSION_PATH.exists(), (
        f"{FROZEN_VERSION_PATH} is missing -- run scripts/export_contracts.py"
    )


def test_live_openapi_schema_matches_frozen_contract() -> None:
    frozen = json.loads(FROZEN_VERSION_PATH.read_text())
    live = app.openapi()

    assert live == frozen, (
        "The live OpenAPI schema no longer matches contracts/stockpilot-api/versions/v1.json. "
        "If this change is intentional, run scripts/export_contracts.py, review the diff, "
        "and commit the refreshed contract."
    )


def test_every_endpoint_schema_file_matches_the_live_app() -> None:
    live_endpoint_schemas = extract_endpoint_schemas(app.openapi())
    on_disk = {path.stem: json.loads(path.read_text()) for path in SCHEMAS_DIR.glob("*.json")}

    assert set(on_disk) == set(live_endpoint_schemas), (
        "contracts/stockpilot-api/schemas/ doesn't have exactly one file per current endpoint -- "
        "run scripts/export_contracts.py."
    )
    for operation_id, live_schema in live_endpoint_schemas.items():
        assert on_disk[operation_id] == live_schema, (
            f"{operation_id}.json is stale -- run scripts/export_contracts.py."
        )


def test_every_response_schema_declares_at_least_one_example() -> None:
    components = app.openapi().get("components", {}).get("schemas", {})
    exempt = {"HTTPValidationError", "ValidationError", "Body_login_auth_login_post"}
    missing_examples = [
        name
        for name, schema in components.items()
        if name not in exempt and "examples" not in schema
    ]

    assert not missing_examples, (
        f"These response/request models have no OpenAPI example: {missing_examples}"
    )
