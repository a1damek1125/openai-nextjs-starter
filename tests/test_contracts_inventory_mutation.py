"""SP0008 mutation / red-team regression locks (§20.35).

Each test pins shut a way the inventory could make a FALSE-SAFE / FALSE-KNOWN /
FALSE-COMPLETE claim. They must FAIL if the corresponding guard is reverted.
The two systemic root causes guarded kernel-wide: truthy-string coercion of
boolean flags (fix: `is True` / strict bool) and blacklist / "missing =
permissive" logic (fix: allowlist + fail-closed). Plus the inventory-specific
invariant: UNKNOWN is never coerced to safe/zero/complete.
"""
from __future__ import annotations

from pathlib import Path

from tools.contracts_inventory import (model, criticality as C, chains,
                                        ownership, envelope, genome, residual,
                                        normalize, discover, evidence,
                                        readiness, negative_space, detectors,
                                        witnesses)

ROOT = Path(__file__).resolve().parents[1]


def _kinds(fs):
    return {f.kind for f in fs}


# M1 — a hard criticality flag UNKNOWN must NOT be read as STANDARD (safe)
def test_m1_unknown_hard_flag_not_standard():
    for d in model.HARD_CRITICALITY_DIMS:
        vec = {dim: C.NO for dim in model.CRITICALITY_DIMS}
        vec[d] = C.UNK
        assert C.verdict(vec) == "ELEVATED", d


# M2 — a single hard flag YES forces CRITICAL (never averaged away)
def test_m2_hard_flag_conjunctive():
    for d in model.HARD_CRITICALITY_DIMS:
        vec = {dim: C.YES for dim in model.CRITICALITY_DIMS}   # all YES
        vec2 = {dim: C.NO for dim in model.CRITICALITY_DIMS}
        vec2[d] = C.YES
        assert C.verdict(vec2) == "CRITICAL", d


# M3 — an UNKNOWN-reachability route is never reported as "reaches_effect false
# with EXACT exactness" (i.e. proven no effect)
def test_m3_unknown_reach_not_exact_absent():
    s = normalize.CanonicalSurface("CS-A", "HTTP_ROUTE", "GET /x", "HTTP_API",
                                   None, model.NEW_SURFACE, ("d",),
                                   (("finalis/portal/app.py", 1),), ("f",), ())
    reach = chains.effect_reachability({"CS-A": set()}, [s])
    assert reach["CS-A"]["exactness"] == "UNKNOWN"     # not EXACT-absent


# M4 — an unfindable consumer is UNKNOWN (dark), never zero-as-safe
def test_m4_dark_consumer_not_zero():
    class S:
        surface_id = "CS-1"; surface_kind = "AUDIT_EVENT"
        canonical_name = "zzz.never.emitted"
        evidence = (("finalis/audit.py", 1),)
    rec = ownership.resolve_consumers(ROOT, S(), name_index={})
    assert rec["certainty"] == model.UNKNOWN
    assert model.DARK_CONSUMER in _kinds(ownership.consumer_findings(S(), rec))


# M5 — envelope structural allowlist rejects any authority-synonym key
def test_m5_envelope_allowlist_fail_closed():
    g = genome.build_genome([])
    env = envelope.inventory_envelope(
        inventory_version="v1", genome=g, surface_count=0,
        finding_counts={"P0": 0, "P1": 0, "P2": 0}, detector_names=[])
    for bad in ("mandate", "ratifies", "empowers", "authority", "grants"):
        assert model.PROOF_ENVELOPE_MISMATCH in _kinds(
            envelope.validate_envelope(dict(env, **{bad: True}))), bad


# M6 — envelope non_authoritative must be exactly True (not a truthy string)
def test_m6_envelope_non_authoritative_strict():
    g = genome.build_genome([])
    env = envelope.inventory_envelope(
        inventory_version="v1", genome=g, surface_count=0,
        finding_counts={"P0": 0, "P1": 0, "P2": 0}, detector_names=[])
    for bad in ("true", 1, "yes"):
        polluted = dict(env, non_authoritative=bad)
        polluted["content_digest"] = _redigest(polluted)
        assert model.PROOF_ENVELOPE_MISMATCH in _kinds(
            envelope.validate_envelope(polluted)), bad


# M7 — a material change moves the genome; a cosmetic change does not
def test_m7_genome_material_sensitivity():
    s = normalize.CanonicalSurface("CS-A", "HTTP_ROUTE", "GET /x", "HTTP_API",
                                   None, model.NEW_SURFACE, ("d",),
                                   (("f.py", 1),), ("fp",), ())
    base = genome.build_genome([s])
    material = normalize.CanonicalSurface("CS-A", "HTTP_ROUTE", "GET /y",
                                          "HTTP_API", None, model.NEW_SURFACE,
                                          ("d",), (("f.py", 1),), ("fp",), ())
    assert genome.build_genome([material])["global_root"] != base["global_root"]


# M8 — genome verify catches a tampered recorded root (P0)
def test_m8_genome_tamper_is_p0():
    s = normalize.CanonicalSurface("CS-A", "DB_TABLE", "cases", "DB_SCHEMA",
                                   None, model.NEW_SURFACE, ("d",),
                                   (("f.py", 1),), ("fp",), ())
    good = genome.build_genome([s])
    bad = dict(good, global_root="deadbeef")
    fs = genome.verify_genome([s], bad)
    assert any(f.severity == model.P0 and f.kind == model.GENOME_ROOT_MISMATCH
               for f in fs)


# M9 — capture-recapture refuses a spurious estimate without recapture
def test_m9_residual_not_estimable_without_recapture():
    obs = discover.discover_all(ROOT)
    est = residual.chao1(obs)
    assert est["estimable"] is False and est["s_hat_lower_bound"] is None


# M10 — an ungrounded (LLM-proposed) witness cannot be admitted
def test_m10_ungrounded_witness_rejected():
    w = {"kind": "POSITIVE", "outcome": "CONFIRMED", "surface_id": "CS-1",
         "grounded": False, "source": {"path": "", "line": 0},
         "witness_id": "WT-x"}
    assert model.WITNESS_UNGROUNDED in _kinds(witnesses.validate_witness(w))


# M11 — an UNKNOWN_OUTCOME witness is not counted as a pass
def test_m11_unknown_outcome_witness_flagged():
    w = {"kind": "POSITIVE", "outcome": "UNKNOWN_OUTCOME", "surface_id": "CS-1",
         "grounded": True, "source": {"path": "f.py", "line": 1},
         "witness_id": "WT-x"}
    assert model.UNKNOWN_OUTCOME_WITNESS in _kinds(
        witnesses.validate_witness(w))


# M12 — bitemporal interval that closes before it opens is inconsistent
def test_m12_bitemporal_inconsistent_caught():
    c = evidence.Claim("CS-1", "p", "v", "f.py", 1, "d",
                       valid_from="2026", valid_to="2020")
    assert model.BITEMPORAL_INCONSISTENT in _kinds(evidence.validate_claim(c))


# M13 — provenance edge to an undeclared node is broken
def test_m13_provenance_broken_caught():
    g = {"nodes": [{"id": "A", "kind": "ENTITY"}],
         "edges": [("A", "GHOST", "USED")]}
    assert model.PROVENANCE_BROKEN in _kinds(evidence.validate_provenance(g))


# M14 — negative space flags a shortfall (declared floor > observed)
def test_m14_negative_space_shortfall():
    # a surfaces list missing routes must fail the declared HTTP_ROUTE floor
    report, findings = negative_space.verify_negative_space(ROOT, [])
    assert model.NEGATIVE_SPACE_UNVERIFIED in _kinds(findings)


# M15 — readiness is fail-closed: any hard blocker => NOT_READY, no authority
def test_m15_readiness_fail_closed():
    s = normalize.CanonicalSurface("CS-A", "HTTP_ROUTE", "POST /x", "HTTP_API",
                                   None, model.NEW_SURFACE, ("d",),
                                   (("f.py", 1),), ("fp",), ())
    a = readiness.assess_surface(
        s, crit_vec={d: "UNKNOWN" for d in model.CRITICALITY_DIMS},
        reach={"exactness": "UNKNOWN"}, consumer={}, witnesses=[])
    assert a["verdict"] == "NOT_READY" and a["grants_authority"] is False


# M16 — identity resolution never mints a parallel CT-* id
def test_m16_no_parallel_registry():
    obs = [discover.Observation("d", "HTTP_ROUTE", "CT-FAKE",
                                "finalis/portal/app.py", 1, {})]
    s = normalize.reconcile(obs, [])
    # a NEW_SURFACE whose name looks like a CT id is flagged, never adopted
    assert normalize.parallel_registry_paths(s)


# M17 — ambiguous identity is never silently resolved to one parent
def test_m17_ambiguous_identity_not_guessed():
    obs = [discover.Observation("d", "HTTP_ROUTE", "GET /x",
                                "finalis/portal/app.py", 1, {})]
    descs = [{"contract_id": "CT-A", "contract_kind": "HTTP_API",
              "source_paths": ["finalis/portal/app.py"]},
             {"contract_id": "CT-B", "contract_kind": "HTTP_API",
              "source_paths": ["finalis"]}]
    s = normalize.reconcile(obs, descs)[0]
    assert s.identity_outcome == model.AMBIGUOUS_IDENTITY
    assert s.parent_contract_id is None


# M18 — common-mode agreement (same method) is NOT counted as real
# corroboration; and a single detector is never corroboration
def test_m18_common_mode_not_corroboration(monkeypatch):
    # force two detectors to share a method => COSMETIC diversity
    monkeypatch.setitem(detectors.CAPABILITY, "audit_events",
                        {"method": "AST_DICT_KEYS", "kinds": ("AUDIT_EVENT",)})
    assert detectors.diversity("run_ledger_events", "audit_events") == \
        model.DIVERSITY_COSMETIC
    # a surface seen by one detector is SINGLE_DETECTOR, not corroborated
    o = discover.Observation("http_routes", "HTTP_ROUTE", "GET /x",
                             "finalis/portal/app.py", 1, {})
    c = detectors.corroboration([o], surface_id=o.surface_id)
    assert c["corroboration"] == "SINGLE_DETECTOR"


# M19 — cut-set search reports LIMIT_REACHED rather than claiming completeness
def test_m19_cut_set_limit_reported():
    # a wide graph forces truncation; exactness must be LIMIT_REACHED
    edges = {"A": {f"m{i}" for i in range(30)}}
    for i in range(30):
        edges[f"m{i}"] = {"S"}
    edges["S"] = set()
    res = chains.minimal_cut_sets(edges, ["A"], {"S"}, max_size=3, limit=50)
    assert res["exactness"] == "LIMIT_REACHED"


# M20 — Report is invalid on any P1 (a required property unmet)
def test_m20_report_invalid_on_p1():
    assert not model.report([model.Finding("K", model.P1, "s", "m")]).valid


# M21 — boundary check is a fail-closed IMPORT ALLOWLIST, not a call denylist
def test_m21_boundary_import_allowlist(tmp_path):
    from tools.contracts_inventory import closure
    pkg = tmp_path / "tools" / "contracts_inventory"
    pkg.mkdir(parents=True)
    (pkg / "evil.py").write_text("import subprocess\nimport requests\n")
    fs = closure.check_no_external_effect(tmp_path)
    assert any(f.severity == model.P0 and f.kind == model.BOUNDARY_VIOLATION
               for f in fs)
    # a subprocess.run call name is also caught even without the import line
    (pkg / "evil2.py").write_text("import os\nos.system('rm -rf /')\n")
    fs2 = closure.check_no_external_effect(tmp_path)
    assert any("system" in f.message for f in fs2)


# M22 — frontier check reads the AST, catching a differently-quoted migration
def test_m22_frontier_ast_catches_alt_quote(tmp_path):
    from tools.contracts_inventory import closure
    db = tmp_path / "finalis" / "portal"
    db.mkdir(parents=True)
    # a v28 migration written with triple-SINGLE quotes (regex-invisible)
    (db / "db.py").write_text(
        "MIGRATIONS = [\n  (27, \"\"\"CREATE TABLE a (id);\"\"\"),\n"
        "  (28, '''CREATE TABLE b (id);'''),\n]\n")
    fs = closure.check_frontier_unchanged(tmp_path)
    assert any(f.kind == model.BOUNDARY_VIOLATION for f in fs)


# M23 — genome moves when a table's DDL changes at a FIXED version/name
def test_m23_genome_sensitive_to_ddl(tmp_path):
    from tools.contracts_inventory import discover
    db = tmp_path / "finalis" / "portal"
    db.mkdir(parents=True)
    (db / "db.py").write_text(
        'MIGRATIONS = [(1, """CREATE TABLE cases '
        '(id TEXT, tenant_id TEXT);""")]\n')
    obs_a = discover.detect_db(tmp_path)
    (db / "db.py").write_text(
        'MIGRATIONS = [(1, """CREATE TABLE cases (id TEXT);""")]\n')  # drop tenant_id
    obs_b = discover.detect_db(tmp_path)
    table_a = next(o for o in obs_a if o.surface_kind == "DB_TABLE")
    table_b = next(o for o in obs_b if o.surface_kind == "DB_TABLE")
    assert table_a.shape["ddl_material"] != table_b.shape["ddl_material"]
    assert genome.surface_material_leaf(_wrap(table_a)) != \
        genome.surface_material_leaf(_wrap(table_b))


# M24 — envelope with NO content_digest is unsealed, not a pass
def test_m24_envelope_missing_digest_fails():
    g = genome.build_genome([])
    env = envelope.inventory_envelope(
        inventory_version="v1", genome=g, surface_count=0,
        finding_counts={"P0": 0, "P1": 0, "P2": 0}, detector_names=[])
    del env["content_digest"]
    assert model.PROOF_ENVELOPE_MISMATCH in _kinds(
        envelope.validate_envelope(env))


# M25 — a route with a resolved edge AND an unresolved external hop is UNKNOWN
def test_m25_partial_resolution_is_unknown():
    s = normalize.CanonicalSurface("CS-R", "HTTP_ROUTE", "POST /x", "HTTP_API",
                                   None, model.NEW_SURFACE, ("d",),
                                   (("f.py", 1),), ("fp",), ())
    t = normalize.CanonicalSurface("CS-T", "DB_TABLE", "cases", "DB_SCHEMA",
                                   None, model.NEW_SURFACE, ("d",),
                                   (("f.py", 2),), ("fp",), ())
    reach = chains.effect_reachability({"CS-R": {"CS-T"}, "CS-T": set()},
                                       [s, t], unresolved={"CS-R"})
    assert reach["CS-R"]["exactness"] == "UNKNOWN"


# M26 — parallel-registry finding fires for a fabricated parent id
def test_m26_parallel_registry_fabricated_parent():
    s = normalize.CanonicalSurface("CS-A", "HTTP_ROUTE", "GET /x", "HTTP_API",
                                   "CT-DOES-NOT-EXIST", model.MATCHED_EXISTING,
                                   ("d",), (("f.py", 1),), ("fp",), ())
    fs = normalize.parallel_registry_findings(
        [s], [{"contract_id": "CT-REAL"}])
    assert model.PARALLEL_REGISTRY_DETECTED in _kinds(fs)


def _wrap(obs):
    return normalize.CanonicalSurface(
        obs.surface_id, obs.surface_kind, obs.canonical_name, "DB_SCHEMA",
        None, model.NEW_SURFACE, (obs.detector,),
        ((obs.evidence_path, obs.evidence_line),),
        (obs.as_dict()["structural_fingerprint"],), ())


def _redigest(env):
    from tools.contracts_inventory.canon import core_hash
    return core_hash({k: env[k] for k in env if k != "content_digest"})
