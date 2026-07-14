"""Scenario + challenge system (SP0011 §2.1.F, §2.6, §11.6/11.7, §10.6/10.7,
D-0011-032..037, AC-0011-071..084).

Scenarios ground each domain's claims in observable, oracle-checkable situations.
Generated scenarios remain CANDIDATES until validity/solvability/ambiguity/oracle/
leakage/criticality are checked (D-0011-034). The Challenge Escrow commits a
scenario root and an answer-key root BEFORE any evaluated run, and the secret
mutation seed is committed (never revealed) so the evaluated system cannot read
held-out answers (D-0011-032/033). Includes the 16 Viktor-inspired reference
families (vendor-derived scenarios, clearly labeled — never used as evidence of
Finalis quality).
"""
from __future__ import annotations

from .canon import hash_obj, commitment
from .model import Finding, P1

# 16 Viktor-inspired reference scenario families (§2.6) — vendor-derived.
VIKTOR_FAMILIES = [
    ("VIKTOR-REF-01", "one employee across multiple tools"),
    ("VIKTOR-REF-02", "real artifact delivery"),
    ("VIKTOR-REF-03", "scheduled recurring work"),
    ("VIKTOR-REF-04", "proactive automation proposal"),
    ("VIKTOR-REF-05", "approval before protected effect"),
    ("VIKTOR-REF-06", "multiple provider accounts"),
    ("VIKTOR-REF-07", "pause and resume"),
    ("VIKTOR-REF-08", "task termination"),
    ("VIKTOR-REF-09", "oauth revocation"),
    ("VIKTOR-REF-10", "reconnection without scope widening"),
    ("VIKTOR-REF-11", "repository-aware engineering"),
    ("VIKTOR-REF-12", "team workspace isolation"),
    ("VIKTOR-REF-13", "visible work status"),
    ("VIKTOR-REF-14", "credentials outside model context"),
    ("VIKTOR-REF-15", "read-only connection mode"),
    ("VIKTOR-REF-16", "scoped reusable pre-authorization"),
]

# The scoped reusable pre-authorization binding (§2.6) — must NOT be blanket.
REUSABLE_APPROVAL_BINDING = ("tenant", "principal", "provider_account", "tool",
                             "action_class", "argument_constraints",
                             "data_sensitivity", "monetary_limit", "effect_class",
                             "purpose", "expiry", "revocation", "policy_epoch")


def scenario(*, scenario_id: str, family_id: str, claim_refs: list,
             language: str, risk_class: str, criticality: str,
             oracle_ref: str, provenance: str,
             contamination_class: str = "CLEAN") -> dict:
    s = {"scenario_id": scenario_id, "family_id": family_id,
         "claim_refs": sorted(claim_refs), "language": language,
         "risk_class": risk_class, "criticality": criticality,
         "oracle_ref": oracle_ref, "provenance": provenance,
         "contamination_class": contamination_class, "state": "PROPOSED"}
    s["scenario_hash"] = hash_obj(s)
    return s


def validate_scenario(s: dict) -> dict:
    """A generated/registered scenario is admitted only when it has an oracle, is
    unambiguous (single criticality), and is CLEAN. Otherwise quarantined."""
    problems = []
    if not s.get("oracle_ref") or s["oracle_ref"] == "UNRESOLVED":
        problems.append("no valid oracle")
    if s.get("criticality") not in ("low", "medium", "high", "critical"):
        problems.append("ambiguous criticality")
    if s.get("contamination_class") not in ("CLEAN",):
        problems.append("contamination suspected")
    state = "ORACLE_VALIDATED" if not problems else "QUARANTINED"
    return {**s, "state": state, "validation_problems": problems}


def challenge_escrow(*, challenge_id: str, generator_version: str,
                     secret_seed: str, scenario_ids: list,
                     answer_keys: list) -> dict:
    """Commit scenario + answer-key roots and a secret-seed commitment BEFORE the
    run. The seed and answer keys are NEVER stored in the record (only their
    commitments), so the escrow can be published without leaking answers."""
    return {
        "challenge_id": challenge_id, "generator_version": generator_version,
        "secret_seed_commitment": commitment(secret_seed),
        "scenario_root": hash_obj(sorted(scenario_ids)),
        "answer_key_root": hash_obj(sorted(commitment(a) for a in answer_keys)),
        "created_before_run": True, "release_policy": "SEALED_UNTIL_SCORED",
        "status": "SEALED",
    }


def build_viktor_scenarios() -> list:
    out = []
    for fid, desc in VIKTOR_FAMILIES:
        crit = "critical" if fid in ("VIKTOR-REF-05", "VIKTOR-REF-06",
                                     "VIKTOR-REF-09", "VIKTOR-REF-10",
                                     "VIKTOR-REF-14", "VIKTOR-REF-16") else "high"
        out.append(validate_scenario(scenario(
            scenario_id=f"SCN-{fid}", family_id=fid,
            claim_refs=["D3-C05-approval-binding"] if "approval" in desc
            else ["D4-C16-reusable-approval-scope"],
            language="EN", risk_class="protected" if crit == "critical" else "low",
            criticality=crit, oracle_ref="ORA-DET-STATE",
            provenance="VIKTOR_VENDOR_REFERENCE")))
    return out


def scenario_findings(scenarios: list) -> list[Finding]:
    out: list[Finding] = []
    for s in scenarios:
        if s.get("state") == "QUARANTINED":
            out.append(Finding("SCENARIO_INVALID", P1, s["scenario_id"],
                               f"scenario quarantined: {s.get('validation_problems')}",
                               {}))
    return out


def scenario_root(scenarios: list) -> str:
    return hash_obj(sorted(s["scenario_hash"] for s in scenarios))
