"""Real-registry distinctions + baseline + isolation (SP0002 AC 01-03,28-34,56,57,
78,80,86 + determinism/no-product-import)."""
from __future__ import annotations

import json
import os
import subprocess
import sys

from tools.semantics.canon import meaning_hash
from tools.semantics.registry import load_registry, validate_registry
from tools.semantics.resolve import Resolver

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REG = os.path.join(ROOT, "docs/semantics/FINALIS_CANONICAL_CONCEPT_REGISTRY.json")


def _reg():
    return load_registry(REG)


def _keys():
    return {c["canonical_key"] for c in _reg()["concepts"]}


def test_sp0000_and_sp0001_precondition():
    m = json.load(open(os.path.join(
        ROOT, "docs/architecture/FINALIS_1000_ARCHITECTURE_MANIFEST.json")))
    assert "COMPLETE" in m["final_result"]           # SP0000
    # SP0001 tooling present + baseline valid
    r = subprocess.run([sys.executable, "-m", "tools.architecture", "validate"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0


def test_real_registry_valid():
    rep = validate_registry(_reg())
    assert rep.valid, [f.to_dict() for f in rep.findings if f.severity != "P2"]
    assert rep.counts()["P0"] == 0 and rep.counts()["P1"] == 0


def test_registry_deterministic():
    assert validate_registry(_reg()).to_dict() == validate_registry(_reg()).to_dict()


def test_meaning_hashes_stored_and_correct():
    for c in _reg()["concepts"]:
        assert c["meaning_hash"] == meaning_hash(c)


# ---- concept distinctions (AC-28..34) -------------------------------------
def test_task_and_owned_work_distinguished():
    k = _keys()
    assert "work.task" in k and "work.owned_work" in k
    assert "work.task" != "work.owned_work"


def test_case_and_run_distinguished():
    assert {"case.case", "run.run"} <= _keys()


def test_action_effect_outcome_completion_distinguished():
    assert {"action.action", "effect.effect", "outcome.business_outcome",
            "lifecycle.completion"} <= _keys()


def test_claim_and_fact_distinguished():
    assert {"evidence.claim", "evidence.fact"} <= _keys()


def test_evidence_and_artifact_distinguished():
    assert {"evidence.evidence", "artifact.artifact"} <= _keys()


def test_tool_skill_capability_distinguished():
    assert {"tool.tool", "skill.skill", "authority.permission",
            "capability.architecture_capability"} <= _keys()


def test_employee_worker_agent_distinguished():
    assert {"employee.employee", "employee.worker", "employee.agent"} <= _keys()


# ---- resolution behavior on the real registry -----------------------------
def test_completed_is_not_guessed():
    out = Resolver(_reg()).resolve("completed")
    assert out["status"] in ("UNKNOWN", "AMBIGUOUS")   # never silently resolved


def test_alias_resolves_deterministically():
    out = Resolver(_reg()).resolve("work_item")
    assert out["status"] == "RESOLVED" and out["canonical_key"] == "work.owned_work"


def test_forbidden_alias_present_on_task():
    task = next(c for c in _reg()["concepts"] if c["canonical_key"] == "work.task")
    assert "owned_work" in task["forbidden_aliases"]


# ---- twin separation (AC-56,57) -------------------------------------------
def test_semantic_twin_separate_from_architecture_twin():
    reg = _reg()
    assert reg["twin_kind"] == "SEMANTIC_DOMAIN_TWIN"
    arch = json.load(open(os.path.join(
        ROOT, "docs/architecture/FINALIS_1000_ARCHITECTURE_TWIN.json")))
    assert arch["twin_kind"] == "DECLARED"          # different twin, different file


# ---- isolation (AC-78) -----------------------------------------------------
def test_product_code_does_not_import_semantics_tooling():
    hits = subprocess.run(["grep", "-rn", "tools.semantics",
                           os.path.join(ROOT, "finalis")],
                          capture_output=True, text=True)
    assert hits.stdout.strip() == "", hits.stdout


def test_cli_validate_exit_zero():
    r = subprocess.run([sys.executable, "-m", "tools.semantics", "validate", "--json"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0
    assert json.loads(r.stdout)["valid"] is True


def test_cli_attest_deterministic():
    def h():
        r = subprocess.run([sys.executable, "-m", "tools.semantics", "attest", "--json"],
                           cwd=ROOT, capture_output=True, text=True)
        return json.loads(r.stdout)["envelope_hash"]
    assert h() == h()


def test_no_product_migration_added():
    # SP0002 must not add a migration (still v27)
    import re
    db = open(os.path.join(ROOT, "finalis/portal/db.py"), encoding="utf-8").read()
    versions = re.findall(r"^\s*\((\d+),\s*\"\"\"", db, re.M)
    assert max(int(v) for v in versions) == 27
