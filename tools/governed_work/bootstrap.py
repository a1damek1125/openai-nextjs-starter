"""Deterministically build docs/governed_work artifacts from a canonical, valid
governed-work example program (SP0006 §9.15). The generated program validates
P0=0 / P1=0 and demonstrates every constitutional structure: candidate intent →
canonical work order → execution identities → attenuated capability leases →
delegation DAG → budget ledger → approval token → outcome contract → recurring
contract → accountability chain, plus the JSON schemas.

Run:  python -m tools.governed_work.bootstrap
"""
from __future__ import annotations

import json
import os

from .canon import semantic_work_hash, work_instance_hash
from .workorder import compile_work_order
from .lease import attenuate
from .budget import new_ledger

DOCS = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..", "..")), "docs",
                    "governed_work")


# --- example canonical program ---------------------------------------------
def _candidate_intent() -> dict:
    return {"candidate_intent_id": "CI-0001", "tenant_id": "tenant-acme",
            "requester_id": "user-ana", "source_surface": "SLACK",
            "source_reference": "slack://C123/T456",
            "proposed_goal": "prepare and send the March invoice to ACME billing",
            "proposed_scope": {"target": ["invoice:INV-2026-03"],
                               "channel": ["email"]},
            "proposed_constraints": [{"constraint_id": "K-approval",
                                      "rule": "requires owner approval before send"}],
            "proposed_outcomes": ["invoice sent and acknowledged"],
            "interpretation_source": "LLM", "status": "UNTRUSTED_PROPOSAL"}


def _outcome_contract() -> dict:
    return {"outcome_contract_id": "OC-0001", "work_order_id": "WO-0001",
            "expected_outcomes": ["invoice INV-2026-03 delivered and acknowledged"],
            "acceptance_predicates": [
                {"predicate_id": "P1", "predicate_type": "ARTIFACT_EXISTS",
                 "artifact_ref": "invoice:INV-2026-03"},
                {"predicate_id": "P2", "predicate_type": "EXTERNAL_ACKNOWLEDGMENT",
                 "source": "billing@acme.example"},
                {"predicate_id": "P3", "predicate_type": "NO_FORBIDDEN_EFFECT"}],
            "required_artifacts": ["invoice:INV-2026-03"],
            "required_evidence": ["delivery_receipt", "ack_event"],
            "forbidden_outcomes": ["duplicate payment", "cross-tenant disclosure"],
            "verification_mode": "INDEPENDENT_QUALIFIED",
            "verifier_requirements": {"independent": True,
                                      "not_the_acting_agent": True},
            "dispute_policy": {"window_days": 30},
            "defeater_policy": {"reopen_on_new_evidence": True},
            "completion_rule": "ALL"}


def _budget_vector() -> dict:
    return {"budget_id": "BV-0001", "work_order_id": "WO-0001",
            "financial_cost": {"total": 0, "unit": "USD"},
            "model_cost": {"total": 200000, "unit": "tokens"},
            "tool_call_quota": {"total": 50, "unit": "calls"},
            "external_effect_quota": {"total": 1, "unit": "sends"},
            "data_access_quota": {"total": 100, "unit": "records"},
            "resource_capacity": {"total": 4, "unit": "workers"},
            "risk_vector": {"operational": "LOW", "financial": "LOW",
                            "privacy": "MEDIUM", "security": "LOW",
                            "legal": "LOW", "rights": "LOW",
                            "reputation": "LOW", "irreversibility": "MEDIUM"},
            "deadline": "2026-03-31T23:59:59Z"}


def _work_order() -> dict:
    ci = _candidate_intent()
    w = compile_work_order(ci, bindings={
        "work_order_id": "WO-0001",
        "accountable_owner_id": "owner-finance-lead",
        "semantic_epoch": "gw-epoch-1",
        "forbidden_scope": {"target": ["ledger:general"], "channel": ["sms"]},
        "outcome_contract": _outcome_contract(),
        "capability_ceiling": {"max_delegation_depth": 4,
                               "max_direct_fanout": 8,
                               "max_descendant_count": 64,
                               "effect_classes": ["READ", "DRAFT", "COMMUNICATION"]},
        "budget_vector": _budget_vector(),
        "privacy_purpose": "billing_operations",
        "retention_rule": "retain_7y",
        "approval_topology": {"topology_id": "AT-0001", "required_class": "A2"},
        "issued_at": "2026-03-01T09:00:00Z",
        "expires_at": "2026-03-31T23:59:59Z",
        "dependency_envelope_ref": "docs/program/FINALIS_1000_PROGRAM_HYPERGRAPH.json",
        "technology_envelope_ref": "docs/technology/FINALIS_TECHNOLOGY_REGISTRY.json",
        "safety_envelope_ref": "docs/safety/FINALIS_HAZARD_REGISTRY.json",
        "risk_requirements": {"non_compensatory": True},
    })
    w["status"] = "ADMITTED"
    return w


def _identities() -> list[dict]:
    return [
        {"execution_identity_id": "EI-root", "work_order_id": "WO-0001",
         "parent_identity_id": None, "role": "ROOT_AGENT", "delegation_depth": 0,
         "responsibility_scope": {"whole": True}, "lease_refs": ["LEASE-root"],
         "created_at": "2026-03-01T09:00:00Z", "expires_at": "2026-03-31T23:59:59Z",
         "status": "ACTIVE"},
        {"execution_identity_id": "EI-drafter", "work_order_id": "WO-0001",
         "parent_identity_id": "EI-root", "role": "SUBAGENT_DRAFTER",
         "delegation_depth": 1, "responsibility_scope": {"draft": True},
         "lease_refs": ["LEASE-drafter"], "created_at": "2026-03-01T09:05:00Z",
         "expires_at": "2026-03-31T23:59:59Z", "status": "ACTIVE"},
        {"execution_identity_id": "EI-verifier", "work_order_id": "WO-0001",
         "parent_identity_id": "EI-root", "role": "INDEPENDENT_VERIFIER",
         "delegation_depth": 1, "responsibility_scope": {"verify": True},
         "lease_refs": ["LEASE-verifier"], "created_at": "2026-03-01T09:05:00Z",
         "expires_at": "2026-03-31T23:59:59Z", "status": "ACTIVE"},
    ]


def _root_lease() -> dict:
    return {"lease_id": "LEASE-root", "root_authority_ref": "WO-0001-authority",
            "parent_lease_id": None, "issuer_identity": "owner-finance-lead",
            "subject_identity": "EI-root", "tenant_id": "tenant-acme",
            "work_order_id": "WO-0001", "purpose": "billing_operations",
            "targets": ["invoice:INV-2026-03", "email:billing@acme.example"],
            "allowed_operations": ["read", "draft", "send"],
            "forbidden_operations": ["delete", "pay"],
            "effect_classes": ["READ", "DRAFT", "COMMUNICATION"],
            "data_classes": ["invoice", "contact"],
            "risk_ceiling": {"financial": "LOW", "irreversibility": "MEDIUM"},
            "cost_ceiling": {"financial_cost": 0, "external_effect_quota": 1},
            "issued_at": "2026-03-01T09:00:00Z", "not_before": "2026-03-01T09:00:00Z",
            "expires_at": "2026-03-31T23:59:59Z", "maximum_uses": 10,
            "current_uses": 0, "approval_floor": "A2", "revocation_state": "ACTIVE",
            "attenuation_delta": {}, "integrity_hash": ""}


def _leases() -> list[dict]:
    root = _root_lease()
    drafter = attenuate(root, {
        "lease_id": "LEASE-drafter", "subject_identity": "EI-drafter",
        "issuer_identity": "EI-root",
        "targets": ["invoice:INV-2026-03"],
        "allowed_operations": ["read", "draft"],
        "effect_classes": ["READ", "DRAFT"], "data_classes": ["invoice"],
        "risk_ceiling": {"financial": "LOW", "irreversibility": "LOW"},
        "cost_ceiling": {"financial_cost": 0, "external_effect_quota": 0},
        "maximum_uses": 4, "approval_floor": "A2"})
    verifier = attenuate(root, {
        "lease_id": "LEASE-verifier", "subject_identity": "EI-verifier",
        "issuer_identity": "EI-root",
        "targets": ["invoice:INV-2026-03"],
        "allowed_operations": ["read"], "effect_classes": ["READ"],
        "data_classes": ["invoice"],
        "risk_ceiling": {"financial": "NONE", "irreversibility": "NONE"},
        "cost_ceiling": {"financial_cost": 0, "external_effect_quota": 0},
        "maximum_uses": 3, "approval_floor": "A0"})
    return [root, drafter, verifier]


def _delegation_edges() -> list[dict]:
    return [
        {"delegation_id": "DEL-1", "work_order_id": "WO-0001",
         "parent_identity": "EI-root", "child_identity": "EI-drafter",
         "parent_lease_refs": ["LEASE-root"], "child_lease_refs": ["LEASE-drafter"],
         "subtask_scope": {"draft_invoice": True},
         "budget_reservation_refs": ["RES-1"],
         "accountable_owner_id": "owner-finance-lead",
         "attenuation_proof_hash": "", "status": "ACTIVE"},
        {"delegation_id": "DEL-2", "work_order_id": "WO-0001",
         "parent_identity": "EI-root", "child_identity": "EI-verifier",
         "parent_lease_refs": ["LEASE-root"], "child_lease_refs": ["LEASE-verifier"],
         "subtask_scope": {"verify_outcome": True},
         "budget_reservation_refs": ["RES-2"],
         "accountable_owner_id": "owner-finance-lead",
         "attenuation_proof_hash": "", "status": "ACTIVE"},
    ]


def _budget_ledgers() -> list[dict]:
    led = new_ledger(_budget_vector())
    led["budget_id"] = "BL-0001"
    led["work_order_id"] = "WO-0001"
    return [led]


def _approval_topology() -> dict:
    return {"approval_topology_id": "AT-0001", "work_order_id": "WO-0001",
            "required_floor": "A2",
            "classes": ["A0", "A1", "A2", "A3", "A4", "A5"],
            "independence_constraints": {"no_self_approval": True},
            "quorum": {"A4": {"number_of_approvers": 2, "distinct_identities": True}}}


def _approval_tokens() -> list[dict]:
    return [{"approval_token_id": "APT-0001", "work_instance_hash": "",
             "action_fingerprint": "", "target_fingerprint": "",
             "material_parameters_hash": "", "effect_class": "COMMUNICATION",
             "risk_snapshot_hash": "", "required_class": "A2",
             "approver_id": "owner-finance-lead", "approver_class": "A2",
             "issued_at": "2026-03-05T10:00:00Z",
             "expires_at": "2026-03-06T10:00:00Z", "maximum_uses": 1,
             "current_uses": 0, "status": "ACTIVE", "integrity_hash": ""}]


def _recurring_contract() -> dict:
    return {"recurrence_contract_id": "RC-0001",
            "semantic_work_hash": semantic_work_hash(_work_order()),
            "cadence": "MONTHLY", "purpose": "billing_operations",
            "scope_ceiling": {"target": ["invoice:*"]},
            "capability_ceiling": {"effect_classes": ["READ", "DRAFT",
                                                      "COMMUNICATION"]},
            "per_run_budget": _budget_vector(),
            "approval_policy": {"required_class": "A2"},
            "reauthorization_requirements": ["tenant", "owner", "policy",
                                             "leases", "approvals", "technology",
                                             "safety", "purpose", "budgets"],
            "active_from": "2026-01-01T00:00:00Z",
            "expiry": "2026-12-31T23:59:59Z",
            "expires_at": "2026-12-31T23:59:59Z",
            "termination_policy": {"on": "expiry_or_owner_revocation"},
            "status": "ACTIVE"}


def _accountability_chain() -> dict:
    return {"chain_id": "AC-0001", "work_order_id": "WO-0001",
            "accountable_owner_id": "owner-finance-lead",
            "links": [
                {"parent_identity": "EI-root", "child_identity": "EI-drafter",
                 "responsible": "EI-drafter",
                 "accountable_owner_id": "owner-finance-lead"},
                {"parent_identity": "EI-root", "child_identity": "EI-verifier",
                 "responsible": "EI-verifier",
                 "accountable_owner_id": "owner-finance-lead"}]}


def build_program() -> dict:
    return {
        "candidate_intents": [_candidate_intent()],
        "work_orders": [_work_order()],
        "execution_identities": _identities(),
        "leases": _leases(),
        "delegation_edges": _delegation_edges(),
        "budget_ledgers": _budget_ledgers(),
        "approval_topologies": [_approval_topology()],
        "approval_tokens": _approval_tokens(),
        "outcome_contracts": [_outcome_contract()],
        "outcome_evidence": [],
        "outcome_defeaters": [],
        "recurring_contracts": [_recurring_contract()],
        "plans": [],
        "accountability_chains": [_accountability_chain()],
    }


# --- file layout -----------------------------------------------------------
_FILE_MAP = {
    "FINALIS_CANDIDATE_INTENTS.json": ("candidate_intents",),
    "FINALIS_WORK_ORDERS.json": ("work_orders",),
    "FINALIS_EXECUTION_IDENTITIES.json": ("execution_identities",),
    "FINALIS_CAPABILITY_LEASES.json": ("leases",),
    "FINALIS_DELEGATION_EDGES.json": ("delegation_edges",),
    "FINALIS_BUDGET_LEDGERS.json": ("budget_ledgers",),
    "FINALIS_APPROVAL_TOPOLOGY.json": ("approval_topologies",),
    "FINALIS_APPROVAL_TOKENS.json": ("approval_tokens",),
    "FINALIS_OUTCOME_CONTRACTS.json": ("outcome_contracts",),
    "FINALIS_OUTCOME_EVIDENCE.json": ("outcome_evidence",),
    "FINALIS_OUTCOME_DEFEATERS.json": ("outcome_defeaters",),
    "FINALIS_RECURRING_WORK_CONTRACTS.json": ("recurring_contracts",),
    "FINALIS_EXECUTION_PLANS.json": ("plans",),
    "FINALIS_ACCOUNTABILITY_CHAINS.json": ("accountability_chains",),
}


def write_artifacts(program: dict, docs_dir: str = DOCS) -> dict:
    os.makedirs(docs_dir, exist_ok=True)
    for fname, keys in _FILE_MAP.items():
        payload = {k: program.get(k, []) for k in keys}
        _dump(os.path.join(docs_dir, fname), payload)
    _write_schemas(docs_dir)
    return {"work_orders": len(program["work_orders"]),
            "leases": len(program["leases"]),
            "delegation_edges": len(program["delegation_edges"]),
            "identities": len(program["execution_identities"])}


def _dump(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True, ensure_ascii=False)
        fh.write("\n")


def _write_schemas(docs_dir: str) -> None:
    for fname, schema in _SCHEMAS.items():
        _dump(os.path.join(docs_dir, fname), schema)


def _schema(title, required, props) -> dict:
    return {"schema_id": title, "type": "object", "required": required,
            "properties": {p: {"type": t} for p, t in props.items()},
            "additionalProperties": True}


_SCHEMAS = {
    "FINALIS_CANDIDATE_INTENT_SCHEMA.json": _schema(
        "CandidateIntent", ["candidate_intent_id", "tenant_id", "requester_id",
                            "source_surface", "status"],
        {"candidate_intent_id": "string", "tenant_id": "string",
         "requester_id": "string", "source_surface": "string",
         "raw_content_hash": "string", "interpretation_source": "string",
         "status": "string"}),
    "FINALIS_WORK_ORDER_SCHEMA.json": _schema(
        "CanonicalWorkOrder", ["work_order_id", "tenant_id", "requester_id",
                              "accountable_owner_id", "canonical_goal",
                              "allowed_scope", "outcome_contract",
                              "capability_ceiling", "budget_vector",
                              "privacy_purpose", "semantic_work_hash",
                              "work_instance_hash", "status"],
        {"work_order_id": "string", "tenant_id": "string",
         "requester_id": "string", "accountable_owner_id": "string",
         "canonical_goal": "object", "allowed_scope": "object",
         "forbidden_scope": "object", "constraints": "array",
         "outcome_contract": "object", "capability_ceiling": "object",
         "budget_vector": "object", "privacy_purpose": "string",
         "semantic_work_hash": "string", "work_instance_hash": "string",
         "status": "string"}),
    "FINALIS_EXECUTION_IDENTITY_SCHEMA.json": _schema(
        "ExecutionIdentity", ["execution_identity_id", "work_order_id", "role",
                             "delegation_depth"],
        {"execution_identity_id": "string", "work_order_id": "string",
         "parent_identity_id": "string", "role": "string",
         "delegation_depth": "integer", "responsibility_scope": "object",
         "lease_refs": "array", "status": "string"}),
    "FINALIS_CAPABILITY_LEASE_SCHEMA.json": _schema(
        "CapabilityLease", ["lease_id", "tenant_id", "work_order_id",
                           "subject_identity", "purpose", "targets",
                           "allowed_operations", "effect_classes", "expires_at",
                           "maximum_uses"],
        {"lease_id": "string", "root_authority_ref": "string",
         "parent_lease_id": "string", "subject_identity": "string",
         "tenant_id": "string", "work_order_id": "string", "purpose": "string",
         "targets": "array", "allowed_operations": "array",
         "effect_classes": "array", "data_classes": "array",
         "risk_ceiling": "object", "cost_ceiling": "object",
         "expires_at": "string", "maximum_uses": "integer",
         "revocation_state": "string", "attenuation_delta": "object",
         "integrity_hash": "string"}),
    "FINALIS_DELEGATION_EDGE_SCHEMA.json": _schema(
        "DelegationEdge", ["delegation_id", "work_order_id", "parent_identity",
                          "child_identity"],
        {"delegation_id": "string", "work_order_id": "string",
         "parent_identity": "string", "child_identity": "string",
         "parent_lease_refs": "array", "child_lease_refs": "array",
         "subtask_scope": "object", "accountable_owner_id": "string",
         "attenuation_proof_hash": "string", "status": "string"}),
    "FINALIS_BUDGET_LEDGER_SCHEMA.json": _schema(
        "BudgetLedger", ["budget_id", "work_order_id"],
        {"budget_id": "string", "work_order_id": "string",
         "financial_cost": "object", "model_cost": "object",
         "tool_call_quota": "object", "external_effect_quota": "object",
         "data_access_quota": "object", "resource_capacity": "object"}),
    "FINALIS_APPROVAL_TOKEN_SCHEMA.json": _schema(
        "ApprovalToken", ["approval_token_id", "work_instance_hash",
                         "action_fingerprint", "required_class", "approver_id",
                         "approver_class", "expires_at", "maximum_uses"],
        {"approval_token_id": "string", "work_instance_hash": "string",
         "action_fingerprint": "string", "target_fingerprint": "string",
         "material_parameters_hash": "string", "effect_class": "string",
         "risk_snapshot_hash": "string", "required_class": "string",
         "approver_id": "string", "approver_class": "string",
         "expires_at": "string", "maximum_uses": "integer", "status": "string"}),
    "FINALIS_APPROVAL_TOPOLOGY_SCHEMA.json": _schema(
        "ApprovalTopology", ["approval_topology_id", "required_floor"],
        {"approval_topology_id": "string", "work_order_id": "string",
         "required_floor": "string", "classes": "array",
         "independence_constraints": "object", "quorum": "object"}),
    "FINALIS_OUTCOME_CONTRACT_SCHEMA.json": _schema(
        "OutcomeContract", ["outcome_contract_id", "work_order_id",
                           "expected_outcomes", "acceptance_predicates",
                           "verification_mode", "completion_rule"],
        {"outcome_contract_id": "string", "work_order_id": "string",
         "expected_outcomes": "array", "acceptance_predicates": "array",
         "required_artifacts": "array", "required_evidence": "array",
         "forbidden_outcomes": "array", "verification_mode": "string",
         "verifier_requirements": "object", "dispute_policy": "object",
         "defeater_policy": "object", "completion_rule": "string"}),
    "FINALIS_RECURRING_WORK_CONTRACT_SCHEMA.json": _schema(
        "RecurringWorkContract", ["recurrence_contract_id", "cadence", "purpose",
                                 "scope_ceiling", "capability_ceiling",
                                 "per_run_budget", "expiry", "termination_policy"],
        {"recurrence_contract_id": "string", "semantic_work_hash": "string",
         "cadence": "string", "purpose": "string", "scope_ceiling": "object",
         "capability_ceiling": "object", "per_run_budget": "object",
         "approval_policy": "object", "reauthorization_requirements": "array",
         "active_from": "string", "expires_at": "string",
         "termination_policy": "object", "status": "string"}),
    "FINALIS_WORK_STATE_MACHINE.json": {
        "schema_id": "GovernedWorkStateMachine",
        "note": "authoritative alphabet lives in tools/governed_work/statemachine.py"},
    "FINALIS_REASON_CODE_REGISTRY.json": {
        "schema_id": "ReasonCodeRegistry",
        "note": "finding kinds are defined in tools/governed_work/model.py"},
}


def write(docs_dir: str = DOCS) -> dict:
    return write_artifacts(build_program(), docs_dir)


if __name__ == "__main__":
    print(json.dumps(write(), indent=2, sort_keys=True))
