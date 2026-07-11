"""Typed data model for the Architecture Immune System.

Plain dataclasses + enums; no external deps. Findings carry a deterministic
severity so hard gates stay Boolean (P0/P1) and advisory signals (P2) never
override them (SP0001 D-0001-09, INV-0001-06).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# --- severities -------------------------------------------------------------
P0 = "P0"   # hard architecture violation — blocks
P1 = "P1"   # hard architecture violation — blocks
P2 = "P2"   # advisory / longitudinal — never blocks on its own
SEVERITIES = (P0, P1, P2)

# --- finding kinds (also the architecture "event" names, SP0001 §16) --------
FORBIDDEN_DEPENDENCY = "FORBIDDEN_DEPENDENCY"
CAPABILITY_OWNERSHIP_CONFLICT = "CAPABILITY_OWNERSHIP_CONFLICT"
UNOWNED_NODE = "UNOWNED_NODE"
MIGRATION_MUTATION = "MIGRATION_MUTATION"
EFFECT_GATE_VIOLATION = "EFFECT_GATE_VIOLATION"
SPEC_CODE_DRIFT_DETECTED = "SPEC_CODE_DRIFT_DETECTED"
ARCHITECTURE_DRIFT_DETECTED = "ARCHITECTURE_DRIFT_DETECTED"
UNDECLARED_ARCHITECTURE_DRIFT = "UNDECLARED_ARCHITECTURE_DRIFT"
DUPLICATION_CANDIDATE = "DUPLICATION_CANDIDATE"
WAIVER_EXPIRED = "WAIVER_EXPIRED"
SCAN_ERROR = "SCAN_ERROR"
UNSUPPORTED_LANGUAGE = "UNSUPPORTED_LANGUAGE_ARCHITECTURE_SCAN"


@dataclass(frozen=True)
class Finding:
    kind: str
    severity: str
    capability: str
    message: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "severity": self.severity,
                "capability": self.capability, "message": self.message,
                "detail": self.detail}


@dataclass
class Capability:
    capability_id: str
    display_name: str
    canonical_owner: str
    classification: str
    purpose: str
    canonical_paths: list[str] = field(default_factory=list)
    extension_points: list[str] = field(default_factory=list)
    route_namespaces: list[str] = field(default_factory=list)
    table_namespaces: list[str] = field(default_factory=list)
    permission_namespaces: list[str] = field(default_factory=list)
    spec_anchors: list[str] = field(default_factory=list)
    test_anchors: list[str] = field(default_factory=list)
    allowed_dependencies: list[str] = field(default_factory=list)
    forbidden_dependencies: list[str] = field(default_factory=list)
    replacement_policy: str = "DO_NOT_REBUILD"

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Capability":
        return Capability(
            capability_id=d["capability_id"],
            display_name=d.get("display_name", d["capability_id"]),
            canonical_owner=d["canonical_owner"],
            classification=d.get("classification", ""),
            purpose=d.get("purpose", ""),
            canonical_paths=list(d.get("canonical_paths", [])),
            extension_points=list(d.get("extension_points", [])),
            route_namespaces=list(d.get("route_namespaces", [])),
            table_namespaces=list(d.get("table_namespaces", [])),
            permission_namespaces=list(d.get("permission_namespaces", [])),
            spec_anchors=list(d.get("spec_anchors", [])),
            test_anchors=list(d.get("test_anchors", [])),
            allowed_dependencies=list(d.get("allowed_dependencies", [])),
            forbidden_dependencies=list(d.get("forbidden_dependencies", [])),
            replacement_policy=d.get("replacement_policy", "DO_NOT_REBUILD"),
        )


@dataclass
class ObservedSnapshot:
    commit: str
    modules: list[str]
    capabilities: list[str]
    import_edges: list[list[str]]        # [from_module, to_module]
    route_edges: list[list[str]]         # [route_namespace, source]
    data_ownership: list[list[str]]      # [table, migration_version]
    migration_digests: list[list[str]]   # [version, sha256]
    effect_observations: list[dict[str, Any]]
    metrics: dict[str, Any] = field(default_factory=dict)
    scan_errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "commit": self.commit,
            "modules": sorted(self.modules),
            "capabilities": sorted(self.capabilities),
            "import_edges": sorted(self.import_edges),
            "route_edges": sorted(self.route_edges),
            "data_ownership": sorted(self.data_ownership),
            "migration_digests": sorted(self.migration_digests),
            "effect_observations": sorted(
                self.effect_observations, key=lambda e: canonical_key(e)),
            "metrics": self.metrics,
            "scan_errors": sorted(self.scan_errors, key=lambda e: canonical_key(e)),
        }


def canonical_key(d: dict[str, Any]) -> str:
    import json
    return json.dumps(d, sort_keys=True)
