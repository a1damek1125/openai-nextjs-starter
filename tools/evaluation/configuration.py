"""Evaluation configuration identity (SP0011 §10.1, §11.1, D-0011-001/002/003,
AC-0011-030..040).

MODEL IDENTITY ALONE NEVER IDENTIFIES THE EVALUATED SYSTEM (INV-4). The evaluated
object is the COMPLETE versioned Finalis configuration: repository commit +
Program Seal + model + harness + prompts + policies + tools + provider adapters +
provider account class + memory snapshot + sandbox + language + packs. Any
material field change creates a NEW configuration identity (D-0011-003), so a
score cannot silently transfer to a different configuration.

The default evaluated configuration is the REPOSITORY-LOCAL reference: the
committed Finalis code at the frozen commit, the deterministic reference harness
(the evaluation kernel's own runner), mocked providers (no live connection), and
the control/work language matrix the repo actually supports. No live model
provider is bound (evaluation is standard-library-only by default).
"""
from __future__ import annotations

from pathlib import Path

from .canon import hash_obj
from .model import Finding, P1
from . import freeze as freeze_mod

# The repository-local reference configuration. Provider/model are the
# DETERMINISTIC REFERENCE (no live provider), recorded honestly as such.
REFERENCE_CONFIGURATION = {
    "configuration_id": "CFG-FINALIS-REPO-REFERENCE",
    "model_identity": {"provider": "NONE_LIVE",
                       "role": "deterministic-reference",
                       "note": "no live model provider bound (std-lib only)"},
    "harness_identity": {"harness": "finalis-evaluation-reference-runner",
                         "version": "1.0"},
    "prompt_epoch": "repo-frozen",
    "policy_epoch": "repo-frozen",
    "tool_versions": {"finalis_portal": "repo-frozen"},
    "provider_adapters": {"telephony": "MOCK", "email": "MOCK",
                          "calendar": "MOCK", "payment": "MOCK",
                          "esignature": "MOCK"},
    "provider_account_classes": {"default": "SANDBOX_MOCK"},
    "memory_snapshot": "repo-frozen",
    "sandbox_identity": "repository-local",
    "languages": ["PL", "EN", "DE", "ES"],
    "control_language": "PL",
    "work_languages": ["EN", "DE", "ES"],
    "role_pack": None,
    "vertical_pack": None,
    "country_pack": None,
    "company_pack": None,
}

# fields whose change creates a NEW configuration identity (materiality rules)
MATERIAL_FIELDS = ("model_identity", "harness_identity", "prompt_epoch",
                   "policy_epoch", "tool_versions", "provider_adapters",
                   "provider_account_classes", "memory_snapshot",
                   "sandbox_identity", "languages", "role_pack", "vertical_pack",
                   "country_pack", "company_pack")


def build_configuration(root: Path) -> dict:
    frz = freeze_mod.freeze(root)
    cfg = dict(REFERENCE_CONFIGURATION)
    cfg["repository_commit"] = frz["starting_head"]
    cfg["program_seal"] = frz["sp0010_program_seal"]
    cfg["architecture_genome_root"] = frz["sp0010_architecture_genome_root"]
    cfg["configuration_root"] = configuration_root(cfg)
    return cfg


def configuration_root(cfg: dict) -> str:
    """The configuration root hashes the repository commit + Program Seal + every
    material field. Any material change moves it (D-0011-003)."""
    material = {"repository_commit": cfg.get("repository_commit"),
                "program_seal": cfg.get("program_seal")}
    for f in MATERIAL_FIELDS:
        material[f] = cfg.get(f)
    return hash_obj(material)


def configuration_findings(cfg: dict) -> list[Finding]:
    out: list[Finding] = []
    for req in ("repository_commit", "program_seal"):
        if not cfg.get(req):
            out.append(Finding(
                "CONFIGURATION_IDENTITY_INCOMPLETE", P1, req,
                f"evaluated configuration is missing {req}: incomplete identity",
                {}))
    return out
