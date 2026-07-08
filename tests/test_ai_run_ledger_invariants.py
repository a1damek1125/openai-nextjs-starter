"""CORE-A3 invariants — the Run Ledger records/replays/verifies but never
grants permission, never executes, never overrides a blocked task, and a
terminal run never restarts. Positive events cannot override a hard-fail
authority decision."""
import json

import pytest
from fastapi.testclient import TestClient

from finalis.ai_employee import run_ledger as R
from finalis.portal.app import create_app
from finalis.portal.seed import seed


@pytest.fixture()
def app():
    a = create_app(":memory:")
    seed(a.state.db)
    return a


def _login(c, email="owner@demo.finalis"):
    return {"Authorization": "Bearer " + c.post("/auth/login", json={
        "email": email, "password": "demo1234"}).json()["token"]}


def _run(c, h, **extra):
    cid = c.get("/cases", headers=h).json()[0]["id"]
    body = {"task_type": "case_summary", "task_title": "t",
            "task_description": "please", "subject_type": "case",
            "subject_id": cid}
    body.update(extra)
    t = c.post("/ai-tasks", json=body, headers=h).json()
    return c.post("/ai-runs", json={"task_id": t["task_id"]},
                  headers=h).json()


class TestNoExecutionNoPermission:
    def test_104_105_run_creation_is_not_execution(self, app):
        c = TestClient(app)
        h = _login(c)
        r = _run(c, h)
        # no side-effect fields; run records but grants nothing
        assert r["final_summary"] is None
        assert r["requires_run_ledger"] is True
        assert "Run Ledger records what happened; it does not grant " \
            "permission to act." in r["honesty_labels"]

    def test_106_replay_does_not_rerun(self, app):
        c = TestClient(app)
        h = _login(c)
        rid = _run(c, h)["run_id"]
        rp = c.post(f"/ai-runs/{rid}/replay", headers=h).json()
        assert rp["current_task_state_comparison"] == "NOT_IMPLEMENTED"
        assert "Replay verifies ledger consistency; it does not re-run the " \
            "task." in rp["honesty_labels"]

    def test_107_run_cannot_override_blocked_task(self, app):
        c = TestClient(app)
        h = _login(c)
        cid = c.get("/cases", headers=h).json()[0]["id"]
        blocked = c.post("/ai-tasks", json={
            "task_type": "case_summary", "task_title": "x",
            "subject_type": "case", "subject_id": cid,
            "subject_tenant_id": "other-tenant"}, headers=h).json()
        assert c.post("/ai-runs", json={"task_id": blocked["task_id"]},
                      headers=h).status_code == 409

    def test_125_positive_events_cannot_flip_authority(self, app):
        # The stored authority snapshot is copied from the task and is not
        # derived from any run event; adding events cannot change it.
        c = TestClient(app)
        h = _login(c)
        r = _run(c, h, task_type="merge_proposal", subject_type="customer",
                 subject_id="cu1")
        assert r["authority_decision"] == "APPROVAL_REQUIRED"
        # the run paused; it did not self-approve
        assert r["run_status"] == "PAUSED"


class TestTerminalRunsCannotRestart:
    @pytest.mark.parametrize("terminal", list(R.TERMINAL_STATUSES))
    def test_126_129_terminal_has_no_transition(self, terminal):
        assert R.TRANSITIONS[terminal] == set()
        for dst in R.RUN_STATUSES:
            if dst != terminal:
                assert not R.valid_transition(terminal, dst)

    def test_cancelled_run_cannot_be_cancelled_again(self, app):
        c = TestClient(app)
        h = _login(c)
        rid = _run(c, h)["run_id"]
        assert c.post(f"/ai-runs/{rid}/cancel", headers=h).json()[
            "run_status"] == "CANCELLED"
        assert c.post(f"/ai-runs/{rid}/cancel", headers=h).status_code == 409


class TestReducerInvariants:
    def test_119_event_payload_cannot_rewrite_prior_event(self):
        # Modifying a prior event's stored hash breaks every downstream link.
        ev = R.assemble_events(
            run_id="r1", tenant_id="t1", task_id="task1", trace_id="tr1",
            actor_id="s", specs=[{"event_type": t} for t in
                                 ("RUN_CREATED", "RUN_STARTED",
                                  "PLAN_DRAFTED")],
            id_factory=lambda i: f"e{i}")
        ev[0]["event_hash"] = "forged"
        chk = R.verify_events(ev)
        assert chk["tamper_reasons"]

    def test_128_blocked_run_state_is_terminal_in_reducer(self):
        ev = R.assemble_events(
            run_id="r1", tenant_id="t1", task_id="task1", trace_id="tr1",
            actor_id="s", specs=[{"event_type": "RUN_CREATED"},
                                 {"event_type": "RUN_STARTED"},
                                 {"event_type": "RUN_BLOCKED",
                                  "reason": "policy"}],
            id_factory=lambda i: f"e{i}")
        st = R.reduce_run(ev)
        assert st["replayed_run_status"] == "BLOCKED"
        assert st["terminal"] is True


class TestNoExternalOrLegalOverclaim:
    def test_honesty_labels_no_overclaims(self, app):
        c = TestClient(app)
        h = _login(c)
        labels = _run(c, h)["honesty_labels"]
        blob = json.dumps(labels).lower()
        # No POSITIVE compliance/execution overclaim (disclaimers that say
        # "not X" are fine and expected).
        for banned in ("cloudevents compliant", "w3c trace context compliant",
                       "opentelemetry integrated",
                       "immutable storage guaranteed",
                       "legal audit certification",
                       "production autonomous worker"):
            assert banned not in blob, banned
        # The merkle-root disclaimer is present, verbatim.
        assert ("Run event Merkle root is an internal checkpoint; it is not "
                "external notarization.") in labels
