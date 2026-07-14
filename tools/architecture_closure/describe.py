"""Architecture Description Package — ISO/IEC/IEEE 42010 views (SP0010 FUNCTION
B, §9.1, D-0010-11, AC-0010-021..030).

The architecture DESCRIPTION is distinct from the architecture (D-0010-11): this
records stakeholders, concerns, viewpoints, the 24 views (AD-01..AD-24), the
view-correspondence rules, and — crucially — the CONFORMANCE of each view to the
real repository (does its declared evidence exist on disk?). A view whose
evidence is present is IMPLEMENTED; one that is documentation-only is
DECLARATIVE_ONLY; both are recorded, neither is hidden (AC-0010-028/029/030).
"""
from __future__ import annotations

from pathlib import Path

from .canon import hash_obj

STAKEHOLDERS = [
    {"id": "architect", "concerns": ["compositional_coherence",
                                     "no_circular_assurance"]},
    {"id": "safety_owner", "concerns": ["safety_dominance", "hazard_control"]},
    {"id": "security_owner", "concerns": ["tenant_isolation",
                                          "authority_conservation"]},
    {"id": "release_owner", "concerns": ["proof_not_authority",
                                         "release_runtime_separation"]},
    {"id": "evaluator_sp0011", "concerns": ["reliability_admission",
                                            "evidence_provenance"]},
    {"id": "operator", "concerns": ["production_gaps", "observability"]},
]

# AD view -> the real repository evidence paths that ground it
VIEWS = {
    "AD-01": ("Entity of Interest & Mission",
              ["docs/roadmap/ROADMAP_LOCK_1_FINALIS_AI_EMPLOYEE_OS.md"]),
    "AD-02": ("Stakeholders & Concerns", ["docs/architecture"]),
    "AD-03": ("Constitutional Layers",
              ["docs/architecture/FINALIS_1000_MASTER_ARCHITECTURE_LOCK.md"]),
    "AD-04": ("Capabilities", ["docs/architecture"]),
    "AD-05": ("Runtime Boundaries", ["finalis/portal/app.py"]),
    "AD-06": ("Semantics", ["tools/semantics", "docs/semantics"]),
    "AD-07": ("Data & Memory", ["finalis/portal/db.py"]),
    "AD-08": ("Program Dependencies",
              ["tools/program_graph",
               "docs/program/FINALIS_1000_PROGRAM_REGISTRY.json"]),
    "AD-09": ("Technology & Providers", ["tools/technology", "docs/technology"]),
    "AD-10": ("Authority & Approvals",
              ["tools/governed_work", "finalis/portal/app.py"]),
    "AD-11": ("Tenant Isolation", ["finalis/portal/app.py",
                                   "finalis/portal/db.py"]),
    "AD-12": ("Safety & Regulatory Truth", ["tools/safety", "docs/safety"]),
    "AD-13": ("Governed Work", ["tools/governed_work", "docs/governed_work"]),
    "AD-14": ("Outcomes & Evidence", ["tools/governed_work"]),
    "AD-15": ("Contract Evolution", ["tools/compatibility",
                                     "docs/compatibility"]),
    "AD-16": ("Contract Inventory", ["tools/contracts_inventory",
                                     "docs/contracts_inventory"]),
    "AD-17": ("Release Assurance", ["tools/release", "docs/release"]),
    "AD-18": ("Failure & Recovery", ["finalis"]),
    "AD-19": ("Learning", ["tools/governed_work"]),
    "AD-20": ("Multilingual Control", ["tools/semantics"]),
    "AD-21": ("Pack Extensibility", ["finalis"]),
    "AD-22": ("Observability", ["finalis/audit.py"]),
    "AD-23": ("Performance & Scale", ["docs/architecture"]),
    "AD-24": ("Production Gaps", ["docs/audits"]),
}

# viewpoints group views by concern
VIEWPOINTS = {
    "VP-COMPOSITION": ["AD-01", "AD-03", "AD-04", "AD-08"],
    "VP-SECURITY": ["AD-10", "AD-11"],
    "VP-SAFETY": ["AD-12"],
    "VP-EVOLUTION": ["AD-15", "AD-16", "AD-17"],
    "VP-OPERATIONS": ["AD-18", "AD-22", "AD-23", "AD-24"],
}

# correspondence rules: a view must be consistent with another
CORRESPONDENCE_RULES = [
    {"rule_id": "CR-1", "from": "AD-11", "to": "AD-10",
     "meaning": "tenant isolation view must agree with authority view"},
    {"rule_id": "CR-2", "from": "AD-16", "to": "AD-15",
     "meaning": "contract inventory must agree with contract evolution"},
    {"rule_id": "CR-3", "from": "AD-17", "to": "AD-16",
     "meaning": "release assurance references the contract inventory genome"},
]


def build_description(root: Path) -> dict:
    views = []
    for vid, (title, evidence) in sorted(VIEWS.items()):
        present = [{"ref": e, "present": (root / e).exists()} for e in evidence]
        implemented = any(p["present"] for p in present)
        views.append({
            "view_id": vid, "title": title, "evidence": present,
            "conformance": "IMPLEMENTED" if implemented else "DECLARATIVE_ONLY",
        })
    desc = {
        "entity_of_interest": "FINALIS AI Employee OS (governance kernel + "
                              "mocked vertical SaaS)",
        "stakeholders": STAKEHOLDERS,
        "concerns": sorted({c for s in STAKEHOLDERS for c in s["concerns"]}),
        "viewpoints": VIEWPOINTS,
        "views": views,
        "correspondence_rules": CORRESPONDENCE_RULES,
        "known_inconsistencies": [
            {"id": "KI-1", "note": "Contract Genome leaf_counts (routes 423, "
             "tables 107) differ from audit raw grep (routes 402, tables 108) "
             "— distinct enumeration provenance, not equated"}],
    }
    desc["description_hash"] = hash_obj(desc)
    return desc


def conformance_matrix(desc: dict) -> dict:
    return {v["view_id"]: v["conformance"] for v in desc["views"]}
