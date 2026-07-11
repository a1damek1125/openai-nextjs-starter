"""Shadow Substitution Lab + version-bound Substitution Evidence (SP0004
D-0004-36/37/42, §10.10/§11.14, INV-0004-20/21).

The lab records a canonical request and replays it against a candidate provider or
a deterministic fake, comparing canonical properties — and it must NEVER cause an
unauthorized external effect (INV-0004-21, AC-0004-076). For effectful
capabilities, real duplicate dual-run is prohibited (D-0004-37, AC-0004-077):
simulation / shadow / record-replay only. Substitution evidence is version-bound:
tested_at + provider_version + contract_version + corpus_version; a material
change invalidates applicability (D-0004-42, §11.14, INV-0004-20).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, P2, SUBSTITUTION_EVIDENCE_STALE,
                    SHADOW_EXTERNAL_EFFECT_BLOCKED, INVALID_TDR)


def shadow_replay(provider, corpus: list[dict]) -> dict:
    """Replay canonical workloads against a candidate in shadow mode. Any workload
    that is effectful but not marked NO_EXTERNAL_EFFECT is refused (fail-closed) —
    the lab cannot create a real external effect (INV-0004-21)."""
    findings: list[Finding] = []
    ran = []
    for w in corpus:
        # FAIL CLOSED (red-team F2): run ONLY when the workload explicitly declares
        # NO_EXTERNAL_EFFECT. A missing/other effect_mode — or a real effect_mode
        # with the optional `effectful` flag omitted — is refused. The lab can
        # never cause an external effect (INV-0004-21).
        if w.get("effect_mode") != "NO_EXTERNAL_EFFECT":
            findings.append(Finding(SHADOW_EXTERNAL_EFFECT_BLOCKED, P0,
                                    w.get("workload_id", "-"),
                                    "shadow lab refused a workload not explicitly "
                                    "in NO_EXTERNAL_EFFECT mode", {}))
            continue
        ran.append(provider.handle(w))
    return {"replayed": len(ran), "blocked_effectful": len(findings),
            "findings": [f.to_dict() for f in findings], "responses": ran}


def validate_substitution_evidence(ev: dict) -> list[Finding]:
    out: list[Finding] = []
    sid = ev.get("substitution_id", "-")
    for req in ("source_provider", "candidate_provider", "contract_version",
                "corpus_version", "provider_version", "tested_at"):
        if not ev.get(req):
            out.append(Finding(INVALID_TDR, P1, sid,
                               f"substitution evidence missing {req} "
                               "(AC-0004-085/086/087)", {}))
    return out


def evidence_applicable(ev: dict, *, current_contract_version: str,
                        current_corpus_version: str,
                        current_provider_version: str | None = None) -> bool:
    """Substitution evidence applies only if its bound versions still match
    (INV-0004-20). Any material version change invalidates it."""
    if ev.get("contract_version") != current_contract_version:
        return False
    if ev.get("corpus_version") != current_corpus_version:
        return False
    # provider_version is a binding dimension: if a current version is supplied,
    # evidence with a different OR MISSING provider_version does not apply
    # (red-team F3, INV-0004-20).
    if current_provider_version is not None and \
            ev.get("provider_version") != current_provider_version:
        return False
    return True


def stale_substitution(evidence_list: list[dict], *, current_contract_version: str,
                       current_corpus_version: str,
                       current_provider_version: str | None = None
                       ) -> list[Finding]:
    out: list[Finding] = []
    for ev in evidence_list:
        if not evidence_applicable(
                ev, current_contract_version=current_contract_version,
                current_corpus_version=current_corpus_version,
                current_provider_version=current_provider_version):
            out.append(Finding(SUBSTITUTION_EVIDENCE_STALE, P2,
                               ev.get("substitution_id", "-"),
                               "substitution evidence is version-stale; a material "
                               "input changed (INV-0004-20)", {}))
    return out
