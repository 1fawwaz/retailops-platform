"""Stage 1 Task 6: export a self-contained JSON Schema per endpoint response
to contracts/stockpilot-api/schemas/, and freeze the full OpenAPI document
as contracts/stockpilot-api/versions/v1.json.

tests/test_contracts.py regenerates both from the live app and fails if
they no longer match what's on disk -- that's what stops a response model
changing shape without the contract being deliberately re-frozen (and,
downstream, without the agent's generated client being regenerated to
match).

Reproducible: `python scripts/export_contracts.py`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.main import app  # noqa: E402

CONTRACTS_DIR = Path(__file__).resolve().parent.parent.parent / "contracts" / "stockpilot-api"
SCHEMAS_DIR = CONTRACTS_DIR / "schemas"
VERSIONS_DIR = CONTRACTS_DIR / "versions"
FROZEN_VERSION_PATH = VERSIONS_DIR / "v1.json"

SUCCESS_STATUS_CODES = ("200", "201")


def _rewrite_refs(node: Any) -> tuple[Any, set[str]]:
    """Recursively rewrites `#/components/schemas/X` refs to `#/$defs/X`
    (so the extracted fragment doesn't depend on the full OpenAPI
    document), collecting every component name reached along the way.
    """
    if isinstance(node, dict):
        if isinstance(node.get("$ref"), str) and node["$ref"].startswith("#/components/schemas/"):
            name = node["$ref"].removeprefix("#/components/schemas/")
            return {"$ref": f"#/$defs/{name}"}, {name}
        result: dict[str, Any] = {}
        refs: set[str] = set()
        for key, value in node.items():
            new_value, sub_refs = _rewrite_refs(value)
            result[key] = new_value
            refs |= sub_refs
        return result, refs
    if isinstance(node, list):
        result_list: list[Any] = []
        refs = set()
        for item in node:
            new_item, sub_refs = _rewrite_refs(item)
            result_list.append(new_item)
            refs |= sub_refs
        return result_list, refs
    return node, set()


def build_self_contained_schema(
    root_schema: dict[str, Any], components: dict[str, Any]
) -> dict[str, Any]:
    """A single endpoint's response schema, with every transitively
    referenced component schema bundled into a local `$defs` -- opening
    the file on its own is enough to validate a response against it.
    """
    rewritten_root, direct_refs = _rewrite_refs(root_schema)
    defs: dict[str, Any] = {}
    pending = list(direct_refs)
    while pending:
        name = pending.pop()
        if name in defs:
            continue
        rewritten_component, nested_refs = _rewrite_refs(components[name])
        defs[name] = rewritten_component
        pending.extend(sorted(nested_refs - defs.keys()))
    result = dict(rewritten_root)
    if defs:
        result["$defs"] = dict(sorted(defs.items()))
    return result


def extract_endpoint_schemas(openapi_schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """operationId -> self-contained response JSON Schema, for every
    operation with a JSON response body (skips 204 No Content routes).
    """
    components = openapi_schema.get("components", {}).get("schemas", {})
    endpoint_schemas: dict[str, dict[str, Any]] = {}
    for _path, operations in openapi_schema["paths"].items():
        for _method, operation in operations.items():
            operation_id = operation["operationId"]
            responses = operation.get("responses", {})
            success = next(
                (responses[code] for code in SUCCESS_STATUS_CODES if code in responses), None
            )
            if success is None:
                continue
            content = success.get("content", {}).get("application/json")
            if content is None:
                continue
            endpoint_schemas[operation_id] = build_self_contained_schema(
                content["schema"], components
            )
    return endpoint_schemas


def main() -> None:
    openapi_schema = app.openapi()
    endpoint_schemas = extract_endpoint_schemas(openapi_schema)

    SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)
    for existing in SCHEMAS_DIR.glob("*.json"):
        existing.unlink()
    for operation_id, schema in endpoint_schemas.items():
        (SCHEMAS_DIR / f"{operation_id}.json").write_text(json.dumps(schema, indent=2) + "\n")
    print(f"Wrote {len(endpoint_schemas)} endpoint schemas to {SCHEMAS_DIR}")

    VERSIONS_DIR.mkdir(parents=True, exist_ok=True)
    FROZEN_VERSION_PATH.write_text(json.dumps(openapi_schema, indent=2) + "\n")
    print(f"Froze full OpenAPI document to {FROZEN_VERSION_PATH}")


if __name__ == "__main__":
    main()
