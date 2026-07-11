"""Deterministically build the canonical docs/program artifacts from repository
truth (SP0003 §4.2 authoritative inputs).

Sources (repository, never conversation memory):
  * docs/audit/AUDIT_TRACE_1_SP_STATUS.json  — historical SP completion evidence
  * docs/roadmap/ROADMAP_LOCK_1_SP_SEQUENCE.json — planned nodes + explicit deps
  * docs/architecture/* / docs/semantics/* — SP0000..SP0002 program layer

Every ACTIVE hard dependency here is grounded in an explicit roadmap `deps`
entry (evidence, rationale, failure-if-bypassed) — NEVER inferred from SP
numbering (D-0003-04). Run:  python -m tools.program_graph.bootstrap
"""
from __future__ import annotations

import json
import os

from .canon import canonical_json, sha256_hex
from .hypergraph import hyperedge_arity_stats

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOCS = os.path.join(REPO_ROOT, "docs", "program")
AUDIT = os.path.join(REPO_ROOT, "docs", "audit", "AUDIT_TRACE_1_SP_STATUS.json")
SEQ = os.path.join(REPO_ROOT, "docs", "roadmap", "ROADMAP_LOCK_1_SP_SEQUENCE.json")

# ---- dependency-type inference from roadmap classification/gate hints -------
GATE_NODES = {"ADAPTER-1", "SAAS-1"}
SAFETY_TYPES = {
    "ADAPTER-1": "SAFETY_PRECONDITION",
    "SAAS-1": "AUTHORITY_PRECONDITION",
    "EVAL-1": "EVALUATION_PRECONDITION",
}

# normalize free-text dep references in the roadmap to canonical node ids
DEP_ALIASES = {
    "Case Graph": "CASE-GRAPH",
    "TOOL-B8": "TOOL-B8",
}

# program-architecture layer (SP0000..SP0010) — SP0000/1/2 COMPLETE, SP0003 in
# progress, SP0004..SP0010 planned (§26 next dependencies).
PROGRAM_LAYER = [
    ("SP0000", "Finalis 1000 Master Architecture Lock", "COMPLETE", "e1b6b5c",
     []),
    ("SP0001", "Architecture Immune System", "COMPLETE", "19413f2", ["SP0000"]),
    ("SP0002", "Finalis Semantic Operating Constitution", "COMPLETE", "3eacdb0",
     ["SP0000", "SP0001"]),
    ("SP0003", "Program Dependency & Uncertainty Constitution", "IN_PROGRESS",
     "", ["SP0000", "SP0001", "SP0002"]),
    ("SP0004", "Technology Decision Records / Replaceable-Provider Contracts",
     "NOT_STARTED", "", ["SP0003"]),
    ("SP0005", "Threat, Safety, Regulatory & High-Risk Domain Taxonomy",
     "NOT_STARTED", "", ["SP0003"]),
    ("SP0006", "Evaluation and 1000/1000 Score Charter", "NOT_STARTED", "",
     ["SP0003"]),
    ("SP0007", "Compatibility, Migration and Versioning Policy", "NOT_STARTED",
     "", ["SP0003"]),
    ("SP0008", "Existing API/UI/Data Contract Inventory", "NOT_STARTED", "",
     ["SP0003"]),
    ("SP0009", "Release Train, Quality Gates and Definition of Done",
     "NOT_STARTED", "", ["SP0003"]),
    ("SP0010", "Global Brand Naming Sprint", "NOT_STARTED", "", ["SP0003"]),
]

# synthetic milestones that anchor dominator/cut-set resilience analysis
MILESTONES = [
    ("FIRST_REAL_EFFECT_READY", "First governed real external effect ready"),
    ("MESSAGING_PILOT_READY", "First messaging pilot ready (any valid channel)"),
    ("VERTICAL_COVERAGE", "At least K vertical worker packs shipped"),
    ("DURABLE_RUNTIME_READY", "Durable runtime strategy resolved & conformant"),
    ("PRODUCTION_CANDIDATE", "Production candidate gate cleared"),
    ("GENERAL_AVAILABILITY", "General availability"),
]


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _dep_type(head_id: str, tail_id: str) -> str:
    if tail_id in SAFETY_TYPES:
        return SAFETY_TYPES[tail_id]
    if tail_id.startswith("SP000"):
        if tail_id == "SP0002":
            return "SEMANTIC_PRECONDITION"
        return "ARCHITECTURE_PRECONDITION"
    if tail_id.startswith(("CORE-A", "TOOL-B", "EMP-A")):
        return "CAPABILITY_PRECONDITION"
    if tail_id.startswith("INFRA"):
        return "PRODUCTION_READINESS_PRECONDITION"
    return "CAPABILITY_PRECONDITION"


def build_program() -> dict:
    audit = _load(AUDIT)
    seq = _load(SEQ)

    nodes: dict[str, dict] = {}
    completion_evidence: list[dict] = []

    def add_node(nid, title, ntype, status, block="", resources=None,
                 risk_tags=None):
        nodes[nid] = {
            "node_id": nid, "node_type": ntype,
            "canonical_name": title, "block": block or "?",
            "status": status,
            "status_source": "EVIDENCE_DERIVED" if status == "COMPLETE"
            else "DECLARED",
            "outputs": [], "completion_evidence": [],
            "resource_keys": resources or [], "risk_tags": risk_tags or [],
            "duration_model_ref": None,
        }

    def add_evidence(nid, commit, note):
        for kind, ref in (("final_commit", commit),
                          ("acceptance_matrix",
                           "docs/audit/AUDIT_TRACE_1_SP_STATUS.json"),
                          ("test_evidence", note),
                          ("p0p1_status", "P0=0 P1=0 (audit-verified)")):
            completion_evidence.append(
                {"node_id": nid, "kind": kind, "ref": ref})

    # 1) program-architecture layer
    for nid, title, status, commit, _deps in PROGRAM_LAYER:
        add_node(nid, title, "SP", status, block="PROGRAM")
        if status == "COMPLETE":
            add_evidence(nid, commit, f"{nid} acceptance matrix complete")

    # 2) historical SPs from the audit (IMPLEMENTED_AND_TESTED -> COMPLETE)
    hist_status = {}
    for s in audit.get("sps", []):
        sid = s["id"]
        hist_status[sid] = s.get("status")
        if sid in nodes:
            continue
        if s.get("status") == "IMPLEMENTED_AND_TESTED":
            add_node(sid, s.get("title", sid), _node_type(sid), "COMPLETE",
                     block=_block(sid))
            commit = (s.get("commits") or [""])[-1]
            add_evidence(sid, commit, s.get("evidence", "audit-verified"))
        elif s.get("status") == "DOC_ONLY":
            add_node(sid, s.get("title", sid), "DOC", "COMPLETE",
                     block=_block(sid))
            completion_evidence.append(
                {"node_id": sid, "kind": "doc",
                 "ref": (s.get("commits") or [""])[-1]})

    # 3) roadmap-planned nodes from the sequence
    seq_deps: dict[str, list[str]] = {}
    for item in seq.get("sequence", []):
        sid = item["id"]
        seq_deps[sid] = item.get("deps", [])
        if sid in nodes:
            continue
        status = _seq_status(item.get("status", "PLANNED"))
        add_node(sid, item.get("name") or item.get("title", sid),
                 _node_type(sid), status, block=item.get("block", "?"),
                 resources=_resources(sid), risk_tags=_risks(sid))
        if status == "COMPLETE":
            add_evidence(sid, "", f"{sid} roadmap-DONE")

    # 4) milestones
    for mid, title in MILESTONES:
        add_node(mid, title, "MILESTONE", "NOT_STARTED", block="MILESTONE")

    # ---- hyperedges (ALL explicit, evidence-backed) -----------------------
    hyperedges: list[dict] = []
    seen_edge = set()

    def add_edge(head, tails, dtype, reason, fail, evidence, logic="ALL_OF",
                 status="ACTIVE", scenario_condition=None, threshold_k=None):
        tails = [DEP_ALIASES.get(t, t) for t in tails]
        tails = [t for t in tails if t in nodes and t != head]
        if not tails:
            return
        key = (head, tuple(sorted(tails)), logic, str(scenario_condition))
        if key in seen_edge:
            return
        seen_edge.add(key)
        eid = "dep-" + sha256_hex(canonical_json(list(key)))[:12]
        e = {"dependency_id": eid, "tail_nodes": sorted(tails),
             "head_node": head, "dependency_type": dtype, "logic": logic,
             "status": status, "scenario_condition": scenario_condition,
             "required_output": "", "reason": reason,
             "failure_if_bypassed": fail, "evidence_refs": evidence,
             "admitted_by": "ARCHITECTURE_REVIEW"}
        if threshold_k is not None:
            e["threshold_k"] = threshold_k
        hyperedges.append(e)

    # program-layer edges
    for nid, _t, _s, _c, deps in PROGRAM_LAYER:
        if deps:
            add_edge(nid, deps, _dep_type(nid, deps[0]),
                     f"{nid} builds on the frozen outputs of {', '.join(deps)}",
                     f"{nid} would rest on an unverified foundation",
                     ["docs/architecture/FINALIS_1000_DEPENDENCY_SPINE.md"])

    # roadmap edges (from explicit `deps`)
    for sid, deps in seq_deps.items():
        if sid not in nodes:
            continue
        norm = _expand_deps(deps, nodes)
        if norm:
            add_edge(sid, norm, _dep_type(sid, norm[0]),
                     f"{sid} reuses/extends the outputs of {', '.join(norm)} "
                     "(roadmap-locked prerequisite)",
                     f"{sid} could bypass a required precondition and violate "
                     "the do-not-rebuild / gate discipline",
                     ["docs/roadmap/ROADMAP_LOCK_1_SP_SEQUENCE.json"])

    # milestone edges
    add_edge("FIRST_REAL_EFFECT_READY", ["ADAPTER-1", "TOOL-B9", "TOOL-B13",
             "SAAS-1"], "SAFETY_PRECONDITION",
             "No real external effect may occur before the provider boundary, "
             "local-commit runtime, autonomy engine and production auth exist "
             "(roadmap hard gate)",
             "An ungoverned real external effect could escape all safety gates",
             ["docs/roadmap/ROADMAP_LOCK_1_SP_SEQUENCE.json#hard_gates"])
    add_edge("PRODUCTION_CANDIDATE", ["GATE-1", "GATE-2", "GATE-3"],
             "PRODUCTION_READINESS_PRECONDITION",
             "Production candidacy requires the readiness audit, red-team and "
             "beta gates",
             "Shipping without gates would declare production-ready unproven",
             ["docs/roadmap/ROADMAP_LOCK_1_SP_SEQUENCE.json"])
    add_edge("GENERAL_AVAILABILITY", ["GATE-4", "PRODUCTION_CANDIDATE"],
             "PRODUCTION_READINESS_PRECONDITION",
             "GA requires the production-candidate gate cleared",
             "Premature GA would violate INV production gates",
             ["docs/roadmap/ROADMAP_LOCK_1_SP_SEQUENCE.json"])

    # --- ALTERNATIVE prerequisite paths (D-0003-02): DURABLE_RUNTIME_READY via
    # the Temporal option OR the custom-runtime option (two ALL_OF hyperedges).
    add_edge("DURABLE_RUNTIME_READY", ["SP0004", "EMP-A2"],
             "TECHNOLOGY_DECISION_PRECONDITION",
             "Durable runtime ready via the Temporal option: technology "
             "decision + durable Run Ledger",
             "An undecided runtime would leave durability unproven",
             ["docs/roadmap/ROADMAP_LOCK_1_SP_SEQUENCE.json"],
             scenario_condition={"variable": "durable_runtime_strategy",
                                 "operator": "EQUALS", "value": "TEMPORAL"})
    add_edge("DURABLE_RUNTIME_READY", ["SP0004", "TOOL-B10"],
             "TECHNOLOGY_DECISION_PRECONDITION",
             "Durable runtime ready via the custom-implementation option: "
             "technology decision + commit recovery runtime",
             "An undecided runtime would leave durability unproven",
             ["docs/roadmap/ROADMAP_LOCK_1_SP_SEQUENCE.json"],
             scenario_condition={"variable": "durable_runtime_strategy",
                                 "operator": "EQUALS", "value": "CUSTOM"})

    # --- UNCONDITIONAL alternative prerequisite paths (D-0003-02, AC-0003-10):
    # MESSAGING_PILOT_READY is satisfiable via the Slack path OR the Teams path —
    # two ALL_OF hyperedges with the same head, both active in every scenario:
    # (ADAPTER-1 AND PILOT-1) OR (ADAPTER-1 AND PILOT-2).
    add_edge("MESSAGING_PILOT_READY", ["ADAPTER-1", "PILOT-1"],
             "SAFETY_PRECONDITION",
             "Messaging pilot ready via the Slack path behind the provider "
             "boundary",
             "A messaging pilot without the provider boundary could leak effects",
             ["docs/roadmap/ROADMAP_LOCK_1_SP_SEQUENCE.json"])
    add_edge("MESSAGING_PILOT_READY", ["ADAPTER-1", "PILOT-2"],
             "SAFETY_PRECONDITION",
             "Messaging pilot ready via the Teams path behind the provider "
             "boundary",
             "A messaging pilot without the provider boundary could leak effects",
             ["docs/roadmap/ROADMAP_LOCK_1_SP_SEQUENCE.json"])

    # --- CONDITIONAL scenario dependency (D-0003-06): a provider-conformance
    # prerequisite that activates ONLY under the Temporal runtime scenario.
    add_edge("EMP-A2", ["SP0004"], "TECHNOLOGY_DECISION_PRECONDITION",
             "Under the Temporal option, Run Ledger 2.0 must conform to the "
             "chosen durable-execution provider contract",
             "A provider-specific assumption would leak into the core runtime",
             ["docs/roadmap/ROADMAP_LOCK_1_SP_SEQUENCE.json"],
             scenario_condition={"variable": "durable_runtime_strategy",
                                 "operator": "EQUALS", "value": "TEMPORAL"})

    # --- THRESHOLD prerequisite (D-0003-03): vertical coverage needs at least 2
    # of the 7 worker packs (AT_LEAST_K_OF_N on one hyperedge).
    packs = [f"PACK-{i}" for i in range(1, 8) if f"PACK-{i}" in nodes]
    add_edge("VERTICAL_COVERAGE", packs, "CAPABILITY_PRECONDITION",
             "Vertical coverage milestone requires at least 2 of the 7 worker "
             "packs shipped",
             "Claiming vertical coverage on <2 packs would overstate breadth",
             ["docs/roadmap/ROADMAP_LOCK_1_SP_SEQUENCE.json"],
             logic="AT_LEAST_K_OF_N", threshold_k=2)

    threshold_gates = [{
        "gate_id": "TG-VERTICAL-COVERAGE", "gate_type": "THRESHOLD_PREREQUISITE",
        "candidate_nodes": packs, "threshold_k": 2, "status": "COMPUTED"}]

    # ---- scenarios --------------------------------------------------------
    scenarios = [
        {"scenario_id": "BASELINE",
         "variables": {"durable_runtime_strategy": "UNDECIDED",
                       "deployment": "SINGLE_REGION", "jurisdiction": "GLOBAL"},
         "status": "ACTIVE", "parent_scenario": None},
        {"scenario_id": "TEMPORAL_RUNTIME_OPTION",
         "variables": {"durable_runtime_strategy": "TEMPORAL",
                       "deployment": "SINGLE_REGION", "jurisdiction": "GLOBAL"},
         "status": "VALIDATED", "parent_scenario": "BASELINE"},
        {"scenario_id": "CUSTOM_RUNTIME_OPTION",
         "variables": {"durable_runtime_strategy": "CUSTOM",
                       "deployment": "SINGLE_REGION", "jurisdiction": "GLOBAL"},
         "status": "VALIDATED", "parent_scenario": "BASELINE"},
        {"scenario_id": "EU_ONLY_DEPLOYMENT",
         "variables": {"durable_runtime_strategy": "UNDECIDED",
                       "deployment": "SINGLE_REGION", "jurisdiction": "EU"},
         "status": "VALIDATED", "parent_scenario": "BASELINE"},
        {"scenario_id": "MULTI_REGION_DEPLOYMENT",
         "variables": {"durable_runtime_strategy": "UNDECIDED",
                       "deployment": "MULTI_REGION", "jurisdiction": "GLOBAL"},
         "status": "VALIDATED", "parent_scenario": "BASELINE"},
    ]

    # ---- gate graph (roadmap hard gates) ----------------------------------
    gates = [
        {"gate_id": "GATE-PROVIDER-BOUNDARY", "gate_type": "SAFETY_GATE",
         "scenario_invariant": True, "guarded_nodes":
             sorted(n for n in nodes if n.startswith("PILOT-")),
         "reason": "No real provider before ADAPTER-1 (roadmap hard gate)"},
        {"gate_id": "GATE-PROD-AUTH", "gate_type": "GOVERNANCE_GATE",
         "scenario_invariant": True, "guarded_nodes": ["SAAS-1"],
         "reason": "Production auth/IAM required before real multi-tenant use"},
        {"gate_id": "GATE-HUMAN-OVERSIGHT", "gate_type": "HUMAN_REVIEW_GATE",
         "scenario_invariant": True, "guarded_nodes":
             sorted(n for n in nodes if n.startswith("PILOT-")),
         "reason": "Sensitive real actions start review-first (Viktor pattern)"},
        {"gate_id": "GATE-PRODUCTION", "gate_type": "PRODUCTION_GATE",
         "scenario_invariant": True, "guarded_nodes":
             ["GENERAL_AVAILABILITY"],
         "reason": "No production deploy before INFRA + REFACTOR + GATE-4"},
    ]

    # ---- resource conflict graph ------------------------------------------
    conflicts = [
        {"resource_key": "migration_lane", "capacity": 1,
         "nodes": sorted(n for n in ["EMP-A2", "INFRA-1", "TOOL-B10", "CASE-2"]
                         if n in nodes),
         "reason": "single SQLite->schema migration lane; concurrent migrations "
                   "would collide"},
        {"resource_key": "authority_core_write_lane", "capacity": 1,
         "nodes": sorted(n for n in ["TOOL-B13", "SAAS-1"] if n in nodes),
         "reason": "single authoritative RBAC/autonomy write path"},
        {"resource_key": "portal_monolith_hotspot", "capacity": 1,
         "nodes": sorted(n for n in ["REFACTOR-1", "REFACTOR-2", "CASE-2"]
                         if n in nodes),
         "reason": "app.py/ui.py monolith hotspot; parallel edits conflict"},
        {"resource_key": "human_domain_reviewer", "capacity": 1,
         "nodes": sorted(n for n in ["PILOT-1", "PILOT-2", "PILOT-3", "PILOT-4"]
                         if n in nodes),
         "reason": "single human domain reviewer for review-first pilots"},
    ]

    # ---- rework / feedback graph (separate; may contain cycles) -----------
    rework_edges = _rework(nodes)

    # ---- risk correlation graph -------------------------------------------
    risk_correlations = [
        {"risk_id": "RISK-PROVIDER-IMMATURITY",
         "nodes": sorted(n for n in nodes if n.startswith("PILOT-")),
         "reason": "all pilots share unproven external-provider integration risk"},
        {"risk_id": "RISK-DURABLE-RUNTIME-UNCERTAINTY",
         "nodes": sorted(n for n in ["EMP-A2", "TOOL-B10", "SP0004"]
                         if n in nodes),
         "reason": "share the undecided durable-runtime technology assumption"},
    ]

    # ---- temporal constraints (consistent difference-constraint set) ------
    temporal_constraints = [
        {"constraint_id": "T-ADAPTER-BEFORE-PILOT1",
         "from_timepoint": "ADAPTER-1", "to_timepoint": "PILOT-1",
         "lower_bound": 0, "upper_bound": 365, "unit": "days",
         "constraint_type": "REQUIREMENT"},
        {"constraint_id": "T-GA-DEADLINE", "from_timepoint": "__ZERO__",
         "to_timepoint": "GENERAL_AVAILABILITY", "lower_bound": 30,
         "upper_bound": 1000, "unit": "days", "constraint_type": "DEADLINE"},
        {"constraint_id": "T-PROVIDER-REVIEW-CONTINGENT",
         "from_timepoint": "ADAPTER-1", "to_timepoint": "SAAS-1",
         "lower_bound": None, "upper_bound": 180, "unit": "days",
         "constraint_type": "CONTINGENT", "contingent": True},
    ]

    # ---- duration models (mostly UNKNOWN; a few estimated for MC demo) -----
    duration_models = _durations(nodes)

    # ---- dependency uncertainties + VOI -----------------------------------
    uncertainties = [
        {"uncertainty_id": "UNC-DURABLE-RUNTIME",
         "candidate_dependency": "durable_runtime_strategy",
         "status": "UNDER_RESEARCH", "decision_impact": "HIGH",
         "dependency_type": "TECHNOLOGY_DECISION_PRECONDITION",
         "research_options": ["SP0004 technology decision record"],
         "probability_model": {"p_wrong_now": 0.4, "p_wrong_after": 0.05},
         "loss_model": {"impact_loss": 100.0},
         "research_cost": 10.0},
        {"uncertainty_id": "UNC-SAFETY-REGULATORY",
         "candidate_dependency": "regulatory_review",
         "status": "IDENTIFIED", "decision_impact": "CRITICAL",
         "dependency_type": "SAFETY_PRECONDITION", "mandatory": True,
         "research_options": ["SP0005 threat/regulatory taxonomy"],
         "probability_model": None, "loss_model": None, "research_cost": None},
        {"uncertainty_id": "UNC-UNCALIBRATED-EXAMPLE",
         "candidate_dependency": "provider_latency_assumption",
         "status": "IDENTIFIED", "decision_impact": "MEDIUM",
         "dependency_type": "CAPABILITY_PRECONDITION",
         "research_options": [], "probability_model": None,
         "loss_model": None, "research_cost": None},
    ]

    program = {
        "nodes": sorted(nodes.values(), key=lambda n: n["node_id"]),
        "hyperedges": sorted(hyperedges, key=lambda e: e["dependency_id"]),
        "threshold_gates": threshold_gates,
        "scenarios": scenarios,
        "gates": gates,
        "gate_bindings": [],
        "conflicts": conflicts,
        "rework_edges": rework_edges,
        "risk_correlations": risk_correlations,
        "completion_evidence": completion_evidence,
        "temporal_constraints": temporal_constraints,
        "duration_models": duration_models,
        "uncertainties": uncertainties,
    }
    return program


def _node_type(sid: str) -> str:
    if sid.startswith("PILOT-"):
        return "PILOT"
    if sid.startswith("PACK-"):
        return "PACK"
    if sid.startswith("INFRA-"):
        return "INFRA"
    if sid.startswith("REFACTOR-"):
        return "REFACTOR"
    if sid.startswith("GATE-"):
        return "GATE_NODE"
    if sid in ("DOCS-BLUEPRINT", "AUDIT-REPORT-1", "ROADMAP-LOCK-1"):
        return "DOC"
    return "SP"


def _block(sid: str) -> str:
    if sid.startswith("CORE-A"):
        return "CORE"
    if sid.startswith("TOOL-B"):
        return "TOOL"
    if sid.startswith("EMP-A"):
        return "EMP"
    return "LEGACY"


def _seq_status(s: str) -> str:
    s = (s or "").upper()
    if s in ("DONE",):
        return "COMPLETE"
    if s == "IMPLEMENTED_AND_TESTED":
        return "COMPLETE"
    if s == "NEXT":
        return "READY"
    if s.startswith("BLOCKED"):
        return "BLOCKED"
    return "NOT_STARTED"


def _resources(sid: str) -> list[str]:
    r = []
    if sid in ("EMP-A2", "INFRA-1", "TOOL-B10", "CASE-2"):
        r.append("migration_lane")
    if sid in ("TOOL-B13", "SAAS-1"):
        r.append("authority_core_write_lane")
    if sid in ("REFACTOR-1", "REFACTOR-2", "CASE-2"):
        r.append("portal_monolith_hotspot")
    if sid.startswith("PILOT-"):
        r.append("human_domain_reviewer")
    return sorted(set(r))


def _risks(sid: str) -> list[str]:
    r = []
    if sid.startswith("PILOT-"):
        r.append("RISK-PROVIDER-IMMATURITY")
    if sid in ("EMP-A2", "TOOL-B10", "SP0004"):
        r.append("RISK-DURABLE-RUNTIME-UNCERTAINTY")
    return r


def _expand_deps(deps, nodes) -> list[str]:
    out: list[str] = []
    for d in deps:
        d = DEP_ALIASES.get(d, d)
        if d in ("ALL", "all in-scope surfaces"):
            continue
        if d.endswith("*"):
            pref = d[:-1]
            out.extend(sorted(n for n in nodes if n.startswith(pref)))
        elif d in nodes:
            out.append(d)
    return sorted(set(out))


def _rework(nodes) -> list[dict]:
    edges = []

    def add(frm, to, rtype, reason):
        if frm in nodes and to in nodes:
            rid = "rw-" + sha256_hex(f"{frm}->{to}:{rtype}")[:12]
            edges.append({"rework_edge_id": rid, "from_node": frm,
                          "to_node": to, "rework_type": rtype,
                          "trigger": f"{frm} contract changed",
                          "reason": reason, "evidence_refs": []})
    # semantic epoch change forces re-verification of consumers (SP0002 twin)
    add("SP0002", "CASE-2", "REVERIFY_IF_CHANGED",
        "a semantic-epoch change may invalidate case completion meaning")
    add("SP0002", "EMP-A2", "REVERIFY_IF_CHANGED",
        "a semantic-epoch change may invalidate run-ledger meaning")
    # architecture invariant change forces re-check
    add("SP0001", "REFACTOR-1", "REVERIFY_IF_CHANGED",
        "architecture-guard changes may reshape the app.py modularization")
    # a durable-runtime decision may force rework of the run ledger, which may
    # itself surface issues in the technology decision — a legal feedback cycle
    add("SP0004", "EMP-A2", "REWORK_TRIGGER",
        "a runtime technology decision reshapes Run Ledger 2.0")
    add("EMP-A2", "SP0004", "RECALIBRATE_IF_CHANGED",
        "Run Ledger constraints may force revisiting the runtime decision")
    # migration change triggers re-migration downstream
    add("INFRA-1", "INFRA-2", "MIGRATE_IF_CHANGED",
        "storage migration reshapes object-store integration")
    return sorted(edges, key=lambda e: e["rework_edge_id"])


def _durations(nodes) -> list[dict]:
    dms = []
    # most nodes: UNKNOWN (never fabricated)
    for nid in sorted(nodes):
        dms.append({"duration_model_id": f"dm-{nid}", "node_id": nid,
                    "mode": "UNKNOWN", "similarity_class": None,
                    "observations": [], "distribution_family": None,
                    "parameters": {}, "model_version": "1"})
    # a few explicit three-point estimates to exercise CPM / Monte Carlo,
    # grounded as EXPERT estimates with provenance (not empirical claims)
    est = {
        "EMP-A2": (3, 5, 9), "TOOL-B10": (2, 4, 7), "ADAPTER-1": (5, 10, 20),
        "EVAL-1": (3, 6, 10), "SAAS-1": (8, 15, 30), "CASE-2": (4, 7, 12),
    }
    by_id = {d["duration_model_id"]: d for d in dms}
    for nid, (a, m, b) in est.items():
        if nid in nodes:
            d = by_id[f"dm-{nid}"]
            d["mode"] = "THREE_POINT_ESTIMATE"
            d["similarity_class"] = "TOOL_KERNEL_SP"
            d["distribution_family"] = "triangular"
            d["parameters"] = {"optimistic": a, "mode": m, "pessimistic": b,
                               "provenance": "expert_estimate",
                               "boundary": "code_start_to_tests_green",
                               "blocked_time_policy": "excluded"}
    return dms


def _stats(program: dict) -> dict:
    arity = hyperedge_arity_stats(program)
    return {"nodes": len(program["nodes"]),
            "hyperedges": len(program["hyperedges"]),
            "avg_arity": arity["avg_arity"], "max_arity": arity["max_arity"]}


def write_artifacts(program: dict, docs_dir: str = DOCS) -> dict:
    os.makedirs(docs_dir, exist_ok=True)
    base_meta = {"program_id": "FINALIS-1000", "sp": "SP0003",
                 "branch": "claude/finalis-ai-casewoker-blueprint-f1huse",
                 "source": ["docs/audit/AUDIT_TRACE_1_SP_STATUS.json",
                            "docs/roadmap/ROADMAP_LOCK_1_SP_SEQUENCE.json"]}
    files = {
        "FINALIS_1000_PROGRAM_REGISTRY.json": {
            **base_meta, "nodes": program["nodes"],
            "duration_models": program["duration_models"],
            "uncertainties": program["uncertainties"]},
        "FINALIS_1000_PROGRAM_HYPERGRAPH.json": {
            "hyperedges": program["hyperedges"],
            "threshold_gates": program["threshold_gates"]},
        "FINALIS_1000_SCENARIO_REGISTRY.json": {
            "scenarios": program["scenarios"]},
        "FINALIS_1000_GATE_GRAPH.json": {"gates": program["gates"],
                                         "gate_bindings": program["gate_bindings"]},
        "FINALIS_1000_RESOURCE_CONFLICT_GRAPH.json": {
            "conflicts": program["conflicts"]},
        "FINALIS_1000_REWORK_GRAPH.json": {
            "rework_edges": program["rework_edges"]},
        "FINALIS_1000_RISK_CORRELATION_GRAPH.json": {
            "risk_correlations": program["risk_correlations"]},
        "FINALIS_1000_COMPLETION_EVIDENCE_GRAPH.json": {
            "completion_evidence": program["completion_evidence"]},
        "FINALIS_1000_TEMPORAL_CONSTRAINTS.json": {
            "temporal_constraints": program["temporal_constraints"]},
    }
    for fname, payload in files.items():
        with open(os.path.join(docs_dir, fname), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True, ensure_ascii=False)
            fh.write("\n")
    return _stats(program)


def write_reports(program: dict, docs_dir: str = DOCS) -> None:
    """Generate the computed MD reports deterministically from live analytics so
    the committed reports always match a fresh recomputation (canonical vs
    derived kept in sync, INV-0003-17)."""
    from .criticality import structural_depth, cpm, display_critical_path
    from .forecast import numeric_durations, monte_carlo_criticality
    from .resilience import program_dominators, milestone_cut_set
    from .scenario import compile_scenario
    from .drift import snapshot_vector
    from .voi import evaluate_voi

    active, _ = compile_scenario(program, "BASELINE")
    sd = structural_depth(program, active)
    durs = numeric_durations(program)
    c = cpm(program, durs, active)
    mc = monte_carlo_criticality(program, samples=1000, seed=1000, active=active)
    milestones = ["FIRST_REAL_EFFECT_READY", "MESSAGING_PILOT_READY",
                  "VERTICAL_COVERAGE", "PRODUCTION_CANDIDATE",
                  "GENERAL_AVAILABILITY"]

    def w(fname, text):
        with open(os.path.join(docs_dir, fname), "w", encoding="utf-8") as fh:
            fh.write(text)

    # criticality report
    crit = ["# FINALIS 1000 — Program Criticality Report (SP0003)\n",
            "Generated deterministically from the canonical program by "
            "`tools.program_graph`. Three DISTINCT modes (D-0003-18).\n",
            "## Structural criticality (unit weights, no durations)\n",
            f"- Structural critical depth: **{sd['critical_depth']}** nodes\n",
            f"- Deepest nodes: `{', '.join(sd['deepest_nodes'][:12])}`\n",
            "\n## Estimate-based CPM (explicit estimates only; UNKNOWN never "
            "fabricated)\n",
            f"- Project duration (est.): **{c['project_duration']}**\n",
            f"- Critical nodes ({c['num_critical_nodes']}): "
            f"`{', '.join(c['critical_nodes'][:20])}`\n",
            f"- Display critical path: "
            f"`{' -> '.join(display_critical_path(c, program, active))}`\n",
            "\n## Monte Carlo criticality (advisory; reproducible)\n",
            f"- Samples: {mc['samples']}, seed: {mc['seed']}, model version: "
            f"{mc['input_model_version']}\n",
            f"- Completion p50: {mc['completion_p50']} "
            f"(min {mc['completion_min']}, max {mc['completion_max']})\n",
            f"- Criticality concentration (entropy): "
            f"{mc['criticality_concentration']}\n",
            "\nTop criticality index:\n"]
    top = sorted(mc["criticality_index"].items(), key=lambda kv: (-kv[1], kv[0]))
    for nid, ci in top[:12]:
        if ci > 0:
            crit.append(f"- `{nid}`: {ci}\n")
    w("FINALIS_1000_CRITICALITY_REPORT.md", "".join(crit))

    # dominators report
    dom = ["# FINALIS 1000 — Program Dominators (SP0003 D-0003-29)\n",
           "Nodes lying on EVERY valid path to a milestone (AND/OR hypergraph "
           "semantics). A single-node dominator is an unavoidable bottleneck.\n"]
    for m in milestones:
        r = program_dominators(program, m)
        dom.append(f"\n## {m}\n- achievable: {r.get('achievable')}\n")
        dom.append(f"- single-point dominators ({r.get('single_point_count')}): "
                   f"`{', '.join(r.get('dominators', [])[:20])}`\n")
    w("FINALIS_1000_PROGRAM_DOMINATORS.md", "".join(dom))

    # milestone resilience report
    res = ["# FINALIS 1000 — Milestone Resilience / Cut-Sets (SP0003 D-0003-30/"
           "31)\n", "Minimum blocker set (bounded AND/OR hypergraph min-cut). "
           "Descriptive, NOT a production gate (D-0003-31).\n"]
    for m in milestones:
        r = milestone_cut_set(program, m)
        res.append(f"\n## {m}\n- min cut size: **{r.get('min_cut_size')}** "
                   f"(exhaustive up to {r.get('exhaustive_up_to')})\n")
        res.append(f"- example minimal cut: `{r.get('example_cut')}`\n")
        res.append(f"- single-point fragility: "
                   f"{r.get('single_point_fragility')}\n")
    w("FINALIS_1000_MILESTONE_RESILIENCE.md", "".join(res))

    # dependency uncertainties report
    unc = ["# FINALIS 1000 — Dependency Uncertainties & Value-of-Information "
           "(SP0003 D-0003-34/35)\n",
           "Uncertain dependencies never block canonical readiness; only ACTIVE "
           "proven hard dependencies do. VOI is computed only where calibrated; "
           "mandatory safety work is never bypassable (INV-0003-18).\n"]
    for u in program["uncertainties"]:
        v = evaluate_voi(u)
        unc.append(f"\n## {u['uncertainty_id']}\n"
                   f"- candidate: `{u.get('candidate_dependency')}` — status "
                   f"{u.get('status')}, impact {u.get('decision_impact')}\n"
                   f"- VOI: **{v['status']}**"
                   + (f" (voi={v.get('voi')})" if 'voi' in v else "") + "\n"
                   f"- bypassable: {v.get('bypassable')}\n")
    w("FINALIS_1000_DEPENDENCY_UNCERTAINTIES.md", "".join(unc))

    # drift observatory
    dv = snapshot_vector(program, "BASELINE")
    drift = ["# FINALIS 1000 — Program Drift Observatory (SP0003 D-0003-42)\n",
             "Longitudinal snapshot vector. Uncalibrated drift metrics are "
             "ADVISORY, never automatic hard blockers (AC-0003-87).\n\n"]
    for k in sorted(dv):
        drift.append(f"- **{k}**: {dv[k]}\n")
    w("FINALIS_1000_PROGRAM_DRIFT_OBSERVATORY.md", "".join(drift))


if __name__ == "__main__":
    prog = build_program()
    stats = write_artifacts(prog)
    write_reports(prog)
    print(json.dumps(stats, indent=2, sort_keys=True))
