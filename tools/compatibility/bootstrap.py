"""Deterministically build docs/compatibility artifacts from repository truth
(SP0007 §9.4): the Compatibility Twin's example program, grounded in the REAL
contract surfaces SWARM-A inventoried — 405 FastAPI routes, the run-ledger
canonical event (finalis-run-event-v1), migrations v1..v27 (forward-only, no
down migrations), the 17-state case FSM, version-pinned proof envelopes, and the
provider Protocol seams. The generated program validates P0=0 / P1=0.

Run:  python -m tools.compatibility.bootstrap
"""
from __future__ import annotations

import json
import os

from .contracts import release
from .vector import build_claim, new_vector
from .canon import fixture_hash
from .negotiation import bridge

DOCS = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..", "..")), "docs",
                    "compatibility")

_DATE = "2026-07-12"
_VALIDATOR = "sp0007-compat-validator-1"


def _descriptor(cid, kind, owner, stability, crit, fmt, paths, *,
                corpus=False, refs=None):
    return {"contract_id": cid, "contract_kind": kind,
            "owner_capability": owner, "authority_class": "GOVERNANCE_REFERENCE",
            "semantic_concept_refs": refs or [], "producer_refs": paths[:1],
            "consumer_refs": [], "current_version": "1.0.0",
            "stability": stability, "criticality": crit,
            "canonical_format": fmt, "source_paths": paths,
            "requires_corpus": corpus}


def _descriptors() -> list[dict]:
    return [
        _descriptor("CT-HTTP-CASES", "HTTP_API", "case_services", "STABLE",
                    "C3", "fastapi-dict-v1", ["finalis/portal/app.py"],
                    corpus=True, refs=["case", "case_state"]),
        _descriptor("CT-EVENT-RUN-LEDGER", "EVENT_MESSAGE",
                    "ai_employee.run_ledger", "STABLE", "C4",
                    "finalis-run-event-v1",
                    ["finalis/ai_employee/run_ledger.py"], corpus=True,
                    refs=["run", "run_event"]),
        _descriptor("CT-DB-SCHEMA", "DB_SCHEMA", "portal.db", "STABLE", "C4",
                    "sqlite-migrations-v27", ["finalis/portal/db.py"]),
        _descriptor("CT-WF-CASE-FSM", "WORKFLOW_HISTORY", "state_machine",
                    "STABLE", "C3", "case-fsm-17-states",
                    ["finalis/state_machine.py"], refs=["case_state"]),
        _descriptor("CT-PROOF-RUN-EVENT", "PROOF_HASH",
                    "ai_employee.run_ledger", "STABLE", "C4",
                    "sha256-canonical-json",
                    ["finalis/ai_employee/run_ledger.py"]),
        _descriptor("CT-STORED-EVIDENCE", "STORED_DATA", "evidence.storage",
                    "STABLE", "C2", "evidence-object-v1",
                    ["finalis/evidence/storage.py"]),
        _descriptor("CT-SEMANTIC-CASE", "SEMANTIC", "semantics", "STABLE",
                    "C3", "sp0002-meaning-hash", ["tools/semantics/canon.py"],
                    refs=["case"]),
        _descriptor("CT-PROVIDER-TELEPHONY", "PROVIDER", "telephony.engine",
                    "STABLE", "C2", "python-protocol",
                    ["finalis/telephony/engine.py"]),
        _descriptor("CT-CLI-GOVERNANCE", "CLI_CONFIG", "tools.governance",
                    "BETA", "C1", "argparse-json", ["tools/semantics/cli.py"]),
        _descriptor("CT-UI-DASHBOARD", "UI_PROJECTION", "portal.ui", "BETA",
                    "C1", "html-projection", ["finalis/portal/ui.py"]),
    ]


def _http_schema_v1() -> dict:
    """The /cases transition contract as SWARM-A found it (dict-shaped)."""
    return {
        "fields": {
            "case_id": {"type": "string", "required": True, "nullable": False,
                        "default": None, "enum": None, "constraints": {},
                        "field_number": 1, "security_relevant": False},
            "to_state": {"type": "string", "required": True, "nullable": False,
                         "default": None,
                         "enum": ["QUALIFIED", "OFFER_SENT", "WON", "LOST"],
                         "constraints": {}, "field_number": 2,
                         "security_relevant": False},
            "actor": {"type": "string", "required": True, "nullable": False,
                      "default": None, "enum": None, "constraints": {},
                      "field_number": 3, "security_relevant": True},
        },
        "temporal": {"timezone": "UTC", "precision": "seconds"},
        "event_identity": {}, "idempotency": {}, "ordering": [],
    }


def _event_schema_v1() -> dict:
    """The run-ledger canonical event identity (finalis-run-event-v1)."""
    return {
        "fields": {
            "event_id": {"type": "string", "required": True, "nullable": False,
                         "default": None, "enum": None, "constraints": {},
                         "field_number": 1, "security_relevant": False},
            "run_id": {"type": "string", "required": True, "nullable": False,
                       "default": None, "enum": None, "constraints": {},
                       "field_number": 2, "security_relevant": False},
            "tenant_id": {"type": "string", "required": True, "nullable": False,
                          "default": None, "enum": None, "constraints": {},
                          "field_number": 3, "security_relevant": True},
        },
        "temporal": {"timezone": "UTC", "precision": "seconds",
                     "ordering": "event_index"},
        "event_identity": {"event_id_meaning": "uuid-per-event",
                           "dedup_key": "event_id",
                           "causation": "causal_parent_event_ids",
                           "partition_key": "run_id"},
        "idempotency": {"key": "event_id", "scope": "run"},
        "ordering": ["event_index"],
    }


def _versions() -> list[dict]:
    out = []
    for d in _descriptors():
        v = {"contract_id": d["contract_id"], "version": "1.0.0",
             "released_at": _DATE, "semantic_epoch": "sem-epoch-1",
             "schema": {}, "behavior_contract": {},
             "security_contract": {"auth": "bearer"},
             "proof_contract": None, "supersedes": None}
        if d["contract_id"] == "CT-HTTP-CASES":
            v["schema"] = _http_schema_v1()
        elif d["contract_id"] == "CT-EVENT-RUN-LEDGER":
            v["schema"] = _event_schema_v1()
        elif d["contract_id"] == "CT-PROOF-RUN-EVENT":
            v["proof_contract"] = {"proof_version": "finalis-run-event-v1",
                                   "algorithm": "sha256",
                                   "canonicalization": "sorted-compact-json"}
        elif d["contract_id"] == "CT-DB-SCHEMA":
            v["schema"] = {"migration_frontier": 27, "forward_only": True,
                           "down_migrations": 0}
        out.append(release(v))
    return out


# --- consumers + claims ------------------------------------------------------
_BOUND = ("CT-HTTP-CASES", "CT-EVENT-RUN-LEDGER", "CT-DB-SCHEMA",
          "CT-WF-CASE-FSM", "CT-PROOF-RUN-EVENT", "CT-SEMANTIC-CASE")


def _bindings() -> list[dict]:
    out = []
    for cid in _BOUND:
        out.append({"consumer_id": f"portal-ui::{cid.lower()}",
                    "contract_id": cid, "version_range": "1.0.0",
                    "version": "1.0.0", "protected": True,
                    "usage_profile": {"reads": True, "writes": False,
                                      "historical_reader": cid ==
                                      "CT-PROOF-RUN-EVENT"},
                    "required_fields": [], "accepted_outputs": {},
                    "unknown_field_policy": "PRESERVE", "criticality": "C3",
                    "enum_world": "OPEN", "active": True, "migrated": True,
                    "owner": "portal.ui", "last_observed": _DATE})
    return out


def _claims() -> list[dict]:
    vec = {d: "COMPATIBLE" for d in new_vector()}
    out = []
    for i, cid in enumerate(_BOUND, 1):
        out.append(build_claim(
            claim_id=f"CLM-{i:04d}", contract_id=cid,
            producer_version="1.0.0",
            consumer_id=f"portal-ui::{cid.lower()}", consumer_version="1.0.0",
            direction="NEW_PRODUCER_TO_OLD_CONSUMER",
            scenario_scope=["declared-supported-behavior"],
            compatibility_vector=dict(vec),
            evidence_refs=[f"FX-{cid}-COMMON"], validator_version=_VALIDATOR,
            tested_at=_DATE))
    return out


# --- historical corpus (D-0007-29/30) ----------------------------------------
def _fixture(cid, cls, kind, payload, expected):
    fx = {"fixture_id": f"FX-{cid}-{cls}", "contract_id": cid,
          "contract_version": "1.0.0", "fixture_kind": kind,
          "payload": payload, "expected_behavior": expected,
          "semantic_epoch": "sem-epoch-1", "tenant_class": "SYNTHETIC",
          "sensitivity": "NON_SENSITIVE", "corpus_class": cls,
          "provenance": {"source": "synthetic-bootstrap",
                         "derived_from": "repository-contract-truth"}}
    fx["fixture_hash"] = fixture_hash(fx)
    return fx


def _fixtures() -> list[dict]:
    out = []
    http = {"case_id": "case-0001", "to_state": "QUALIFIED", "actor": "ops"}
    for cls, payload, exp in (
            ("COMMON", http, {"status": 200}),
            ("EDGE", dict(http, to_state="WON"), {"status": 200}),
            ("ADVERSARIAL", dict(http, to_state="'; DROP--"),
             {"status": 422, "rejected": True}),
            ("RARE_CRITICAL", dict(http, case_id="case-terminal-reopen"),
             {"status": 409, "rejected": True}),
            ("INCIDENT_REPRODUCTION", dict(http, actor=""),
             {"status": 422, "rejected": True})):
        out.append(_fixture("CT-HTTP-CASES", cls, "REQUEST", payload, exp))
    ev = {"event_id": "evt-0001", "run_id": "run-0001",
          "tenant_id": "tenant-synthetic", "event_index": 1,
          "previous_event_hash": "GENESIS"}
    for cls, payload, exp in (
            ("COMMON", ev, {"accepted": True}),
            ("EDGE", dict(ev, event_index=2,
                          previous_event_hash="a" * 64), {"accepted": True}),
            ("ADVERSARIAL", dict(ev, tenant_id="tenant-OTHER"),
             {"accepted": False, "reason": "cross-tenant"}),
            ("RARE_CRITICAL", dict(ev, event_index=0),
             {"accepted": False, "reason": "index-contiguity"}),
            ("INCIDENT_REPRODUCTION", dict(ev, previous_event_hash=""),
             {"accepted": False, "reason": "broken-chain"})):
        out.append(_fixture("CT-EVENT-RUN-LEDGER", cls, "EVENT", payload, exp))
    return out


# --- migration graph (expand-only, mirrors forward-only DB reality) ----------
def _migration_edges() -> list[dict]:
    lv_none = {d: "NONE" for d in
               ("field_loss", "semantic_loss", "precision_loss", "history_loss",
                "provenance_loss", "authority_loss", "evidence_loss",
                "ordering_loss", "referential_loss")}
    return [
        {"migration_edge_id": "ME-HTTP-1to2", "contract_id": "CT-HTTP-CASES",
         "from_version": "1.0.0", "to_version": "2.0.0",
         "transformer_ref": "TR-HTTP-1to2",
         "inverse_transformer_ref": "TR-HTTP-2to1",
         "inverse_verified": True,
         "preconditions": ["expand: to_state enum widened only"],
         "postconditions": ["old requests still accepted"],
         "loss_vector": dict(lv_none), "reversibility": "REVERSIBLE",
         "downtime_class": "NONE", "lock_profile": {},
         "last_safe_rollback_point": "ME-HTTP-1to2:contract",
         "operational_risk": 1, "evidence_refs": ["RT-HTTP-1to2"]},
        {"migration_edge_id": "ME-DB-add-column",
         "contract_id": "CT-DB-SCHEMA", "from_version": "1.0.0",
         "to_version": "1.1.0", "transformer_ref": "TR-DB-add-column",
         "inverse_transformer_ref": None,
         "preconditions": ["ADD COLUMN with default (online-safe)"],
         "postconditions": ["v27 readers unaffected"],
         "loss_vector": dict(lv_none), "reversibility": "ONE_WAY",
         "downtime_class": "NONE", "lock_profile": {"lock": "ACCESS_EXCLUSIVE",
                                                    "brief": True},
         "last_safe_rollback_point": "ME-DB-add-column:pre-backfill",
         "forward_fix_plan_ref": "FF-DB-add-column",
         "irreversible_declared": True, "operational_risk": 2,
         "evidence_refs": []},
    ]


def _migration_plans() -> list[dict]:
    return [{"migration_plan_id": "MP-HTTP-2", "change_intent_ref": "CI-HTTP-2",
             "source_versions": ["1.0.0"], "target_version": "2.0.0",
             "steps": [{"step_id": "S1", "phase": "EXPAND",
                        "idempotency_key": "mp-http-2-expand"},
                       {"step_id": "S2", "phase": "MIGRATE",
                        "idempotency_key": "mp-http-2-migrate"},
                       {"step_id": "S3", "phase": "VERIFY",
                        "idempotency_key": "mp-http-2-verify"},
                       {"step_id": "S4", "phase": "CONTRACT",
                        "idempotency_key": "mp-http-2-contract"}],
             "consumer_order": ["portal-ui::ct-http-cases"],
             "expand_phase": {"breaks_old_consumers": False},
             "migrate_phase": {"dual_read": True},
             "verify_phase": {"replay": True},
             "contract_phase": {"gated": True},
             "rollback_plan_ref": "RB-HTTP-2",
             "forward_fix_plan_ref": "FF-HTTP-2",
             "approval_requirements": ["A2"], "status": "DRAFT"}]


def _deprecations() -> list[dict]:
    return [{"deprecation_id": "DEP-HTTP-V1", "contract_id": "CT-HTTP-CASES",
             "version": "1.0.0", "surface": "/cases/{id}/transition v1",
             "replacement": "/cases/{id}/transition v2", "replacement_required": True,
             "reason": "widened to_state enum needs v2 negotiation",
             "announced_in": "2.0.0", "support_until": "2027-07-12",
             "support_window_ref": "SW-HTTP-V1",
             "sunset_conditions": ["all known consumers migrated",
                                   "no unknown critical consumer"],
             "active_consumer_refs": ["portal-ui::ct-http-cases"],
             "status": "ANNOUNCED"}]


def _support_windows() -> list[dict]:
    return [{"support_window_id": "SW-HTTP-V1", "contract_id": "CT-HTTP-CASES",
             "version": "1.0.0", "status": "ACTIVE",
             "review_due": "2027-01-12", "expires_at": "2027-07-12"}]


def _reserved() -> dict:
    return {"reserved_field_numbers": {"CT-EVENT-RUN-LEDGER": [90, 91, 92]},
            "reserved_enum_codes": {"CT-HTTP-CASES": ["LEGACY_HOLD"]},
            "reserved_event_ids": ["run.cancelled.v0"],
            "reserved_field_names": {"CT-EVENT-RUN-LEDGER": ["legacy_run_key"]}}


def _proof_readers() -> list[dict]:
    return [{"proof_version": "finalis-run-event-v1",
             "reader": "run_ledger.verify_events", "reinterprets": False,
             "supported_versions": ["finalis-run-event-v1"]}]


def _provider_pins() -> list[dict]:
    return [{"provider": "telephony", "contract_id": "CT-PROVIDER-TELEPHONY",
             "version": "mock-telephony-v1", "protected": True}]


def _change_intents() -> list[dict]:
    return [{"change_intent_id": "CI-HTTP-2", "intent_id": "CI-HTTP-2",
             "changed_surface": "CT-HTTP-CASES", "surface": "CT-HTTP-CASES",
             "old_version": "1.0.0", "new_version": "2.0.0",
             "compatibility_directions": ["NEW_PRODUCER_TO_OLD_CONSUMER",
                                          "OLD_PRODUCER_TO_NEW_CONSUMER"],
             "consumers": ["portal-ui::ct-http-cases"],
             "migration_plan_ref": "MP-HTTP-2", "deprecation_ref": "DEP-HTTP-V1",
             "rollback_ref": "RB-HTTP-2", "forward_fix_ref": "FF-HTTP-2",
             "proof_impact": "no proof-contract change",
             "security_impact": "none — actor field unchanged",
             "architecture_refs": ["L7"], "semantic_refs": ["case_state"]}]


def _bridges() -> list[dict]:
    b = bridge("PROTOCOL_VERSION", "finalis-run-event-v1",
               "finalis-run-event-v1", rules={"identity": True})
    b["bridge_id"] = "BR-RUN-EVENT"
    return [b]


def build_program() -> dict:
    return {
        "descriptors": _descriptors(),
        "versions": _versions(),
        "bindings": _bindings(),
        "claims": _claims(),
        "fixtures": _fixtures(),
        "migration_edges": _migration_edges(),
        "migration_plans": _migration_plans(),
        "deprecations": _deprecations(),
        "support_windows": _support_windows(),
        "reserved_identifiers": _reserved(),
        "proof_readers": _proof_readers(),
        "provider_pins": _provider_pins(),
        "change_intents": _change_intents(),
        "adapters": [],
        "bridges": _bridges(),
        "workflow_changes": [],
        "proof_envelopes": [],
    }


_FILE_MAP = {
    "FINALIS_CONTRACT_DESCRIPTORS.json": ("descriptors",),
    "FINALIS_CONTRACT_VERSIONS.json": ("versions",),
    "FINALIS_CONSUMER_BINDINGS.json": ("bindings",),
    "FINALIS_COMPATIBILITY_CLAIMS.json": ("claims",),
    "FINALIS_HISTORICAL_CORPUS.json": ("fixtures",),
    "FINALIS_MIGRATION_GRAPH.json": ("migration_edges",),
    "FINALIS_MIGRATION_PLANS.json": ("migration_plans",),
    "FINALIS_DEPRECATIONS.json": ("deprecations",),
    "FINALIS_SUPPORT_WINDOWS.json": ("support_windows",),
    "FINALIS_RESERVED_IDENTIFIERS.json": ("reserved_identifiers",),
    "FINALIS_PROOF_READERS.json": ("proof_readers",),
    "FINALIS_PROVIDER_PINS.json": ("provider_pins",),
    "FINALIS_CHANGE_INTENTS.json": ("change_intents",),
}


def _dump(path, payload):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True, ensure_ascii=False)
        fh.write("\n")


def write_artifacts(program: dict, docs_dir: str = DOCS) -> dict:
    os.makedirs(docs_dir, exist_ok=True)
    for fname, keys in _FILE_MAP.items():
        payload = {}
        for k in keys:
            payload[k] = program.get(k, [] if k != "reserved_identifiers"
                                     else {})
        _dump(os.path.join(docs_dir, fname), payload)
    _write_schemas(docs_dir)
    return {"descriptors": len(program["descriptors"]),
            "versions": len(program["versions"]),
            "claims": len(program["claims"]),
            "fixtures": len(program["fixtures"]),
            "migration_edges": len(program["migration_edges"])}


def _schema(title, required, props):
    return {"schema_id": title, "type": "object", "required": required,
            "properties": {p: {"type": t} for p, t in props.items()},
            "additionalProperties": True}


_SCHEMAS = {
    "FINALIS_CONTRACT_SURFACE_TAXONOMY.json": {
        "schema_id": "ContractSurfaceTaxonomy",
        "contract_kinds": list(__import__("tools.compatibility.model",
                                          fromlist=["CONTRACT_KINDS"])
                               .CONTRACT_KINDS),
        "note": "authoritative alphabets live in tools/compatibility/model.py"},
    "FINALIS_CONTRACT_DESCRIPTOR_SCHEMA.json": _schema(
        "ContractDescriptor", ["contract_id", "contract_kind",
                              "owner_capability", "stability", "criticality"],
        {"contract_id": "string", "contract_kind": "string",
         "owner_capability": "string", "authority_class": "string",
         "semantic_concept_refs": "array", "producer_refs": "array",
         "consumer_refs": "array", "current_version": "string",
         "stability": "string", "criticality": "string",
         "canonical_format": "string", "source_paths": "array"}),
    "FINALIS_CONTRACT_VERSION_SCHEMA.json": _schema(
        "ContractVersion", ["contract_id", "version", "status"],
        {"contract_id": "string", "version": "string", "released_at": "string",
         "status": "string", "semantic_epoch": "string", "schema": "object",
         "behavior_contract": "object", "security_contract": "object",
         "proof_contract": "object", "supersedes": "string",
         "immutable": "boolean", "content_hash": "string"}),
    "FINALIS_CONSUMER_BINDING_SCHEMA.json": _schema(
        "ConsumerBinding", ["consumer_id", "contract_id", "version_range",
                           "owner"],
        {"consumer_id": "string", "contract_id": "string",
         "version_range": "string", "usage_profile": "object",
         "required_fields": "array", "accepted_outputs": "object",
         "unknown_field_policy": "string", "criticality": "string",
         "owner": "string"}),
    "FINALIS_COMPATIBILITY_VECTOR_SCHEMA.json": _schema(
        "CompatibilityVector", [],
        {d: "string" for d in __import__("tools.compatibility.model",
                                         fromlist=["COMPAT_DIMENSIONS"])
         .COMPAT_DIMENSIONS}),
    "FINALIS_COMPATIBILITY_CLAIM_SCHEMA.json": _schema(
        "CompatibilityClaim", ["claim_id", "producer_version",
                              "consumer_version", "direction", "scenario_scope",
                              "evidence_refs", "validator_version", "tested_at"],
        {"claim_id": "string", "contract_id": "string",
         "producer_version": "string", "consumer_id": "string",
         "consumer_version": "string", "direction": "string",
         "scenario_scope": "array", "compatibility_vector": "object",
         "hard_gate_result": "string", "evidence_refs": "array",
         "environment_hash": "string", "validator_version": "string",
         "tested_at": "string", "expires_at": "string", "status": "string"}),
    "FINALIS_COMPATIBILITY_EVIDENCE_SCHEMA.json": _schema(
        "CompatibilityEvidence", ["evidence_id", "kind"],
        {"evidence_id": "string", "kind": "string", "fixture_refs": "array",
         "result": "object", "produced_by": "string"}),
    "FINALIS_MIGRATION_GRAPH_SCHEMA.json": _schema(
        "MigrationEdge", ["migration_edge_id", "contract_id", "from_version",
                         "to_version", "transformer_ref", "loss_vector",
                         "reversibility"],
        {"migration_edge_id": "string", "contract_id": "string",
         "from_version": "string", "to_version": "string",
         "transformer_ref": "string", "inverse_transformer_ref": "string",
         "preconditions": "array", "postconditions": "array",
         "loss_vector": "object", "reversibility": "string",
         "downtime_class": "string", "lock_profile": "object",
         "last_safe_rollback_point": "string", "evidence_refs": "array"}),
    "FINALIS_MIGRATION_PLAN_SCHEMA.json": _schema(
        "MigrationPlan", ["migration_plan_id", "source_versions",
                         "target_version", "steps", "status"],
        {"migration_plan_id": "string", "change_intent_ref": "string",
         "source_versions": "array", "target_version": "string",
         "steps": "array", "consumer_order": "array", "expand_phase": "object",
         "migrate_phase": "object", "verify_phase": "object",
         "contract_phase": "object", "rollback_plan_ref": "string",
         "forward_fix_plan_ref": "string", "approval_requirements": "array",
         "status": "string"}),
    "FINALIS_MIGRATION_STEP_SCHEMA.json": _schema(
        "MigrationStep", ["step_id", "phase"],
        {"step_id": "string", "phase": "string", "preconditions": "array",
         "operation": "object", "postconditions": "array",
         "idempotency_key": "string", "checkpoint_policy": "object",
         "failure_policy": "object", "rollback_boundary_effect": "string",
         "status": "string"}),
    "FINALIS_TRANSFORMER_SCHEMA.json": _schema(
        "Transformer", ["transformer_id", "from_version", "to_version"],
        {"transformer_id": "string", "from_version": "string",
         "to_version": "string", "rules": "object", "loss_vector": "object",
         "inverse_verified": "boolean"}),
    "FINALIS_LOSS_VECTOR_SCHEMA.json": _schema(
        "LossVector", [],
        {d: "string" for d in __import__("tools.compatibility.model",
                                         fromlist=["LOSS_DIMENSIONS"])
         .LOSS_DIMENSIONS}),
    "FINALIS_ROLLBACK_PLAN_SCHEMA.json": _schema(
        "RollbackPlan", ["rollback_plan_id", "edge_ids"],
        {"rollback_plan_id": "string", "edge_ids": "array",
         "step_order": "array", "last_safe_rollback_point": "string",
         "forward_fix_plan_ref": "string"}),
    "FINALIS_DEPRECATION_SCHEMA.json": _schema(
        "DeprecationNotice", ["deprecation_id", "contract_id", "version",
                             "surface", "status"],
        {"deprecation_id": "string", "contract_id": "string", "version": "string",
         "surface": "string", "replacement": "string", "reason": "string",
         "announced_in": "string", "support_until": "string",
         "sunset_conditions": "array", "active_consumer_refs": "array",
         "status": "string"}),
    "FINALIS_SUPPORT_WINDOW_SCHEMA.json": _schema(
        "SupportWindow", ["support_window_id", "contract_id", "status"],
        {"support_window_id": "string", "contract_id": "string",
         "version": "string", "status": "string", "review_due": "string",
         "expires_at": "string", "waiver_expires_at": "string"}),
    "FINALIS_HISTORICAL_CORPUS_SCHEMA.json": _schema(
        "HistoricalFixture", ["fixture_id", "contract_id", "contract_version",
                             "fixture_kind", "semantic_epoch", "corpus_class"],
        {"fixture_id": "string", "contract_id": "string",
         "contract_version": "string", "fixture_kind": "string",
         "payload": "object", "expected_behavior": "object",
         "semantic_epoch": "string", "tenant_class": "string",
         "sensitivity": "string", "corpus_class": "string",
         "provenance": "object", "fixture_hash": "string"}),
    "FINALIS_COMPATIBILITY_PROOF_SCHEMA.json": _schema(
        "CompatibilityProofEnvelope", ["envelope_version", "envelope_hash"],
        {"envelope_version": "string", "contract_descriptor_hash": "string",
         "producer_version_hash": "string", "consumer_binding_hash": "string",
         "compatibility_vector_hash": "string", "historical_corpus_hash": "string",
         "semantic_analysis_hash": "string", "behavioral_analysis_hash": "string",
         "replay_result_hash": "string", "security_result_hash": "string",
         "validator_version": "string", "envelope_hash": "string"}),
    "FINALIS_MIGRATION_PROOF_SCHEMA.json": _schema(
        "MigrationProofEnvelope", ["envelope_version", "envelope_hash"],
        {"envelope_version": "string", "migration_plan_hash": "string",
         "source_state_hash": "string", "target_state_hash": "string",
         "transformer_hash": "string", "checkpoint_manifest_hash": "string",
         "loss_vector_hash": "string", "round_trip_result_hash": "string",
         "replay_result_hash": "string", "rollback_result_hash": "string",
         "consumer_verification_hash": "string", "validator_version": "string",
         "envelope_hash": "string"}),
    "FINALIS_REASON_CODE_REGISTRY.json": {
        "schema_id": "ReasonCodeRegistry",
        "note": "finding kinds are defined in tools/compatibility/model.py"},
}


def _write_schemas(docs_dir):
    for fname, schema in _SCHEMAS.items():
        _dump(os.path.join(docs_dir, fname), schema)


def write(docs_dir: str = DOCS) -> dict:
    return write_artifacts(build_program(), docs_dir)


if __name__ == "__main__":
    print(json.dumps(write(), indent=2, sort_keys=True))
