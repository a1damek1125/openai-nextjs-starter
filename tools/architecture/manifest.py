"""Twin manifest loader + deterministic structural validator (SP0001 §17.1).

Dependency-free (no external `jsonschema` package required). Validates the
declared twin against the required shape, rejecting: path traversal, duplicate
capability ids, missing owners, invalid references, self-contradictory ownership.
If the `jsonschema` package IS installed, the JSON Schema file is additionally
enforced; otherwise the built-in validator is authoritative.
"""
from __future__ import annotations

import json
import os
from typing import Any

REQUIRED_TWIN_FIELDS = ["schema_version", "program", "capabilities",
                        "dependency_rules", "migration_integrity",
                        "effect_gates", "waiver_policy", "scanner_adapters"]
REQUIRED_CAP_FIELDS = ["capability_id", "canonical_owner", "canonical_paths"]


def _path_ok(p: str) -> bool:
    return ".." not in p.split("/") and not p.startswith("/") \
        and not p.startswith("~")


def validate_twin(twin: dict) -> list[str]:
    errors: list[str] = []
    for f in REQUIRED_TWIN_FIELDS:
        if f not in twin:
            errors.append(f"twin missing required field: {f}")
    if "capabilities" not in twin:
        return errors

    seen_ids: set[str] = set()
    route_ns: dict[str, str] = {}
    table_ns: dict[str, str] = {}
    for cap in twin["capabilities"]:
        for f in REQUIRED_CAP_FIELDS:
            if f not in cap:
                errors.append(f"capability missing field {f}: {cap.get('capability_id')}")
        cid = cap.get("capability_id")
        if cid in seen_ids:
            errors.append(f"duplicate capability id: {cid}")
        seen_ids.add(cid)
        if not cap.get("canonical_owner"):
            errors.append(f"capability {cid} has no canonical owner")
        for p in cap.get("canonical_paths", []):
            if not _path_ok(p):
                errors.append(f"path traversal / abs path in {cid}: {p}")
        # self-contradictory ownership: a namespace claimed twice
        for ns in cap.get("route_namespaces", []):
            if ns in route_ns and route_ns[ns] != cid:
                errors.append(f"route namespace {ns} declared by {route_ns[ns]} and {cid}")
            route_ns[ns] = cid
        for ns in cap.get("table_namespaces", []):
            if ns in table_ns and table_ns[ns] != cid:
                errors.append(f"table namespace {ns} declared by {table_ns[ns]} and {cid}")
            table_ns[ns] = cid
        for dep in cap.get("forbidden_dependencies", []):
            if not isinstance(dep, str):
                errors.append(f"invalid forbidden dependency ref in {cid}: {dep!r}")

    # cross-check: a FORBIDDEN dependency_rule must be reflected in the named
    # capability's forbidden_dependencies. Emptying the per-cap list while the
    # rule still stands is self-contradiction that would silently disable a P0
    # gate (red-team GAP-2). Anchoring the two representations makes tampering
    # visible to the tool, not only to a git diff.
    cap_by_id = {c.get("capability_id"): c for c in twin["capabilities"]}
    for rule in twin.get("dependency_rules", []):
        if rule.get("rule") == "FORBIDDEN":
            cid = rule.get("capability")
            pfx = rule.get("forbidden_import_prefix")
            cap = cap_by_id.get(cid)
            if cap is not None and pfx not in cap.get("forbidden_dependencies", []):
                errors.append(
                    f"twin self-contradiction: dependency_rule forbids {pfx} for "
                    f"{cid} but capability.forbidden_dependencies omits it")

    # optional strict schema enforcement if jsonschema is available
    try:
        import jsonschema  # type: ignore
        schema_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "docs", "architecture",
            "FINALIS_1000_ARCHITECTURE_TWIN_SCHEMA.json")
        if os.path.exists(schema_path):
            schema = json.load(open(schema_path, encoding="utf-8"))
            v = jsonschema.Draft202012Validator(schema)
            for e in v.iter_errors(twin):
                errors.append(f"jsonschema: {e.message}")
    except ImportError:
        pass  # built-in validator is authoritative
    return errors


def load_twin(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
