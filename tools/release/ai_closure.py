"""AI Release Closure (SP0009 FUNCTION L, §10.13, §11.20, D-0009-58/59/60/61,
AC-0009-224..230).

SAME MODEL NAME != SAME MODEL BEHAVIOR and SAME PROMPT TEXT != SAME AI SYSTEM:
an AI release identity is the COMPOSITE fingerprint of model identity, provider
identity, provider ACCOUNT (accounts stay distinct — INV-0009-59), the full
fallback chain (order + conditions are material, D-0009-59), prompts, skills,
tool contracts, retrieval configuration, policy packs, router, safety
configuration, generation parameters and the evaluation-set fingerprint.
Changing ANY material member changes the closure hash and therefore requires a
new AI release identity. Unexpected provider behavior raises
OPAQUE_PROVIDER_UPDATE_SUSPECTED (D-0009-60). The SP0011 qualification
interface is a PLACEHOLDER that can carry no fabricated evaluation evidence
(D-0009-61).
"""
from __future__ import annotations

from .canon import hash_obj
from .model import Finding, P0, P1

MATERIAL_MEMBERS = (
    "model_identity", "provider_identity", "provider_account_ref",
    "fallback_chain", "prompt_hashes", "skill_hashes",
    "tool_contract_hashes", "retrieval_configuration_hash",
    "policy_pack_hash", "router_hash", "safety_configuration_hash",
    "generation_parameters", "evaluation_set_hash",
)


def ai_release_closure(*, candidate_genome: str, model_identity: dict,
                       provider_identity: dict, provider_account_ref: str,
                       fallback_chain: list, prompt_hashes: list,
                       skill_hashes: list, tool_contract_hashes: list,
                       retrieval_configuration_hash: str,
                       policy_pack_hash: str, router_hash: str,
                       safety_configuration_hash: str,
                       generation_parameters: dict,
                       evaluation_set_hash: str,
                       known_limitations: list) -> dict:
    c = {
        "candidate_genome": candidate_genome,
        "model_identity": model_identity,
        "provider_identity": provider_identity,
        "provider_account_ref": provider_account_ref,
        "fallback_chain": list(fallback_chain),   # ORDER is material
        "prompt_hashes": sorted(prompt_hashes),
        "skill_hashes": sorted(skill_hashes),
        "tool_contract_hashes": sorted(tool_contract_hashes),
        "retrieval_configuration_hash": retrieval_configuration_hash,
        "policy_pack_hash": policy_pack_hash,
        "router_hash": router_hash,
        "safety_configuration_hash": safety_configuration_hash,
        "generation_parameters": dict(generation_parameters),
        "evaluation_set_hash": evaluation_set_hash,
        "known_limitations": list(known_limitations),
    }
    c["closure_hash"] = hash_obj({k: c[k] for k in MATERIAL_MEMBERS})
    missing = [k for k in MATERIAL_MEMBERS if c.get(k) in (None, "", [], {})]
    c["closure_status"] = "COMPLETE" if not missing else "INCOMPLETE"
    c["missing_members"] = missing
    c["ai_release_id"] = "AIR-" + c["closure_hash"][:20]
    return c


def closure_findings(c: dict, *, protected: bool) -> list[Finding]:
    out: list[Finding] = []
    subject = str(c.get("ai_release_id") or "-")
    if c.get("closure_status") != "COMPLETE" and protected:
        out.append(Finding(
            "AI_RELEASE_CLOSURE_INCOMPLETE", P0, subject,
            f"protected AI change with incomplete closure: missing "
            f"{c.get('missing_members')} — an unknown closure member blocks "
            "(FUNCTION L)", {"missing": c.get("missing_members")}))
    # model identity must be composite, never just a name (D-0009-58)
    mi = c.get("model_identity") or {}
    if mi and set(mi.keys()) <= {"name"}:
        out.append(Finding(
            "AI_RELEASE_CLOSURE_INCOMPLETE", P1, subject,
            "model identity is only a name; a name alone is not an AI "
            "identity (D-0009-58) — bind deployment/version/config",
            {"model_identity": mi}))
    return out


def material_change(old: dict, new: dict) -> bool:
    """True when any material member differs => new AI release identity."""
    return old.get("closure_hash") != new.get("closure_hash")


def account_separation_findings(closures: list) -> list[Finding]:
    """Provider accounts remain distinct (INV-0009-59): two closures declaring
    DIFFERENT provider identities but the SAME account ref have merged
    accounts."""
    out: list[Finding] = []
    by_account: dict = {}
    for c in closures:
        acct = c.get("provider_account_ref")
        prov = hash_obj(c.get("provider_identity") or {})
        by_account.setdefault(acct, set()).add(prov)
    for acct, provs in sorted(by_account.items(), key=lambda kv: str(kv[0])):
        if acct and len(provs) > 1:
            out.append(Finding(
                "AI_RELEASE_CLOSURE_INCOMPLETE", P1, str(acct),
                "one provider account is shared by multiple distinct "
                "provider identities: accounts must remain separate "
                "(AC-0009-225)", {"provider_count": len(provs)}))
    return out


def opaque_update_findings(*, pinned_behavior_hash: str,
                           observed_behavior_hash: str,
                           closure_changed: bool, subject: str
                           ) -> list[Finding]:
    """Opaque provider update detector (D-0009-60): behavior changed while the
    declared closure did NOT change => the provider changed something opaque
    underneath the same identity."""
    out: list[Finding] = []
    if pinned_behavior_hash and observed_behavior_hash \
            and pinned_behavior_hash != observed_behavior_hash \
            and not closure_changed:
        out.append(Finding(
            "OPAQUE_PROVIDER_UPDATE_SUSPECTED", P1, subject,
            "observed provider behavior diverges from the pinned behavioral "
            "fingerprint while the declared AI closure is unchanged: opaque "
            "provider update suspected (D-0009-60) — requalification "
            "required for protected AI changes",
            {"pinned": pinned_behavior_hash,
             "observed": observed_behavior_hash}))
    return out


# --- SP0011 qualification placeholder (D-0009-61, AC-0009-230) -----------------------
def sp0011_placeholder() -> dict:
    """The reserved Evaluation qualification interface: permanently PENDING
    until SP0011 itself runs. It cannot carry evidence."""
    return {"qualification": "PENDING_SP0011",
            "evidence": None,
            "note": "SP0011 Evaluation has not run; no evaluation evidence "
                    "exists and none may be fabricated (D-0009-61)"}


def validate_sp0011(placeholder: dict) -> list[Finding]:
    out: list[Finding] = []
    if placeholder.get("qualification") != "PENDING_SP0011":
        out.append(Finding(
            "SP0011_EVIDENCE_FABRICATION_REJECTED", P0, "SP0011",
            "SP0011 placeholder must remain PENDING_SP0011", {}))
    if placeholder.get("evidence") is not None:
        out.append(Finding(
            "SP0011_EVIDENCE_FABRICATION_REJECTED", P0, "SP0011",
            "SP0011 placeholder carries evidence: evaluation evidence cannot "
            "exist before SP0011 runs — fabrication rejected (D-0009-61)",
            {}))
    return out
