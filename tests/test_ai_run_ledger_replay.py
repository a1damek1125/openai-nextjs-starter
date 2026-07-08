"""CORE-A3 — event-sourced replay reducer, chain integrity, Merkle checkpoint,
and tamper/reorder/truncation detection (pure + API)."""
import base64
import copy
import json

import pytest
from fastapi.testclient import TestClient

from finalis.ai_employee import run_ledger as R
from finalis.portal.app import create_app
from finalis.portal.seed import seed


def _chain(types):
    return R.assemble_events(
        run_id="r1", tenant_id="t1", task_id="task1", trace_id="tr1",
        actor_id="sys", specs=[{"event_type": t} for t in types],
        id_factory=lambda i: f"e{i}")


DRAFT_SEQ = ["RUN_CREATED", "TASK_ENVELOPE_SNAPSHOT_RECORDED",
             "TASK_CONTRACT_SNAPSHOT_RECORDED", "AUTHORITY_SNAPSHOT_RECORDED",
             "CAPABILITY_SNAPSHOT_RECORDED", "DATA_SCOPE_SNAPSHOT_RECORDED",
             "POLICY_PRECHECK_RECORDED", "RUN_STARTED", "PLAN_DRAFTED",
             "DRAFT_OUTPUT_PLACEHOLDER_CREATED"]


class TestReducerPure:
    def test_draft_sequence_reduces_to_draft_ready(self):
        st = R.reduce_run(_chain(DRAFT_SEQ))
        assert st["replayed_run_status"] == "DRAFT_READY"
        assert st["replay_errors"] == []
        assert st["event_count"] == 10

    def test_deterministic_state_hash(self):
        ev = _chain(DRAFT_SEQ)
        assert R.reduce_run(ev)["run_state_hash"] \
            == R.reduce_run(ev)["run_state_hash"]

    def test_first_event_genesis_and_chain_links(self):
        ev = _chain(DRAFT_SEQ)
        assert ev[0]["previous_event_hash"] == R.GENESIS
        assert ev[1]["previous_event_hash"] == ev[0]["event_hash"]
        assert R.reduce_run(ev)["latest_event_hash"] == ev[-1]["event_hash"]

    def test_run_chain_hash_and_merkle_change_on_reorder(self):
        ev = _chain(DRAFT_SEQ)
        hashes = [e["event_hash"] for e in ev]
        reordered = hashes[:7] + [hashes[8], hashes[7]] + hashes[9:]
        assert R.run_chain_hash(hashes) != R.run_chain_hash(reordered)
        assert R.run_event_merkle_root(hashes) \
            != R.run_event_merkle_root(reordered)

    def test_invalid_transition_is_replay_error(self):
        # STARTED -> COMPLETED_NO_SIDE_EFFECTS is not allowed.
        ev = _chain(["RUN_CREATED", "RUN_STARTED",
                     "RUN_COMPLETED_NO_SIDE_EFFECTS"])
        st = R.reduce_run(ev)
        assert any("invalid transition" in e for e in st["replay_errors"])

    def test_unknown_event_type_is_replay_error(self):
        ev = _chain(["RUN_CREATED", "RUN_STARTED"])
        ev[1]["event_type"] = "MADE_UP_EVENT"
        st = R.reduce_run(ev)
        assert any("unknown event_type" in e for e in st["replay_errors"])

    def test_truncation_changes_chain_and_state(self):
        ev = _chain(DRAFT_SEQ)
        full = R.reduce_run(ev)
        truncated = R.reduce_run(ev[:-1])
        assert truncated["event_count"] != full["event_count"]
        assert truncated["run_chain_hash"] != full["run_chain_hash"]


class TestVerifyPure:
    def test_untampered_verifies_clean(self):
        chk = R.verify_events(_chain(DRAFT_SEQ))
        assert chk["tamper_reasons"] == []
        assert chk["event_index_status"] == "CONTIGUOUS"
        assert chk["causal_link_status"] == "VALID"

    def test_payload_tamper_detected(self):
        ev = _chain(DRAFT_SEQ)
        ev[3]["event_payload"] = {"k": "TAMPERED"}   # hash now stale
        chk = R.verify_events(ev)
        assert any("hash mismatch" in r for r in chk["tamper_reasons"])

    def test_reorder_detected(self):
        ev = _chain(DRAFT_SEQ)
        ev[7], ev[8] = ev[8], ev[7]
        chk = R.verify_events(ev)
        assert chk["tamper_reasons"]


class TestApiTamperDetection:
    @pytest.fixture()
    def app(self):
        a = create_app(":memory:")
        seed(a.state.db)
        return a

    def _run(self, app):
        c = TestClient(app)
        h = {"Authorization": "Bearer " + c.post("/auth/login", json={
            "email": "owner@demo.finalis", "password": "demo1234"}).json()[
            "token"]}
        cid = c.get("/cases", headers=h).json()[0]["id"]
        tk = c.post("/ai-tasks", json={
            "task_type": "case_summary", "task_title": "s",
            "task_description": "please", "subject_type": "case",
            "subject_id": cid}, headers=h).json()
        run = c.post("/ai-runs", json={"task_id": tk["task_id"]},
                     headers=h).json()
        return c, h, run["run_id"]

    def test_verify_matched_untampered(self, app):
        c, h, rid = self._run(app)
        v = c.post(f"/ai-runs/{rid}/verify", headers=h).json()
        assert v["verification_status"] == "MATCHED"
        assert v["tamper_detected"] is False
        assert v["verification_kind"] == "ledger_integrity_verification"
        assert v["current_task_state_comparison"] == "NOT_IMPLEMENTED"

    def test_verify_mismatch_on_stored_event_tamper(self, app):
        c, h, rid = self._run(app)
        # Tamper a stored event envelope's payload without fixing its hash.
        row = app.state.db.one(
            "SELECT id, envelope_json FROM ai_run_events WHERE run_id=? AND "
            "event_index=4", rid)
        env = json.loads(row["envelope_json"])
        env["event_payload"] = {"k": "TAMPERED"}
        app.state.db.conn.execute(
            "UPDATE ai_run_events SET envelope_json=? WHERE id=?",
            (json.dumps(env), row["id"]))
        app.state.db.conn.commit()
        v = c.post(f"/ai-runs/{rid}/verify", headers=h).json()
        assert v["verification_status"] == "MISMATCHED"
        assert v["tamper_detected"] is True
        assert v["tamper_reasons"]

    def test_verify_mismatch_on_stored_summary_tamper(self, app):
        c, h, rid = self._run(app)
        # Tamper the stored run summary hash -> replay/state mismatch.
        row = app.state.db.one("SELECT payload_json FROM ai_runs WHERE id=?",
                               rid)
        p = json.loads(row["payload_json"])
        p["run_state_hash"] = "deadbeef" * 8
        app.state.db.conn.execute(
            "UPDATE ai_runs SET payload_json=?, run_state_hash=? WHERE id=?",
            (json.dumps(p), "deadbeef" * 8, rid))
        app.state.db.conn.commit()
        v = c.post(f"/ai-runs/{rid}/verify", headers=h).json()
        assert v["run_state_hash_status"] == "MISMATCHED"
        assert v["verification_status"] == "MISMATCHED"

    def test_replay_does_not_rerun_task(self, app):
        c, h, rid = self._run(app)
        rp = c.post(f"/ai-runs/{rid}/replay", headers=h).json()
        assert rp["replay_status"] == "MATCHED"
        assert rp["current_task_state_comparison"] == "NOT_IMPLEMENTED"
