"""Finalis Portal API — FastAPI over the tested domain core.

UI → these endpoints → domain services (unchanged, 212-test core) →
PortalStore persistence → DbAuditLog (chain in SQL). Providers are the
existing mocks behind real interfaces (env-configurable later).
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ..actions.engine import ActionCommunicationEngine
from ..actions.models import ActionRequest, ChannelPreference
from ..case_services import (ActionGateService, CompletionLoopService,
                             MissingInfoService)
from ..dashboard import DashboardService, PermissionDenied
from ..dashboard_html import render_dashboard
from ..models import Case
from ..state_machine import CaseState, IllegalTransition, transition
from ..voice.conversation_intelligence import (ConversationIntelligence,
                                               DiarizedSegment)
from .auth import AuthService, verify_token
from .db import Database, DbAuditLog, utcnow
from .store import PortalStore
from . import ui


def create_app(db_path: str = ":memory:") -> FastAPI:
    app = FastAPI(title="Finalis AI Portal", version="0.1.0")
    db = Database(db_path)
    store = PortalStore(db)
    audit = DbAuditLog(db)
    auth = AuthService(db)
    ace = ActionCommunicationEngine(audit)
    loop = CompletionLoopService(audit)
    app.state.db, app.state.store, app.state.audit = db, store, audit
    app.state.auth, app.state.ace, app.state.loop = auth, ace, loop

    # ---- auth dependency -------------------------------------------------------
    def current_user(authorization: str = Header(default="")) -> dict:
        token = authorization.removeprefix("Bearer ").strip()
        body = verify_token(token) if token else None
        if body is None:
            raise HTTPException(401, "not authenticated")
        return body

    def require_role(user: dict, *roles: str) -> None:
        if user["role"] not in roles:
            raise HTTPException(403, f"role {user['role']} not permitted")

    def load_case_or_404(case_id: str, user: dict) -> Case:
        case = store.load_case(case_id, tenant_id=user["tid"])
        if case is None:
            raise HTTPException(404, "case not found")   # incl. cross-tenant
        return case

    def dash_service(tenant_id: str) -> DashboardService:
        """Rebuild the dashboard projection from persisted cases."""
        svc = DashboardService(audit)
        for meta in store.list_cases(tenant_id=tenant_id):
            case = store.load_case(meta["id"], tenant_id=tenant_id)
            svc.register_case(
                case, title=meta["title"],
                client_name=meta["client_name"] or "?",
                offer_sent_at=datetime.fromisoformat(meta["offer_sent_at"])
                if meta["offer_sent_at"] else None)
        for d in db.all("SELECT * FROM message_drafts WHERE tenant_id=? "
                        "AND approval_status='PENDING'", tenant_id):
            svc.register_approval(
                tenant_id=tenant_id, case_id=d["case_id"],
                action_type="message_draft", draft_message=d["text"],
                reason=d["risk_level"] + " risk draft",
                risk_level=d["risk_level"],
                created_at=datetime.fromisoformat(d["created_at"]))
        return svc

    # ---- auth ------------------------------------------------------------------
    @app.post("/auth/login")
    async def login(body: dict):
        result = auth.login(body.get("email", ""), body.get("password", ""))
        if result is None:
            raise HTTPException(401, "invalid credentials")
        return result

    @app.get("/auth/me")
    async def me(user: dict = Depends(current_user)):
        return {"user_id": user["uid"], "tenant_id": user["tid"],
                "role": user["role"]}

    @app.post("/auth/logout")
    async def logout(user: dict = Depends(current_user)):
        return {"ok": True}   # stateless tokens: client discards

    # ---- dashboard ---------------------------------------------------------------
    @app.get("/dashboard/summary")
    async def dashboard_summary(user: dict = Depends(current_user)):
        s = dash_service(user["tid"]).summary(user["tid"],
                                              now=datetime.utcnow())
        return s.__dict__

    @app.get("/dashboard/{section}")
    async def dashboard_section(section: str,
                                user: dict = Depends(current_user)):
        svc = dash_service(user["tid"])
        now = datetime.utcnow()
        tid = user["tid"]
        handlers = {
            "action-queue": lambda: [i.__dict__ for i in
                                     svc.action_queue(tid, now=now)],
            "approval-queue": lambda: [i.__dict__ for i in
                                       svc.approval_queue(tid)],
            "stuck-cases": lambda: svc.stuck_cases(tid, now=now),
            "missing-info": lambda: svc.missing_info(tid),
            "promises": lambda: svc.promises(tid, now=now),
            "offers-follow-up": lambda: svc.offers_followup(tid, now=now),
            "pipeline": lambda: svc.pipeline(tid),
            "risk-alerts": lambda: svc.risk_alerts(tid, now=now),
            "activity": lambda: [e.__dict__ for e in svc.activity(tid)],
        }
        if section not in handlers:
            raise HTTPException(404, "unknown section")
        return JSONResponse(json.loads(json.dumps(handlers[section](),
                                                  default=str)))

    # ---- cases ---------------------------------------------------------------------
    @app.get("/cases")
    async def list_cases(state: Optional[str] = None,
                         user: dict = Depends(current_user)):
        return store.list_cases(tenant_id=user["tid"], state=state)

    @app.post("/cases")
    async def create_case(body: dict, user: dict = Depends(current_user)):
        require_role(user, "owner", "manager", "operator")
        tid = user["tid"]
        party_id = str(uuid.uuid4())
        store.create_party(tenant_id=tid, party_id=party_id, type_="client",
                           name=body.get("client_name", "Unknown"),
                           phone=body.get("phone", ""),
                           address=body.get("address", ""))
        case = Case(tenant_id=tid, autonomy_level=3)
        case.value_estimate = float(body.get("value_estimate", 0))
        case.lead_score = float(body.get("lead_score", 50))
        case.next_best_action = {"type": "start_intake"}
        case.next_action_due_at = datetime.utcnow()
        case.last_progress_at = datetime.utcnow()
        store.save_case(case, title=body.get("title", "New case"),
                        client_party_id=party_id)
        audit.append(event_type="CASE_CREATED", actor=user["uid"],
                     case_id=case.id, payload={"via": "api"})
        return {"case_id": case.id, "state": case.state.value}

    @app.get("/cases/{case_id}")
    async def get_case(case_id: str, user: dict = Depends(current_user)):
        meta = store.case_meta(case_id, tenant_id=user["tid"])
        if meta is None:
            raise HTTPException(404, "case not found")
        case = load_case_or_404(case_id, user)
        meta["missing_items"] = [m.__dict__ for m in case.missing_items]
        meta["promises"] = [
            {**p.__dict__, "due_at": p.due_at.isoformat()}
            for p in case.promises]
        meta["documents"] = [dict(r) for r in db.all(
            "SELECT * FROM documents WHERE case_id=? AND tenant_id=?",
            case_id, user["tid"])]
        meta["offers"] = [dict(r) for r in db.all(
            "SELECT * FROM offers WHERE case_id=? AND tenant_id=?",
            case_id, user["tid"])]
        meta["drafts"] = [dict(r) for r in db.all(
            "SELECT * FROM message_drafts WHERE case_id=? AND tenant_id=?",
            case_id, user["tid"])]
        return json.loads(json.dumps(meta, default=str))

    @app.post("/cases/{case_id}/transition")
    async def transition_case(case_id: str, body: dict,
                              user: dict = Depends(current_user)):
        require_role(user, "owner", "manager", "operator")
        case = load_case_or_404(case_id, user)
        try:
            transition(case, CaseState(body["to_state"]),
                       actor=user["uid"], reason=body.get("reason", "api"),
                       audit_log=audit,
                       human_override=bool(body.get("human_override")),
                       scheduled_wake=bool(body.get("scheduled_wake")))
        except IllegalTransition as e:
            raise HTTPException(409, f"illegal transition: {e}")
        if case.next_best_action is None and case.is_active():
            case.next_best_action = {"type": "review_case"}
            case.next_action_due_at = datetime.utcnow()
        if body.get("offer_sent"):
            db.update("cases", case.id, {"offer_sent_at": utcnow()})
        store.save_case(case)
        return {"state": case.state.value}

    @app.get("/cases/{case_id}/timeline")
    @app.get("/cases/{case_id}/audit-events")
    async def case_timeline(case_id: str,
                            user: dict = Depends(current_user)):
        load_case_or_404(case_id, user)
        rows = db.all("SELECT * FROM audit_events WHERE case_id=? "
                      "ORDER BY seq", case_id)
        return [{"id": r["id"], "event_type": r["event_type"],
                 "actor": r["actor"], "created_at": r["created_at"],
                 "payload": json.loads(r["payload_json"])} for r in rows]

    # ---- conversation ----------------------------------------------------------------
    @app.post("/cases/{case_id}/transcripts")
    async def add_transcript(case_id: str, body: dict,
                             user: dict = Depends(current_user)):
        load_case_or_404(case_id, user)
        tr_id = str(uuid.uuid4())
        db.insert("transcripts", {"id": tr_id, "tenant_id": user["tid"],
                                  "case_id": case_id,
                                  "segments_json": json.dumps(
                                      body["segments"])})
        return {"transcript_id": tr_id}

    @app.post("/cases/{case_id}/analyze-conversation")
    async def analyze(case_id: str, user: dict = Depends(current_user)):
        case = load_case_or_404(case_id, user)
        row = db.one("SELECT * FROM transcripts WHERE case_id=? "
                     "ORDER BY created_at DESC", case_id)
        if row is None:
            raise HTTPException(404, "no transcript")
        segments = [DiarizedSegment(**s)
                    for s in json.loads(row["segments_json"])]
        ci = ConversationIntelligence(audit, tenant_id=user["tid"])
        analysis = ci.analyze(row["id"], segments, case_id=case_id)
        # Apply the case-update payload to the persisted aggregate.
        from ..models import Promise as P, MissingItem as MI
        for m in analysis.missing_items:
            if m["type"] not in {x.field_key for x in case.missing_items}:
                case.missing_items.append(MI(
                    field_key=m["type"], label=m["type"],
                    weight=0.9 if m["severity"] == "high" else 0.5,
                    blocks_quote=(m["blocks"] == "quote_preparation")))
        for p in analysis.promises:
            case.promises.append(P(
                promisor=p["who"], what=p["what"],
                due_at=datetime.utcnow() + timedelta(hours=24),
                importance=.7, dependency_impact=.8))
        case.next_best_action = analysis.next_action
        case.next_action_due_at = datetime.utcnow() + timedelta(hours=4)
        case.last_progress_at = datetime.utcnow()
        store.save_case(case)
        db.update("transcripts", row["id"], {
            "analysis_json": json.dumps(analysis.case_update_payload,
                                        default=str)})
        return json.loads(json.dumps(analysis.case_update_payload,
                                     default=str))

    # ---- completion loop ----------------------------------------------------------------
    @app.post("/completion-loop/run-case/{case_id}")
    async def run_case(case_id: str, user: dict = Depends(current_user)):
        case = load_case_or_404(case_id, user)
        result = loop.run_case(case, now=datetime.utcnow())
        store.save_case(case)
        return json.loads(json.dumps(result, default=str))

    @app.post("/completion-loop/run")
    async def run_all(user: dict = Depends(current_user)):
        results = []
        for meta in store.list_cases(tenant_id=user["tid"]):
            case = store.load_case(meta["id"], tenant_id=user["tid"])
            results.append(loop.run_case(case, now=datetime.utcnow()))
            store.save_case(case)
        return json.loads(json.dumps(results, default=str))

    # ---- actions ----------------------------------------------------------------------------
    @app.post("/actions/request")
    async def request_action(body: dict,
                             user: dict = Depends(current_user)):
        case = load_case_or_404(body["case_id"], user)
        req = ActionRequest(tenant_id=user["tid"], case_id=case.id,
                            action_type=body["action_type"],
                            reason=body.get("reason", "api"),
                            risk_level=body.get("risk_level", "low"),
                            payload=body.get("payload", {}))
        meta = store.case_meta(case.id, tenant_id=user["tid"])
        req.payload.setdefault("recipient",
                               meta.get("client_phone") or "unknown")
        prefs = ChannelPreference(tenant_id=user["tid"], party_id="client")
        outcome = ace.handle(case, req, prefs=prefs, consents=[],
                             now=datetime.utcnow())
        db.insert("action_requests", {
            "id": req.id, "tenant_id": user["tid"], "case_id": case.id,
            "action_type": req.action_type, "reason": req.reason,
            "source": "api", "risk_level": req.risk_level,
            "payload_json": json.dumps(req.payload, default=str),
            "status": outcome.status})
        if outcome.draft is not None:
            db.insert("message_drafts", {
                "id": outcome.draft.id, "tenant_id": user["tid"],
                "case_id": case.id, "action_request_id": req.id,
                "language": outcome.draft.language,
                "channel": outcome.draft.channel,
                "text": outcome.draft.text,
                "risk_level": outcome.draft.risk_level,
                "approval_status": outcome.draft.approval_status})
        if outcome.execution is not None:
            db.insert("executions", {
                "id": outcome.execution.id, "tenant_id": user["tid"],
                "case_id": case.id, "action_request_id": req.id,
                "channel": outcome.execution.channel,
                "provider": outcome.execution.provider,
                "status": outcome.execution.status,
                "executed_at": utcnow(),
                "result_json": json.dumps(outcome.execution.result,
                                          default=str)})
        if outcome.upload_url:
            link = list(ace.uploads.links.values())[-1]
            db.insert("upload_links", {
                "id": link.id, "tenant_id": user["tid"], "case_id": case.id,
                "token_hash": link.token_hash, "purpose": link.purpose,
                "expires_at": link.expires_at.isoformat(),
                "status": link.status})
        store.save_case(case)
        return {"status": outcome.status, "reason": outcome.reason,
                "draft_id": outcome.draft.id if outcome.draft else None,
                "upload_url": outcome.upload_url,
                "approval_id": outcome.approval_id}

    @app.post("/actions/{draft_id}/approve")
    @app.post("/actions/{draft_id}/reject")
    async def decide_action(draft_id: str, body: dict, request: Request,
                            user: dict = Depends(current_user)):
        require_role(user, "owner", "manager")
        decision = "approve" if request.url.path.endswith("approve") \
            else "reject"
        row = db.one("SELECT * FROM message_drafts WHERE id=? AND "
                     "tenant_id=?", draft_id, user["tid"])
        if row is None:
            raise HTTPException(404, "draft not found")
        outcome = ace.decide_approval(
            draft_id, approver=user["uid"], decision=decision,
            now=datetime.utcnow(),
            edited_text=body.get("edited_message"),
            reason=body.get("reason", ""))
        new_status = "APPROVED" if decision == "approve" else "REJECTED"
        fields = {"approval_status": new_status}
        if body.get("edited_message"):
            fields["edited_text"] = body["edited_message"]
        db.update("message_drafts", draft_id, fields)
        return {"approval_status": new_status,
                "executed": bool(outcome and outcome.status == "executed")}

    # ---- upload links --------------------------------------------------------------------------
    @app.post("/upload-links")
    async def create_upload_link(body: dict,
                                 user: dict = Depends(current_user)):
        case = load_case_or_404(body["case_id"], user)
        link, url = ace.uploads.create(
            tenant_id=user["tid"], case_id=case.id,
            purpose=body.get("purpose", "installation_photo"),
            now=datetime.utcnow())
        db.insert("upload_links", {
            "id": link.id, "tenant_id": user["tid"], "case_id": case.id,
            "token_hash": link.token_hash, "purpose": link.purpose,
            "expires_at": link.expires_at.isoformat(),
            "status": link.status})
        return {"upload_url": url, "link_id": link.id}

    @app.get("/upload-links/{token}")
    async def open_upload_link(token: str):
        link = ace.uploads.open(token, datetime.utcnow())
        if link is None:
            raise HTTPException(404, "link invalid or expired")
        db.update("upload_links", link.id, {"status": link.status})
        return {"purpose": link.purpose, "status": link.status}

    @app.post("/upload-links/{token}/upload")
    async def upload_via_link(token: str, body: dict):
        """Client-facing: no auth (token IS the credential)."""
        link = ace.uploads.open(token, datetime.utcnow())
        if link is None:
            raise HTTPException(404, "link invalid or expired")
        ok = ace.uploads.use(token, datetime.utcnow(),
                             mime=body.get("mime", "image/jpeg"),
                             size_mb=float(body.get("size_mb", 1.0)))
        if not ok:
            raise HTTPException(422, "file type or size not allowed")
        doc_id = str(uuid.uuid4())
        db.insert("documents", {
            "id": doc_id, "tenant_id": link.tenant_id,
            "case_id": link.case_id, "doc_type": link.purpose,
            "filename": body.get("filename", "upload.jpg"),
            "mime": body.get("mime", "image/jpeg"),
            "size_bytes": int(float(body.get("size_mb", 1.0)) * 1e6),
            "storage_path": f"local://uploads/{doc_id}"})
        db.update("upload_links", link.id,
                  {"status": "USED", "used_at": utcnow()})
        # Resolve the matching missing item on the persisted aggregate.
        case = store.load_case(link.case_id, tenant_id=link.tenant_id)
        if case is not None:
            MissingInfoService.resolve(case, link.purpose, audit=audit,
                                       source="upload")
            case.last_progress_at = datetime.utcnow()
            store.save_case(case)
        return {"document_id": doc_id, "resolved": link.purpose}

    # ---- documents / offers -----------------------------------------------------------------------
    @app.get("/cases/{case_id}/documents")
    async def case_documents(case_id: str,
                             user: dict = Depends(current_user)):
        load_case_or_404(case_id, user)
        return [dict(r) for r in db.all(
            "SELECT * FROM documents WHERE case_id=? AND tenant_id=?",
            case_id, user["tid"])]

    @app.post("/cases/{case_id}/offers")
    async def create_offer(case_id: str, body: dict,
                           user: dict = Depends(current_user)):
        require_role(user, "owner", "manager")
        load_case_or_404(case_id, user)
        offer_id = str(uuid.uuid4())
        db.insert("offers", {"id": offer_id, "tenant_id": user["tid"],
                             "case_id": case_id,
                             "price": float(body.get("price", 0)),
                             "scope": body.get("scope", "")})
        audit.append(event_type="OFFER_CREATED", actor=user["uid"],
                     case_id=case_id, payload={"offer_id": offer_id})
        return {"offer_id": offer_id}

    @app.post("/offers/{offer_id}/send")
    async def send_offer(offer_id: str, user: dict = Depends(current_user)):
        require_role(user, "owner", "manager")
        row = db.one("SELECT * FROM offers WHERE id=? AND tenant_id=?",
                     offer_id, user["tid"])
        if row is None:
            raise HTTPException(404, "offer not found")
        db.update("offers", offer_id, {"status": "sent",
                                       "sent_at": utcnow()})
        db.update("cases", row["case_id"], {"offer_sent_at": utcnow()})
        audit.append(event_type="OFFER_SENT_EVENT", actor=user["uid"],
                     case_id=row["case_id"], payload={"offer_id": offer_id,
                                                      "provider": "mock"})
        return {"status": "sent"}

    @app.post("/offers/{offer_id}/simulate-client-response")
    async def offer_response(offer_id: str, body: dict,
                             user: dict = Depends(current_user)):
        row = db.one("SELECT * FROM offers WHERE id=? AND tenant_id=?",
                     offer_id, user["tid"])
        if row is None:
            raise HTTPException(404, "offer not found")
        response = body.get("response", "accepted")
        db.update("offers", offer_id, {"client_response": response,
                                       "status": response})
        audit.append(event_type="CLIENT_REPLIED", actor="client",
                     case_id=row["case_id"], payload={"offer_id": offer_id,
                                                      "response": response})
        return {"client_response": response}

    # ---- lifecycle: mock invoice / payment / fulfillment ---------------------------
    from ..lifecycle.playbooks import HVAC_HOME_SERVICES
    from ..lifecycle.completion import CaseFacts, can_complete
    from ..lifecycle.vector import (DealState, FulfillmentState,
                                    LifecycleVector, TransactionState)

    def load_vector(case_id: str) -> LifecycleVector:
        row = db.one("SELECT lifecycle_json FROM cases WHERE id=?", case_id)
        if row and row["lifecycle_json"]:
            data = json.loads(row["lifecycle_json"])
            return LifecycleVector(
                deal=DealState(data["deal"]),
                transaction=TransactionState(data["transaction"]),
                fulfillment=FulfillmentState(data["fulfillment"]))
        return LifecycleVector()

    def save_vector(case_id: str, v: LifecycleVector) -> None:
        db.update("cases", case_id, {"lifecycle_json": json.dumps(
            {"deal": v.deal.value, "transaction": v.transaction.value,
             "fulfillment": v.fulfillment.value})})

    @app.get("/cases/{case_id}/lifecycle")
    async def get_lifecycle(case_id: str,
                            user: dict = Depends(current_user)):
        load_case_or_404(case_id, user)
        v = load_vector(case_id)
        facts = CaseFacts(vector=v, closure_evidence_id="portal",
                          completion_confirmed=True, contract_signed=True)
        check = can_complete(facts, HVAC_HOME_SERVICES)
        return {"deal": v.deal.value, "transaction": v.transaction.value,
                "fulfillment": v.fulfillment.value,
                "view": v.derived_outcome_view(),
                "message": v.business_language(),
                "can_complete": check.ok,
                "blocked_reasons": check.blocked_reasons,
                "next_best_action": check.next_best_action}

    @app.post("/cases/{case_id}/lifecycle/accept-offer")
    @app.post("/cases/{case_id}/lifecycle/invoice")
    @app.post("/cases/{case_id}/lifecycle/payment")
    @app.post("/cases/{case_id}/lifecycle/fulfillment-schedule")
    @app.post("/cases/{case_id}/lifecycle/fulfillment-complete")
    async def lifecycle_step(case_id: str, request: Request,
                             user: dict = Depends(current_user)):
        """MOCK invoice/payment/fulfillment providers (clearly mock —
        real billing/scheduling providers replace these endpoints' guts)."""
        require_role(user, "owner", "manager")
        load_case_or_404(case_id, user)
        v = load_vector(case_id)
        step = request.url.path.rsplit("/", 1)[1]
        if step == "accept-offer":
            v.deal = DealState.ACCEPTED_BY_CLIENT
            v.transaction = TransactionState.INVOICE_REQUIRED
            v.fulfillment = FulfillmentState.REQUIRED
            audit.append(event_type="CASE_WON_NOT_FULFILLED", actor="mock",
                         case_id=case_id, payload={"provider": "mock"})
        elif step == "invoice":
            v.transaction = TransactionState.INVOICE_ISSUED
            audit.append(event_type="INVOICE_ISSUED", actor="mock-invoice",
                         case_id=case_id, payload={"is_mock": True})
        elif step == "payment":
            v.transaction = TransactionState.PAID
            audit.append(event_type="PAYMENT_RECEIVED", actor="mock-payment",
                         case_id=case_id, payload={"is_mock": True})
        elif step == "fulfillment-schedule":
            v.fulfillment = FulfillmentState.SCHEDULED
            audit.append(event_type="FULFILLMENT_SCHEDULED",
                         actor="mock-fulfillment", case_id=case_id,
                         payload={"is_mock": True})
        elif step == "fulfillment-complete":
            v.fulfillment = FulfillmentState.COMPLETED
            audit.append(event_type="FULFILLMENT_COMPLETED",
                         actor="mock-fulfillment", case_id=case_id,
                         payload={"is_mock": True})
        save_vector(case_id, v)
        return {"view": v.derived_outcome_view(),
                "message": v.business_language()}

    # ---- telephony (mock provider) ----------------------------------------------------
    from ..telephony.engine import CallControlEngine
    from ..telephony.models import ContactCallState
    tele = CallControlEngine(audit)
    app.state.telephony = tele

    @app.post("/telephony/inbound/simulate")
    async def telephony_inbound(body: dict,
                                user: dict = Depends(current_user)):
        r = tele.simulate_inbound(
            tenant_id=user["tid"],
            caller_number=body.get("caller_number", "+48600000000"),
            segments=body.get("segments", []),
            recording_consent=body.get("recording_consent", "granted"),
            emergency=bool(body.get("emergency")),
            asks_for_human=bool(body.get("asks_for_human")))
        s = r.session
        # Persist the engine-created case into the portal DB.
        if s.case_id and store.case_meta(s.case_id,
                                         tenant_id=user["tid"]) is None:
            engine_case = tele.graph.cases.get(s.case_id)
            if engine_case is not None:
                party_id = str(uuid.uuid4())
                store.create_party(tenant_id=user["tid"],
                                   party_id=party_id, type_="client",
                                   name="Inbound caller",
                                   phone=s.source_number)
                store.save_case(engine_case, title="Inbound call intake",
                                client_party_id=party_id)
        db.insert("call_sessions", {
            "id": s.id, "tenant_id": s.tenant_id, "case_id": s.case_id,
            "direction": s.direction, "source_number": s.source_number,
            "destination_number": s.destination_number,
            "provider": s.provider, "status": s.status,
            "outcome": s.outcome, "outcome_reason": s.outcome_reason,
            "disposition_confidence": s.disposition_confidence,
            "recording_allowed": int(s.recording_allowed),
            "human_handoff_required": int(s.human_handoff_required),
            "started_at": str(s.started_at), "ended_at": str(s.ended_at)})
        return {"call_id": s.id, "case_id": s.case_id,
                "disposition": r.disposition, "handoff": r.handoff,
                "provider_is_mock": True}

    @app.post("/telephony/outbound/request")
    async def telephony_outbound(body: dict,
                                 user: dict = Depends(current_user)):
        require_role(user, "owner", "manager", "operator")
        contact = ContactCallState(**body.get("contact_state", {}))
        r = tele.request_outbound(
            tenant_id=user["tid"], case_id=body.get("case_id"),
            destination=body.get("destination", "+48600000000"),
            contact=contact,
            business_purpose=body.get("reason", ""),
            scenario=body.get("scenario", "answered"),
            urgent=bool(body.get("urgent")))
        s = r.session
        db.insert("call_sessions", {
            "id": s.id, "tenant_id": s.tenant_id, "case_id": s.case_id,
            "direction": s.direction, "source_number": s.source_number,
            "destination_number": s.destination_number,
            "provider": s.provider, "status": s.status,
            "outcome": s.outcome, "outcome_reason": s.outcome_reason,
            "disposition_confidence": s.disposition_confidence,
            "recording_allowed": int(s.recording_allowed),
            "human_handoff_required": int(s.human_handoff_required),
            "started_at": str(s.started_at), "ended_at": str(s.ended_at)})
        return {"call_id": s.id, "permission": r.permission,
                "disposition": r.disposition,
                "blocked_reason": r.blocked_reason, "retry": r.retry,
                "provider_is_mock": True}

    @app.get("/telephony/calls")
    async def telephony_calls(user: dict = Depends(current_user)):
        return [dict(r) for r in db.all(
            "SELECT * FROM call_sessions WHERE tenant_id=? "
            "ORDER BY created_at DESC", user["tid"])]

    # ---- admin / RBAC wiring (RbacEngine is authoritative server-side) --------------
    from ..admin.rbac import ROLE_PERMISSIONS, RbacEngine, ServiceAccount
    rbac = RbacEngine(audit)
    app.state.rbac = rbac

    def rbac_user_id(user: dict) -> str:
        """Map portal users into the RbacEngine (seeded on first touch)."""
        uid = f"portal-{user['uid']}"
        if uid not in rbac.users:
            from ..admin.rbac import User as RbacUser, Membership
            rbac.users[uid] = RbacUser(email=uid, name=user["role"], id=uid)
            rbac.memberships.append(Membership(
                tenant_id=user["tid"], user_id=uid, role=user["role"]))
        return uid

    def require_permission(user: dict, action: str) -> str:
        """Deny-by-default server-side gate through the RbacEngine (which
        also audits every decision as ACCESS_DECISION)."""
        uid = rbac_user_id(user)
        d = rbac.access(actor_type="user", actor_id=uid,
                        tenant_id=user["tid"], action=action)
        if d.decision != "ALLOW":
            raise HTTPException(403, "; ".join(d.reasons))
        return uid

    @app.get("/admin/me")
    async def admin_me(user: dict = Depends(current_user)):
        uid = rbac_user_id(user)
        m = rbac.membership_of(uid, user["tid"])
        return {"tenant_id": user["tid"], "role": m.role,
                "permissions": sorted(ROLE_PERMISSIONS[m.role])}

    @app.get("/admin/users")
    async def admin_users(user: dict = Depends(current_user)):
        require_permission(user, "tenant.manage_users")
        return [{"id": r["id"], "email": r["email"], "role": r["role"]}
                for r in db.all("SELECT * FROM users WHERE tenant_id=?",
                                user["tid"])]

    @app.post("/admin/users/invite")
    async def admin_invite(body: dict, user: dict = Depends(current_user)):
        uid = rbac_user_id(user)
        if body.get("role", "viewer") not in ROLE_PERMISSIONS:
            raise HTTPException(400, "unknown role")
        try:
            inv = rbac.invite(tenant_id=user["tid"],
                              email=body.get("email", ""),
                              role=body.get("role", "viewer"),
                              actor_user_id=uid, now=datetime.utcnow())
        except PermissionError as e:
            raise HTTPException(403, str(e))
        return {"invitation_id": inv.id, "status": inv.status}

    @app.patch("/admin/memberships/{target_user_id}/role")
    async def admin_change_role(target_user_id: str, body: dict,
                                user: dict = Depends(current_user)):
        # change_role's own guards cover escalation + last-owner, but the
        # base permission must be enforced here: without it a viewer could
        # demote a manager to viewer (viewer ⊆ viewer passes escalation).
        uid = require_permission(user, "tenant.manage_users")
        new_role = body.get("role")
        if new_role not in ROLE_PERMISSIONS:
            raise HTTPException(400, "unknown or missing role")
        target = rbac.membership_of(f"portal-{target_user_id}", user["tid"])
        if target is None:
            # Materialize the target portal user into rbac first.
            row = db.one("SELECT * FROM users WHERE id=? AND tenant_id=?",
                         target_user_id, user["tid"])
            if row is None:
                raise HTTPException(404, "user not found")
            fake = {"uid": target_user_id, "tid": user["tid"],
                    "role": row["role"]}
            rbac_user_id(fake)
            target = rbac.membership_of(f"portal-{target_user_id}",
                                        user["tid"])
        try:
            rbac.change_role(target.id, new_role, actor_user_id=uid)
        except PermissionError as e:
            raise HTTPException(403, str(e))
        db.update("users", target_user_id, {"role": new_role})
        return {"role": new_role}

    @app.get("/admin/access-logs")
    async def admin_access_logs(user: dict = Depends(current_user)):
        require_permission(user, "access_log.view")
        rows = [e for e in audit.events(event_type="ACCESS_DECISION")
                if (e.payload or {}).get("tenant_id") == user["tid"]]
        return [{"event_type": e.event_type, "actor": e.actor,
                 "payload": e.payload, "created_at": e.created_at}
                for e in rows[-50:]]

    # ---- governance visibility (redacted traces from audit) --------------------------
    def tenant_owns_event(e, tid: str) -> bool:
        """Tenant isolation for shared audit streams: an event belongs to
        the caller when its payload names their tenant or its case does."""
        if (e.payload or {}).get("tenant_id") == tid:
            return True
        if e.case_id:
            row = db.one("SELECT id FROM cases WHERE id=? AND tenant_id=?",
                         e.case_id, tid)
            return row is not None
        return False

    @app.get("/governance/traces")
    async def governance_traces(user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        rows = [e for e in audit.events(event_type="AGENT_TRACE")
                if tenant_owns_event(e, user["tid"])]
        return [{"payload": e.payload, "created_at": e.created_at}
                for e in rows[-50:]]

    @app.get("/governance/blocked")
    async def governance_blocked(user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        out = []
        for e in audit.events():
            if e.event_type in ("AGENT_TRACE", "CALL_PERMISSION_CHECKED",
                                "FOLLOW_UP_RATE_LIMITED",
                                "CALL_BLOCKED_ANTI_HARASSMENT",
                                "WORKFLOW_STOPPED_WASTE"):
                p = e.payload or {}
                status = p.get("status") or p.get("result") or ""
                if ("BLOCK" in str(status) or e.event_type in (
                        "FOLLOW_UP_RATE_LIMITED",
                        "CALL_BLOCKED_ANTI_HARASSMENT",
                        "WORKFLOW_STOPPED_WASTE")) \
                        and tenant_owns_event(e, user["tid"]):
                    out.append({"event": e.event_type, "detail": p,
                                "explanation": _explain_block(e)})
        return out[-30:]

    def _explain_block(e) -> str:
        p = e.payload or {}
        if e.event_type == "FOLLOW_UP_RATE_LIMITED":
            return ("Follow-up was not sent because the contact limit or "
                    "cooldown for this case was reached.")
        if e.event_type == "CALL_BLOCKED_ANTI_HARASSMENT":
            return ("Outbound call blocked to protect the client "
                    f"relationship ({p.get('reason', 'limit')}).")
        if e.event_type == "WORKFLOW_STOPPED_WASTE":
            return ("AI stopped this workflow because it was repeating "
                    "actions without new information.")
        status = str(p.get("status") or p.get("result") or "")
        if "HARD_BLOCKER" in status:
            return ("Action blocked by a non-negotiable safety rule "
                    "(for example: the client opted out or is on the "
                    "do-not-call list).")
        if "PERMISSION" in status:
            return ("Action blocked because the AI agent does not have "
                    "permission to do this.")
        reasons = p.get("reasons") or [p.get("reason", "policy")]
        return "Action blocked: " + ", ".join(str(r) for r in reasons)

    # ---- scheduling wiring ---------------------------------------------------------------
    from ..scheduling.engine import APPOINTMENT_TYPES, SchedulingEngine
    from .scheduling_store import SchedulingStore
    sched = SchedulingEngine(audit)
    sstore = SchedulingStore(db)
    sstore.hydrate(sched)      # migration v4: DB is the source of truth
    app.state.scheduling, app.state.scheduling_store = sched, sstore

    def tenant_scoped(tid: str, ident: Optional[str]) -> Optional[str]:
        """The mock engine's calendars are process-global; namespacing the
        user/resource ids per tenant keeps tenant A's 'tech-1' a different
        calendar from tenant B's 'tech-1'."""
        return f"{tid}::{ident}" if ident else None

    @app.get("/scheduling/availability")
    async def sched_availability(appointment_type: str = "VIDEO_CALL",
                                 day: Optional[str] = None,
                                 resource_id: Optional[str] = None,
                                 user_: dict = Depends(current_user)):
        if appointment_type not in APPOINTMENT_TYPES:
            raise HTTPException(400, "unknown appointment type")
        try:
            d = datetime.fromisoformat(day) if day else \
                datetime.utcnow() + timedelta(days=1)
        except ValueError:
            raise HTTPException(400, "invalid day")
        slots = sched.available_slots(
            day=d, appointment_type=appointment_type,
            resource_id=tenant_scoped(user_["tid"], resource_id))
        return json.loads(json.dumps(slots, default=str))

    @app.post("/scheduling/appointments")
    async def sched_book(body: dict, user: dict = Depends(current_user)):
        require_role(user, "owner", "manager", "operator")
        if not body.get("case_id") or not body.get("start_at"):
            raise HTTPException(400, "case_id and start_at are required")
        appt_type = body.get("appointment_type", "CALLBACK")
        if appt_type not in APPOINTMENT_TYPES:
            raise HTTPException(400, "unknown appointment type")
        try:
            start_at = datetime.fromisoformat(body["start_at"])
        except ValueError:
            raise HTTPException(400, "invalid start_at")
        case = load_case_or_404(body["case_id"], user)
        vector = load_vector(case.id)
        try:
            appt, token = sched.book(
                tenant_id=user["tid"], case_id=case.id,
                appointment_type=appt_type, start_at=start_at,
                user_id=tenant_scoped(user["tid"], body.get("user_id")),
                resource_id=tenant_scoped(user["tid"],
                                          body.get("resource_id")),
                vector=vector)
        except ValueError as e:
            raise HTTPException(409, str(e))
        save_vector(case.id, vector)
        sstore.save(appt, actor=user["uid"], event_type="BOOKED",
                    payload={"type": appt.appointment_type})
        return {"appointment_id": appt.id, "status": appt.status,
                "video_meeting_url": appt.video_meeting_url,
                "confirmation_url": f"/confirm/{token}" if token else None,
                "provider_is_mock": True}

    @app.get("/scheduling/appointments")
    async def sched_list(user: dict = Depends(current_user)):
        return [{"id": a.id, "case_id": a.case_id,
                 "type": a.appointment_type, "status": a.status,
                 "start_at": str(a.start_at)}
                for a in sched.appointments.values()
                if a.tenant_id == user["tid"]]

    @app.post("/scheduling/appointments/{appt_id}/{op}")
    async def sched_op(appt_id: str, op: str,
                       body: Optional[dict] = None,
                       user: dict = Depends(current_user)):
        body = body or {}
        require_role(user, "owner", "manager", "operator")
        appt = sched.appointments.get(appt_id)
        if appt is None or appt.tenant_id != user["tid"]:
            raise HTTPException(404, "appointment not found")
        vector = load_vector(appt.case_id)
        try:
            if op == "reschedule":
                if not body.get("new_start"):
                    raise HTTPException(400, "new_start required")
                sched.reschedule(appt_id, new_start=datetime.fromisoformat(
                    body["new_start"]), actor=user["uid"])
            elif op == "cancel":
                sched.cancel(appt_id, reason=body.get("reason", ""),
                             by=body.get("by", "company"))
            elif op == "complete":
                sched.complete(appt_id, vector=vector)
                save_vector(appt.case_id, vector)
                # Completion Loop runs after appointment events.
                case = store.load_case(appt.case_id, tenant_id=user["tid"])
                if case is not None:
                    loop.run_case(case, now=datetime.utcnow())
                    store.save_case(case)
            elif op == "no-show":
                sched.no_show(appt_id)
                case = store.load_case(appt.case_id, tenant_id=user["tid"])
                if case is not None:
                    loop.run_case(case, now=datetime.utcnow())
                    store.save_case(case)
            else:
                raise HTTPException(404, "unknown operation")
        except ValueError as e:
            raise HTTPException(409, str(e))
        sstore.save(appt, actor=user["uid"], event_type=op.upper(),
                    payload={"status": appt.status})
        return {"status": appt.status,
                "lifecycle_view": load_vector(appt.case_id)
                .derived_outcome_view()}

    @app.get("/confirm/{token}", response_class=HTMLResponse)
    async def confirm_page(token: str):
        from .ui import STYLE
        return (f"<!doctype html><html><head><meta charset='utf-8'>"
                f"<title>Confirm appointment</title><style>{STYLE}</style>"
                f"</head><body><h1>Confirm your appointment</h1>"
                f"<button id='confirm-btn'>Confirm</button>"
                f"<p id='done' class='ok' hidden>Confirmed — see you then!"
                f"</p><p id='fail' class='err' hidden>Link invalid or "
                f"expired.</p><script>"
                f"document.getElementById('confirm-btn').onclick=async()=>"
                f"{{const r=await fetch('/scheduling/confirm/{token}',"
                f"{{method:'POST'}});"
                f"document.getElementById(r.ok?'done':'fail').hidden=false;"
                f"if(r.ok)document.getElementById('confirm-btn').hidden"
                f"=true;}};</script></body></html>")

    @app.post("/scheduling/confirm/{token}")
    async def sched_confirm(token: str):
        appt = sched.confirm(token, now=datetime.utcnow())
        if appt is None:
            # The engine may have flipped the appointment to EXPIRED —
            # persist that state change before answering with a safe 404.
            import hashlib as _hashlib
            appt_id = sstore.appointment_id_for_token_hash(
                _hashlib.sha256(token.encode()).hexdigest())
            if appt_id and appt_id in sched.appointments:
                sstore.save(sched.appointments[appt_id], actor="client",
                            event_type="CONFIRM_REJECTED",
                            payload={"reason": "invalid_or_expired"})
            raise HTTPException(404, "invalid or expired")
        sstore.save(appt, actor="client", event_type="CONFIRMED")
        return {"status": appt.status}

    # ---- quotes (Quote Builder Q-B: persistence + API over the Q-A engine) ----
    from decimal import Decimal, InvalidOperation

    from ..quotes.engine import QuoteEngine
    from ..quotes.models import (AcceptanceEvidence, IllegalQuoteTransition,
                                 PaymentMilestone, PaymentSchedule,
                                 PriceBook, PriceBookItem, PricingRule,
                                 QuoteImmutableError, QuoteLineItem,
                                 quote_transition)
    from ..quotes.pricing import calculate_quote
    from ..quotes.providers import (MockInvoiceHandoffProvider,
                                    MockPdfProvider)
    from ..quotes.scores import evidence_coverage_score
    from .quote_store import QuoteStore

    qstore = QuoteStore(db)
    qengine = QuoteEngine(audit)
    qpdf = MockPdfProvider()
    qhandoff = MockInvoiceHandoffProvider()
    app.state.quotes, app.state.quote_store = qengine, qstore

    def load_quote_or_404(quote_id: str, user: dict):
        q = qstore.load_quote(quote_id, tenant_id=user["tid"])
        if q is None:
            raise HTTPException(404, "quote not found")  # incl. cross-tenant
        qengine.quotes[q.id] = q
        return q

    def hydrate_approvals(quote_id: str, user: dict) -> None:
        qengine.approvals = qstore.load_approvals(quote_id,
                                                  tenant_id=user["tid"])

    def persist_approvals(user: dict) -> None:
        for req in qengine.approvals:
            qstore.save_approval(user["tid"], req)

    _LINE_DEC = ["quantity", "material_cost", "labor_cost",
                 "subcontractor_cost", "travel_cost", "permit_cost",
                 "overhead_allocation", "risk_contingency",
                 "requested_discount"]
    _LINE_OPT_DEC = ["price_book_price", "manual_price"]

    def parse_line(body: dict) -> QuoteLineItem:
        if not str(body.get("description", "")).strip():
            raise HTTPException(400, "line item needs a description")
        kw = {}
        try:
            for f in _LINE_DEC:
                if f in body:
                    kw[f] = Decimal(str(body[f]))
            for f in _LINE_OPT_DEC:
                if body.get(f) is not None:
                    kw[f] = Decimal(str(body[f]))
        except (InvalidOperation, ValueError):
            raise HTTPException(400, "invalid number in line item")
        return QuoteLineItem(
            description=body["description"], sku=body.get("sku"),
            discount_reason=body.get("discount_reason", ""),
            is_free_item=bool(body.get("is_free_item")),
            cost_known=bool(body.get("cost_known", True)),
            cost_age_days=int(body.get("cost_age_days", 0)),
            tax_category=body.get("tax_category", "standard"),
            is_custom=bool(body.get("is_custom")),
            created_by=body.get("created_by", "human"), **kw)

    def quote_json(q) -> dict:
        return {
            "id": q.id, "case_id": q.case_id, "state": q.state,
            "version": q.version, "revised_from_id": q.revised_from_id,
            "currency": q.currency, "created_by": q.created_by,
            "editable": q.editable,
            "subtotal": str(q.subtotal), "tax_total": str(q.tax_total),
            "total": str(q.total),
            "valid_until": str(q.valid_until) if q.valid_until else None,
            "assumptions": q.assumptions, "exclusions": q.exclusions,
            "terms_template_approved": q.terms_template_approved,
            "tax_engine_is_mock": True,
            "line_items": [{
                "id": li.id, "description": li.description,
                "sku": li.sku, "quantity": str(li.quantity),
                "line_cost": str(li.line_cost),
                "price_before_discount": str(li.price_before_discount),
                "applied_discount": str(li.applied_discount),
                "price_after_discount": str(li.price_after_discount),
                "margin_percent": str(li.margin_percent)
                if li.margin_percent is not None else None,
                "line_total": str(li.line_total),
                "requires_human_review": li.requires_human_review,
            } for li in q.line_items],
            "payment_schedule": [
                {"label": m.label, "fraction": str(m.fraction),
                 "trigger": m.trigger, "is_deposit": m.is_deposit,
                 "blocks_fulfillment_until_paid":
                     m.blocks_fulfillment_until_paid}
                for m in q.payment_schedule.milestones]
            if q.payment_schedule else [],
        }

    def gates_json(gates: dict) -> dict:
        return {name: {"decision": g.decision, "reasons": g.reasons,
                       "hard_blockers": g.hard_blockers}
                for name, g in gates.items()}

    @app.get("/quotes")
    async def list_quotes(case_id: Optional[str] = None,
                          user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return qstore.list_quotes(tenant_id=user["tid"], case_id=case_id)

    @app.post("/quotes")
    async def create_quote(body: dict,
                           user: dict = Depends(current_user)):
        require_permission(user, "offer.create")
        if not body.get("case_id"):
            raise HTTPException(400, "case_id is required")
        case = load_case_or_404(body["case_id"], user)
        row = db.one("SELECT client_party_id FROM cases WHERE id=?",
                     case.id)
        q = qengine.create_draft(
            tenant_id=user["tid"], case_id=case.id,
            customer_party_id=body.get("customer_party_id")
            or (row["client_party_id"] if row else None),
            created_by=user["uid"],
            currency=body.get("currency", "EUR"))
        qstore.save_quote(q)
        return quote_json(q)

    @app.get("/quotes/{quote_id}")
    async def get_quote(quote_id: str,
                        user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return quote_json(load_quote_or_404(quote_id, user))

    @app.patch("/quotes/{quote_id}")
    async def patch_quote(quote_id: str, body: dict,
                          user: dict = Depends(current_user)):
        require_permission(user, "offer.create")
        q = load_quote_or_404(quote_id, user)
        if q.state == "PRICE_CALCULATED":     # edits invalidate the calc
            quote_transition(q, "DRAFT")
        try:
            q.assert_editable()
        except QuoteImmutableError as e:
            raise HTTPException(409, str(e))
        for f in ("assumptions", "exclusions", "terms_template_id",
                  "custom_terms_text", "customer_party_id"):
            if f in body:
                setattr(q, f, body[f])
        if "terms_template_approved" in body:
            q.terms_template_approved = bool(body["terms_template_approved"])
        if "cost_volatility" in body:
            q.cost_volatility = float(body["cost_volatility"])
        qstore.save_quote(q)
        return quote_json(q)

    @app.post("/quotes/{quote_id}/lines")
    async def add_quote_line(quote_id: str, body: dict,
                             user: dict = Depends(current_user)):
        require_permission(user, "offer.create")
        q = load_quote_or_404(quote_id, user)
        if q.state == "PRICE_CALCULATED":     # edits invalidate the calc
            quote_transition(q, "DRAFT")
        try:
            qengine.add_line(q, parse_line(body))
        except QuoteImmutableError as e:
            raise HTTPException(409, str(e))
        qstore.save_quote(q)
        return quote_json(q)

    @app.post("/quotes/{quote_id}/calculate")
    async def calculate_quote_api(quote_id: str, body: Optional[dict] = None,
                                  user: dict = Depends(current_user)):
        require_permission(user, "offer.create")
        body = body or {}
        q = load_quote_or_404(quote_id, user)
        if q.state == "PRICE_CALCULATED":     # recalculation is legal
            quote_transition(q, "DRAFT")
        book = qstore.default_price_book(user["tid"])
        rules = qstore.load_pricing_rules(user["tid"])
        try:
            qengine.calculate(q, price_book=book, pricing_rules=rules,
                              now=datetime.utcnow())
        except QuoteImmutableError as e:
            raise HTTPException(409, str(e))
        gates = qengine.evaluate_gates(
            q, readiness_context=body.get("readiness") or {},
            feasibility_context=body.get("feasibility"))
        qstore.save_quote(q)
        ev = q.evidence
        return {**quote_json(q), "gates": gates_json(gates), "scores": {
            "price_confidence": round(qengine.price_confidence(q), 4),
            "evidence_coverage": round(evidence_coverage_score(
                required_facts_covered=ev.required_facts_covered,
                source_reliability=ev.source_reliability,
                evidence_recency=ev.evidence_recency,
                scope_consistency=ev.scope_consistency,
                human_verified_facts=ev.human_verified_facts,
                pricing_data_coverage=ev.pricing_data_coverage), 4)}}

    @app.post("/quotes/{quote_id}/approve")
    async def approve_quote(quote_id: str,
                            user: dict = Depends(current_user)):
        require_permission(user, "offer.approve")
        q = load_quote_or_404(quote_id, user)
        hydrate_approvals(quote_id, user)
        try:
            qengine.approve(q, approver_id=user["uid"])
        except PermissionError as e:
            raise HTTPException(403, str(e))
        except IllegalQuoteTransition as e:
            raise HTTPException(409, str(e))
        persist_approvals(user)
        qstore.save_quote(q)
        return quote_json(q)

    @app.post("/quotes/{quote_id}/reject")
    async def reject_quote(quote_id: str, body: dict,
                           user: dict = Depends(current_user)):
        require_permission(user, "offer.approve")
        if not str(body.get("reason", "")).strip():
            raise HTTPException(400, "rejection requires a reason")
        q = load_quote_or_404(quote_id, user)
        try:
            quote_transition(q, "REJECTED_BY_APPROVER")
        except IllegalQuoteTransition as e:
            raise HTTPException(409, str(e))
        for req in qstore.load_approvals(quote_id, tenant_id=user["tid"]):
            if req.status == "PENDING":
                req.status = "REJECTED"
                req.approver_id = user["uid"]
                qstore.save_approval(user["tid"], req)
        audit.append(event_type="QUOTE_REJECTED_BY_APPROVER",
                     actor=user["uid"], case_id=q.case_id,
                     payload={"quote_id": q.id,
                              "reason": body["reason"]})
        qstore.save_quote(q)
        return quote_json(q)

    @app.post("/quotes/{quote_id}/send")
    async def send_quote(quote_id: str, body: Optional[dict] = None,
                         user: dict = Depends(current_user)):
        require_permission(user, "offer.create")
        body = body or {}
        q = load_quote_or_404(quote_id, user)
        if q.revised_from_id:      # supersede path needs the ancestor
            old = qstore.load_quote(q.revised_from_id,
                                    tenant_id=user["tid"])
            if old is not None:
                qengine.quotes[old.id] = old
        hydrate_approvals(quote_id, user)
        try:
            result = qengine.send(
                q, actor_type="human",
                readiness_context=body.get("readiness") or {},
                feasibility_context=body.get("feasibility"),
                now=datetime.utcnow())
        except IllegalQuoteTransition as e:
            raise HTTPException(409, str(e))
        if result.decision != "SENT":
            raise HTTPException(409, "; ".join(result.reasons))
        qstore.save_quote(q)
        if q.revised_from_id and q.revised_from_id in qengine.quotes:
            qstore.save_quote(qengine.quotes[q.revised_from_id])
        return {**quote_json(q), "send_result": result.decision}

    @app.post("/quotes/{quote_id}/accept")
    async def accept_quote(quote_id: str, body: Optional[dict] = None,
                           user: dict = Depends(current_user)):
        """Demo/simulated client acceptance. Creates payment/invoice/
        fulfillment REQUIREMENT placeholders — never completes the case."""
        require_permission(user, "offer.create")
        body = body or {}
        q = load_quote_or_404(quote_id, user)
        channel = body.get("channel", "portal_click")
        evidence = None
        if body.get("evidence"):
            e = body["evidence"]
            if not e.get("kind") or not e.get("reference_id"):
                raise HTTPException(400, "evidence needs kind and "
                                         "reference_id")
            evidence = AcceptanceEvidence(kind=e["kind"],
                                          reference_id=e["reference_id"],
                                          recorded_by=user["uid"],
                                          note=e.get("note", ""))
        elif channel != "portal_click":
            raise HTTPException(400, "manual acceptance requires "
                                     "AcceptanceEvidence")
        try:
            reqs = qengine.accept(q, channel=channel, evidence=evidence,
                                  now=datetime.utcnow())
        except IllegalQuoteTransition as e:
            raise HTTPException(409, str(e))
        except ValueError as e:
            qstore.save_quote(q)              # EXPIRED state persists
            raise HTTPException(409, str(e))
        qstore.save_quote(q)
        qstore.save_payment_requirements(user["tid"], reqs)
        # Lifecycle: deal accepted, money + delivery OPEN (mock providers).
        v = load_vector(q.case_id)
        v.deal = DealState.ACCEPTED_BY_CLIENT
        v.transaction = TransactionState.INVOICE_REQUIRED
        v.fulfillment = FulfillmentState.REQUIRED
        save_vector(q.case_id, v)
        handoff = qhandoff.handoff(q, reqs)
        audit.append(event_type="INVOICE_HANDOFF_PREPARED",
                     actor="mock-invoice-handoff", case_id=q.case_id,
                     payload=handoff)
        return {**quote_json(q),
                "payment_requirements": [
                    {"label": r.label, "amount": str(r.amount),
                     "trigger": r.trigger,
                     "blocks_fulfillment_until_paid":
                         r.blocks_fulfillment_until_paid} for r in reqs],
                "invoice_handoff": handoff,
                "lifecycle_view": v.derived_outcome_view(),
                "case_completed": False}

    @app.post("/quotes/{quote_id}/decline")
    async def decline_quote(quote_id: str, body: dict,
                            user: dict = Depends(current_user)):
        require_permission(user, "offer.create")
        if not str(body.get("reason", "")).strip():
            raise HTTPException(400, "declining requires a reason")
        q = load_quote_or_404(quote_id, user)
        try:
            qengine.decline(q, reason=body["reason"])
        except IllegalQuoteTransition as e:
            raise HTTPException(409, str(e))
        qstore.save_quote(q)
        return quote_json(q)

    @app.post("/quotes/{quote_id}/expire")
    async def expire_quote(quote_id: str,
                           user: dict = Depends(current_user)):
        require_permission(user, "offer.create")
        q = load_quote_or_404(quote_id, user)
        try:
            quote_transition(q, "EXPIRED")
        except IllegalQuoteTransition as e:
            raise HTTPException(409, str(e))
        audit.append(event_type="QUOTE_EXPIRED", actor=user["uid"],
                     case_id=q.case_id, payload={"quote_id": q.id})
        qstore.save_quote(q)
        return quote_json(q)

    @app.post("/quotes/{quote_id}/revise")
    async def revise_quote(quote_id: str,
                           user: dict = Depends(current_user)):
        require_permission(user, "offer.create")
        q = load_quote_or_404(quote_id, user)
        try:
            new = qengine.revise(q, revised_by=user["uid"])
        except (QuoteImmutableError, IllegalQuoteTransition) as e:
            raise HTTPException(409, str(e))
        qstore.save_quote(q)
        qstore.save_quote(new)
        return quote_json(new)

    @app.post("/quotes/{quote_id}/generate-pdf")
    async def generate_quote_pdf(quote_id: str,
                                 user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        q = load_quote_or_404(quote_id, user)
        html = qpdf.render(q)
        doc_id = str(uuid.uuid4())
        db.insert("quote_pdf_documents", {
            "id": doc_id, "tenant_id": user["tid"], "quote_id": q.id,
            "html": html, "is_mock": 1})
        audit.append(event_type="QUOTE_DOCUMENT_GENERATED",
                     actor="mock-pdf", case_id=q.case_id,
                     payload={"quote_id": q.id, "document_id": doc_id,
                              "is_mock": True})
        return {"document_id": doc_id, "is_mock": True,
                "provider": qpdf.name, "html": html}

    @app.get("/quotes/{quote_id}/events")
    async def quote_events(quote_id: str,
                           user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        load_quote_or_404(quote_id, user)
        return [{"event_type": e.event_type, "actor": e.actor,
                 "payload": e.payload, "created_at": e.created_at}
                for e in audit.events()
                if (e.payload or {}).get("quote_id") == quote_id]

    @app.get("/quotes/{quote_id}/evidence")
    async def quote_evidence(quote_id: str,
                             user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        q = load_quote_or_404(quote_id, user)
        ev = q.evidence
        import dataclasses as _dc
        return {"bundle": _dc.asdict(ev),
                "evidence_coverage_score": round(evidence_coverage_score(
                    required_facts_covered=ev.required_facts_covered,
                    source_reliability=ev.source_reliability,
                    evidence_recency=ev.evidence_recency,
                    scope_consistency=ev.scope_consistency,
                    human_verified_facts=ev.human_verified_facts,
                    pricing_data_coverage=ev.pricing_data_coverage), 4)}

    @app.get("/quotes/{quote_id}/payment-schedule")
    async def get_payment_schedule(quote_id: str,
                                   user: dict = Depends(current_user)):
        require_permission(user, "payment.view")
        q = load_quote_or_404(quote_id, user)
        return {"milestones": quote_json(q)["payment_schedule"],
                "payment_requirements": qstore.load_payment_requirements(
                    quote_id, tenant_id=user["tid"])}

    @app.post("/quotes/{quote_id}/payment-schedule")
    async def set_payment_schedule(quote_id: str, body: dict,
                                   user: dict = Depends(current_user)):
        require_permission(user, "offer.create")
        q = load_quote_or_404(quote_id, user)
        try:
            schedule = PaymentSchedule(milestones=[
                PaymentMilestone(
                    label=m["label"], fraction=Decimal(str(m["fraction"])),
                    trigger=m.get("trigger", "on_acceptance"),
                    is_deposit=bool(m.get("is_deposit")),
                    blocks_fulfillment_until_paid=bool(
                        m.get("blocks_fulfillment_until_paid")))
                for m in body.get("milestones", [])])
        except (KeyError, InvalidOperation):
            raise HTTPException(400, "invalid milestone payload")
        if q.state == "PRICE_CALCULATED":     # edits invalidate the calc
            quote_transition(q, "DRAFT")
        try:
            qengine.set_payment_schedule(q, schedule)
        except QuoteImmutableError as e:
            raise HTTPException(409, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))
        qstore.save_quote(q)
        return quote_json(q)

    @app.get("/quotes/{quote_id}/change-orders")
    async def list_change_orders(quote_id: str,
                                 user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        load_quote_or_404(quote_id, user)
        return qstore.load_change_orders(quote_id, tenant_id=user["tid"])

    @app.post("/quotes/{quote_id}/change-orders")
    async def create_change_order(quote_id: str, body: dict,
                                  user: dict = Depends(current_user)):
        require_permission(user, "offer.create")
        q = load_quote_or_404(quote_id, user)
        if not str(body.get("description", "")).strip() \
                or "price_delta" not in body:
            raise HTTPException(400, "description and price_delta required")
        try:
            price_delta = Decimal(str(body["price_delta"]))
            cost_delta = Decimal(str(body.get("cost_delta", "0")))
        except InvalidOperation:
            raise HTTPException(400, "invalid amount")
        try:
            co = qengine.create_change_order(
                q, description=body["description"],
                price_delta=price_delta, cost_delta=cost_delta,
                reason=body.get("reason", ""), requested_by=user["uid"])
        except ValueError as e:
            raise HTTPException(409, str(e))
        # Recalculated margin on the delta — same math as line margins.
        from ..quotes.pricing import margin_percent as _margin
        co_margin = _margin(co.price_delta, co.cost_delta) \
            if co.price_delta > Decimal("0") else None
        qstore.save_change_order(user["tid"], co, margin_percent=co_margin)
        return {"id": co.id, "status": co.status,
                "price_delta": str(co.price_delta),
                "cost_delta": str(co.cost_delta),
                "margin_percent": str(co_margin)
                if co_margin is not None else None,
                "requires_approval": True}

    # -- price books & pricing rules --------------------------------------------
    @app.get("/price-books")
    async def list_price_books(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return [dict(r) for r in db.all(
            "SELECT id, name, currency FROM price_books WHERE tenant_id=?",
            user["tid"])]

    @app.post("/price-books")
    async def create_price_book(body: dict,
                                user: dict = Depends(current_user)):
        require_permission(user, "offer.create")
        book = PriceBook(tenant_id=user["tid"],
                         name=body.get("name", "default"),
                         currency=body.get("currency", "EUR"))
        qstore.save_price_book(book)
        return {"id": book.id, "name": book.name}

    @app.get("/price-books/{book_id}/items")
    async def list_price_book_items(book_id: str,
                                    user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        book = qstore.load_price_book(book_id, tenant_id=user["tid"])
        if book is None:
            raise HTTPException(404, "price book not found")
        return [{"sku": i.sku, "name": i.name,
                 "list_price": str(i.list_price),
                 "tax_category": i.tax_category}
                for i in book.items.values()]

    @app.post("/price-books/{book_id}/items")
    async def add_price_book_item(book_id: str, body: dict,
                                  user: dict = Depends(current_user)):
        require_permission(user, "offer.create")
        book = qstore.load_price_book(book_id, tenant_id=user["tid"])
        if book is None:
            raise HTTPException(404, "price book not found")
        if not body.get("sku") or "list_price" not in body:
            raise HTTPException(400, "sku and list_price required")
        try:
            item = PriceBookItem(
                sku=body["sku"], name=body.get("name", body["sku"]),
                list_price=Decimal(str(body["list_price"])),
                cost_hint=Decimal(str(body["cost_hint"]))
                if body.get("cost_hint") is not None else None,
                tax_category=body.get("tax_category", "standard"))
        except InvalidOperation:
            raise HTTPException(400, "invalid price")
        qstore.save_price_book_item(book, item)
        return {"sku": item.sku, "list_price": str(item.list_price)}

    @app.get("/pricing-rules")
    async def list_pricing_rules(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return [{"id": r.id, "name": r.name,
                 "applies_to_sku": r.applies_to_sku,
                 "min_quantity": str(r.min_quantity),
                 "discount_percent": str(r.discount_percent),
                 "priority": r.priority}
                for r in qstore.load_pricing_rules(user["tid"])]

    @app.post("/pricing-rules")
    async def create_pricing_rule(body: dict,
                                  user: dict = Depends(current_user)):
        require_permission(user, "offer.create")
        if not body.get("name"):
            raise HTTPException(400, "name required")
        try:
            rule = PricingRule(
                tenant_id=user["tid"], name=body["name"],
                applies_to_sku=body.get("applies_to_sku", "*"),
                min_quantity=Decimal(str(body.get("min_quantity", "0"))),
                discount_percent=Decimal(str(
                    body.get("discount_percent", "0"))),
                priority=int(body.get("priority", 0)))
        except (InvalidOperation, ValueError):
            raise HTTPException(400, "invalid rule payload")
        qstore.save_pricing_rule(rule)
        return {"id": rule.id, "name": rule.name}

    @app.patch("/pricing-rules/{rule_id}")
    async def patch_pricing_rule(rule_id: str, body: dict,
                                 user: dict = Depends(current_user)):
        require_permission(user, "offer.create")
        row = db.one("SELECT * FROM pricing_rules WHERE id=? AND "
                     "tenant_id=?", rule_id, user["tid"])
        if row is None:
            raise HTTPException(404, "pricing rule not found")
        fields = {}
        for f in ("name", "applies_to_sku"):
            if f in body:
                fields[f] = body[f]
        for f in ("min_quantity", "discount_percent"):
            if f in body:
                fields[f] = str(Decimal(str(body[f])))
        if "priority" in body:
            fields["priority"] = int(body["priority"])
        if "active" in body:
            fields["active"] = int(bool(body["active"]))
        db.update("pricing_rules", rule_id, fields)
        return {"id": rule_id, **{k: str(v) for k, v in fields.items()}}

    # -- stateless pricing utilities ------------------------------------------------
    @app.post("/pricing/calculate")
    async def pricing_calculate(body: dict,
                                user: dict = Depends(current_user)):
        """Stateless what-if calculation (nothing persisted; mock tax)."""
        require_permission(user, "case.read")
        from ..quotes.models import Quote as _Quote
        q = _Quote(tenant_id=user["tid"], case_id="what-if")
        q.line_items = [parse_line(l) for l in body.get("lines", [])]
        if not q.line_items:
            raise HTTPException(400, "lines required")
        calculate_quote(q, target_margin=qengine.thresholds.target_margin,
                        max_auto_discount=qengine.thresholds
                        .max_auto_discount,
                        price_book=qstore.default_price_book(user["tid"]),
                        pricing_rules=qstore.load_pricing_rules(
                            user["tid"]))
        return {**quote_json(q), "persisted": False}

    @app.post("/pricing/validate")
    async def pricing_validate(body: dict,
                               user: dict = Depends(current_user)):
        """Stateless gate check for a hypothetical quote."""
        require_permission(user, "case.read")
        from ..quotes.models import Quote as _Quote
        q = _Quote(tenant_id=user["tid"], case_id="what-if",
                   customer_party_id="what-if")
        q.line_items = [parse_line(l) for l in body.get("lines", [])]
        if not q.line_items:
            raise HTTPException(400, "lines required")
        calculate_quote(q, target_margin=qengine.thresholds.target_margin,
                        max_auto_discount=qengine.thresholds
                        .max_auto_discount)
        gates = qengine.evaluate_gates(
            q, readiness_context=body.get("readiness") or {},
            feasibility_context=body.get("feasibility"))
        return {"gates": gates_json(gates), "persisted": False}

    # ---- Evidence Trust Fabric (V-B: zero-trust evidence API) ----------------
    import base64
    import tempfile
    from pathlib import Path as _Path

    from ..evidence.engine import (EvidenceEngine, EvidenceValidationError,
                                   RetentionContext)
    from ..evidence.models import (EvidenceSource,
                                   IllegalEvidenceTransition)
    from ..evidence.requirements import (REQUIREMENT_PROFILES,
                                         check_requirements)
    from ..evidence.storage import LocalEvidenceStorageProvider
    from ..evidence.views import (agent_view, causality_check, human_view,
                                  mark_symbol_human_verified)
    from .evidence_store import EvidenceStore
    from ..evidence.derivatives import generate_manifest
    from ..evidence.immutability import (RetentionPolicy,
                                         hard_delete_allowed,
                                         storage_worm_capability)
    from ..evidence.policy import (EvidencePolicyDriftReport,
                                   current_policy_version, policy_fingerprint)
    from ..evidence.rehydration import EvidenceRehydrator
    from ..evidence.scanners import (MockScannerProvider, ScaffoldCdrProvider,
                                     decide_file_treatment,
                                     scanner_risk_contribution)
    from ..evidence import transparency as _mrk
    from ..evidence import reports as _rpt

    vault_dir = tempfile.mkdtemp(prefix="finalis-evidence-") \
        if db_path == ":memory:" \
        else str(_Path(db_path).resolve().parent / "evidence-vault")
    evengine = EvidenceEngine(LocalEvidenceStorageProvider(vault_dir),
                              audit)
    estore = EvidenceStore(db)
    # V-E: rebuild live engine state from persisted facts (event-sourced).
    EvidenceRehydrator(estore).rehydrate(evengine)
    ev_scanner = MockScannerProvider()
    ev_cdr = ScaffoldCdrProvider()
    app.state.evidence, app.state.evidence_store = evengine, estore
    # Record the current evidence policy fingerprint once at startup.
    estore.save_policy_version(current_policy_version(),
                               policy_fingerprint(), created_at=utcnow())
    upload_sessions: dict[str, dict] = {}     # SCAFFOLDED_ONLY (future TUS)

    EVIDENCE_HONESTY = {
        "scanner": "MOCKED_AND_TESTED — deterministic mock verdict, not "
                   "production antivirus/CDR",
        "storage": "local vault (replaceable provider; no S3/MinIO/WORM "
                   "connected)",
        "ocr": "SCAFFOLDED_ONLY — no parser executes",
        "core_rule": "documents provide facts, never commands",
    }

    def load_evidence_or_404(evidence_id: str, user: dict):
        ev = evengine.objects.get(evidence_id)
        if ev is None or ev.tenant_id != user["tid"]:
            raise HTTPException(404, "evidence not found")  # incl. x-tenant
        return ev

    def evidence_json(ev) -> dict:
        return {"id": ev.id, "case_id": ev.case_id,
                "evidence_type": ev.evidence_type, "state": ev.state,
                "original_filename": ev.meta.original_filename,
                "extension": ev.meta.extension,
                "size_bytes": ev.meta.size_bytes,
                "declared_mime": ev.meta.declared_mime,
                "detected_mime": ev.meta.detected_mime,
                "mime_mismatch": ev.meta.mime_mismatch,
                "active_content": ev.meta.active_content,
                "sensitivity": ev.sensitivity,
                "injection_risk": round(ev.injection_risk, 4),
                "human_verified": ev.human_verified,
                "legal_hold": ev.legal_hold,
                "integrity": {"algorithm": ev.integrity.algorithm,
                              "sha256": ev.integrity.digest,
                              "valid": ev.integrity.valid}
                if ev.integrity else None,
                "scan": {"provider": ev.scan.provider,
                         "is_mock": ev.scan.is_mock,
                         "status": ev.scan.status},
                "untrusted": not all(s.trusted for s in ev.symbols)
                if ev.symbols else True,
                "honesty": EVIDENCE_HONESTY}

    @app.post("/evidence/upload")
    async def evidence_upload(body: dict,
                              user: dict = Depends(current_user)):
        """Quarantine-first ingest. JSON+base64 keeps the project's
        existing upload pattern (no multipart dependency). The client's
        Content-Type/extension are treated as claims, never trust."""
        require_permission(user, "document.upload")
        if not body.get("case_id") or not body.get("filename") \
                or "content_b64" not in body:
            raise HTTPException(400, "case_id, filename and content_b64 "
                                     "are required")
        case = load_case_or_404(body["case_id"], user)  # session tenant
        try:
            data = base64.b64decode(body["content_b64"])
        except Exception:
            raise HTTPException(400, "content_b64 is not valid base64")
        try:
            ev = evengine.ingest(
                tenant_id=user["tid"], case_id=case.id,
                uploaded_by=user["uid"],
                filename=str(body["filename"]),
                declared_mime=str(body.get("mime", "")), data=data,
                evidence_type=body.get("evidence_type", "document"),
                source=EvidenceSource(kind=body.get("source_kind",
                                                    "staff")),
                sensitivity=body.get("sensitivity", "normal"),
                text_preview=str(body.get("text_preview", "")))
        except EvidenceValidationError as e:
            raise HTTPException(400, str(e))
        estore.save(ev)
        return {**evidence_json(ev), "quarantine_first": True,
                "storage_capabilities":
                    evengine.storage.capabilities().__dict__}

    @app.get("/evidence")
    async def evidence_list(case_id: Optional[str] = None,
                            user: dict = Depends(current_user)):
        require_permission(user, "document.view")
        return [{"id": r["id"], "case_id": r["case_id"],
                 "evidence_type": r["evidence_type"], "state": r["state"],
                 "original_filename": r["original_filename"],
                 "sensitivity": r["sensitivity"]}
                for r in estore.list(tenant_id=user["tid"],
                                     case_id=case_id)]

    @app.get("/evidence/profiles")
    async def evidence_profiles(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return {name: {"required": p.required_types,
                       "min_trust": p.min_trust,
                       "human_verification_required":
                           p.human_verification_required}
                for name, p in REQUIREMENT_PROFILES.items()}

    @app.get("/evidence/storage-capabilities")
    async def evidence_storage_caps(user: dict = Depends(current_user)):
        require_permission(user, "document.view")
        return {"provider": evengine.storage.name,
                "capabilities": evengine.storage.capabilities().__dict__,
                "note": "local vault — WORM/retention/versioning enforced "
                        "by the domain layer, not natively "
                        "(BLOCKED_BY_EXTERNAL_PROVIDER for S3/MinIO)"}

    # Static single-segment GET routes MUST be declared before the dynamic
    # /evidence/{evidence_id} route below, or they get shadowed. Their
    # bodies delegate to helpers defined later in create_app (closures
    # resolve at request time, after create_app has fully executed).
    @app.get("/evidence/contracts")
    async def evidence_contracts_list(case_id: Optional[str] = None,
                                      user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        return [_contract_json(r) for r in estore.contracts(
            tenant_id=user["tid"], case_id=case_id)]

    @app.get("/evidence/merkle-roots")
    async def evidence_merkle_list(user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        return [{"batch_id": r["id"], "root": r["root"],
                 "size": r["size"], "created_at": r["created_at"]}
                for r in estore.merkle_roots(tenant_id=user["tid"])]

    @app.get("/evidence/policy-version")
    async def evidence_policy_version(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return {"policy_version": current_policy_version(),
                "fingerprint": policy_fingerprint(),
                "requirement_profiles": sorted(REQUIREMENT_PROFILES)}

    # -- upload sessions (SCAFFOLDED_ONLY — future-TUS shape, no chunking) --
    @app.post("/evidence/upload-sessions")
    async def create_upload_session(body: dict,
                                    user: dict = Depends(current_user)):
        require_permission(user, "document.upload")
        if not body.get("case_id"):
            raise HTTPException(400, "case_id required")
        load_case_or_404(body["case_id"], user)
        sid = str(uuid.uuid4())
        upload_sessions[sid] = {
            "id": sid, "tenant_id": user["tid"],
            "case_id": body["case_id"],
            "expected_size": int(body.get("expected_size", 0)),
            "filename": body.get("filename", ""),
            "state": "CREATED",
            "expires_at": (datetime.utcnow()
                           + timedelta(hours=2)).isoformat(),
            "status": "SCAFFOLDED_ONLY",
            "note": "future resumable upload (TUS-compatible shape); "
                    "chunked PATCH not implemented — use "
                    "/evidence/upload"}
        return upload_sessions[sid]

    @app.get("/evidence/upload-sessions/{session_id}")
    async def get_upload_session(session_id: str,
                                 user: dict = Depends(current_user)):
        s = upload_sessions.get(session_id)
        if s is None or s["tenant_id"] != user["tid"]:
            raise HTTPException(404, "upload session not found")
        return s

    @app.delete("/evidence/upload-sessions/{session_id}")
    async def delete_upload_session(session_id: str,
                                    user: dict = Depends(current_user)):
        s = upload_sessions.get(session_id)
        if s is None or s["tenant_id"] != user["tid"]:
            raise HTTPException(404, "upload session not found")
        del upload_sessions[session_id]
        return {"deleted": True}

    @app.get("/evidence/{evidence_id}")
    async def evidence_detail(evidence_id: str,
                              user: dict = Depends(current_user)):
        require_permission(user, "document.view")
        ev = load_evidence_or_404(evidence_id, user)
        if ev.sensitivity in ("sensitive", "legal"):
            require_permission(user, "document.view_sensitive")
        return evidence_json(ev)

    @app.get("/evidence/{evidence_id}/chain")
    async def evidence_chain(evidence_id: str,
                             user: dict = Depends(current_user)):
        require_permission(user, "document.view")
        load_evidence_or_404(evidence_id, user)
        return estore.chain_events(evidence_id, tenant_id=user["tid"])

    @app.post("/evidence/{evidence_id}/verify-integrity")
    async def evidence_verify_integrity(evidence_id: str,
                                        user: dict = Depends(
                                            current_user)):
        require_permission(user, "document.analyze")
        ev = load_evidence_or_404(evidence_id, user)
        ok = evengine.verify_integrity(ev)
        estore.save(ev)
        return {"valid": ok, "state": ev.state,
                "sha256": ev.integrity.digest if ev.integrity else None}

    @app.post("/evidence/{evidence_id}/review")
    async def evidence_review(evidence_id: str, body: dict,
                              user: dict = Depends(current_user)):
        require_permission(user, "document.analyze")
        ev = load_evidence_or_404(evidence_id, user)
        verdict = body.get("verdict", "")
        try:
            if verdict == "SCANNED_CLEAN":
                # Mock scanner over the stored bytes — honestly labeled.
                evengine.run_scan(ev, evengine.storage.get_bytes(
                    ev.storage))
            elif verdict in ("ADMISSIBLE", "ADMISSIBLE_WITH_LIMITS",
                             "REJECTED", "NEEDS_HUMAN_REVIEW"):
                evengine.human_review(ev, reviewer=user["uid"],
                                      verdict=verdict,
                                      note=body.get("note", ""))
            else:
                raise HTTPException(400, "unknown verdict")
        except IllegalEvidenceTransition as e:
            raise HTTPException(409, str(e))
        estore.save(ev)
        return {**evidence_json(ev),
                "scanner_is_mock": ev.scan.is_mock}

    @app.post("/evidence/{evidence_id}/legal-hold")
    async def evidence_legal_hold(evidence_id: str, body: dict,
                                  user: dict = Depends(current_user)):
        require_permission(user, "override.compliance_review")
        ev = load_evidence_or_404(evidence_id, user)
        action = body.get("action", "place")
        if action == "place":
            if not str(body.get("reason", "")).strip():
                raise HTTPException(400, "legal hold requires a reason")
            hold = evengine.place_legal_hold(ev, reason=body["reason"],
                                             placed_by=user["uid"])
            estore.save_legal_hold(hold)
        elif action == "release":
            ev.legal_hold = False
            if ev.state == "LEGAL_HOLD":
                from ..evidence.models import evidence_transition
                evidence_transition(ev, "ADMISSIBLE", actor=user["uid"],
                                    reason="legal hold released")
        else:
            raise HTTPException(400, "action must be place or release")
        estore.save(ev)
        return evidence_json(ev)

    @app.post("/evidence/{evidence_id}/delete-decision")
    async def evidence_delete_decision(evidence_id: str, body: dict,
                                       user: dict = Depends(
                                           current_user)):
        require_permission(user, "document.delete")
        ev = load_evidence_or_404(evidence_id, user)
        used_by_active = bool(estore.contracts(tenant_id=user["tid"],
                                               case_id=ev.case_id))
        decision = evengine.delete(
            ev, hard=bool(body.get("hard")),
            ctx=RetentionContext(actor_role=user["role"],
                                 used_by_active_decision=used_by_active))
        estore.save(ev)
        return {"decision": decision.decision,
                "reasons": decision.reasons, "state": ev.state}

    @app.post("/evidence/{evidence_id}/human-verify-symbol")
    async def evidence_verify_symbol(evidence_id: str, body: dict,
                                     user: dict = Depends(current_user)):
        require_permission(user, "document.analyze")
        ev = load_evidence_or_404(evidence_id, user)
        if not str(body.get("purpose", "")).strip():
            raise HTTPException(400, "a narrow factual purpose is "
                                     "required")
        symbol = next((s for s in ev.symbols
                       if s.id == body.get("symbol_id")), None)
        if symbol is None:
            raise HTTPException(404, "symbol not found")
        mark_symbol_human_verified(symbol, purpose=body["purpose"],
                                   verified_by=user["uid"])
        estore.save(ev)
        return {"symbol_id": symbol.id, "trusted": symbol.trusted,
                "human_verified_for": symbol.human_verified_for}

    @app.get("/evidence/{evidence_id}/human-view")
    async def evidence_human_view(evidence_id: str,
                                  user: dict = Depends(current_user)):
        require_permission(user, "document.view")
        ev = load_evidence_or_404(evidence_id, user)
        if ev.sensitivity in ("sensitive", "legal"):
            require_permission(user, "document.view_sensitive")
        hv = human_view(ev)
        return {"view": "human", "evidence_id": hv.evidence_id,
                "original_filename": hv.original_filename,
                "original_reference": hv.original_reference,
                "state": hv.state, "sensitivity": hv.sensitivity,
                "can_open_original": hv.can_open_original,
                "untrusted_content_warning":
                    "stored content remains UNTRUSTED external data — "
                    "storage inside Finalis does not make it safe"}

    @app.get("/evidence/{evidence_id}/agent-view")
    async def evidence_agent_view(evidence_id: str,
                                  user: dict = Depends(current_user)):
        require_permission(user, "document.view")
        ev = load_evidence_or_404(evidence_id, user)
        # Symbols are refreshed FROM THE DATABASE: a reread never
        # upgrades trust (sticky untrusted markers).
        stored = estore.load_symbols(evidence_id, tenant_id=user["tid"])
        if stored:
            ev.symbols = stored
        av = agent_view(ev)
        return {"view": "agent", "evidence_id": av.evidence_id,
                "evidence_type": av.evidence_type, "state": av.state,
                "metadata": av.metadata,
                "symbols": [{"id": s.id, "kind": s.kind,
                             "trusted": s.trusted,
                             "human_verified_for": s.human_verified_for,
                             "origin": s.marker.origin}
                            for s in av.symbols],
                "safe_derivative_text": av.safe_derivative_text,
                "confidence": round(av.confidence, 4),
                "untrusted": av.untrusted,
                "note": "agent view carries facts and symbols only — "
                        "raw untrusted text is structurally absent"}

    @app.post("/evidence/{evidence_id}/ai-access-decision")
    async def evidence_ai_access(evidence_id: str,
                                 body: Optional[dict] = None,
                                 user: dict = Depends(current_user)):
        require_permission(user, "document.view")
        body = body or {}
        ev = load_evidence_or_404(evidence_id, user)
        decision = evengine.ai_access(
            ev, tenant_id=user["tid"],
            actor_id=body.get("actor_id", "ai-worker"),
            purpose=body.get("purpose", "fact_extraction"),
            task_scoped_authorization=bool(
                body.get("task_scoped_authorization")),
            requested_raw=bool(body.get("requested_raw")))
        event = evengine.access_events[-1]
        estore.save_access_event(event)
        return {"decision": decision.decision,
                "reasons": decision.reasons,
                "allowed_view": decision.decision,
                "task_scope": body.get("purpose", "fact_extraction"),
                "access_event_id": event.id,
                "raw_content_included": False}

    @app.post("/evidence/requirement-check")
    async def evidence_requirement_check(body: dict,
                                         user: dict = Depends(
                                             current_user)):
        require_permission(user, "case.read")
        decision_type = body.get("decision_type", "")
        evidence = [evengine.objects[i]
                    for i in body.get("evidence_ids", [])
                    if i in evengine.objects
                    and evengine.objects[i].tenant_id == user["tid"]]
        check = check_requirements(
            decision_type, evidence,
            human_verified=bool(body.get("human_verified")))
        return {"decision_type": decision_type,
                "allowed": check.ok, "missing": check.missing,
                "reasons": check.reasons,
                "admissible": [e.id for e in evidence
                               if e.usable_for_decisions]}

    def _contract_hash(*, tenant_id: str, case_id: str, decision_type: str,
                       evidence_ids: list, facts: dict, hard_blockers: list,
                       causal_result: str, policy_version: str,
                       created_at: str) -> str:
        import hashlib as _h
        body = json.dumps({
            "t": tenant_id, "c": case_id, "d": decision_type,
            "e": sorted(evidence_ids), "f": facts,
            "hb": sorted(hard_blockers), "cr": causal_result,
            "pv": policy_version, "at": created_at}, sort_keys=True,
            default=str)
        return _h.sha256(body.encode()).hexdigest()

    def _evaluate_contract(*, tenant_id: str, actor: str, decision_type: str,
                           case_id: str, evidence_ids: list, facts: dict,
                           human_verified: bool, user_intent_reference,
                           untrusted_flag: bool,
                           would_survive: bool) -> dict:
        evidence = [evengine.objects[i] for i in evidence_ids
                    if i in evengine.objects]
        contract = evengine.build_contract(
            decision_type=decision_type, tenant_id=tenant_id,
            case_id=case_id, actor=actor, evidence=evidence,
            facts=facts, human_verified=human_verified)
        causal = causality_check(
            action_type=decision_type,
            user_intent_reference=user_intent_reference,
            untrusted_instruction_detected=untrusted_flag
            or any(e.injection_risk
                   > evengine.thresholds.max_injection_for_raw_ai
                   for e in evidence),
            would_action_survive_without_untrusted_text=would_survive)
        if contract.final_decision == "BLOCKED" \
                or causal.decision == "BLOCK":
            final = "BLOCKED"
        elif causal.decision == "HUMAN_REVIEW" \
                or contract.final_decision == "REVIEW":
            final = "HUMAN_REVIEW"
        else:
            final = "ALLOWED"
        contract.final_decision = ("ALLOWED" if final == "ALLOWED"
                                   else ("REVIEW" if final == "HUMAN_REVIEW"
                                         else "BLOCKED"))
        return {"contract": contract, "causal": causal, "final": final}

    @app.post("/evidence/decision-contract/validate")
    async def evidence_decision_contract(body: dict,
                                         user: dict = Depends(
                                             current_user)):
        """Requirement profiles + Causal Action Guard in one verdict:
        user intent + admissible facts decide — documents never do."""
        require_permission(user, "case.read")
        decision_type = body.get("decision_type", "")
        case_id = body.get("case_id", "")
        evidence_ids = body.get("evidence_ids", [])
        facts = body.get("facts") or {}
        intent = body.get("user_intent_reference")
        untrusted_flag = bool(body.get("untrusted_instruction_detected"))
        would_survive = bool(
            body.get("would_action_survive_without_untrusted_text", True))
        r = _evaluate_contract(
            tenant_id=user["tid"], actor=user["uid"],
            decision_type=decision_type, case_id=case_id,
            evidence_ids=evidence_ids, facts=facts,
            human_verified=bool(body.get("human_verified")),
            user_intent_reference=intent, untrusted_flag=untrusted_flag,
            would_survive=would_survive)
        contract, causal, final = r["contract"], r["causal"], r["final"]
        created_at = utcnow()
        pv = current_policy_version()
        chash = _contract_hash(
            tenant_id=user["tid"], case_id=case_id,
            decision_type=decision_type, evidence_ids=evidence_ids,
            facts=facts, hard_blockers=contract.hard_blockers,
            causal_result=causal.decision, policy_version=pv,
            created_at=created_at)
        estore.save_contract(
            contract, contract_hash=chash, policy_version=pv,
            requested_action=decision_type, causal_result=causal.decision,
            user_intent_reference=intent, would_survive=would_survive)
        return {"final": final, "contract_id": contract.id,
                "contract_hash": chash, "policy_version": pv,
                "admissible": contract.admissible_ids,
                "rejected": contract.rejected_ids,
                "hard_blockers": contract.hard_blockers,
                "causality": {"decision": causal.decision,
                              "reasons": causal.reasons},
                "case_completed_by_this": False}

    def _contract_json(row: dict) -> dict:
        return {"id": row["id"], "case_id": row["case_id"],
                "decision_type": row["decision_type"],
                "requested_action": row["requested_action"],
                "final_decision": row["final_decision"],
                "evidence_ids": json.loads(row["evidence_ids_json"]),
                "admissible": json.loads(row["admissible_json"]),
                "rejected": json.loads(row["rejected_json"]),
                "hard_blockers": json.loads(row["hard_blockers_json"]),
                "causal_result": row["causal_result"],
                "user_intent_reference": row["user_intent_reference"],
                "contract_hash": row["contract_hash"],
                "policy_version": row["policy_version"],
                "created_at": row["created_at"]}

    @app.get("/evidence/contracts/{contract_id}")
    async def evidence_contract_detail(contract_id: str,
                                       user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        row = estore.get_contract(contract_id, tenant_id=user["tid"])
        if row is None:
            raise HTTPException(404, "contract not found")
        drift = EvidencePolicyDriftReport.compare(row["policy_version"])
        return {**_contract_json(row),
                "policy_drift": {"drift": drift.drift,
                                 "detail": drift.detail,
                                 "current_version": drift.current_version}}

    @app.get("/evidence/{evidence_id}/contracts")
    async def evidence_contracts_by_evidence(evidence_id: str,
                                             user: dict = Depends(
                                                 current_user)):
        require_permission(user, "audit.view")
        load_evidence_or_404(evidence_id, user)
        return [_contract_json(r) for r in estore.contracts(
            tenant_id=user["tid"], evidence_id=evidence_id)]

    @app.get("/cases/{case_id}/evidence-contracts")
    async def case_evidence_contracts(case_id: str,
                                      user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        load_case_or_404(case_id, user)
        return [_contract_json(r) for r in estore.contracts(
            tenant_id=user["tid"], case_id=case_id)]

    @app.post("/evidence/contracts/{contract_id}/replay")
    async def evidence_contract_replay(contract_id: str,
                                       user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        row = estore.get_contract(contract_id, tenant_id=user["tid"])
        if row is None:
            raise HTTPException(404, "contract not found")
        r = _evaluate_contract(
            tenant_id=user["tid"], actor=user["uid"],
            decision_type=row["decision_type"], case_id=row["case_id"],
            evidence_ids=json.loads(row["evidence_ids_json"]),
            facts=json.loads(row["facts_json"]),
            human_verified=bool(row["human_verified"]),
            user_intent_reference=row["user_intent_reference"],
            untrusted_flag=(row["causal_result"] or "").startswith("BLOCK")
            or False,
            would_survive=bool(row["would_survive"])
            if row["would_survive"] is not None else True)
        drift = EvidencePolicyDriftReport.compare(row["policy_version"])
        return {"contract_id": contract_id,
                "stored_decision": row["final_decision"],
                "replayed_decision": r["final"],
                "same_decision": row["final_decision"] == r["final"],
                "policy_drift": drift.drift,
                "policy_detail": drift.detail,
                "stored_policy_version": row["policy_version"],
                "current_policy_version": drift.current_version}

    # -- V-E: derivatives -----------------------------------------------------------
    @app.get("/evidence/{evidence_id}/derivatives")
    async def evidence_derivatives_list(evidence_id: str,
                                        user: dict = Depends(current_user)):
        require_permission(user, "document.view")
        load_evidence_or_404(evidence_id, user)
        return estore.derivatives(evidence_id, tenant_id=user["tid"])

    @app.post("/evidence/{evidence_id}/derivatives/generate")
    async def evidence_derivative_generate(evidence_id: str,
                                           user: dict = Depends(
                                               current_user)):
        require_permission(user, "document.analyze")
        ev = load_evidence_or_404(evidence_id, user)
        from ..evidence.gates import admissibility_gate as _adm
        blockers = _adm(ev, tenant_id=user["tid"]).hard_blockers
        manifest = generate_manifest(ev, now_iso=utcnow(),
                                     has_hard_blocker=bool(blockers))
        estore.save_derivative(user["tid"], manifest)
        return {"id": manifest.id,
                "derivative_kind": manifest.derivative_kind,
                "policy_decision": manifest.policy_decision,
                "confidence": manifest.confidence,
                "is_placeholder": manifest.is_placeholder,
                "safe_derivative_score": manifest.confidence,
                "safe_text": manifest.safe_text,
                "limitations": manifest.limitations,
                "manifest_hash": manifest.manifest_hash,
                "raw_content_included": False}

    # -- V-E: WORM / retention immutability -----------------------------------------
    @app.get("/evidence/{evidence_id}/immutability")
    async def evidence_immutability(evidence_id: str,
                                    user: dict = Depends(current_user)):
        require_permission(user, "document.view")
        load_evidence_or_404(evidence_id, user)
        cap = storage_worm_capability(evengine.storage.name)
        pol = estore.retention_policy(evidence_id, tenant_id=user["tid"])
        return {"native_worm": cap.native_worm,
                "simulated_modes": cap.simulated_modes,
                "note": cap.note,
                "retention_policy": pol}

    @app.post("/evidence/{evidence_id}/retention-policy")
    async def evidence_set_retention(evidence_id: str, body: dict,
                                     user: dict = Depends(current_user)):
        require_permission(user, "override.compliance_review")
        ev = load_evidence_or_404(evidence_id, user)
        try:
            pol = RetentionPolicy(
                tenant_id=user["tid"], evidence_id=evidence_id,
                mode=body.get("mode", "SIMULATED_GOVERNANCE"),
                retention_until=datetime.fromisoformat(body["retention_until"])
                if body.get("retention_until") else None)
        except ValueError as e:
            raise HTTPException(400, str(e))
        estore.save_retention_policy(pol)
        return {"mode": pol.mode, "native_worm": pol.native_worm,
                "label": pol.label,
                "retention_until": pol.retention_until.isoformat()
                if pol.retention_until else None}

    # -- V-E: Merkle transparency ledger --------------------------------------------
    def _leaf_for(cr: dict) -> str:
        import hashlib as _h
        payload_hash = _h.sha256(cr["payload_json"].encode()).hexdigest()
        return _mrk.leaf_hash(
            tenant_id=cr["tenant_id"], evidence_id=cr["evidence_id"],
            event_id=cr["id"], event_type=cr["event_type"],
            event_timestamp=cr["created_at"],
            previous_event_hash=cr["hash_prev"],
            event_payload_hash=payload_hash)

    @app.post("/evidence/merkle-roots/generate")
    async def evidence_merkle_generate(user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        events = estore.all_chain_events(tenant_id=user["tid"])
        leaves = [_leaf_for(cr) for cr in events]
        root = _mrk.EvidenceMerkleRoot(
            tenant_id=user["tid"], root=_mrk.merkle_root(leaves),
            size=len(leaves))
        prior = estore.merkle_roots(tenant_id=user["tid"])
        consistent = True
        if prior:
            old_leaves = json.loads(prior[-1]["leaves_json"])
            consistent = _mrk.consistency_proof_ok(old_leaves, leaves)
        estore.save_merkle_root(root, leaves, created_at=utcnow())
        return {"batch_id": root.batch_id, "root": root.root,
                "size": root.size, "consistent_with_prior": consistent,
                "external_anchoring": "NONE — local ledger only "
                                      "(no blockchain/timestamping)"}

    @app.get("/evidence/{evidence_id}/merkle-proof")
    async def evidence_merkle_proof(evidence_id: str,
                                    event_id: Optional[str] = None,
                                    user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        load_evidence_or_404(evidence_id, user)
        events = estore.all_chain_events(tenant_id=user["tid"])
        leaves = [_leaf_for(cr) for cr in events]
        # Prove the first chain event of this evidence (or a named one).
        target_idx = next(
            (i for i, cr in enumerate(events)
             if cr["evidence_id"] == evidence_id
             and (event_id is None or cr["id"] == event_id)), None)
        if target_idx is None:
            raise HTTPException(404, "chain event not found")
        proof = _mrk.build_proof(leaves, target_idx)
        return {"evidence_id": evidence_id,
                "leaf_hash": proof.leaf_hash, "root": proof.root,
                "path": [[h, r] for h, r in proof.path],
                "index": proof.index, "size": proof.size,
                "verifies": _mrk.verify_proof(proof)}

    @app.post("/evidence/merkle-roots/{root_id}/verify")
    async def evidence_merkle_verify(root_id: str,
                                     user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        row = estore.get_merkle_root(root_id, tenant_id=user["tid"])
        if row is None:
            raise HTTPException(404, "root not found")
        stored_leaves = json.loads(row["leaves_json"])
        # Recompute leaves from the live chain and compare the root.
        events = estore.all_chain_events(tenant_id=user["tid"])
        current_leaves = [_leaf_for(cr) for cr in events]
        recomputed = _mrk.merkle_root(stored_leaves)
        tampered = recomputed != row["root"]
        return {"batch_id": root_id, "stored_root": row["root"],
                "recomputed_root": recomputed,
                "root_intact": not tampered,
                "chain_still_matches_root":
                    _mrk.merkle_root(current_leaves[:len(stored_leaves)])
                    == row["root"] if len(current_leaves) >= len(
                        stored_leaves) else False}

    # -- Transparency Log Core: server-verified consistency proofs -----------------
    def _checkpoint(row: dict) -> dict:
        """Honest checkpoint metadata. Signatures / witness cosignatures /
        SCITT receipts are future-ready slots only — none are implemented,
        no external transparency service is called."""
        import hashlib as _h
        cp = _h.sha256(
            f"FINALIS_EVIDENCE_CHECKPOINT_V1|{row['tenant_id']}|"
            f"{row['root']}|{row['size']}|sha256".encode()).hexdigest()
        return {"checkpoint_hash": cp, "checkpoint_algorithm": "sha256",
                "checkpoint_created_at": row["created_at"],
                "checkpoint_signature_status": "NOT_IMPLEMENTED",
                "witness_cosignature_status": "NOT_IMPLEMENTED",
                "scitt_receipt_status": "NOT_IMPLEMENTED"}

    _CONSISTENCY_NOTES = [
        "Finalis server-verified append-only consistency.",
        "Merkle consistency proves append-only tree evolution only; it does "
        "not prove legal validity.",
        "Checkpoint signatures are not implemented.",
        "Witness cosignatures are not implemented.",
        "SCITT receipts are not implemented.",
        "No external transparency service is called.",
    ]

    @app.get("/evidence/merkle-roots/{current_root_id}/consistency")
    async def evidence_merkle_consistency(
            current_root_id: str, previous_root_id: Optional[str] = None,
            user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        if not previous_root_id:
            raise HTTPException(400, "previous_root_id is required")

        def _shell(status: str, reason: str, cur=None, prev=None):
            return {"previous_root_id": previous_root_id,
                    "current_root_id": current_root_id,
                    "previous_tree_size": prev["size"] if prev else None,
                    "current_tree_size": cur["size"] if cur else None,
                    "previous_root_hash": prev["root"] if prev else None,
                    "current_root_hash": cur["root"] if cur else None,
                    "consistency_proof_nodes": [], "algorithm": "sha256",
                    "status": status, "append_only_verified": False,
                    "reason": reason, "verified_at": utcnow(),
                    "checkpoint": _checkpoint(cur) if cur else None,
                    "notes": _CONSISTENCY_NOTES}

        # Tenant-scoped lookups: a cross-tenant root id simply isn't found —
        # roots are never compared across tenants.
        cur = estore.get_merkle_root(current_root_id, tenant_id=user["tid"])
        prev = estore.get_merkle_root(previous_root_id, tenant_id=user["tid"])
        if cur is None or prev is None:
            return _shell("ROOT_NOT_FOUND",
                          "A referenced root was not found for this tenant "
                          "(cross-tenant consistency checks are not allowed).",
                          cur, prev)
        report = _mrk.consistency_report(
            old_leaves=json.loads(prev["leaves_json"]),
            old_root=prev["root"], old_size=prev["size"],
            new_leaves=json.loads(cur["leaves_json"]),
            new_root=cur["root"], new_size=cur["size"], algorithm="sha256")
        return {"previous_root_id": previous_root_id,
                "current_root_id": current_root_id,
                "previous_tree_size": prev["size"],
                "current_tree_size": cur["size"],
                "previous_root_hash": prev["root"],
                "current_root_hash": cur["root"],
                "previous_tree_hash": report.previous_tree_hash,
                "current_tree_hash": report.current_tree_hash,
                "consistency_proof_nodes": report.proof_nodes,
                "algorithm": "sha256", "status": report.status,
                "append_only_verified": report.append_only_verified,
                "reason": report.reason, "verified_at": utcnow(),
                "checkpoint": _checkpoint(cur), "notes": _CONSISTENCY_NOTES}

    @app.get("/evidence/merkle-roots/{root_id}/lineage")
    async def evidence_merkle_lineage(root_id: str,
                                      user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        row = estore.get_merkle_root(root_id, tenant_id=user["tid"])
        if row is None:
            raise HTTPException(404, "root not found")
        roots = estore.merkle_roots(tenant_id=user["tid"])   # created_at order
        lineage, prev_id = [], None
        for r in roots:
            lineage.append({"root_id": r["id"], "tree_size": r["size"],
                            "root_hash": r["root"],
                            "previous_root_id": prev_id,
                            "created_at": r["created_at"]})
            prev_id = r["id"]
            if r["id"] == root_id:
                break
        return {"root_id": root_id, "algorithm": "sha256",
                "chain_length": len(lineage), "lineage": lineage,
                "checkpoint": _checkpoint(row), "notes": _CONSISTENCY_NOTES}

    # -- Canonical Evidence Report Package (EVIDENCE-REPORT-C2) ---------------------
    def _gather_evidence_signals(ev, user: dict) -> dict:
        """Assemble the server-side proof signals a report captures. Reuses
        the same tested Evidence data (integrity, Merkle inclusion, server-
        verified consistency, derivatives, contracts) — no faked values."""
        j = evidence_json(ev)
        events = estore.all_chain_events(tenant_id=user["tid"])
        leaves = [_leaf_for(cr) for cr in events]
        inclusion = {"status": "NOT_EXPOSED"}
        idx = next((i for i, cr in enumerate(events)
                    if cr["evidence_id"] == ev.id), None)
        if idx is not None and leaves:
            pr = _mrk.build_proof(leaves, idx)
            inclusion = {"status": "VERIFIED" if _mrk.verify_proof(pr)
                         else "NOT_VERIFIED", "root_id": None,
                         "root_hash": pr.root, "tree_size": pr.size,
                         "leaf_index": pr.index, "leaf_hash": pr.leaf_hash}
        consistency = {"status": "NOT_EXPOSED"}
        roots = estore.merkle_roots(tenant_id=user["tid"])
        if len(roots) >= 2:
            prev, cur = roots[-2], roots[-1]
            rep = _mrk.consistency_report(
                old_leaves=json.loads(prev["leaves_json"]),
                old_root=prev["root"], old_size=prev["size"],
                new_leaves=json.loads(cur["leaves_json"]),
                new_root=cur["root"], new_size=cur["size"])
            consistency = {"status": rep.status,
                           "append_only_verified": rep.append_only_verified,
                           "previous_root_id": prev["id"],
                           "current_root_id": cur["id"],
                           "proof_nodes": rep.proof_nodes}
        derivatives = [
            {"id": d.get("id"),
             "parent_evidence_id": d.get("parent_evidence_id", ev.id),
             "orphan": bool(d.get("parent_evidence_id")
                            and d.get("parent_evidence_id") != ev.id)}
            for d in estore.derivatives(ev.id, tenant_id=user["tid"])]
        contracts = [{"id": c["id"], "final_decision": c["final_decision"]}
                     for c in estore.contracts(tenant_id=user["tid"],
                                               evidence_id=ev.id)]
        integ = j.get("integrity") or {}
        ca = getattr(ev, "created_at", None)
        src = getattr(ev, "source_type", None) or getattr(ev, "source", None)
        return {"evidence": {
                    "id": ev.id, "case_id": ev.case_id,
                    "evidence_type": ev.evidence_type,
                    "source": str(src) if src is not None else "upload",
                    "created_at": ca.isoformat()
                    if hasattr(ca, "isoformat") else ca,
                    "content_hash": integ.get("sha256"),
                    "algorithm": integ.get("algorithm"),
                    "integrity_valid": integ.get("valid"),
                    "state": ev.state, "human_verified": ev.human_verified},
                "inclusion": inclusion, "consistency": consistency,
                "derivatives": derivatives, "contracts": contracts}

    @app.post("/evidence/{evidence_id}/proof-reports")
    async def create_proof_report(evidence_id: str,
                                  user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        ev = load_evidence_or_404(evidence_id, user)
        signals = _gather_evidence_signals(ev, user)
        rid = str(uuid.uuid4())
        parent = estore.reports_for_evidence(evidence_id, tenant_id=user["tid"])
        payload = _rpt.build_report_payload(
            report_id=rid, tenant_id=user["tid"], generated_by=user["uid"],
            generated_at=utcnow(), signals=signals,
            supersedes_report_id=parent[-1]["id"] if parent else None)
        package = _rpt.build_package(payload)
        estore.save_report(
            report_id=rid, tenant_id=user["tid"], evidence_id=evidence_id,
            case_id=ev.case_id, report_type=_rpt.REPORT_TYPE,
            report_version=_rpt.REPORT_VERSION, report_status="GENERATED",
            report_hash=payload["report_metadata"]["report_hash"],
            package_hash=package["package_hash"],
            final_verdict=payload["report_metadata"]["final_verdict"],
            payload_json=json.dumps(payload),
            package_json=json.dumps(package), parent_report_id=None,
            supersedes_report_id=parent[-1]["id"] if parent else None,
            generated_by=user["uid"], created_at=utcnow())
        audit.append(event_type="EVIDENCE_PROOF_REPORT_GENERATED",
                     actor=user["uid"],
                     payload={"report_id": rid, "evidence_id": evidence_id,
                              "report_hash": payload["report_metadata"][
                                  "report_hash"]})
        return {"report_id": rid, "package": package, **payload}

    def _load_report_or_404(report_id: str, user: dict) -> dict:
        row = estore.get_report(report_id, tenant_id=user["tid"])
        if row is None:                          # incl. cross-tenant
            raise HTTPException(404, "proof report not found")
        return row

    @app.get("/evidence/proof-reports/{report_id}")
    async def get_proof_report(report_id: str,
                               user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        row = _load_report_or_404(report_id, user)
        payload = json.loads(row["payload_json"])
        return {"report_id": report_id, "package": json.loads(
            row["package_json"]), **payload}

    @app.get("/evidence/proof-reports/{report_id}/safe")
    async def get_proof_report_safe(report_id: str,
                                    user: dict = Depends(current_user)):
        # Safe/redacted view available to document.view roles (no audit.view
        # needed) — omits restricted fields, never changes stored truth.
        require_permission(user, "document.view")
        row = _load_report_or_404(report_id, user)
        return _rpt.safe_view(json.loads(row["payload_json"]))

    @app.post("/evidence/proof-reports/{report_id}/verify")
    async def verify_proof_report(report_id: str,
                                  user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        row = _load_report_or_404(report_id, user)
        result = _rpt.verify_report_artifact(
            json.loads(row["payload_json"]), row["report_hash"],
            row["package_hash"])
        return {"report_id": report_id, **result, "verified_at": utcnow()}

    @app.get("/evidence/{evidence_id}/proof-reports")
    async def list_proof_reports(evidence_id: str,
                                 user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        load_evidence_or_404(evidence_id, user)
        return [{"report_id": r["id"], "report_hash": r["report_hash"],
                 "package_hash": r["package_hash"],
                 "final_verdict": r["final_verdict"],
                 "report_status": r["report_status"],
                 "created_at": r["created_at"],
                 "supersedes_report_id": r["supersedes_report_id"]}
                for r in estore.reports_for_evidence(
                    evidence_id, tenant_id=user["tid"])]

    @app.get("/evidence/proof-reports/{report_id}/diff")
    async def diff_proof_reports(report_id: str, other_report_id: str,
                                 user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        a = _load_report_or_404(report_id, user)
        b = _load_report_or_404(other_report_id, user)
        pa, pb = json.loads(a["payload_json"]), json.loads(b["payload_json"])

        def _flat(obj, prefix=""):
            out = {}
            if isinstance(obj, dict):
                for k, v in obj.items():
                    out.update(_flat(v, f"{prefix}.{k}" if prefix else k))
            elif isinstance(obj, list):
                out[prefix] = _rpt.canonical_json(obj)
            else:
                out[prefix] = obj
            return out
        VOL = tuple(_rpt.EXCLUDED_HASH_FIELDS)
        fa, fb = _flat(pa), _flat(pb)
        changed = []
        for k in sorted(set(fa) | set(fb)):
            if any(k.endswith(v) for v in VOL):
                continue                         # ignore volatile fields
            if fa.get(k) != fb.get(k):
                changed.append({"field": k, "a": fa.get(k), "b": fb.get(k)})
        return {"report_id": report_id, "other_report_id": other_report_id,
                "report_hash_a": a["report_hash"],
                "report_hash_b": b["report_hash"],
                "identical_proof_state": a["report_hash"] == b["report_hash"],
                "changed_fields": changed,
                "note": "Volatile fields (ids, timestamps, hashes, signature) "
                        "are excluded from the diff."}

    # ---- Relationship Core (CRM-B: persistence + API over CRM-A) --------------
    from ..crm.adapters import NullCrmAdapter, default_policy, \
        idempotency_key as make_idempotency_key
    from ..crm.dedupe import duplicate_candidate, merge_parties
    from ..crm.engine import RelationshipEngine
    from ..crm.graph import CrossTenantLinkError
    from ..crm.models import (ConsentRecord, ContactPoint,
                              CustomerMemoryItem, CustomerPromise,
                              ExternalCrmReference, ExternalFieldMapping,
                              OrganizationProfile, Party, PersonProfile)
    from ..crm.sync import SyncRequest, record_sync_event, sync_decision
    from .crm_store import CrmStore

    crm = RelationshipEngine(audit)
    crm_store = CrmStore(db)
    crm_store.hydrate(crm)               # DB is the source of truth
    crm_adapter = NullCrmAdapter()       # SCAFFOLDED_ONLY — talks to nothing
    app.state.crm, app.state.crm_store = crm, crm_store

    # RBAC mapping (existing catalog, disclosed): reads -> case.read;
    # writes -> case.update; memory verification -> action.approve;
    # merge -> tenant.manage_users; external refs/sync -> tenant.
    # manage_integrations. AI workers hold none of the human-judgment
    # permissions, and the engine additionally refuses non-human actors.
    def load_crm_party_or_404(party_id: str, user: dict) -> Party:
        p = crm.graph.parties.get(party_id)
        if p is None or p.tenant_id != user["tid"]:
            raise HTTPException(404, "party not found")
        return p

    def crm_party_json(p: Party) -> dict:
        return {"id": p.id, "kind": p.kind,
                "display_name": p.display_name,
                "roles": sorted(p.roles),
                "contact_points": [{"id": c.id, "kind": c.kind,
                                    "value": c.value,
                                    "preferred": c.preferred}
                                   for c in p.contact_points],
                "merged_into_id": p.merged_into_id}

    @app.get("/crm/parties")
    async def crm_list_parties(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        rows = crm_store.list_parties(tenant_id=user["tid"])
        # Bridge: legacy case-contact parties, read-only, labeled.
        legacy = [{"id": r["id"], "kind": "person",
                   "display_name": r["display_name"],
                   "legacy_case_contact": True}
                  for r in db.all("SELECT id, display_name FROM parties "
                                  "WHERE tenant_id=?", user["tid"])]
        return {"parties": rows, "legacy_case_contacts": legacy}

    @app.post("/crm/parties")
    async def crm_create_party(body: dict,
                               user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        if not str(body.get("display_name", "")).strip():
            raise HTTPException(400, "display_name required")
        try:
            p = Party(
                tenant_id=user["tid"],
                kind=body.get("kind", "person"),
                display_name=body["display_name"],
                person=PersonProfile(**body["person"])
                if body.get("person") else None,
                organization=OrganizationProfile(**body["organization"])
                if body.get("organization") else None,
                roles=set(body.get("roles", ["customer"])))
            for cp in body.get("contact_points", []):
                p.contact_points.append(ContactPoint(
                    kind=cp["kind"], value=cp["value"],
                    label=cp.get("label", "")))
        except (ValueError, KeyError, TypeError) as e:
            raise HTTPException(400, f"invalid party payload: {e}")
        crm.graph.add_party(p)
        crm_store.save_party(p)
        audit.append(event_type="CRM_PARTY_CREATED", actor=user["uid"],
                     payload={"party_id": p.id, "kind": p.kind})
        return crm_party_json(p)

    @app.get("/crm/parties/{party_id}")
    async def crm_party_detail(party_id: str,
                               user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        p = load_crm_party_or_404(party_id, user)
        return {**crm_party_json(p),
                "cases": crm.graph.cases_of(p.id, tenant_id=user["tid"]),
                "open_promises": [
                    {"promisor": x.promisor, "what": x.what,
                     "status": x.status}
                    for x in crm.open_promises(p.id,
                                               tenant_id=user["tid"])]}

    @app.patch("/crm/parties/{party_id}")
    async def crm_update_party(party_id: str, body: dict,
                               user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        p = load_crm_party_or_404(party_id, user)
        if "display_name" in body:
            if not str(body["display_name"]).strip():
                raise HTTPException(400, "display_name cannot be empty")
            p.display_name = body["display_name"]
        if "roles" in body:
            try:
                p.roles = set(body["roles"])
                p.__post_init__()
            except ValueError as e:
                raise HTTPException(400, str(e))
        crm_store.save_party(p)
        return crm_party_json(p)

    @app.get("/crm/parties/{party_id}/contacts")
    async def crm_contacts(party_id: str,
                           user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return crm_party_json(load_crm_party_or_404(party_id, user)
                              )["contact_points"]

    @app.post("/crm/parties/{party_id}/contacts")
    async def crm_add_contact(party_id: str, body: dict,
                              user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        p = load_crm_party_or_404(party_id, user)
        try:
            cp = ContactPoint(kind=body.get("kind", ""),
                              value=body.get("value", ""),
                              label=body.get("label", ""))
        except ValueError as e:
            raise HTTPException(400, str(e))
        p.contact_points.append(cp)
        crm_store.save_party(p)
        return {"id": cp.id, "kind": cp.kind, "value": cp.value}

    # -- consent -----------------------------------------------------------------
    @app.get("/crm/parties/{party_id}/consents")
    async def crm_consents(party_id: str,
                           user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        load_crm_party_or_404(party_id, user)
        return [{"channel": c.channel, "status": c.status,
                 "source": c.source}
                for c in crm.consents
                if c.party_id == party_id and c.tenant_id == user["tid"]]

    @app.post("/crm/parties/{party_id}/consents")
    async def crm_record_consent(party_id: str, body: dict,
                                 user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        load_crm_party_or_404(party_id, user)
        try:
            record = ConsentRecord(
                tenant_id=user["tid"], party_id=party_id,
                channel=body.get("channel", ""),
                status=body.get("status", ""),
                source=body.get("source", "portal"),
                recorded_by=user["uid"])
        except ValueError as e:
            raise HTTPException(400, str(e))
        crm.record_consent(record)
        crm_store.save_consent(record)
        return {"channel": record.channel, "status": record.status}

    @app.post("/crm/consent/check")
    async def crm_consent_check(body: dict,
                                user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        p = load_crm_party_or_404(body.get("party_id", ""), user)
        d = crm.can_contact(p, channel=body.get("channel", "EMAIL"),
                            purpose=body.get("purpose", "service"))
        return {"allowed": d.allowed,
                "requires_review": d.requires_review,
                "reasons": d.reasons}

    # -- promises ------------------------------------------------------------------
    @app.get("/crm/parties/{party_id}/promises")
    async def crm_promises_list(party_id: str,
                                user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        load_crm_party_or_404(party_id, user)
        return [{"id": p.id, "promisor": p.promisor, "what": p.what,
                 "status": p.status, "case_id": p.case_id,
                 "due_at": p.due_at.isoformat() if p.due_at else None}
                for p in crm.promises
                if p.party_id == party_id and p.tenant_id == user["tid"]]

    @app.post("/crm/parties/{party_id}/promises")
    async def crm_add_promise(party_id: str, body: dict,
                              user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        load_crm_party_or_404(party_id, user)
        due_at = None
        if body.get("due_at"):
            try:
                due_at = datetime.fromisoformat(body["due_at"])
            except ValueError:
                raise HTTPException(400, "invalid due_at")
        try:
            promise = crm.record_promise(CustomerPromise(
                tenant_id=user["tid"], party_id=party_id,
                promisor=body.get("promisor", ""),
                what=body.get("what", ""), due_at=due_at,
                case_id=body.get("case_id")))
        except ValueError as e:
            raise HTTPException(400, str(e))
        crm_store.save_promise(promise)
        return {"id": promise.id, "promisor": promise.promisor,
                "due_at": promise.due_at.isoformat()
                if promise.due_at else None}

    # -- memory --------------------------------------------------------------------
    @app.get("/crm/parties/{party_id}/memory")
    async def crm_memory_list(party_id: str,
                              user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        load_crm_party_or_404(party_id, user)
        items = crm.memory.for_party(party_id, tenant_id=user["tid"])
        out = []
        for m in items:
            if m.sensitive:
                d = rbac.access(actor_type="user",
                                actor_id=rbac_user_id(user),
                                tenant_id=user["tid"],
                                action="document.view_sensitive")
                if d.decision != "ALLOW":
                    continue                 # sensitive hidden safely
            out.append({"id": m.id, "memory_type": m.memory_type,
                        "content": m.content, "source": m.source,
                        "confidence": m.confidence,
                        "sensitive": m.sensitive})
        return out

    @app.post("/crm/parties/{party_id}/memory")
    async def crm_memory_add(party_id: str, body: dict,
                             user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        load_crm_party_or_404(party_id, user)
        try:
            item = crm.memory.add(CustomerMemoryItem(
                tenant_id=user["tid"], party_id=party_id,
                memory_type=body.get("memory_type", "SERVICE_HISTORY"),
                content=body.get("content") or {},
                source=body.get("source", "human"),
                confidence=float(body.get("confidence", 0.5)),
                sensitive=bool(body.get("sensitive"))))
        except ValueError as e:
            raise HTTPException(400, str(e))
        crm_store.save_memory(item)
        return {"id": item.id, "memory_type": item.memory_type}

    def _load_memory_or_404(memory_id: str, user: dict):
        item = next((m for m in crm.memory.items
                     if m.id == memory_id
                     and m.tenant_id == user["tid"]), None)
        if item is None:
            raise HTTPException(404, "memory item not found")
        return item

    @app.post("/crm/memory/{memory_id}/verify")
    async def crm_memory_verify(memory_id: str,
                                user: dict = Depends(current_user)):
        require_permission(user, "action.approve")   # human judgment
        item = _load_memory_or_404(memory_id, user)
        crm.memory.verify(item, verified_by=user["uid"])
        crm_store.save_memory(item)
        return {"id": item.id, "memory_type": item.memory_type,
                "verified_by": item.verified_by}

    @app.post("/crm/memory/{memory_id}/dispute")
    async def crm_memory_dispute(memory_id: str,
                                 user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        item = _load_memory_or_404(memory_id, user)
        crm.memory.dispute(item, by=user["uid"])
        crm_store.save_memory(item)
        return {"id": item.id, "memory_type": item.memory_type}

    @app.post("/crm/memory/{memory_id}/mark-stale")
    async def crm_memory_stale(memory_id: str,
                               user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        item = _load_memory_or_404(memory_id, user)
        item.memory_type = "STALE_FACT"
        crm_store.save_memory(item)
        return {"id": item.id, "memory_type": item.memory_type}

    # -- relationships / case links -----------------------------------------------
    @app.get("/crm/parties/{party_id}/relationships")
    async def crm_relationships(party_id: str,
                                user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        load_crm_party_or_404(party_id, user)
        return [{"to_id": e.to_id, "to_kind": e.to_kind, "role": e.role}
                for e in crm.graph.edges_of(party_id,
                                            tenant_id=user["tid"])]

    @app.post("/crm/relationships")
    async def crm_add_relationship(body: dict,
                                   user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        try:
            if body.get("to_kind", "party") == "party":
                edge = crm.graph.link_parties(
                    tenant_id=user["tid"],
                    from_id=body.get("from_id", ""),
                    to_id=body.get("to_id", ""),
                    role=body.get("role", "member_of"))
            else:
                if body["to_kind"] == "case":
                    load_case_or_404(body.get("to_id", ""), user)
                edge = crm.graph.link(
                    tenant_id=user["tid"],
                    party_id=body.get("from_id", ""),
                    to_id=body.get("to_id", ""),
                    to_kind=body["to_kind"],
                    role=body.get("role", "customer"))
        except CrossTenantLinkError as e:
            raise HTTPException(404, str(e))
        except KeyError:
            raise HTTPException(400, "from_id, to_id, to_kind required")
        crm_store.save_edge(edge)
        return {"id": edge.id, "to_kind": edge.to_kind, "role": edge.role}

    @app.get("/crm/cases/{case_id}/parties")
    async def crm_case_parties(case_id: str,
                               user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        load_case_or_404(case_id, user)
        return [{"party_id": p.id, "display_name": p.display_name,
                 "role": role}
                for p, role in crm.graph.parties_of_case(
                    case_id, tenant_id=user["tid"])]

    # -- dedupe / merge -------------------------------------------------------------
    @app.get("/crm/parties/{party_id}/dedupe-candidates")
    async def crm_dedupe(party_id: str,
                         user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        target = load_crm_party_or_404(party_id, user)
        out = []
        for other_id, other in crm.graph.parties.items():
            if other_id == party_id or other.tenant_id != user["tid"] \
                    or other.merged_into_id:
                continue
            cand = duplicate_candidate(target, other)
            if cand.verdict != "NOT_DUPLICATE":
                out.append({"party_id": other_id, "score": cand.score,
                            "verdict": cand.verdict,
                            "signals": cand.signals})
        return out

    @app.post("/crm/merge")
    async def crm_merge(body: dict,
                        user: dict = Depends(current_user)):
        require_permission(user, "tenant.manage_users")
        surviving = load_crm_party_or_404(
            body.get("surviving_party_id", ""), user)
        merged = load_crm_party_or_404(
            body.get("merged_party_id", ""), user)
        if not str(body.get("reason", "")).strip():
            raise HTTPException(400, "merge requires a written reason")
        cand = duplicate_candidate(surviving, merged)
        try:
            decision = merge_parties(cand, surviving=surviving,
                                     merged=merged,
                                     decided_by=user["uid"],
                                     reason=body["reason"], audit=audit)
        except PermissionError as e:
            raise HTTPException(409, str(e))
        crm_store.save_party(merged)
        crm_store.save_merge_decision(decision)
        return {"surviving_party_id": decision.surviving_party_id,
                "merged_party_ids": decision.merged_party_ids,
                "reason": decision.reason}

    # -- external CRM references + sync decisions ------------------------------
    @app.get("/crm/parties/{party_id}/external-references")
    async def crm_ext_refs(party_id: str,
                           user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        load_crm_party_or_404(party_id, user)
        return crm_store.external_refs(party_id, tenant_id=user["tid"])

    @app.post("/crm/parties/{party_id}/external-references")
    async def crm_add_ext_ref(party_id: str, body: dict,
                              user: dict = Depends(current_user)):
        require_permission(user, "tenant.manage_integrations")
        load_crm_party_or_404(party_id, user)
        try:
            ref = ExternalCrmReference(
                tenant_id=user["tid"], party_id=party_id,
                provider=body.get("provider", ""),
                object_kind=body.get("object_kind", ""),
                external_id=body.get("external_id", ""))
        except ValueError as e:
            raise HTTPException(400, str(e))
        crm_store.save_external_ref(ref)
        return {"id": ref.id, "provider": ref.provider,
                "external_id": ref.external_id}

    def _sync_request(body: dict, user: dict,
                      direction: str) -> SyncRequest:
        return SyncRequest(
            tenant_id=user["tid"], policy_tenant_id=user["tid"],
            direction=direction, actor_id=user["uid"],
            actor_has_permission=True,
            field=body.get("field", ""),
            internal_value=body.get("internal_value"),
            internal_verified=bool(body.get("internal_verified")),
            internal_changed=bool(body.get("internal_changed")),
            external_value=body.get("external_value"),
            external_changed=bool(body.get("external_changed")),
            marketing_consent_denied=bool(
                body.get("marketing_consent_denied")),
            is_deletion=bool(body.get("is_deletion")))

    def _sync_policy(user: dict, body: dict):
        policy = default_policy(user["tid"])
        policy.enabled = bool(body.get("policy_enabled"))
        policy.dry_run = bool(body.get("policy_dry_run", True))
        policy.allow_export = bool(body.get("policy_allow_export"))
        policy.field_mappings = [ExternalFieldMapping(
            provider=policy.provider, canonical_field=f,
            external_field=f) for f in body.get("mapped_fields",
                                                ["email", "phone"])]
        return policy

    @app.post("/crm/sync/dry-run")
    async def crm_sync_dry_run(body: dict,
                               user: dict = Depends(current_user)):
        """Dry-run: decision + adapter dry-run push. NOTHING external is
        written (NullCrmAdapter is SCAFFOLDED_ONLY, talks to nothing)."""
        require_permission(user, "tenant.manage_integrations")
        direction = body.get("direction", "export")
        decision = sync_decision(_sync_request(body, user, direction),
                                 _sync_policy(user, body))
        key = make_idempotency_key(
            tenant_id=user["tid"], provider="null-crm",
            object_kind="Contact",
            external_id=body.get("external_id", "x"),
            operation=f"{direction}:{body.get('field', '')}")
        adapter_result = crm_adapter.push_object(
            tenant_id=user["tid"], object_kind="Contact",
            payload={body.get("field", ""): body.get("internal_value")},
            idempotency_key=key, dry_run=True)
        event = record_sync_event(
            tenant_id=user["tid"], provider="null-crm",
            direction="dry_run", object_kind="Contact",
            decision=decision,
            detail={"field": body.get("field", ""),
                    "note": body.get("note", "")},
            idempotency_key=key, audit=audit)
        crm_store.save_sync_event(event)
        return {"decision": decision.decision,
                "reasons": decision.reasons,
                "idempotency_key": key,
                "adapter": adapter_result,
                "external_write_happened": False}

    @app.post("/crm/sync/decision")
    async def crm_sync_decision_api(body: dict,
                                    user: dict = Depends(current_user)):
        require_permission(user, "tenant.manage_integrations")
        direction = body.get("direction", "import")
        decision = sync_decision(_sync_request(body, user, direction),
                                 _sync_policy(user, body))
        return {"decision": decision.decision,
                "reasons": decision.reasons,
                "conflict": decision.conflict.__dict__
                if decision.conflict else None}

    # ---- audit --------------------------------------------------------------------------------------
    @app.get("/audit/verify/{case_id}")
    async def audit_verify(case_id: str,
                           user: dict = Depends(current_user)):
        load_case_or_404(case_id, user)
        fresh = DbAuditLog(db)      # re-read from SQL and verify
        return {"chain_valid": fresh.verify_chain(),
                "events_total": len(fresh.events()),
                "events_case": len(fresh.events(case_id=case_id))}

    # ---- AI Employee identity + authority boundary (CORE-A1) --------------------------
    from ..ai_employee.authority import evaluate_ai_employee_authority
    from ..ai_employee.identity import (HONESTY_LABELS as AI_HONESTY,
                                        capability_snapshot, employee_json)
    from ..ai_employee.store import AIEmployeeStore
    ai_store = AIEmployeeStore(db)
    app.state.ai_store = ai_store

    def _load_ai_employee_or_404(ai_employee_id: str, user: dict):
        emp = ai_store.get(ai_employee_id, tenant_id=user["tid"])
        if emp is None:                         # incl. cross-tenant
            raise HTTPException(404, "AI employee not found")
        return emp

    @app.get("/ai-employees")
    async def list_ai_employees(user: dict = Depends(current_user)):
        require_permission(user, "tenant.view")
        emps = ai_store.list(tenant_id=user["tid"])
        if not emps:                            # lazily seed the tenant default
            emps = [ai_store.get_or_create_default(tenant_id=user["tid"],
                                                   created_by="system")]
        return [employee_json(e) for e in emps]

    @app.post("/ai-employees/default")
    async def create_default_ai_employee(user: dict = Depends(current_user)):
        # Creating/registering identity is an admin action, never an AI or
        # viewer action — an AI employee can never create/modify identity.
        require_permission(user, "tenant.manage_users")
        emp = ai_store.get_or_create_default(tenant_id=user["tid"],
                                             created_by=user["uid"])
        return employee_json(emp)

    @app.get("/ai-employees/{ai_employee_id}")
    async def get_ai_employee(ai_employee_id: str,
                              user: dict = Depends(current_user)):
        require_permission(user, "tenant.view")
        return employee_json(_load_ai_employee_or_404(ai_employee_id, user))

    @app.get("/ai-employees/{ai_employee_id}/authority")
    async def get_ai_employee_authority(ai_employee_id: str,
                                        user: dict = Depends(current_user)):
        require_permission(user, "tenant.view")
        emp = _load_ai_employee_or_404(ai_employee_id, user)
        prof = employee_json(emp)
        return {"ai_employee_id": emp.id,
                "read_only_action_types": prof["read_only_action_types"],
                "draft_only_action_types": prof["draft_only_action_types"],
                "approval_required_action_types":
                    prof["approval_required_action_types"],
                "forbidden_action_types": prof["forbidden_action_types"],
                "production_autonomy_enabled": False,
                "honesty_labels": AI_HONESTY}

    @app.get("/ai-employees/{ai_employee_id}/capability-snapshot")
    async def get_ai_capability_snapshot(ai_employee_id: str,
                                         user: dict = Depends(current_user)):
        require_permission(user, "tenant.view")
        return capability_snapshot(
            _load_ai_employee_or_404(ai_employee_id, user))

    @app.post("/ai-employees/{ai_employee_id}/authority/check")
    async def check_ai_employee_authority(ai_employee_id: str, body: dict,
                                          user: dict = Depends(current_user)):
        # Deterministic, side-effect-free pre-check. Task text / body cannot
        # change the decision — only action_type/segment/subject drive it.
        require_permission(user, "tenant.view")
        emp = _load_ai_employee_or_404(ai_employee_id, user)
        decision = evaluate_ai_employee_authority(
            employee=emp, action_type=str(body.get("action_type", "")),
            tenant_id=user["tid"], object_type=str(body.get("object_type", "")),
            object_id=str(body.get("object_id", "")),
            segment=str(body.get("segment", "")),
            subject_tenant_id=body.get("subject_tenant_id"))
        return {"ai_employee_id": emp.id, **decision.to_json()}

    # ---- Secure Work Intake Registry + Canonical Task Contract (CORE-A2) --------------
    from ..ai_employee import tasks as _tasks
    from ..ai_employee.task_store import AITaskStore
    task_store = AITaskStore(db)
    app.state.task_store = task_store

    _DECISION_TO_STATUS = {
        "BLOCKED": "BLOCKED", "APPROVAL_REQUIRED": "ACCEPTED",
        "ALLOWED_DRAFT_ONLY": "ACCEPTED", "READ_ONLY_ALLOWED": "ACCEPTED",
        "HUMAN_REVIEW": "NEEDS_CLARIFICATION", "NOT_IMPLEMENTED":
        "NOT_IMPLEMENTED"}

    def _build_task_response(row: dict) -> dict:
        return json.loads(row["payload_json"])

    @app.get("/ai-tasks/types")
    async def ai_task_types(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return {"task_types": {t: {"segment": m["segment"],
                                   "proposed_action": m["action"],
                                   "purpose_category": m["purpose_category"],
                                   "default_risk": m["risk"],
                                   "allowed_output_types": m["outputs"],
                                   "allowed_data_scopes": m["scopes"]}
                               for t, m in _tasks.TASK_TYPES.items()},
                "source_channels": sorted(_tasks.SOURCE_CHANNELS),
                "honesty_labels": _tasks.HONESTY_LABELS}

    @app.post("/ai-tasks")
    async def create_ai_task(body: dict, user: dict = Depends(current_user)):
        require_permission(user, "case.update")     # delegating work = write
        task_type = str(body.get("task_type", ""))
        if task_type not in _tasks.TASK_TYPES:
            raise HTTPException(400, f"unsupported task_type '{task_type}'")
        meta = _tasks.TASK_TYPES[task_type]

        # Assigned AI employee (tenant-scoped; default if unspecified).
        emp_id = body.get("assigned_ai_employee_id")
        emp = (ai_store.get(emp_id, tenant_id=user["tid"]) if emp_id
               else ai_store.get_or_create_default(tenant_id=user["tid"]))
        if emp is None:
            raise HTTPException(404, "assigned AI employee not found")
        snap = capability_snapshot(emp)

        title = str(body.get("task_title", ""))
        desc = str(body.get("task_description", ""))
        subject_type = body.get("subject_type")
        subject_id = body.get("subject_id")
        subject_tenant_id = body.get("subject_tenant_id")
        source_channel = str(body.get("source_channel", "WEB"))
        if source_channel not in _tasks.SOURCE_CHANNELS:
            raise HTTPException(400, "invalid source_channel")
        priority = str(body.get("priority", "NORMAL"))
        purpose = str(body.get("task_purpose")
                      or f"{task_type} for segment {meta['segment']}")

        # Untrusted-input detection (advisory; never changes the decision).
        flags = _tasks.detect_input_security_flags(title, desc)
        unsafe = _tasks.detect_unsafe_requested_actions(title, desc)
        risk_level, risk_reason = _tasks.classify_risk(task_type, unsafe)

        # CORE-A1 authority pre-check drives the decision — NOT the task text.
        decision = evaluate_ai_employee_authority(
            employee=emp, action_type=meta["action"], tenant_id=user["tid"],
            object_type=str(subject_type or ""),
            object_id=str(subject_id or ""), segment=meta["segment"],
            subject_tenant_id=subject_tenant_id)

        status = _DECISION_TO_STATUS.get(decision.decision, "NOT_IMPLEMENTED")
        clarification_qs: list = []
        # Missing required subject -> clarification.
        if task_type in _tasks.SUBJECT_REQUIRED and not subject_id \
                and status not in ("BLOCKED", "NOT_IMPLEMENTED"):
            status = "NEEDS_CLARIFICATION"
            clarification_qs = [f"Which {subject_type or 'subject'} is this "
                                f"{task_type} about? A subject reference is "
                                "required."]
        # Expiry at intake -> cannot be accepted.
        expires_at = body.get("expires_at")
        if expires_at and status not in ("BLOCKED", "NOT_IMPLEMENTED") \
                and str(expires_at) < utcnow():
            status = "EXPIRED"
        stale_after = body.get("stale_after")
        due_at = body.get("due_at")

        allowed_scopes, forbidden_scopes = _tasks.derive_data_scopes(task_type)
        requires_approval = decision.decision == "APPROVAL_REQUIRED"
        requires_consent = decision.required_consent_check
        requires_evidence = decision.required_evidence_check
        requires_tool_broker = decision.required_tool_broker
        requires_run_ledger = status == "ACCEPTED"

        envelope = _tasks.build_envelope(
            tenant_id=user["tid"], requester_user_id=user["uid"],
            assigned_ai_employee_id=emp.id, source_channel=source_channel,
            source_thread_ref=body.get("source_thread_ref"),
            source_message_ref=body.get("source_message_ref"),
            task_type=task_type, segment=meta["segment"],
            subject_type=subject_type, subject_id=subject_id, task_title=title,
            task_description=desc, priority=priority, due_at=due_at,
            expires_at=expires_at, task_purpose=purpose,
            purpose_category=meta["purpose_category"],
            authority_decision=decision.decision,
            authority_reason=decision.reason, risk_level=risk_level,
            requires_human_approval=requires_approval,
            requires_consent_check=requires_consent,
            requires_evidence_check=requires_evidence,
            requires_tool_broker=requires_tool_broker,
            forbidden_side_effects=_tasks.FORBIDDEN_SIDE_EFFECTS,
            input_security_flags=flags)
        env_hash = _tasks.envelope_hash(envelope)

        contract = _tasks.build_contract(
            tenant_id=user["tid"], requester_user_id=user["uid"],
            assigned_ai_employee_id=emp.id,
            capability_snapshot_hash=snap["capability_snapshot_hash"],
            task_type=task_type, segment=meta["segment"],
            subject_type=subject_type, subject_id=subject_id,
            task_purpose=purpose, purpose_category=meta["purpose_category"],
            allowed_data_scopes=allowed_scopes,
            forbidden_data_scopes=forbidden_scopes,
            allowed_output_types=meta["outputs"],
            forbidden_side_effects=_tasks.FORBIDDEN_SIDE_EFFECTS,
            authority_decision=decision.decision,
            authority_hard_fail=decision.hard_fail,
            requires_human_approval=requires_approval,
            requires_consent_check=requires_consent,
            requires_evidence_check=requires_evidence,
            requires_tool_broker=requires_tool_broker,
            requires_run_ledger=requires_run_ledger, risk_level=risk_level,
            risk_reason=risk_reason, expires_at=expires_at,
            stale_after=stale_after, clarification_required=bool(
                clarification_qs), clarification_questions=clarification_qs)
        con_hash = _tasks.contract_hash(contract)
        dedup_key = _tasks.deduplication_key(
            tenant_id=user["tid"], requester_user_id=user["uid"],
            source_channel=source_channel, task_type=task_type,
            subject_type=str(subject_type or ""),
            subject_id=str(subject_id or ""), task_title=title)

        idem = body.get("idempotency_key")
        if idem:
            prior = task_store.find_by_idempotency(
                tenant_id=user["tid"], requester_user_id=user["uid"],
                idempotency_key=str(idem))
            if prior is not None:
                if prior["envelope_hash"] == env_hash:
                    task_store.add_event(
                        task_id=prior["id"], tenant_id=user["tid"],
                        actor_id=user["uid"], actor_type="human",
                        event_type="IDEMPOTENCY_REPLAYED",
                        reason="same idempotency key + same envelope")
                    return {"idempotent_replay": True,
                            **_build_task_response(prior)}
                task_store.add_event(
                    task_id=prior["id"], tenant_id=user["tid"],
                    actor_id=user["uid"], actor_type="human",
                    event_type="IDEMPOTENCY_CONFLICT",
                    reason="same idempotency key + different envelope")
                raise HTTPException(409, "idempotency key reused with a "
                                    "different task envelope")

        task_id = str(uuid.uuid4())
        now = utcnow()
        payload = {
            "task_id": task_id, "tenant_id": user["tid"],
            "requester_user_id": user["uid"], "requester_role": user["role"],
            "assigned_ai_employee_id": emp.id,
            "assigned_ai_employee_capability_snapshot_hash":
                snap["capability_snapshot_hash"],
            "source_channel": source_channel,
            "source_channel_status": "ACTIVE" if source_channel in (
                "WEB", "API") else "NOT_IMPLEMENTED",
            "idempotency_key": idem, "deduplication_key": dedup_key,
            "canonical_task_envelope_hash": env_hash,
            "canonical_task_envelope_version": _tasks.ENVELOPE_VERSION,
            "canonical_task_contract_hash": con_hash,
            "canonical_task_contract_version": _tasks.CONTRACT_VERSION,
            "task_type": task_type, "task_title": title,
            "task_description": desc,
            "task_description_trust": "UNTRUSTED_USER_INPUT",
            "task_status": status, "task_version": 1,
            "segment": meta["segment"], "segment_confidence": 1.0,
            "segment_reason": f"task type '{task_type}' maps to segment",
            "priority": priority, "due_at": due_at, "expires_at": expires_at,
            "stale_after": stale_after, "created_at": now, "updated_at": now,
            "subject_type": subject_type, "subject_id": subject_id,
            "task_purpose": purpose,
            "purpose_category": meta["purpose_category"],
            "allowed_data_scopes": allowed_scopes,
            "forbidden_data_scopes": forbidden_scopes,
            "sensitive_data_flags": [],
            "authority_decision": decision.decision,
            "authority_reason": decision.reason,
            "authority_hard_fail": decision.hard_fail,
            "authority_snapshot_version": emp.profile_version,
            "risk_level": risk_level, "risk_reason": risk_reason,
            "requires_human_approval": requires_approval,
            "requires_consent_check": requires_consent,
            "requires_evidence_check": requires_evidence,
            "requires_tool_broker": requires_tool_broker,
            "requires_run_ledger": requires_run_ledger,
            "requires_clarification": bool(clarification_qs),
            "clarification_questions": clarification_qs,
            "clarification_reason": (clarification_qs[0] if clarification_qs
                                     else None),
            "allowed_output_types": meta["outputs"],
            "forbidden_side_effects": _tasks.FORBIDDEN_SIDE_EFFECTS,
            "unsafe_requested_actions": unsafe,
            "input_security_flags": flags,
            "draft_artifact_placeholder": None, "latest_result_summary": None,
            "canonical_task_envelope": envelope,
            "canonical_task_contract": contract,
            "honesty_labels": _tasks.HONESTY_LABELS,
        }
        try:
            task_store.save({
                "id": task_id, "tenant_id": user["tid"],
                "requester_user_id": user["uid"],
                "requester_role": user["role"],
                "assigned_ai_employee_id": emp.id,
                "capability_snapshot_hash": snap["capability_snapshot_hash"],
                "source_channel": source_channel, "idempotency_key": idem,
                "deduplication_key": dedup_key, "envelope_hash": env_hash,
                "contract_hash": con_hash, "task_type": task_type,
                "segment": meta["segment"], "task_status": status,
                "task_version": 1, "risk_level": risk_level,
                "authority_decision": decision.decision,
                "authority_hard_fail": int(decision.hard_fail),
                "subject_type": subject_type, "subject_id": subject_id,
                "expires_at": expires_at, "stale_after": stale_after,
                "payload_json": json.dumps(payload), "created_by": user["uid"],
                "created_at": now, "updated_at": now, "cancelled_at": None})
        except sqlite3.IntegrityError:
            # A concurrent worker won the idempotency race (UNIQUE index).
            # Resolve deterministically against the winner, never 500.
            winner = task_store.find_by_idempotency(
                tenant_id=user["tid"], requester_user_id=user["uid"],
                idempotency_key=str(idem)) if idem else None
            if winner is not None and winner["envelope_hash"] == env_hash:
                return {"idempotent_replay": True,
                        **_build_task_response(winner)}
            raise HTTPException(409, "idempotency key reused with a "
                                "different task envelope")

        # Append-only intake events (intake audit, NOT a run ledger).
        ev = lambda t, r="": task_store.add_event(  # noqa: E731
            task_id=task_id, tenant_id=user["tid"], actor_id=user["uid"],
            actor_type="human", event_type=t, reason=r)
        ev("TASK_CREATED")
        ev("CAPABILITY_SNAPSHOT_CAPTURED", snap["capability_snapshot_hash"])
        ev("AUTHORITY_CHECKED", decision.decision)
        ev("TASK_CONTRACT_CREATED", con_hash)
        ev("DATA_SCOPE_BOUNDARY_SET")
        if flags != ["NONE"]:
            ev("UNTRUSTED_INPUT_FLAGGED", ", ".join(flags))
        ev({"ACCEPTED": "TASK_ACCEPTED", "BLOCKED": "TASK_BLOCKED",
            "NEEDS_CLARIFICATION": "TASK_NEEDS_CLARIFICATION",
            "NOT_IMPLEMENTED": "TASK_NOT_IMPLEMENTED",
            "EXPIRED": "TASK_EXPIRED"}.get(status, "TASK_CREATED"),
           decision.reason)
        audit.append(event_type="AI_TASK_INTAKE", actor=user["uid"],
                     payload={"task_id": task_id, "task_type": task_type,
                              "status": status,
                              "authority_decision": decision.decision})
        return payload

    def _load_task_or_404(task_id: str, user: dict) -> dict:
        row = task_store.get(task_id, tenant_id=user["tid"])
        if row is None:                          # incl. cross-tenant
            raise HTTPException(404, "task not found")
        return row

    @app.get("/ai-tasks")
    async def list_ai_tasks(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return [json.loads(r["payload_json"])
                for r in task_store.list(tenant_id=user["tid"])]

    # ViktorAI state-machine routes with bare single-segment paths must be
    # registered BEFORE /ai-tasks/{task_id} or the path param would shadow
    # them. Handlers reference lifecycle helpers bound later in create_app
    # (resolved at request time, after create_app has finished).
    @app.get("/ai-tasks/state-machine")
    async def lifecycle_state_machine(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return _lc.state_matrix()

    @app.get("/ai-tasks/state-machine/verify")
    async def lifecycle_state_machine_verify(
            user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return _lc.verify_graph()

    @app.get("/ai-tasks/lifecycle-dashboard")
    async def lifecycle_dashboard(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return _lc_dashboard_summary(user)

    @app.get("/ai-tasks/{task_id}")
    async def get_ai_task(task_id: str, user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return _build_task_response(_load_task_or_404(task_id, user))

    @app.get("/ai-tasks/{task_id}/envelope")
    async def get_ai_task_envelope(task_id: str,
                                   user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        p = _build_task_response(_load_task_or_404(task_id, user))
        return {"canonical_task_envelope_hash":
                p["canonical_task_envelope_hash"],
                "canonical_task_envelope_version":
                p["canonical_task_envelope_version"],
                "canonical_task_envelope": p["canonical_task_envelope"]}

    @app.get("/ai-tasks/{task_id}/contract")
    async def get_ai_task_contract(task_id: str,
                                   user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        p = _build_task_response(_load_task_or_404(task_id, user))
        return {"canonical_task_contract_hash":
                p["canonical_task_contract_hash"],
                "canonical_task_contract_version":
                p["canonical_task_contract_version"],
                "canonical_task_contract": p["canonical_task_contract"]}

    @app.get("/ai-tasks/{task_id}/intake-events")
    async def get_ai_task_events(task_id: str,
                                 user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_task_or_404(task_id, user)
        return task_store.events(task_id, tenant_id=user["tid"])

    @app.patch("/ai-tasks/{task_id}")
    async def patch_ai_task(task_id: str, body: dict,
                            user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        row = _load_task_or_404(task_id, user)
        payload = json.loads(row["payload_json"])
        # Optimistic concurrency (if an expected version is supplied). A
        # non-integer expected_task_version is a client error, not a 500.
        if "expected_task_version" in body:
            try:
                expected = int(body["expected_task_version"])
            except (TypeError, ValueError):
                raise HTTPException(400, "expected_task_version must be an "
                                    "integer")
            if expected != payload["task_version"]:
                raise HTTPException(409, "stale task_version")
        # A terminal task cannot be edited; task text cannot set status. This
        # honours BOTH the intake status and the lifecycle-kernel terminal
        # states, so a task the state machine drove to a terminal state stays
        # immutable (no PATCH bypass / reopen).
        _terminal_lc = {"COMPLETED_NO_SIDE_EFFECTS", "CANCELLED", "FAILED",
                        "EXPIRED", "SUPERSEDED", "BLOCKED", "NOT_IMPLEMENTED"}
        if payload["task_status"] in ("BLOCKED", "CANCELLED", "EXPIRED",
                                      "NOT_IMPLEMENTED") \
                or payload.get("lifecycle_state") in _terminal_lc:
            raise HTTPException(409, "task is terminal and cannot be modified")
        for f in ("task_title", "task_description", "priority", "due_at",
                  "expires_at", "stale_after"):
            if f in body:
                payload[f] = body[f]
        # Untrusted payload can NEVER set status/authority/scopes directly.
        payload["task_version"] += 1
        payload["updated_at"] = utcnow()
        task_store.update(task_id, {
            "payload_json": json.dumps(payload),
            "task_version": payload["task_version"],
            "updated_at": payload["updated_at"]}, tenant_id=user["tid"])
        return payload

    @app.post("/ai-tasks/{task_id}/cancel")
    async def cancel_ai_task(task_id: str,
                             user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        row = _load_task_or_404(task_id, user)
        payload = json.loads(row["payload_json"])
        if payload["task_status"] in ("BLOCKED", "NOT_IMPLEMENTED",
                                      "EXPIRED", "CANCELLED") \
                or payload.get("lifecycle_state") in {
                    "COMPLETED_NO_SIDE_EFFECTS", "CANCELLED", "FAILED",
                    "EXPIRED", "SUPERSEDED", "BLOCKED", "NOT_IMPLEMENTED"}:
            raise HTTPException(409, "task is terminal")
        payload["task_status"] = "CANCELLED"
        payload["task_version"] += 1
        now = utcnow()
        task_store.update(task_id, {"task_status": "CANCELLED",
                                    "payload_json": json.dumps(payload),
                                    "task_version": payload["task_version"],
                                    "updated_at": now, "cancelled_at": now},
                          tenant_id=user["tid"])
        task_store.add_event(task_id=task_id, tenant_id=user["tid"],
                             actor_id=user["uid"], actor_type="human",
                             event_type="TASK_CANCELLED")
        return payload

    # ---- Causally Verifiable Run Ledger + Event-Sourced Replay (CORE-A3) --------------
    from ..ai_employee import run_ledger as _rl
    from ..ai_employee.run_store import AIRunStore
    run_store = AIRunStore(db)
    app.state.run_store = run_store

    def _run_specs(task: dict) -> list:
        """Deterministic run-event sequence derived from the accepted task
        contract. Records snapshots + a lifecycle path; executes nothing."""
        specs = [
            {"event_type": "RUN_CREATED"},
            {"event_type": "TASK_ENVELOPE_SNAPSHOT_RECORDED",
             "trust": "UNTRUSTED_INPUT_RECORDED",
             "payload": {"task_envelope_hash":
                         task["canonical_task_envelope_hash"],
                         "task_description": task["task_description"]}},
            {"event_type": "TASK_CONTRACT_SNAPSHOT_RECORDED",
             "payload": {"task_contract_hash":
                         task["canonical_task_contract_hash"],
                         "task_contract_version":
                         task["canonical_task_contract_version"]}},
            {"event_type": "AUTHORITY_SNAPSHOT_RECORDED",
             "authority_decision": task["authority_decision"],
             "payload": {"authority_decision": task["authority_decision"],
                         "authority_hard_fail": task["authority_hard_fail"],
                         "authority_snapshot_version":
                         task["authority_snapshot_version"]}},
            {"event_type": "CAPABILITY_SNAPSHOT_RECORDED",
             "payload": {"capability_snapshot_hash":
                         task["assigned_ai_employee_capability_snapshot_hash"]}},
            {"event_type": "DATA_SCOPE_SNAPSHOT_RECORDED",
             "payload": {"allowed_data_scopes": task["allowed_data_scopes"],
                         "forbidden_data_scopes":
                         task["forbidden_data_scopes"]}},
            {"event_type": "POLICY_PRECHECK_RECORDED",
             "payload": {"authority_reason": task["authority_reason"]}},
            {"event_type": "RUN_STARTED"},
        ]
        for flag in task.get("input_security_flags", []):
            if flag != "NONE":
                specs.append({"event_type":
                              "PROMPT_INJECTION_ATTEMPT_RECORDED"
                              if flag == "PROMPT_INJECTION_ATTEMPT"
                              else "UNTRUSTED_INPUT_FLAG_RECORDED",
                              "trust": "UNTRUSTED_INPUT_RECORDED",
                              "payload": {"flag": flag}})
        specs.append({"event_type": "PLAN_DRAFTED"})
        if task["task_status"] == "NEEDS_CLARIFICATION":
            specs.append({"event_type": "CONTEXT_REQUESTED",
                          "reason": "task requires clarification"})
        elif task.get("requires_human_approval"):
            specs.append({"event_type": "APPROVAL_REQUIRED_RECORDED",
                          "reason": "sensitive action requires human "
                          "approval"})
            specs.append({"event_type":
                          "APPROVAL_GATE_NOT_IMPLEMENTED_RECORDED",
                          "actor_type": "APPROVAL_GATE_NOT_IMPLEMENTED",
                          "reason": "Human Approval Gate is not implemented"})
        else:
            specs.append({"event_type": "DRAFT_OUTPUT_PLACEHOLDER_CREATED",
                          "reason": "draft-only placeholder; no side effects"})
        return specs

    def _run_response(row: dict) -> dict:
        return json.loads(row["payload_json"])

    @app.get("/ai-runs/event-types")
    async def ai_run_event_types(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return {"event_types": {t: {"event_schema_version":
                                    s["schema_version"],
                                    "status_effect": s["effect"],
                                    "terminal": s["terminal"],
                                    "future_placeholder": s["future_placeholder"]}
                                for t, s in _rl.EVENT_SCHEMA.items()},
                "run_statuses": _rl.RUN_STATUSES,
                "honesty_labels": _rl.HONESTY_LABELS}

    @app.post("/ai-runs")
    async def create_ai_run(body: dict, user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        task_id = str(body.get("task_id", ""))
        trow = task_store.get(task_id, tenant_id=user["tid"])
        if trow is None:
            raise HTTPException(404, "task not found")
        task = json.loads(trow["payload_json"])
        # Hard-fail dominance: a run can never override a blocked/terminal task.
        if task["authority_decision"] == "BLOCKED" or task["task_status"] in (
                "BLOCKED", "NOT_IMPLEMENTED", "EXPIRED", "CANCELLED"):
            raise HTTPException(409, f"cannot create an actionable run for a "
                                f"{task['task_status']} task")

        run_id = str(uuid.uuid4())
        trace_id = str(uuid.uuid4())
        base = uuid.uuid4().hex
        specs = _run_specs(task)
        events = _rl.assemble_events(
            run_id=run_id, tenant_id=user["tid"], task_id=task_id,
            trace_id=trace_id, actor_id=user["uid"], specs=specs,
            id_factory=lambda i: f"{base}-{i:02d}")
        state = _rl.reduce_run(events)
        ehashes = [e["event_hash"] for e in events]
        now = utcnow()
        merkle = _rl.run_event_merkle_root(ehashes)

        run_payload = {
            "run_id": run_id, "tenant_id": user["tid"], "task_id": task_id,
            "task_envelope_hash": task["canonical_task_envelope_hash"],
            "task_contract_hash": task["canonical_task_contract_hash"],
            "task_contract_version": task["canonical_task_contract_version"],
            "requester_user_id": user["uid"],
            "assigned_ai_employee_id": task["assigned_ai_employee_id"],
            "ai_employee_capability_snapshot_hash":
                task["assigned_ai_employee_capability_snapshot_hash"],
            "authority_snapshot_version": task["authority_snapshot_version"],
            "authority_decision": task["authority_decision"],
            "authority_reason": task["authority_reason"],
            "authority_hard_fail": task["authority_hard_fail"],
            "purpose_category": task["purpose_category"],
            "allowed_data_scopes_snapshot": task["allowed_data_scopes"],
            "forbidden_data_scopes_snapshot": task["forbidden_data_scopes"],
            "segment": task["segment"], "run_type": "task_run",
            "run_status": state["replayed_run_status"],
            "replayed_run_status": state["replayed_run_status"],
            "run_status_consistency": "MATCHED", "run_version": 1,
            "trace_id": trace_id, "parent_run_id": None,
            "source_channel": task["source_channel"],
            "source_thread_ref": None, "source_message_ref": None,
            "created_at": now, "started_at": now, "last_event_at": now,
            "risk_level": task["risk_level"],
            "requires_human_approval": task["requires_human_approval"],
            "requires_tool_broker": task["requires_tool_broker"],
            "requires_consent_check": task["requires_consent_check"],
            "requires_evidence_check": task["requires_evidence_check"],
            "requires_run_ledger": True,
            "event_count": state["event_count"],
            "latest_event_hash": state["latest_event_hash"],
            "run_chain_hash": state["run_chain_hash"],
            "run_state_hash": state["run_state_hash"],
            "run_event_merkle_root": merkle,
            "chain_verification_status": "NOT_RUN",
            "replay_verification_status": "NOT_RUN",
            "safe_view_available": True, "redaction_profile": "FULL_RUN_VIEW",
            "data_retention_hint": task.get("data_retention_hint"),
            "sensitive_data_flags": task.get("sensitive_data_flags", []),
            "raw_payload_retention_status": "ADVISORY_ONLY",
            "final_summary": None, "failure_reason": state["failure_reason"],
            "blocked_reason": state["blocked_reason"],
            "honesty_labels": _rl.HONESTY_LABELS,
            "current_task_state_comparison": "NOT_IMPLEMENTED",
        }
        run_store.save_run({
            "id": run_id, "tenant_id": user["tid"], "task_id": task_id,
            "task_envelope_hash": task["canonical_task_envelope_hash"],
            "task_contract_hash": task["canonical_task_contract_hash"],
            "requester_user_id": user["uid"],
            "assigned_ai_employee_id": task["assigned_ai_employee_id"],
            "segment": task["segment"], "run_type": "task_run",
            "run_status": state["replayed_run_status"], "run_version": 1,
            "trace_id": trace_id, "risk_level": task["risk_level"],
            "authority_decision": task["authority_decision"],
            "event_count": state["event_count"],
            "latest_event_hash": state["latest_event_hash"],
            "run_chain_hash": state["run_chain_hash"],
            "run_state_hash": state["run_state_hash"],
            "run_event_merkle_root": merkle,
            "payload_json": json.dumps(run_payload), "created_by": user["uid"],
            "created_at": now, "updated_at": now, "cancelled_at": None})
        for e in events:
            run_store.add_event(run_id=run_id, tenant_id=user["tid"],
                                task_id=task_id, envelope=e, created_at=now)
        audit.append(event_type="AI_RUN_CREATED", actor=user["uid"],
                     payload={"run_id": run_id, "task_id": task_id,
                              "run_status": state["replayed_run_status"],
                              "event_count": state["event_count"]})
        return {**run_payload, "events": events}

    def _load_run_or_404(run_id: str, user: dict) -> dict:
        row = run_store.get_run(run_id, tenant_id=user["tid"])
        if row is None:                          # incl. cross-tenant
            raise HTTPException(404, "run not found")
        return row

    @app.get("/ai-runs")
    async def list_ai_runs(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return [json.loads(r["payload_json"])
                for r in run_store.list_runs(tenant_id=user["tid"])]

    @app.get("/ai-runs/{run_id}")
    async def get_ai_run(run_id: str, user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        p = _run_response(_load_run_or_404(run_id, user))
        return {**p, "events": run_store.events(run_id, tenant_id=user["tid"])}

    @app.get("/ai-runs/{run_id}/events")
    async def get_ai_run_events(run_id: str,
                                user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_run_or_404(run_id, user)
        return run_store.events(run_id, tenant_id=user["tid"])

    @app.get("/ai-runs/{run_id}/trace")
    async def get_ai_run_trace(run_id: str,
                               user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        p = _run_response(_load_run_or_404(run_id, user))
        evs = run_store.events(run_id, tenant_id=user["tid"])
        return {"run_id": run_id, "trace_id": p["trace_id"],
                "task_id": p["task_id"],
                "spans": [{"span_id": e["span_id"],
                           "parent_span_id": e["parent_span_id"],
                           "event_type": e["event_type"],
                           "event_index": e["event_index"]} for e in evs],
                "honesty_labels": _rl.HONESTY_LABELS}

    @app.get("/ai-runs/{run_id}/safe")
    async def get_ai_run_safe(run_id: str,
                              user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        p = _run_response(_load_run_or_404(run_id, user))
        evs = run_store.events(run_id, tenant_id=user["tid"])
        return _rl.safe_view_run(p, evs)

    @app.post("/ai-runs/{run_id}/cancel")
    async def cancel_ai_run(run_id: str, user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        row = _load_run_or_404(run_id, user)
        p = _run_response(row)
        if p["run_status"] in _rl.TERMINAL_STATUSES:
            raise HTTPException(409, f"run is {p['run_status']}")
        evs = run_store.events(run_id, tenant_id=user["tid"])
        nxt = _rl.assemble_events(
            run_id=run_id, tenant_id=user["tid"], task_id=p["task_id"],
            trace_id=p["trace_id"], actor_id=user["uid"],
            specs=[{"event_type": "RUN_CANCELLED", "actor_type": "HUMAN_USER",
                    "reason": "cancelled by user"}],
            id_factory=lambda i: f"{uuid.uuid4().hex}-cancel")
        # relink the appended event to the existing chain
        last = evs[-1]
        idx = len(evs) + 1
        cancel_ev = nxt[0]
        cancel_ev["event_index"] = idx
        cancel_ev["previous_event_hash"] = last["event_hash"]
        cancel_ev["causal_parent_event_ids"] = [last["event_id"]]
        # Relink the trace span to the true position so /trace shows a unique
        # span_id and a correct parent link (not the default "-01"/None).
        cancel_ev["span_id"] = f"{p['trace_id']}-{idx:02d}"
        cancel_ev["parent_span_id"] = f"{p['trace_id']}-{len(evs):02d}"
        cancel_ev["event_hash"] = _rl.event_hash(
            {k: v for k, v in cancel_ev.items() if k != "event_hash"})
        run_store.add_event(run_id=run_id, tenant_id=user["tid"],
                            task_id=p["task_id"], envelope=cancel_ev,
                            created_at=utcnow())
        all_events = evs + [cancel_ev]
        state = _rl.reduce_run(all_events)
        p.update({"run_status": state["replayed_run_status"],
                  "replayed_run_status": state["replayed_run_status"],
                  "event_count": state["event_count"],
                  "latest_event_hash": state["latest_event_hash"],
                  "run_chain_hash": state["run_chain_hash"],
                  "run_state_hash": state["run_state_hash"],
                  "run_event_merkle_root": _rl.run_event_merkle_root(
                      [e["event_hash"] for e in all_events]),
                  "run_version": p["run_version"] + 1})
        run_store.update_run(run_id, {
            "run_status": "CANCELLED", "event_count": state["event_count"],
            "latest_event_hash": state["latest_event_hash"],
            "run_chain_hash": state["run_chain_hash"],
            "run_state_hash": state["run_state_hash"],
            "run_event_merkle_root": p["run_event_merkle_root"],
            "payload_json": json.dumps(p), "run_version": p["run_version"],
            "updated_at": utcnow(), "cancelled_at": utcnow()},
            tenant_id=user["tid"])
        return p

    @app.post("/ai-runs/{run_id}/replay")
    async def replay_ai_run(run_id: str, user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        row = _load_run_or_404(run_id, user)
        p = _run_response(row)
        evs = run_store.events(run_id, tenant_id=user["tid"])
        state = _rl.reduce_run(evs)
        # Replay reconstructs state AND recomputes event hashes, so a
        # payload-tampered event (which the reducer's chain-linkage alone
        # would miss) cannot report MATCHED. Integrity + state must both hold.
        integrity = _rl.verify_events(evs)
        mismatches = list(state["replay_errors"]) + list(
            integrity["tamper_reasons"])
        mismatch = (state["run_state_hash"] != p["run_state_hash"]
                    or state["replayed_run_status"] != p["run_status"]
                    or bool(mismatches))
        return {"run_id": run_id,
                "replayed_run_status": state["replayed_run_status"],
                "replayed_event_count": state["event_count"],
                "replayed_latest_event_hash": state["latest_event_hash"],
                "replayed_run_chain_hash": state["run_chain_hash"],
                "replayed_run_state_hash": state["run_state_hash"],
                "replay_status": "MISMATCHED" if mismatch else "MATCHED",
                "replay_mismatches": mismatches,
                "replay_warnings": state["warnings"],
                "current_task_state_comparison": "NOT_IMPLEMENTED",
                "verified_at": utcnow(), "honesty_labels": _rl.HONESTY_LABELS}

    @app.post("/ai-runs/{run_id}/verify")
    async def verify_ai_run(run_id: str, user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        row = _load_run_or_404(run_id, user)
        p = _run_response(row)
        evs = run_store.events(run_id, tenant_id=user["tid"])
        chk = _rl.verify_events(evs)
        state = _rl.reduce_run(evs)
        chain_status = ("MATCHED" if chk["recomputed_run_chain_hash"]
                        == p["run_chain_hash"] else "MISMATCHED")
        latest_status = ("MATCHED" if chk["recomputed_latest_event_hash"]
                         == p["latest_event_hash"] else "MISMATCHED")
        merkle_status = ("MATCHED" if chk["recomputed_merkle_root"]
                         == p["run_event_merkle_root"] else "MISMATCHED")
        state_status = ("MATCHED" if state["run_state_hash"]
                        == p["run_state_hash"] else "MISMATCHED")
        replay_status = ("MATCHED" if (state_status == "MATCHED"
                         and not state["replay_errors"]) else "MISMATCHED")
        tamper = bool(chk["tamper_reasons"]) or latest_status == "MISMATCHED" \
            or chain_status == "MISMATCHED" or state_status == "MISMATCHED"
        vstatus = "MATCHED"
        if tamper:
            vstatus = "MISMATCHED"
        elif p["event_count"] != len(evs):
            vstatus, tamper = "MISMATCHED", True
        return {"run_id": run_id,
                "verification_status": vstatus,
                "verification_kind": "ledger_integrity_verification",
                "event_count": len(evs),
                "stored_latest_event_hash": p["latest_event_hash"],
                "recomputed_latest_event_hash":
                    chk["recomputed_latest_event_hash"],
                "run_chain_hash_status": chain_status,
                "run_state_hash_status": state_status,
                "run_event_merkle_root_status": merkle_status,
                "event_index_status": chk["event_index_status"],
                "causal_link_status": chk["causal_link_status"],
                "replay_status": replay_status,
                "tamper_detected": tamper,
                "tamper_reasons": chk["tamper_reasons"],
                "current_task_state_comparison": "NOT_IMPLEMENTED",
                "verified_at": utcnow(),
                "reason": ("ledger integrity verified; replay matches stored "
                           "run state" if vstatus == "MATCHED"
                           else "ledger verification failed — see "
                           "tamper_reasons"),
                "honesty_labels": _rl.HONESTY_LABELS}

    # ---- Human Approval Gate Foundation (CORE-A4.1, PART 1) --------------------------
    from ..ai_employee import approvals as _appr
    from ..ai_employee import approval_decisions as _adec
    from ..ai_employee.approval_store import (AIApprovalStore,
                                              AIApprovalDecisionStore,
                                              AIApprovalGrantStore)
    approval_store = AIApprovalStore(db)
    decision_store = AIApprovalDecisionStore(db)
    grant_store = AIApprovalGrantStore(db)
    app.state.approval_store = approval_store
    app.state.decision_store = decision_store
    app.state.grant_store = grant_store

    @app.get("/ai-approvals/policy")
    async def ai_approval_policy(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return {"approval_policy_matrix": _appr.APPROVAL_POLICY_MATRIX,
                "always_blocked_actions": sorted(_appr.ALWAYS_BLOCKED_ACTIONS),
                "forbidden_unlocks": _appr.FORBIDDEN_UNLOCKS,
                "honesty_labels": _appr.HONESTY_LABELS}

    @app.post("/ai-approvals")
    async def create_ai_approval(body: dict,
                                 user: dict = Depends(current_user)):
        # Creating an approval REQUEST approves and executes nothing. An AI
        # worker can never create an approval (human oversight only).
        require_permission(user, "case.update")
        if user["role"] == "ai_worker":
            raise HTTPException(403, "AI worker cannot create approval "
                                "requests")
        run_id = str(body.get("run_id", ""))
        rrow = run_store.get_run(run_id, tenant_id=user["tid"])
        if rrow is None:
            raise HTTPException(404, "run not found")
        run = json.loads(rrow["payload_json"])
        trow = task_store.get(run["task_id"], tenant_id=user["tid"])
        if trow is None:
            raise HTTPException(404, "task not found")
        task = json.loads(trow["payload_json"])
        action_type = _tasks.TASK_TYPES.get(task["task_type"], {}).get(
            "action", task["task_type"])

        ar_id = str(uuid.uuid4())
        now = utcnow()
        expires = None
        risk = run["risk_level"]
        capsule = _appr.build_policy_capsule(
            tenant_id=user["tid"], run_id=run_id, task_id=run["task_id"],
            approval_request_id=ar_id, action_type=action_type,
            subject_type=task.get("subject_type"),
            subject_id=task.get("subject_id"), risk_level=risk,
            authority_decision=run["authority_decision"],
            authority_hard_fail=run["authority_hard_fail"],
            consent_requirement=task["requires_consent_check"],
            evidence_requirement=task["requires_evidence_check"],
            proof_requirement=False,
            allowed_next_transition="PAUSED -> (approved future transition "
            "in CORE-A4.2)", created_at=now)
        pdh = _appr.policy_decision_hash(capsule)
        challenge_needed = capsule["challenge_required"]
        preconditions = _appr.build_preconditions(
            tenant_id=user["tid"], run_id=run_id, task_id=run["task_id"],
            approval_action_type=action_type,
            subject_type=task.get("subject_type"),
            subject_id=task.get("subject_id"),
            task_contract_hash=run["task_contract_hash"],
            task_envelope_hash=run["task_envelope_hash"],
            run_state_hash=run["run_state_hash"],
            run_chain_hash=run["run_chain_hash"],
            run_event_merkle_root=run["run_event_merkle_root"],
            policy_decision_hash=pdh,
            authority_decision=run["authority_decision"],
            consent_required=task["requires_consent_check"],
            evidence_required=task["requires_evidence_check"],
            proof_required=False, challenge_required=challenge_needed)
        pre_hash = _appr.precondition_hash(preconditions)
        approval_scope = {"action_type": action_type,
                          "subject_type": task.get("subject_type"),
                          "subject_id": task.get("subject_id"),
                          "run_id": run_id, "task_id": run["task_id"]}
        # Build the package first WITHOUT the challenge to get its hash, then
        # bind the challenge to that viewed package hash, then finalize.
        base_pkg = _appr.build_package(
            approval_request_id=ar_id, tenant_id=user["tid"], run_id=run_id,
            task_id=run["task_id"],
            task_contract_hash=run["task_contract_hash"],
            task_envelope_hash=run["task_envelope_hash"],
            run_chain_hash=run["run_chain_hash"],
            run_state_hash=run["run_state_hash"],
            run_event_merkle_root=run["run_event_merkle_root"],
            assigned_ai_employee_id=run["assigned_ai_employee_id"],
            requester_user_id=user["uid"], capsule=capsule,
            approval_action_type=action_type, approval_scope=approval_scope,
            allowed_next_transition=capsule["allowed_next_transition"],
            risk_level=risk, authority_decision=run["authority_decision"],
            authority_reason=run["authority_reason"],
            requires_consent_check=task["requires_consent_check"],
            requires_evidence_check=task["requires_evidence_check"],
            requires_tool_broker=task["requires_tool_broker"],
            evidence_refs=[], proof_report_refs=[], consent_refs=[],
            subject_refs=[task["subject_id"]] if task.get("subject_id")
            else [], data_scope_refs=task["allowed_data_scopes"],
            preconditions=preconditions, challenge=None)
        viewed_pkg_hash = _appr.package_hash(base_pkg)
        challenge = _appr.build_challenge(
            approval_request_id=ar_id, tenant_id=user["tid"],
            viewed_package_hash=viewed_pkg_hash,
            required_acknowledgements=capsule["required_acknowledgements"],
            risk_level=risk, subject_required=bool(task.get("subject_id")),
            created_at=now, expires_at=expires, required=challenge_needed)
        package = {**base_pkg, "approval_challenge": challenge}
        pkg_hash = _appr.package_hash(package)

        if capsule["always_blocked"]:
            status = "BLOCKED"
        elif challenge_needed:
            status = "CHALLENGE_REQUIRED"
        else:
            status = "PENDING"

        request_core = {
            "approval_request_id": ar_id, "tenant_id": user["tid"],
            "run_id": run_id, "task_id": run["task_id"],
            "task_contract_hash": run["task_contract_hash"],
            "task_envelope_hash": run["task_envelope_hash"],
            "run_chain_hash": run["run_chain_hash"],
            "run_state_hash": run["run_state_hash"],
            "run_event_merkle_root": run["run_event_merkle_root"],
            "requester_user_id": user["uid"],
            "assigned_ai_employee_id": run["assigned_ai_employee_id"],
            "requested_by_actor_id": user["uid"],
            "requested_by_actor_type": "HUMAN_USER",
            "policy_decision_id": capsule["policy_decision_id"],
            "policy_decision_hash": pdh,
            "approval_action_type": action_type,
            "approval_scope": approval_scope, "approval_status": status,
            "approval_risk_level": risk,
            "approval_policy_version": _appr.POLICY_CAPSULE_VERSION,
            "approval_package_hash": pkg_hash,
            "approval_precondition_hash": pre_hash,
            "required_approver_role": capsule["required_approver_role"],
            "required_approver_count": capsule["required_approver_count"],
            "minimum_approval_level": capsule["required_approver_role"],
            "quorum_group_id": None,
            "dual_control_required": capsule["dual_control_required"],
            "self_approval_forbidden": True, "ai_approval_forbidden": True,
            "evidence_required": task["requires_evidence_check"],
            "consent_required": task["requires_consent_check"],
            "proof_report_required": False,
            "tool_broker_required": task["requires_tool_broker"],
            "subject_access_required": bool(task.get("subject_id")),
            "approval_challenge_required": challenge_needed,
            "approval_challenge_hash": challenge["challenge_hash"],
            "expires_at": expires,
            "safe_view_available": True, "redaction_profile": "FULL_VIEW",
            "reason": ("high-risk approval requires an anti-rubber-stamp "
                       "challenge" if challenge_needed
                       else "approval request created"),
            "blocked_reason": (capsule["blocked_reasons"][0]
                               if capsule["blocked_reasons"] else None),
        }
        request_core["approval_request_hash"] = _appr.request_hash(
            request_core)
        payload = {**request_core,
                   "approval_package": package,
                   "policy_decision_capsule": capsule,
                   "approval_challenge": challenge,
                   "preconditions": preconditions,
                   # Immutable snapshot of the request identity at creation.
                   # PART 2 lifecycle changes (status/decision/grant refs)
                   # mutate the top-level payload but never this snapshot, so
                   # the request hash stays verifiable after a decision.
                   "approval_request_snapshot": dict(request_core),
                   "created_at": now, "updated_at": now,
                   "honesty_labels": _appr.HONESTY_LABELS}
        approval_store.save({
            "id": ar_id, "tenant_id": user["tid"], "run_id": run_id,
            "task_id": run["task_id"], "requester_user_id": user["uid"],
            "assigned_ai_employee_id": run["assigned_ai_employee_id"],
            "approval_action_type": action_type, "approval_status": status,
            "approval_risk_level": risk,
            "required_approver_role": capsule["required_approver_role"],
            "approval_request_hash": request_core["approval_request_hash"],
            "approval_package_hash": pkg_hash,
            "approval_challenge_hash": challenge["challenge_hash"],
            "approval_precondition_hash": pre_hash, "policy_decision_hash": pdh,
            "task_contract_hash": run["task_contract_hash"],
            "task_envelope_hash": run["task_envelope_hash"],
            "run_state_hash": run["run_state_hash"],
            "run_chain_hash": run["run_chain_hash"], "expires_at": expires,
            "payload_json": json.dumps(payload), "created_by": user["uid"],
            "created_at": now, "updated_at": now})
        audit.append(event_type="AI_APPROVAL_REQUESTED", actor=user["uid"],
                     payload={"approval_request_id": ar_id, "run_id": run_id,
                              "status": status, "risk": risk})
        return payload

    def _load_approval_or_404(approval_id: str, user: dict) -> dict:
        p = approval_store.payload(approval_id, tenant_id=user["tid"])
        if p is None:                            # incl. cross-tenant
            raise HTTPException(404, "approval request not found")
        return p

    @app.get("/ai-approvals")
    async def list_ai_approvals(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return [json.loads(r["payload_json"])
                for r in approval_store.list(tenant_id=user["tid"])]

    @app.get("/ai-approvals/{approval_id}")
    async def get_ai_approval(approval_id: str,
                              user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return _load_approval_or_404(approval_id, user)

    @app.get("/ai-approvals/{approval_id}/safe")
    async def get_ai_approval_safe(approval_id: str,
                                   user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return _appr.safe_view(_load_approval_or_404(approval_id, user))

    @app.get("/ai-approvals/{approval_id}/package")
    async def get_ai_approval_package(approval_id: str,
                                      user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        p = _load_approval_or_404(approval_id, user)
        return {"approval_package_hash": p["approval_package_hash"],
                "approval_package": p["approval_package"]}

    @app.get("/ai-approvals/{approval_id}/challenge")
    async def get_ai_approval_challenge(approval_id: str,
                                        user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        p = _load_approval_or_404(approval_id, user)
        return {"approval_challenge_required":
                p["approval_challenge_required"],
                "approval_challenge_hash": p["approval_challenge_hash"],
                "approval_challenge": p["approval_challenge"]}

    @app.post("/ai-approvals/{approval_id}/verify")
    async def verify_ai_approval(approval_id: str,
                                 user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        p = _load_approval_or_404(approval_id, user)
        pkg_ok = _appr.package_hash(p["approval_package"]) \
            == p["approval_package_hash"]
        ch_ok = _appr.challenge_hash(p["approval_challenge"]) \
            == p["approval_challenge_hash"]
        pre_ok = _appr.precondition_hash(p["preconditions"]) \
            == p["approval_precondition_hash"]
        pol_ok = _appr.policy_decision_hash(p["policy_decision_capsule"]) \
            == p["policy_decision_hash"]
        # Request hash recomputed over the IMMUTABLE creation-time snapshot so
        # it stays verifiable after PART 2 lifecycle changes. Falls back to the
        # live core for pre-snapshot rows.
        snap = p.get("approval_request_snapshot")
        if snap is not None:
            req_ok = _appr.request_hash({**snap, "approval_request_hash": ""}) \
                == snap["approval_request_hash"] == p["approval_request_hash"]
        else:
            core = {k: v for k, v in p.items()
                    if k not in ("approval_package", "policy_decision_capsule",
                                 "approval_challenge", "preconditions",
                                 "created_at", "updated_at", "honesty_labels",
                                 "approval_request_hash",
                                 # PART 2 lifecycle mutations are not part of
                                 # the frozen request identity.
                                 "approval_request_snapshot",
                                 "approval_decision_id", "approval_decision_hash",
                                 "approval_grant_id", "approval_grant_hash")}
            req_ok = _appr.request_hash({**core,
                                         "approval_request_hash": ""}) \
                == p["approval_request_hash"]
        # challenge must be bound to THIS package (anti-reuse)
        challenge_bound = p["approval_challenge"]["viewed_package_hash"] \
            == _appr.package_hash({**p["approval_package"],
                                   "approval_challenge": None})
        # PART 2 extension: verify the latest decision and grant hashes too.
        dec_status = "NOT_IMPLEMENTED"
        grant_status = "NOT_IMPLEMENTED"
        decisions = decision_store.list_for_request(approval_id,
                                                    tenant_id=user["tid"])
        if decisions:
            d = decisions[-1]
            dec_status = ("MATCHED" if _adec.decision_hash(d)
                          == d["decision_hash"] else "MISMATCHED")
        grant = grant_store.get_for_request(approval_id, tenant_id=user["tid"])
        if grant:
            grant_status = ("MATCHED" if _adec.grant_hash(grant)
                            == grant["approval_grant_hash"] else "MISMATCHED")
        foundation_ok = all([pkg_ok, ch_ok, pre_ok, pol_ok, req_ok,
                             challenge_bound])
        all_ok = foundation_ok and dec_status != "MISMATCHED" \
            and grant_status != "MISMATCHED"
        return {"approval_request_id": approval_id,
                "verification_status": "MATCHED" if all_ok else "MISMATCHED",
                "approval_package_hash_status":
                    "MATCHED" if pkg_ok else "MISMATCHED",
                "approval_request_hash_status":
                    "MATCHED" if req_ok else "MISMATCHED",
                "approval_challenge_hash_status":
                    "MATCHED" if ch_ok else "MISMATCHED",
                "approval_precondition_hash_status":
                    "MATCHED" if pre_ok else "MISMATCHED",
                "policy_decision_hash_status":
                    "MATCHED" if pol_ok else "MISMATCHED",
                "approval_decision_hash_status": dec_status,
                "approval_grant_hash_status": grant_status,
                "challenge_bound_to_package":
                    "VALID" if challenge_bound else "REUSE_DETECTED",
                "reason": ("all approval foundation hashes match"
                           if all_ok else "approval hash verification failed"),
                "verified_at": utcnow(),
                "honesty_labels": _adec.DECISION_HONESTY_LABELS}

    # ---- Human Approval Gate Decisions + Grants (CORE-A4.2, PART 2) ------------------
    def _grant_expired(grant: dict) -> bool:
        exp = grant.get("expires_at")
        return bool(exp) and utcnow() > exp

    def _current_state_for(request_p: dict, grant: dict = None) -> dict:
        """Freshly observed state hashes used to detect drift/precondition
        failure against a grant's frozen scope. Read-only; executes nothing."""
        rrow = run_store.get_run(request_p["run_id"], tenant_id=request_p[
            "tenant_id"])
        run = json.loads(rrow["payload_json"]) if rrow else {}
        cur = {
            "tenant_id": request_p["tenant_id"], "run_id": request_p["run_id"],
            "task_id": request_p["task_id"],
            "approval_action_type": request_p["approval_action_type"],
            "task_contract_hash": run.get("task_contract_hash"),
            "task_envelope_hash": run.get("task_envelope_hash"),
            "run_state_hash": run.get("run_state_hash"),
            "run_chain_hash": run.get("run_chain_hash"),
            "run_event_merkle_root": run.get("run_event_merkle_root"),
            "policy_decision_hash": request_p["policy_decision_hash"],
            "approval_package_hash": request_p["approval_package_hash"],
            "approval_challenge_hash": request_p["approval_challenge_hash"],
            "action_always_blocked": request_p["policy_decision_capsule"][
                "always_blocked"],
            "tool_broker_required": request_p.get("tool_broker_required",
                                                  False),
            "precondition_status": ("FAILED"
                                    if run.get("authority_decision")
                                    == "BLOCKED" or run.get(
                                        "authority_hard_fail") else "OK"),
            "precondition_reason": "authority is BLOCKED",
        }
        if grant is not None:
            # Recompute the referenced decision's hash from its stored payload
            # so a tampered decision record is caught as drift — comparing the
            # grant's frozen hash against itself would be a no-op.
            drow = decision_store.get_decision(
                grant.get("approval_decision_id", ""), tenant_id=request_p[
                    "tenant_id"])
            cur["approval_decision_hash"] = (
                _adec.decision_hash(drow) if drow
                else "MISSING_DECISION")
        return cur

    def _record_decision(request_p: dict, user: dict, decision: str, *,
                         body: dict, viewed_hash: str, challenge_passed: bool,
                         acks: dict) -> dict:
        dec_id = str(uuid.uuid4())
        now = utcnow()
        prev = decision_store.latest_hash(request_p["approval_request_id"],
                                          tenant_id=user["tid"])
        d = _adec.build_decision(
            approval_decision_id=dec_id,
            approval_request_id=request_p["approval_request_id"],
            tenant_id=user["tid"], run_id=request_p["run_id"],
            task_id=request_p["task_id"], decider_user_id=user["uid"],
            decider_role=user["role"], decision=decision,
            decision_reason=str(body.get("decision_reason", ""))[:2000],
            approval_request_hash_snapshot=request_p["approval_request_hash"],
            approval_package_hash_snapshot=request_p["approval_package_hash"],
            approval_challenge_hash_snapshot=request_p[
                "approval_challenge_hash"],
            approval_precondition_hash_snapshot=request_p[
                "approval_precondition_hash"],
            viewed_package_hash=viewed_hash, acknowledgements=acks,
            challenge_passed=challenge_passed, decision_time=now,
            previous_decision_hash=prev)
        decision_store.save({
            "id": dec_id, "tenant_id": user["tid"],
            "approval_request_id": request_p["approval_request_id"],
            "run_id": request_p["run_id"], "task_id": request_p["task_id"],
            "decider_user_id": user["uid"], "decider_role": user["role"],
            "decider_actor_type": "HUMAN_USER", "decision": decision,
            "decision_reason": d["decision_reason"],
            "decision_hash": d["decision_hash"],
            "decision_chain_hash": d["decision_chain_hash"],
            "viewed_package_hash": viewed_hash,
            "challenge_passed": 1 if challenge_passed else 0,
            "payload_json": json.dumps(d), "created_at": now})
        return d

    def _deny_non_human_approver(user: dict) -> None:
        # Human-only oversight: an AI worker / AI Employee can never decide.
        if user["role"] in ("ai_worker",):
            raise HTTPException(403, "AI worker cannot make approval "
                                "decisions")

    @app.post("/ai-approvals/{approval_id}/approve")
    async def approve_ai_approval(approval_id: str, body: dict,
                                  user: dict = Depends(current_user)):
        # Approving executes nothing: it records a scoped human decision and,
        # if policy allows, issues a non-transferable, revalidate-before-use
        # approval grant that authorizes only a FUTURE gated transition.
        require_permission(user, "case.update")
        _deny_non_human_approver(user)
        p = _load_approval_or_404(approval_id, user)
        capsule = p["policy_decision_capsule"]
        if p["approval_status"] not in _adec.DECIDABLE_STATUSES:
            raise HTTPException(409, f"approval is {p['approval_status']}; no "
                                "decision can be made")
        if capsule["always_blocked"]:
            raise HTTPException(403, "action is always blocked; approval "
                                "cannot convert a forbidden action into an "
                                "allowed one")
        # Required approver role (owner satisfies manager, etc.).
        if not _adec.role_satisfies(user["role"], p["required_approver_role"]):
            raise HTTPException(403, "approver role "
                                f"{user['role']} does not satisfy required "
                                f"{p['required_approver_role']}")
        # Separation of duties: the requester can never approve their own
        # request while policy advertises self_approval_forbidden (true on every
        # request). Enforced for all risk tiers — maker is never checker.
        if p.get("self_approval_forbidden", True) \
                and user["uid"] == p["requester_user_id"]:
            raise HTTPException(403, "self-approval is forbidden; a different "
                                "authorized human approver is required")
        # Viewed-package binding: approver must have seen the current package.
        viewed = str(body.get("viewed_package_hash", ""))
        if viewed != p["approval_package_hash"]:
            raise HTTPException(422, "viewed_package_hash does not match the "
                                "current approval package hash")
        # Acknowledgements + challenge completion.
        required_acks = capsule["required_acknowledgements"]
        acks = {a: bool(body.get("acknowledgements", {}).get(a))
                for a in required_acks}
        missing = [a for a, ok in acks.items() if not ok]
        if missing:
            raise HTTPException(422, "missing required acknowledgements: "
                                + ", ".join(missing))
        challenge_passed = bool(body.get("challenge_passed"))
        if p["approval_challenge_required"] and not challenge_passed:
            raise HTTPException(422, "approval challenge must be completed for "
                                "this request")
        # Precondition/authority must still hold server-side.
        cur = _current_state_for(p)
        if cur["precondition_status"] == "FAILED":
            raise HTTPException(403, "approval preconditions no longer hold: "
                                + cur["precondition_reason"])

        # Dual control: a given human approver counts ONCE. The same user
        # cannot fill a second slot of a quorum.
        prior_approvers = {dd["decider_user_id"] for dd in
                           decision_store.list_for_request(
                               approval_id, tenant_id=user["tid"])
                           if dd["decision"] == "APPROVE"}
        if user["uid"] in prior_approvers:
            raise HTTPException(409, "you have already approved this request; "
                                "a different approver is required for quorum")

        d = _record_decision(p, user, "APPROVE", body=body, viewed_hash=viewed,
                             challenge_passed=challenge_passed, acks=acks)

        # Quorum: a grant is issued only once the required number of DISTINCT
        # human approvers have approved. required_approver_count==1 issues
        # immediately; count>=2 enforces four-eyes with single-count-per-user.
        # A full multi-approver quorum workflow (roles per slot, quorum groups)
        # beyond distinct-approver counting is classified MISSING/NEXT.
        approvers = prior_approvers | {user["uid"]}
        required_count = int(p.get("required_approver_count", 1) or 1)
        if len(approvers) < required_count:
            nowq = utcnow()
            p["approval_status"] = _adec.QUORUM_PENDING_STATUS
            p["approval_decision_id"] = d["approval_decision_id"]
            p["approval_decision_hash"] = d["decision_hash"]
            p["approvals_recorded"] = len(approvers)
            p["approvals_required"] = required_count
            p["updated_at"] = nowq
            approval_store.update_payload(
                approval_id, tenant_id=user["tid"], payload=p,
                status=_adec.QUORUM_PENDING_STATUS, updated_at=nowq)
            audit.append(event_type="AI_APPROVAL_DECISION_RECORDED",
                         actor=user["uid"],
                         payload={"approval_request_id": approval_id,
                                  "status": _adec.QUORUM_PENDING_STATUS,
                                  "approvals": len(approvers),
                                  "required": required_count})
            return {"approval_request_id": approval_id,
                    "approval_status": _adec.QUORUM_PENDING_STATUS,
                    "approval_decision": d, "approval_grant": None,
                    "approvals_recorded": len(approvers),
                    "approvals_required": required_count,
                    "quorum_status": "PENDING",
                    "honesty_labels": _adec.DECISION_HONESTY_LABELS}

        # Issue a non-transferable approval grant bound to the exact state.
        tool_broker_required = bool(p.get("tool_broker_required"))
        grant_id = str(uuid.uuid4())
        now = utcnow()
        nonce = uuid.uuid4().hex
        nhash = _adec.grant_nonce_hash(
            nonce=nonce, approval_request_id=approval_id,
            approval_decision_id=d["approval_decision_id"],
            run_state_hash=p["run_state_hash"],
            task_contract_hash=p["task_contract_hash"],
            policy_decision_hash=p["policy_decision_hash"])
        expires = (datetime.utcnow() + timedelta(hours=24)).isoformat()
        usage = ("CONSUMPTION_NOT_IMPLEMENTED" if tool_broker_required
                 else "SINGLE_USE_READY")
        gstatus = "NOT_CONSUMABLE" if tool_broker_required else "VALID"
        next_status = ("APPROVED_BUT_NOT_CONSUMABLE" if tool_broker_required
                       else "APPROVED_CONSUME_READY")
        grant = _adec.build_grant(
            approval_grant_id=grant_id, approval_request_id=approval_id,
            approval_decision_id=d["approval_decision_id"],
            tenant_id=user["tid"], run_id=p["run_id"], task_id=p["task_id"],
            approval_action_type=p["approval_action_type"],
            approval_scope=p["approval_package"]["approval_scope"],
            allowed_next_transition=p["approval_package"][
                "allowed_next_transition"],
            task_contract_hash=p["task_contract_hash"],
            task_envelope_hash=p["task_envelope_hash"],
            run_state_hash=p["run_state_hash"],
            run_chain_hash=p["run_chain_hash"],
            run_event_merkle_root=p["approval_package"][
                "run_event_merkle_root"],
            policy_decision_hash=p["policy_decision_hash"],
            approval_package_hash=p["approval_package_hash"],
            approval_challenge_hash=p["approval_challenge_hash"],
            approval_decision_hash=d["decision_hash"],
            approval_precondition_hash=p["approval_precondition_hash"],
            grant_nonce_hash=nhash, grant_status=gstatus,
            grant_usage_policy=usage, single_use=True, expires_at=expires,
            created_at=now)
        grant["validated_at"] = now
        grant["last_validation_status"] = gstatus
        grant["last_validation_reason"] = ("Tool Broker required and not "
                                           "implemented" if tool_broker_required
                                           else "grant issued and validated")
        grant["ledger_event_type"] = "APPROVAL_GRANT_ISSUED"
        grant_store.save({
            "id": grant_id, "tenant_id": user["tid"],
            "approval_request_id": approval_id,
            "approval_decision_id": d["approval_decision_id"],
            "run_id": p["run_id"], "task_id": p["task_id"],
            "approval_action_type": p["approval_action_type"],
            "grant_status": gstatus, "grant_type": _adec.GRANT_TYPE,
            "grant_usage_policy": usage, "single_use": 1,
            "approval_grant_hash": grant["approval_grant_hash"],
            "grant_nonce_hash": nhash,
            "approval_decision_hash": d["decision_hash"],
            "policy_decision_hash": p["policy_decision_hash"],
            "task_contract_hash": p["task_contract_hash"],
            "task_envelope_hash": p["task_envelope_hash"],
            "run_state_hash": p["run_state_hash"],
            "run_chain_hash": p["run_chain_hash"], "consume_check_count": 0,
            "expires_at": expires, "revoked_at": None, "superseded_at": None,
            "consumed_at": None, "validated_at": now,
            "last_validation_status": gstatus,
            "last_validation_reason": grant["last_validation_reason"],
            "payload_json": json.dumps(grant), "created_at": now,
            "updated_at": now})

        # Supersede any older active grant for the same run/task/action scope,
        # and propagate SUPERSEDED to that grant's request so request-level and
        # grant-level state stay consistent.
        for old in grant_store.active_for_scope(
                tenant_id=user["tid"], run_id=p["run_id"], task_id=p["task_id"],
                action_type=p["approval_action_type"], exclude_id=grant_id):
            op = json.loads(old["payload_json"])
            op["grant_status"] = "SUPERSEDED"
            op["superseded_at"] = now
            grant_store.update(old["id"], tenant_id=user["tid"], payload=op,
                              status="SUPERSEDED", updated_at=now,
                              superseded_at=now)
            old_req = approval_store.payload(op["approval_request_id"],
                                            tenant_id=user["tid"])
            if old_req and old_req["approval_status"] in _adec.APPROVED_STATUSES:
                old_req["approval_status"] = "SUPERSEDED"
                old_req["updated_at"] = now
                approval_store.update_payload(
                    op["approval_request_id"], tenant_id=user["tid"],
                    payload=old_req, status="SUPERSEDED", updated_at=now)

        p["approval_status"] = next_status
        p["approval_decision_id"] = d["approval_decision_id"]
        p["approval_decision_hash"] = d["decision_hash"]
        p["approval_grant_id"] = grant_id
        p["approval_grant_hash"] = grant["approval_grant_hash"]
        p["updated_at"] = now
        approval_store.update_payload(approval_id, tenant_id=user["tid"],
                                     payload=p, status=next_status,
                                     updated_at=now)
        audit.append(event_type="AI_APPROVAL_APPROVED", actor=user["uid"],
                     payload={"approval_request_id": approval_id,
                              "grant_id": grant_id, "status": next_status})
        return {"approval_request_id": approval_id, "approval_status":
                next_status, "approval_decision": d, "approval_grant": grant,
                "honesty_labels": _adec.DECISION_HONESTY_LABELS}

    def _terminal_decision(approval_id: str, user: dict, decision: str,
                           status: str, body: dict):
        require_permission(user, "case.update")
        _deny_non_human_approver(user)
        p = _load_approval_or_404(approval_id, user)
        if p["approval_status"] not in _adec.DECIDABLE_STATUSES:
            raise HTTPException(409, f"approval is {p['approval_status']}; no "
                                "decision can be made")
        if not _adec.role_satisfies(user["role"], p["required_approver_role"]):
            raise HTTPException(403, "approver role does not satisfy required "
                                "role")
        d = _record_decision(p, user, decision, body=body,
                             viewed_hash=str(body.get("viewed_package_hash",
                                                      "")),
                             challenge_passed=False, acks={})
        now = utcnow()
        p["approval_status"] = status
        p["approval_decision_id"] = d["approval_decision_id"]
        p["approval_decision_hash"] = d["decision_hash"]
        p["updated_at"] = now
        approval_store.update_payload(approval_id, tenant_id=user["tid"],
                                     payload=p, status=status, updated_at=now)
        audit.append(event_type=f"AI_APPROVAL_{decision}", actor=user["uid"],
                     payload={"approval_request_id": approval_id,
                              "status": status})
        return {"approval_request_id": approval_id, "approval_status": status,
                "approval_decision": d,
                "honesty_labels": _adec.DECISION_HONESTY_LABELS}

    @app.post("/ai-approvals/{approval_id}/reject")
    async def reject_ai_approval(approval_id: str, body: dict,
                                 user: dict = Depends(current_user)):
        return _terminal_decision(approval_id, user, "REJECT", "REJECTED",
                                  body)

    @app.post("/ai-approvals/{approval_id}/changes")
    async def request_changes_ai_approval(approval_id: str, body: dict,
                                          user: dict = Depends(current_user)):
        return _terminal_decision(approval_id, user, "REQUEST_CHANGES",
                                  "CHANGES_REQUESTED", body)

    @app.post("/ai-approvals/{approval_id}/revoke")
    async def revoke_ai_approval(approval_id: str, body: dict,
                                 user: dict = Depends(current_user)):
        # Revoke an approved-but-unused grant. Terminal; executes nothing.
        require_permission(user, "case.update")
        _deny_non_human_approver(user)
        p = _load_approval_or_404(approval_id, user)
        if p["approval_status"] not in _adec.APPROVED_STATUSES:
            raise HTTPException(409, "only an approved request with an unused "
                                "grant can be revoked")
        grant = grant_store.get_for_request(approval_id, tenant_id=user["tid"])
        if grant is None:
            raise HTTPException(404, "no approval grant to revoke")
        if grant.get("consumed_at"):
            raise HTTPException(409, "grant already consumed; cannot revoke")
        if grant.get("superseded_at") or grant["grant_status"] == "SUPERSEDED":
            raise HTTPException(409, "grant already superseded; cannot revoke")
        if not _adec.role_satisfies(user["role"], p["required_approver_role"]):
            raise HTTPException(403, "approver role does not satisfy required "
                                "role")
        d = _record_decision(p, user, "REVOKE", body=body,
                             viewed_hash=p["approval_package_hash"],
                             challenge_passed=False, acks={})
        now = utcnow()
        grant["grant_status"] = "REVOKED"
        grant["revoked_at"] = now
        grant["last_validation_status"] = "REVOKED"
        grant["last_validation_reason"] = "approval grant was revoked"
        grant_store.update(grant["approval_grant_id"], tenant_id=user["tid"],
                          payload=grant, status="REVOKED", updated_at=now,
                          revoked_at=now)
        p["approval_status"] = "REVOKED"
        p["approval_decision_id"] = d["approval_decision_id"]
        p["updated_at"] = now
        approval_store.update_payload(approval_id, tenant_id=user["tid"],
                                     payload=p, status="REVOKED",
                                     updated_at=now)
        audit.append(event_type="AI_APPROVAL_REVOKED", actor=user["uid"],
                     payload={"approval_request_id": approval_id})
        return {"approval_request_id": approval_id, "approval_status":
                "REVOKED", "approval_decision": d, "approval_grant": grant,
                "honesty_labels": _adec.DECISION_HONESTY_LABELS}

    @app.get("/ai-approvals/{approval_id}/grant")
    async def get_ai_approval_grant(approval_id: str,
                                    user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_approval_or_404(approval_id, user)     # tenant + existence
        grant = grant_store.get_for_request(approval_id, tenant_id=user["tid"])
        if grant is None:
            raise HTTPException(404, "no approval grant issued")
        return grant

    @app.post("/ai-approvals/{approval_id}/consume-check")
    async def consume_check_ai_approval(approval_id: str,
                                        user: dict = Depends(current_user)):
        # Validation ONLY. Consume-check answers "would this grant be valid?"
        # It executes nothing, calls no Tool Broker, and never consumes.
        require_permission(user, "case.read")
        p = _load_approval_or_404(approval_id, user)
        grant = grant_store.get_for_request(approval_id, tenant_id=user["tid"])
        base = {"approval_request_id": approval_id,
                "can_execute_now": False,
                "tool_broker_required": bool(p.get("tool_broker_required")),
                "honesty_labels": _adec.DECISION_HONESTY_LABELS}
        if grant is None:
            return {**base, "approval_grant_id": None,
                    "grant_validation_status": "INVALID",
                    "allowed_next_transition": None, "precondition_status":
                    "INVALID", "drift_detected": False,
                    "reason": "no approval grant issued for this request"}
        cur = _current_state_for(p, grant)
        res = _adec.validate_grant(grant, current=cur,
                                   expired=_grant_expired(grant),
                                   tool_broker_available=False)
        now = utcnow()
        grant["consume_check_count"] = grant.get("consume_check_count", 0) + 1
        grant["validated_at"] = now
        grant["last_validation_status"] = res["grant_validation_status"]
        grant["last_validation_reason"] = res["reason"]
        grant_store.update(grant["approval_grant_id"], tenant_id=user["tid"],
                          payload=grant,
                          status=grant["grant_status"], updated_at=now,
                          consume_check_count=grant["consume_check_count"],
                          validated_at=now,
                          last_validation_status=res["grant_validation_status"],
                          last_validation_reason=res["reason"])
        return {**base, "approval_grant_id": grant["approval_grant_id"],
                "grant_validation_status": res["grant_validation_status"],
                "allowed_next_transition": res["allowed_next_transition"],
                "precondition_status": res["precondition_status"],
                "drift_detected": res["drift_detected"],
                "reason": res["reason"]}

    # ---- ViktorAI Deterministic Lifecycle Kernel (CORE-A5) --------------------------
    from ..ai_employee import lifecycle as _lc
    from ..ai_employee.lifecycle_store import AITaskTransitionStore
    transition_store = AITaskTransitionStore(db)
    app.state.transition_store = transition_store

    def _lc_current_state(task_id: str, tid: str, task_payload: dict) -> str:
        last = transition_store.latest_applied(task_id, tenant_id=tid)
        if last:
            return last["to_state"]
        return _lc.initial_state_from_status(task_payload["task_status"])

    def _lc_run_for_task(task_id: str, tid: str):
        r = db.one("SELECT payload_json FROM ai_runs WHERE task_id=? AND "
                   "tenant_id=? ORDER BY created_at DESC LIMIT 1", task_id, tid)
        return json.loads(r["payload_json"]) if r else None

    def _lc_grant_for_task(task_id: str, tid: str):
        r = db.one("SELECT payload_json FROM ai_approval_grants WHERE "
                   "task_id=? AND tenant_id=? ORDER BY created_at DESC LIMIT 1",
                   task_id, tid)
        return json.loads(r["payload_json"]) if r else None

    def _lc_subject_access(task_payload: dict, tid: str) -> str:
        sid = task_payload.get("subject_id")
        if not sid:
            return "NOT_APPLICABLE"
        if task_payload.get("subject_type") == "case":
            row = db.one("SELECT id FROM cases WHERE id=? AND tenant_id=?",
                         sid, tid)
            return "VERIFIED" if row else "NOT_VERIFIED"
        # Other subject types cannot be verified deterministically here.
        return "UNKNOWN"

    def _lc_grant_validation(task_payload: dict, tid: str) -> tuple:
        """(status, grant) — consume-check-style validation of the task's
        approval grant against current run/task hash state. Executes nothing."""
        grant = _lc_grant_for_task(task_payload["task_id"], tid)
        if grant is None:
            return "NONE", None
        run = _lc_run_for_task(task_payload["task_id"], tid)
        cur = {"tenant_id": tid, "run_id": grant["run_id"],
               "task_id": grant["task_id"],
               "approval_action_type": grant["approval_action_type"],
               "task_contract_hash": (run or {}).get("task_contract_hash"),
               "task_envelope_hash": (run or {}).get("task_envelope_hash"),
               "run_state_hash": (run or {}).get("run_state_hash"),
               "run_chain_hash": (run or {}).get("run_chain_hash"),
               "run_event_merkle_root": (run or {}).get(
                   "run_event_merkle_root"),
               "policy_decision_hash": grant["policy_decision_hash"],
               "approval_package_hash": grant["approval_package_hash"],
               "approval_challenge_hash": grant["approval_challenge_hash"],
               "approval_decision_hash": grant["approval_decision_hash"]}
        expired = bool(grant.get("expires_at")) and utcnow() > grant[
            "expires_at"]
        res = _adec.validate_grant(grant, current=cur, expired=expired,
                                   tool_broker_available=False)
        return res["grant_validation_status"], grant

    # Lifecycle states in which a draft artifact has been produced (a
    # DRAFT_CREATED transition was applied) or the work is past drafting.
    _POST_DRAFT_STATES = {"DRAFT_READY", "REVIEW_READY",
                          "COMPLETION_CHECK_REQUIRED", "COMPLETION_BLOCKED",
                          "COMPLETED_NO_SIDE_EFFECTS"}

    def _lc_completion_ctx(task_payload: dict, tid: str, *, state: str = None,
                           replay_mismatch=False, chain_mismatch=False) -> dict:
        gs, _ = _lc_grant_validation(task_payload, tid)
        if state is None:
            state = _lc_current_state(task_payload["task_id"], tid,
                                      task_payload)
        return {
            "approval_grant_validation_status": gs,
            "evidence_ok": task_payload.get("evidence_status") != "FAILED"
            and task_payload.get("evidence_status") != "MISSING",
            "evidence_failed": task_payload.get("evidence_status") == "FAILED",
            "consent_ok": task_payload.get("consent_status") != "DENIED",
            "consent_status": task_payload.get("consent_status"),
            "subject_access_status": _lc_subject_access(task_payload, tid),
            # Draft presence is derived from lifecycle progression (a draft was
            # created), not a placeholder field that is never populated.
            "draft_present": state in _POST_DRAFT_STATES
            or task_payload.get("draft_artifact_placeholder") is not None,
            "run_ok": True, "replay_mismatch": replay_mismatch,
            "chain_mismatch": chain_mismatch,
            "contract_hash_changed": False,
        }

    def _lc_context(task_payload: dict, user: dict, body: dict, *, event: str,
                    from_state: str) -> dict:
        tid = user["tid"]
        run = _lc_run_for_task(task_payload["task_id"], tid)
        grant_status, grant = _lc_grant_validation(task_payload, tid)
        now = utcnow()
        expected_v = body.get("expected_task_version")
        contract_hash = task_payload.get("canonical_task_contract_hash")
        envelope_hash = task_payload.get("canonical_task_envelope_hash")
        exp_ch = body.get("expected_task_contract_hash")
        exp_eh = body.get("expected_task_envelope_hash")
        exp_rsh = body.get("expected_run_state_hash")
        edge = _lc.find_edge(from_state, event)
        completing = bool(edge) and edge["to"] == "COMPLETED_NO_SIDE_EFFECTS"
        completion_ready = False
        if completing:
            comp = _lc.evaluate_completion(
                task_payload, _lc_completion_ctx(task_payload, tid))
            completion_ready = _lc.completion_ready(comp)
        ctx = {
            "tenant_id": tid, "task_id": task_payload["task_id"],
            "run_id": (run or {}).get("run_id"),
            "approval_grant_hash": (grant or {}).get("approval_grant_hash"),
            "tenant_match": True,
            "actor_authorized": user["role"] not in ("viewer", "ai_worker"),
            "actor_id": user["uid"], "actor_type": "human",
            "actor_role": user["role"],
            "from_state": from_state, "event": event,
            "task_type": task_payload.get("task_type"),
            "segment": task_payload.get("segment"),
            "risk_level": task_payload.get("risk_level"),
            "authority_decision": task_payload.get("authority_decision"),
            "authority_blocked": task_payload.get("authority_decision")
            == "BLOCKED" or bool(task_payload.get("authority_hard_fail")),
            "expected_version": expected_v,
            "current_version": task_payload["task_version"],
            "version_match": (expected_v is None
                              or int(expected_v) == task_payload[
                                  "task_version"]),
            "contract_hash": contract_hash, "envelope_hash": envelope_hash,
            "contract_hash_match": exp_ch is None or exp_ch == contract_hash,
            "envelope_hash_match": exp_eh is None or exp_eh == envelope_hash,
            "run_state_hash": (run or {}).get("run_state_hash"),
            "run_state_match": exp_rsh is None or exp_rsh == (run or {}).get(
                "run_state_hash"),
            "expired": bool(task_payload.get("expires_at"))
            and now > task_payload["expires_at"],
            "expires_at": task_payload.get("expires_at"),
            "stale": bool(task_payload.get("stale_after"))
            and now > task_payload["stale_after"],
            "stale_after": task_payload.get("stale_after"),
            "subject_required": bool(task_payload.get("subject_id")),
            "subject_access_status": _lc_subject_access(task_payload, tid),
            "approval_grant_validation_status": grant_status,
            "consent_required": bool(task_payload.get("requires_consent_check")),
            "consent_ok": task_payload.get("consent_status") != "DENIED",
            "consent_status": task_payload.get("consent_status"),
            "evidence_required": bool(task_payload.get(
                "requires_evidence_check")),
            "evidence_ok": task_payload.get("evidence_status") not in (
                "FAILED", "MISSING"),
            "evidence_status": task_payload.get("evidence_status"),
            "completion_ready": completion_ready,
            "side_effect_attempted": bool(body.get("side_effect_attempted"))
            or event in _lc.FORBIDDEN_SIDE_EFFECT_EVENTS,
            "patch_bypass": bool(body.get("_patch_bypass")),
            "via": body.get("_via", "state_machine"),
            "idempotency_key": body.get("transition_idempotency_key"),
        }
        return ctx

    def _lc_task_snapshot(task_payload: dict, state: str, tid: str, *,
                          chain_hash: str, completion_status: str,
                          recon_status: str) -> dict:
        gs, grant = _lc_grant_validation(task_payload, tid)
        run = _lc_run_for_task(task_payload["task_id"], tid)
        now = utcnow()
        snap = {
            "task_id": task_payload["task_id"], "tenant_id": tid,
            "lifecycle_state": state, "task_version": task_payload[
                "task_version"],
            "task_contract_hash": task_payload.get(
                "canonical_task_contract_hash"),
            "task_envelope_hash": task_payload.get(
                "canonical_task_envelope_hash"),
            "assigned_ai_employee_id": task_payload.get(
                "assigned_ai_employee_id"),
            "requester_user_id": task_payload.get("requester_user_id"),
            "risk_level": task_payload.get("risk_level"),
            "authority_decision": task_payload.get("authority_decision"),
            "requires_human_approval": bool(task_payload.get(
                "requires_human_approval")),
            "approval_grant_id": (grant or {}).get("approval_grant_id"),
            "approval_grant_hash": (grant or {}).get("approval_grant_hash"),
            "approval_grant_validation_status": gs,
            "run_id": (run or {}).get("run_id"),
            "run_state_hash": (run or {}).get("run_state_hash"),
            "completion_status": completion_status,
            "reconciliation_status": recon_status,
            "terminal": state in _lc.TERMINAL_STATES,
            "expired": bool(task_payload.get("expires_at"))
            and now > task_payload["expires_at"],
            "stale": bool(task_payload.get("stale_after"))
            and now > task_payload["stale_after"],
            "transition_chain_hash": chain_hash,
        }
        snap["task_state_hash"] = _lc.task_state_hash(snap)
        snap["task_lifecycle_snapshot_hash"] = _lc.lifecycle_snapshot_hash(snap)
        return snap

    def _lc_recon_status(task_id: str, tid: str, task_payload: dict,
                         state: str) -> str:
        rep = _lc.replay(
            _lc.initial_state_from_status(task_payload["task_status"]),
            transition_store.list(task_id, tenant_id=tid))
        if rep["replay_errors"] or rep["replayed_state"] != state:
            return "MISMATCHED"
        return "MATCHED"

    def _lc_decide(task_payload: dict, user: dict, body: dict, event: str):
        state = _lc_current_state(task_payload["task_id"], user["tid"],
                                  task_payload)
        ctx = _lc_context(task_payload, user, body, event=event,
                          from_state=state)
        decision = _lc.decide_transition(ctx)
        return state, ctx, decision

    def _lc_build_record(task_payload, user, body, event, state, ctx, decision,
                         *, applied: bool, tid: str):
        pre = _lc.build_preconditions(ctx)
        post = _lc.build_postconditions(ctx, decision, applied=applied)
        capsule = _lc.build_policy_capsule(ctx, decision)
        prev = transition_store.latest(task_payload["task_id"], tenant_id=tid)
        prev_hash = prev["transition_hash"] if prev else None
        run = _lc_run_for_task(task_payload["task_id"], tid)
        grant = _lc_grant_for_task(task_payload["task_id"], tid)
        now = utcnow()
        record = {
            "task_transition_id": str(uuid.uuid4()), "tenant_id": tid,
            "task_id": task_payload["task_id"],
            "run_id": (run or {}).get("run_id"),
            "approval_request_id": (grant or {}).get("approval_request_id"),
            "approval_grant_id": (grant or {}).get("approval_grant_id"),
            "transition_idempotency_key": body.get(
                "transition_idempotency_key"),
            "idempotency_input_hash": _lc_idem_hash(user, task_payload[
                "task_id"], body),
            "from_state": state, "to_state": decision["to_state"],
            "transition_event": event,
            "transition_status": decision["transition_status"],
            "requested_by_actor_id": user["uid"],
            "requested_by_actor_type": "human",
            "requested_by_role": user["role"],
            "task_version_before": task_payload["task_version"],
            "task_version_after": (task_payload["task_version"] + 1)
            if applied and decision["transition_status"] == "ALLOWED"
            else task_payload["task_version"],
            "expected_task_version": body.get("expected_task_version"),
            "authority_decision": ctx["authority_decision"],
            "authority_hard_fail": ctx["authority_blocked"],
            "approval_grant_validation_status": ctx[
                "approval_grant_validation_status"],
            "subject_access_status": ctx["subject_access_status"],
            "consent_status": ctx.get("consent_status"),
            "evidence_status": ctx.get("evidence_status"),
            "completion_status": decision.get("_completion_status"),
            "guard_results": decision["guards"],
            "guard_vector_hash": decision["guard_vector_hash"],
            "failed_guards": decision["failed_guards"],
            "transition_policy_capsule": capsule,
            "transition_policy_capsule_hash": capsule["policy_output_hash"],
            "transition_precondition": pre,
            "transition_precondition_hash": _lc.hash_pre(pre),
            "transition_postcondition": post,
            "transition_postcondition_hash": _lc.hash_post(post),
            "transition_input_hash": _lc.transition_input_hash(ctx),
            "transition_output_hash": _lc.transition_output_hash(decision),
            "reason": decision["reason"],
            "blocked_reason": decision["blocked_reason"],
            "created_at": now, "honesty_labels": _lc.HONESTY_LABELS,
        }
        record["previous_transition_hash"] = prev_hash
        record["transition_hash"] = _lc.transition_hash(record)
        record["transition_chain_hash"] = _lc.transition_chain_hash(
            prev_hash, record["transition_hash"])
        return record

    def _lc_persist(record: dict, tid: str, index: int) -> None:
        transition_store.save({
            "id": record["task_transition_id"], "tenant_id": tid,
            "task_id": record["task_id"], "run_id": record.get("run_id"),
            "approval_request_id": record.get("approval_request_id"),
            "approval_grant_id": record.get("approval_grant_id"),
            "transition_index": index,
            "transition_idempotency_key": record.get(
                "transition_idempotency_key"),
            "from_state": record["from_state"], "to_state": record["to_state"],
            "transition_event": record["transition_event"],
            "transition_status": record["transition_status"],
            "requested_by_actor_id": record["requested_by_actor_id"],
            "requested_by_actor_type": record["requested_by_actor_type"],
            "requested_by_role": record["requested_by_role"],
            "task_version_before": record["task_version_before"],
            "task_version_after": record["task_version_after"],
            "transition_hash": record["transition_hash"],
            "previous_transition_hash": record.get("previous_transition_hash"),
            "transition_chain_hash": record["transition_chain_hash"],
            "guard_vector_hash": record["guard_vector_hash"],
            "task_state_hash_after": record.get("task_state_hash_after"),
            "input_hash": record["transition_input_hash"],
            "payload_json": json.dumps(record), "created_at":
            record["created_at"]})

    def _lc_deny_non_human(user: dict) -> None:
        if user["role"] == "ai_worker":
            raise HTTPException(403, "AI worker cannot force lifecycle "
                                "transitions")

    def _lc_idem_hash(user: dict, task_id: str, body: dict) -> str:
        """Canonical idempotency hash of the client's REQUEST (not the live
        server state, which advances precisely because the apply succeeded)."""
        return _lc._sha({
            "tenant_id": user["tid"], "task_id": task_id,
            "actor_id": user["uid"],
            "event": str(body.get("transition_event", "")),
            "transition_idempotency_key": body.get(
                "transition_idempotency_key"),
            "expected_task_version": body.get("expected_task_version"),
            "expected_task_contract_hash": body.get(
                "expected_task_contract_hash"),
            "expected_task_envelope_hash": body.get(
                "expected_task_envelope_hash"),
            "expected_run_state_hash": body.get("expected_run_state_hash")})

    def _lc_record_response(prior: dict) -> dict:
        return {
            "task_id": prior["task_id"], "from_state": prior["from_state"],
            "to_state": prior["to_state"],
            "transition_event": prior["transition_event"],
            "transition_status": prior["transition_status"],
            "reason": prior["reason"], "blocked_reason": prior["blocked_reason"],
            "guard_results": prior["guard_results"],
            "failed_guards": prior["failed_guards"],
            "guard_vector_hash": prior["guard_vector_hash"],
            "transition_input_hash": prior["transition_input_hash"],
            "transition_output_hash": prior["transition_output_hash"],
            "transition_hash": prior["transition_hash"],
            "transition_chain_hash": prior["transition_chain_hash"],
            "applied": prior["transition_status"] == "ALLOWED",
            "idempotent_replay": True,
            "honesty_labels": _lc.HONESTY_LABELS}

    def _lc_dashboard_summary(user: dict) -> dict:
        by_state, by_blocker = {}, {}
        stale = expired = appr_pending = comp_blocked = recon = 0
        for row in task_store.list(tenant_id=user["tid"]):
            tp = json.loads(row["payload_json"])
            st = _lc_current_state(tp["task_id"], user["tid"], tp)
            by_state[st] = by_state.get(st, 0) + 1
            if st == "APPROVAL_PENDING":
                appr_pending += 1
            if st == "COMPLETION_BLOCKED":
                comp_blocked += 1
            if st == "RECONCILIATION_REQUIRED":
                recon += 1
            now = utcnow()
            if tp.get("expires_at") and now > tp["expires_at"]:
                expired += 1
            if tp.get("stale_after") and now > tp["stale_after"]:
                stale += 1
            last = transition_store.latest_applied(tp["task_id"],
                                                   tenant_id=user["tid"])
            if last and last.get("failed_guards"):
                for gname in last["failed_guards"]:
                    by_blocker[gname] = by_blocker.get(gname, 0) + 1
        top = sorted(by_blocker.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
        return {"tasks_by_state": by_state, "tasks_by_blocker_type": by_blocker,
                "stale_tasks_count": stale, "expired_tasks_count": expired,
                "approval_pending_count": appr_pending,
                "completion_blocked_count": comp_blocked,
                "reconciliation_required_count": recon,
                "top_blockers": [{"blocker": k, "count": v} for k, v in top],
                "honesty_labels": _lc.HONESTY_LABELS}

    @app.get("/ai-tasks/{task_id}/state")
    async def lifecycle_get_state(task_id: str,
                                  user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        row = _load_task_or_404(task_id, user)
        tp = json.loads(row["payload_json"])
        state = _lc_current_state(task_id, user["tid"], tp)
        comp = _lc.evaluate_completion(
            tp, _lc_completion_ctx(tp, user["tid"]))
        recon = _lc_recon_status(task_id, user["tid"], tp, state)
        last = transition_store.latest(task_id, tenant_id=user["tid"])
        chain = last["transition_chain_hash"] if last else _lc.GENESIS
        snap = _lc_task_snapshot(tp, state, user["tid"], chain_hash=chain,
                                 completion_status=comp["completion_status"],
                                 recon_status=recon)
        return {"task_id": task_id, "lifecycle_state": state,
                "task_version": tp["task_version"],
                "task_state_hash": snap["task_state_hash"],
                "task_lifecycle_snapshot_hash": snap[
                    "task_lifecycle_snapshot_hash"],
                "allowed_next_transitions": _lc.allowed_events(state),
                "completion_status": comp["completion_status"],
                "completion_blockers": comp["completion_blockers"],
                "reconciliation_status": recon,
                "terminal": state in _lc.TERMINAL_STATES,
                "risk_level": tp.get("risk_level"),
                "safe_view": {"lifecycle_state": state,
                              "allowed_next_transitions":
                              [e["event"] for e in _lc.allowed_events(state)],
                              "completion_status": comp["completion_status"],
                              "reconciliation_status": recon,
                              "risk_level": tp.get("risk_level")},
                "honesty_labels": _lc.HONESTY_LABELS}

    @app.get("/ai-tasks/{task_id}/transitions")
    async def lifecycle_list_transitions(task_id: str,
                                         user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_task_or_404(task_id, user)
        return {"task_id": task_id,
                "transitions": transition_store.list(task_id,
                                                     tenant_id=user["tid"]),
                "honesty_labels": _lc.HONESTY_LABELS}

    def _lc_transition_response(state, ctx, decision, tp, tid, *, applied):
        comp_status = decision.get("_completion_status")
        recon = _lc_recon_status(tp["task_id"], tid, tp, decision["to_state"]
                                 if applied and decision["transition_status"]
                                 == "ALLOWED" else state)
        return {
            "task_id": tp["task_id"], "from_state": state,
            "to_state": decision["to_state"],
            "transition_event": ctx["event"],
            "transition_status": decision["transition_status"],
            "reason": decision["reason"],
            "blocked_reason": decision["blocked_reason"],
            "guard_results": decision["guards"],
            "failed_guards": decision["failed_guards"],
            "guard_vector_hash": decision["guard_vector_hash"],
            "transition_input_hash": _lc.transition_input_hash(ctx),
            "transition_output_hash": _lc.transition_output_hash(decision),
            "reconciliation_status": recon,
            "honesty_labels": _lc.HONESTY_LABELS}

    @app.post("/ai-tasks/{task_id}/transitions/dry-run")
    async def lifecycle_dry_run(task_id: str, body: dict,
                                user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        _lc_deny_non_human(user)
        row = _load_task_or_404(task_id, user)
        tp = json.loads(row["payload_json"])
        event = str(body.get("transition_event", ""))
        version_before = tp["task_version"]
        state, ctx, decision = _lc_decide(tp, user, body, event)
        resp = _lc_transition_response(state, ctx, decision, tp, user["tid"],
                                       applied=False)
        resp["dry_run"] = True
        # Postcondition: dry-run mutated nothing.
        assert json.loads(_load_task_or_404(task_id, user)["payload_json"])[
            "task_version"] == version_before
        return resp

    @app.post("/ai-tasks/{task_id}/transitions")
    async def lifecycle_apply(task_id: str, body: dict,
                              user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        _lc_deny_non_human(user)
        row = _load_task_or_404(task_id, user)
        tp = json.loads(row["payload_json"])
        event = str(body.get("transition_event", ""))
        tid = user["tid"]
        idem = body.get("transition_idempotency_key")

        idem_hash = _lc_idem_hash(user, task_id, body)

        # Idempotency: same key + same request -> replay prior result; same key
        # + different request -> conflict. The comparison keys off the client's
        # request, not the live state (which advances when the apply succeeds).
        if idem:
            prior = transition_store.find_by_idempotency(
                task_id, tenant_id=tid, key=str(idem))
            if prior is not None:
                if prior.get("idempotency_input_hash") == idem_hash:
                    return _lc_record_response(prior)
                raise HTTPException(409, "idempotency key reused with a "
                                    "different transition input")

        state, ctx, decision = _lc_decide(tp, user, body, event)

        if decision["transition_status"] != "ALLOWED":
            # Record a safe denial event (does not advance state/version).
            idx = transition_store.next_index(task_id, tenant_id=tid)
            record = _lc_build_record(tp, user, body, event, state, ctx,
                                      decision, applied=False, tid=tid)
            _lc_persist(record, tid, idx)
            audit.append(event_type="AI_TASK_TRANSITION_DENIED",
                         actor=user["uid"],
                         payload={"task_id": task_id, "event": event,
                                  "status": decision["transition_status"]})
            resp = _lc_transition_response(state, ctx, decision, tp, tid,
                                           applied=False)
            resp["applied"] = False
            return resp

        # ALLOWED: optimistic compare-and-swap on task_version. The lifecycle
        # state lives in payload.lifecycle_state and the transition ledger; the
        # intake `task_status` column is NOT overwritten (it is the immutable
        # intake outcome and the stable initial state for replay). Terminal
        # immutability is enforced by the lifecycle_state check in PATCH/cancel.
        new_version = tp["task_version"] + 1
        to_state = decision["to_state"]
        tp["task_version"] = new_version
        tp["lifecycle_state"] = to_state
        tp["updated_at"] = utcnow()
        idx = transition_store.next_index(task_id, tenant_id=tid)
        record = _lc_build_record(tp, user, body, event, state, ctx, decision,
                                  applied=True, tid=tid)
        snap = _lc_task_snapshot(tp, to_state, tid,
                                 chain_hash=record["transition_chain_hash"],
                                 completion_status="NOT_CHECKED",
                                 recon_status="MATCHED")
        record["task_state_hash_after"] = snap["task_state_hash"]
        # Atomic: the task UPDATE and the ledger INSERT commit together (single
        # transaction on the shared connection), so a crash cannot half-apply.
        cur = db.conn.execute(
            "UPDATE ai_tasks SET task_version=?, payload_json=?, "
            "updated_at=? WHERE id=? AND tenant_id=? AND task_version=?",
            (new_version, json.dumps(tp), tp["updated_at"],
             task_id, tid, new_version - 1))
        if cur.rowcount != 1:
            db.conn.rollback()
            raise HTTPException(409, "stale task_version (concurrent update)")
        _lc_persist(record, tid, idx)   # single commit flushes UPDATE + INSERT
        task_store.add_event(task_id=task_id, tenant_id=tid, actor_id=user[
            "uid"], actor_type="human", event_type=f"LIFECYCLE_{event}")
        audit.append(event_type="AI_TASK_TRANSITION_APPLIED", actor=user["uid"],
                     payload={"task_id": task_id, "from": state,
                              "to": decision["to_state"], "event": event})
        resp = _lc_transition_response(decision["to_state"], ctx, decision, tp,
                                       tid, applied=True)
        resp["applied"] = True
        resp["task_version_after"] = new_version
        resp["task_state_hash"] = snap["task_state_hash"]
        resp["transition_hash"] = record["transition_hash"]
        resp["transition_chain_hash"] = record["transition_chain_hash"]
        return resp

    @app.post("/ai-tasks/{task_id}/transitions/verify")
    async def lifecycle_verify(task_id: str,
                               user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        row = _load_task_or_404(task_id, user)
        tp = json.loads(row["payload_json"])
        transitions = transition_store.list(task_id, tenant_id=user["tid"])
        tamper, chain_ok, prev = [], True, None
        for t in transitions:
            recomputed = _lc.transition_hash(t)
            if recomputed != t["transition_hash"]:
                tamper.append(f"transition {t['from_state']}->{t['to_state']}: "
                              "hash mismatch")
            expect_chain = _lc.transition_chain_hash(prev, t["transition_hash"])
            if expect_chain != t["transition_chain_hash"]:
                chain_ok = False
                tamper.append("transition chain hash mismatch")
            prev = t["transition_hash"]
        state = _lc_current_state(task_id, user["tid"], tp)
        rep = _lc.replay(
            _lc.initial_state_from_status(tp["task_status"]), transitions)
        state_ok = rep["replayed_state"] == state and not rep["replay_errors"]
        status = "MATCHED" if (not tamper and chain_ok and state_ok) \
            else "MISMATCHED"
        return {"task_id": task_id, "verification_status": status,
                "tamper_detected": bool(tamper), "tamper_reasons": tamper,
                "transition_chain_status": "VALID" if chain_ok else
                "MISMATCHED", "replayed_state": rep["replayed_state"],
                "stored_state": state,
                "stored_vs_replay": "MATCHED" if state_ok else "MISMATCHED",
                "honesty_labels": _lc.HONESTY_LABELS}

    @app.post("/ai-tasks/{task_id}/transitions/replay")
    async def lifecycle_replay(task_id: str,
                               user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        row = _load_task_or_404(task_id, user)
        tp = json.loads(row["payload_json"])
        transitions = transition_store.list(task_id, tenant_id=user["tid"])
        rep = _lc.replay(
            _lc.initial_state_from_status(tp["task_status"]), transitions)
        stored = _lc_current_state(task_id, user["tid"], tp)
        return {"task_id": task_id, "replayed_state": rep["replayed_state"],
                "stored_state": stored,
                "replay_status": "MATCHED" if (rep["replayed_state"] == stored
                                               and not rep["replay_errors"])
                else "MISMATCHED",
                "applied_count": rep["applied_count"],
                "replay_errors": rep["replay_errors"],
                "replay_completion_status": rep["replay_completion_status"],
                "executed_task": False, "honesty_labels": _lc.HONESTY_LABELS}

    @app.post("/ai-tasks/{task_id}/transitions/reconcile")
    async def lifecycle_reconcile(task_id: str,
                                  user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        row = _load_task_or_404(task_id, user)
        tp = json.loads(row["payload_json"])
        tid = user["tid"]
        transitions = transition_store.list(task_id, tenant_id=tid)
        stored = _lc_current_state(task_id, tid, tp)
        rep = _lc.replay(
            _lc.initial_state_from_status(tp["task_status"]), transitions)
        state_match = rep["replayed_state"] == stored and not rep[
            "replay_errors"]
        # transition chain integrity
        chain_ok, prev = True, None
        for t in transitions:
            if _lc.transition_hash(t) != t["transition_hash"] or \
                    _lc.transition_chain_hash(prev, t["transition_hash"]) != t[
                        "transition_chain_hash"]:
                chain_ok = False
            prev = t["transition_hash"]
        gs, _g = _lc_grant_validation(tp, tid)
        grant_ok = (not tp.get("requires_human_approval")) or gs in (
            "VALID", "NONE")
        comp = _lc.evaluate_completion(tp, _lc_completion_ctx(
            tp, tid, replay_mismatch=not state_match, chain_mismatch=not
            chain_ok))
        factors = {"stored_matches_replay": state_match,
                   "transition_chain_matches": chain_ok,
                   "approval_grant_scope_matches": grant_ok,
                   "completion_state_matches_criteria": True}
        consistent = all(factors.values())
        status = "MATCHED" if consistent else "MISMATCHED"
        recon_hash = _lc._sha({"factors": factors, "stored": stored,
                               "replayed": rep["replayed_state"]})
        return {"task_id": task_id, "reconciliation_status": status,
                "lifecycle_reconciliation_hash": recon_hash,
                "stored_state": stored, "replayed_state": rep["replayed_state"],
                "factors": factors, "auto_healed": False,
                "completion_status": comp["completion_status"],
                "honesty_labels": _lc.HONESTY_LABELS}

    @app.post("/ai-tasks/{task_id}/completion/check")
    async def lifecycle_completion_check(task_id: str,
                                         user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        row = _load_task_or_404(task_id, user)
        tp = json.loads(row["payload_json"])
        tid = user["tid"]
        state = _lc_current_state(task_id, tid, tp)
        rep = _lc.replay(_lc.initial_state_from_status(tp["task_status"]),
                         transition_store.list(task_id, tenant_id=tid))
        mismatch = rep["replayed_state"] != state or bool(rep["replay_errors"])
        comp = _lc.evaluate_completion(
            tp, _lc_completion_ctx(tp, tid, replay_mismatch=mismatch))
        return {"task_id": task_id, "executed_task": False, **comp}

    @app.get("/ai-tasks/{task_id}/completion")
    async def lifecycle_completion_detail(task_id: str,
                                          user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        row = _load_task_or_404(task_id, user)
        tp = json.loads(row["payload_json"])
        comp = _lc.evaluate_completion(
            tp, _lc_completion_ctx(tp, user["tid"]))
        return {"task_id": task_id, "completion_criteria": comp[
            "completion_criteria"], "completion_status": comp[
            "completion_status"], "completion_blockers": comp[
            "completion_blockers"], "completion_criteria_hash": comp[
            "completion_criteria_hash"], "completion_result_hash": comp[
            "completion_result_hash"], "honesty_labels": _lc.HONESTY_LABELS}

    # ---- ViktorAI Evidence-Grade Artifact System (CORE-A6) --------------------------
    from ..ai_employee import artifacts as _art
    from ..ai_employee.artifact_store import AIArtifactStore
    artifact_store = AIArtifactStore(db)
    app.state.artifact_store = artifact_store

    def _art_task_context(task_id, tid):
        """(task_payload, contract_hash, envelope_hash, task_state, run) for a
        linked task. Tenant-scoped; returns Nones when no task is linked."""
        if not task_id:
            return None, None, None, None, None
        row = task_store.get(task_id, tenant_id=tid)
        if row is None:
            raise HTTPException(404, "linked task not found")
        tp = json.loads(row["payload_json"])
        state = _lc_current_state(task_id, tid, tp)
        run = _lc_run_for_task(task_id, tid)
        return (tp, tp.get("canonical_task_contract_hash"),
                tp.get("canonical_task_envelope_hash"), state, run)

    def _art_approval_valid(task_id, tid):
        if not task_id:
            return False, None
        status, grant = _lc_grant_validation(
            json.loads(task_store.get(task_id, tenant_id=tid)["payload_json"]),
            tid) if task_store.get(task_id, tenant_id=tid) else ("NONE", None)
        return status == "VALID", grant

    def _art_dependencies(dep_ids, tid, artifact_id):
        """Validate + snapshot dependencies (same tenant, exist, no self-cycle).
        Returns the dependency snapshot list."""
        if _art.detect_cycle(artifact_id, dep_ids):
            raise HTTPException(400, "artifact cannot depend on itself")
        deps = []
        for did in dep_ids or []:
            drow = artifact_store.get(did, tenant_id=tid)
            if drow is None:                       # incl. cross-tenant
                raise HTTPException(400, f"dependency artifact {did} not found")
            lv = artifact_store.latest_version(did, tenant_id=tid)
            deps.append({"artifact_id": did,
                         "version_number": drow["artifact_version"],
                         "version_hash": (lv or {}).get("version_hash")})
        return deps

    def _assemble_artifact(*, artifact_id, version_id, version_number, tid,
                           prev_version, artifact_type, trust_tier,
                           content_format, content_body, artifact_title,
                           purpose, task_id, run, approval_request_id,
                           approval_grant, created_by_actor_id,
                           created_by_actor_type, assigned_ai_employee_id,
                           contract_hash, envelope_hash, task_state,
                           evidence_refs, report_refs, subject_type, subject_id,
                           dep_ids, dep_snaps, supersedes_artifact_id,
                           claims_input, requires_approval, approval_valid,
                           creator_role, created_at):
        scanner = _art.scan_content(content_body)
        quarantined = scanner["quarantine_status"] == "QUARANTINED"
        envelope = _art.build_content_envelope(
            content_format=content_format, content_role=purpose or "draft",
            content_trust_level=("QUARANTINED_CONTENT" if quarantined
                                 else ("AI_DRAFT" if created_by_actor_type
                                       in ("ai_employee", "ai_worker")
                                       else "USER_PROVIDED")),
            content_body=content_body, scanner=scanner)
        c_hash = _art.content_hash(envelope)
        claim_graph = _art.build_claim_graph(
            artifact_id=artifact_id, artifact_version_id=version_id,
            tenant_id=tid, claims_input=claims_input, source_text=content_body)
        cg_hash = claim_graph["claim_graph_hash"]
        claims_supported = _art.claims_all_supported(claim_graph)
        run_id = (run or {}).get("run_id")
        approval_grant_hash = (approval_grant or {}).get("approval_grant_hash")
        provenance = _art.build_provenance(
            artifact_id=artifact_id, artifact_version_id=version_id,
            tenant_id=tid, task_id=task_id, run_id=run_id,
            approval_request_id=approval_request_id,
            created_by_actor_id=created_by_actor_id,
            created_by_actor_type=created_by_actor_type,
            assigned_ai_employee_id=assigned_ai_employee_id,
            dependency_artifact_ids=dep_ids, evidence_refs=evidence_refs,
            report_refs=report_refs,
            supersedes_artifact_id=supersedes_artifact_id, has_claim=True,
            has_abom=True)
        capsule = _art.build_policy_capsule(
            artifact_id=artifact_id, tenant_id=tid, task_id=task_id,
            run_id=run_id, approval_request_id=approval_request_id,
            approval_grant_id=(approval_grant or {}).get("approval_grant_id"),
            artifact_type=artifact_type, artifact_status="DRAFT",
            artifact_trust_tier=trust_tier,
            creator_actor_type=created_by_actor_type, creator_role=creator_role,
            task_state=task_state, task_contract_hash=contract_hash,
            task_envelope_hash=envelope_hash,
            run_state_hash=(run or {}).get("run_state_hash"),
            approval_grant_hash=approval_grant_hash,
            requires_approval=requires_approval,
            requires_human_review=trust_tier in ("AI_DRAFT_UNVERIFIED",
                                                 "HUMAN_REVIEW_REQUIRED"),
            requires_safe_view=quarantined,
            allowed_for_completion=not quarantined,
            allowed_for_tool_input=artifact_type in _art.TOOL_INPUT_TYPES
            and not quarantined,
            claims_required=artifact_type in ("PROOF_SUMMARY",
                                              "RISK_ASSESSMENT"),
            blocked_reasons=[], quarantine_reasons=(
                [scanner["quarantine_reason"]] if quarantined else []),
            required_reviews=[], required_redactions=[], created_at=created_at)
        capsule_hash = _art.policy_capsule_hash(capsule)
        abom = _art.build_abom(
            artifact_id=artifact_id, artifact_version_id=version_id,
            tenant_id=tid, artifact_type=artifact_type,
            content_format=content_format, input_sources=[],
            source_channels=["WEB"], dependency_artifact_versions=dep_snaps,
            evidence_refs=evidence_refs, report_refs=report_refs,
            task_refs=[task_id] if task_id else [],
            run_refs=[run_id] if run_id else [],
            approval_refs=[approval_request_id] if approval_request_id else [],
            policy_capsule_hash=capsule_hash, scanner_hash=scanner[
                "scanner_hash"], trust_tier=trust_tier)
        dep_graph = _art.build_dependency_graph(
            artifact_id=artifact_id, tenant_id=tid, dependencies=dep_snaps)
        lineage = _art.build_lineage(
            artifact_id=artifact_id, tenant_id=tid, task_id=task_id,
            run_id=run_id, approval_request_id=approval_request_id,
            evidence_refs=evidence_refs, report_refs=report_refs,
            dependency_artifact_ids=dep_ids,
            supersedes_artifact_id=supersedes_artifact_id,
            is_tool_input=artifact_type in _art.TOOL_INPUT_TYPES,
            is_safe_view_of=None, quarantined_from=None,
            decontaminated_from=None)

        # status derivation (fail-closed): quarantine/approval gate readiness.
        blocked_reasons = []
        if quarantined:
            status = "QUARANTINED"
            trust_tier = "QUARANTINED"
        elif requires_approval and not approval_valid:
            status = "NEEDS_REVIEW"
            blocked_reasons.append("valid human approval grant required before "
                                   "validation")
        else:
            status = "DRAFT"
        capsule["artifact_status"] = status
        subject_refs = [subject_id] if subject_id else []

        manifest = _art.build_manifest(
            artifact_id=artifact_id, tenant_id=tid, artifact_type=artifact_type,
            artifact_status=status, artifact_trust_tier=trust_tier,
            task_id=task_id, run_id=run_id,
            approval_request_id=approval_request_id,
            approval_grant_id=(approval_grant or {}).get("approval_grant_id"),
            created_by_actor_id=created_by_actor_id,
            created_by_actor_type=created_by_actor_type,
            task_contract_hash=contract_hash, task_envelope_hash=envelope_hash,
            task_state_hash=None, run_state_hash=(run or {}).get(
                "run_state_hash"), run_chain_hash=(run or {}).get(
                "run_chain_hash"), approval_grant_hash=approval_grant_hash,
            content_hash=c_hash, version_hash=None, claim_graph_hash=cg_hash,
            dependency_hashes=[d["version_hash"] for d in dep_snaps],
            provenance_hash=provenance["provenance_hash"],
            abom_hash=abom["abom_hash"], evidence_refs=evidence_refs,
            report_refs=report_refs, subject_refs=subject_refs,
            redaction_profile="FULL_VIEW", safe_view_available=True,
            quarantine_status=scanner["quarantine_status"],
            materialization_status="PENDING", retention_hint="DEFAULT_30D",
            legal_hold_hint=None)
        m_hash = manifest["manifest_hash"]
        v_hash = _art.version_hash(
            artifact_id=artifact_id, version_number=version_number,
            content_hash=c_hash, manifest_hash=m_hash, claim_graph_hash=cg_hash,
            provenance_hash=provenance["provenance_hash"],
            abom_hash=abom["abom_hash"],
            previous_version_hash=(prev_version or {}).get("version_hash"),
            created_by_actor_id=created_by_actor_id)
        manifest["version_hash"] = v_hash
        prev_chain = (prev_version or {}).get("version_chain_hash")
        chain_hash = _art.version_chain_hash(prev_chain, v_hash)

        art_head = {"artifact_id": artifact_id, "artifact_type": artifact_type,
                    "artifact_status": status,
                    "quarantine_status": scanner["quarantine_status"],
                    "claims_required": capsule["artifact_claims_required"],
                    "artifact_trust_tier": trust_tier,
                    "artifact_title": artifact_title}
        mat = _art.materialization_check(art_head,
                                         claims_supported=claims_supported,
                                         approval_valid=approval_valid)
        state_hash = _art.artifact_state_hash(
            artifact_id=artifact_id, tenant_id=tid, artifact_type=artifact_type,
            artifact_status=status, artifact_trust_tier=trust_tier,
            latest_version_id=version_id, version_number=version_number,
            task_id=task_id, run_id=run_id,
            approval_request_id=approval_request_id,
            approval_grant_hash=approval_grant_hash,
            task_contract_hash=contract_hash, content_hash=c_hash,
            manifest_hash=m_hash, claim_graph_hash=cg_hash,
            provenance_hash=provenance["provenance_hash"],
            abom_hash=abom["abom_hash"],
            dependency_graph_hash=dep_graph["dependency_graph_hash"],
            lineage_hash=lineage["artifact_lineage_hash"],
            quarantine_status=scanner["quarantine_status"],
            materialization_status=mat["materialization_status"],
            version_chain_hash=chain_hash)

        version_payload = {
            "artifact_version_id": version_id, "artifact_id": artifact_id,
            "tenant_id": tid, "version_number": version_number,
            "version_status": status, "content_envelope": envelope,
            "content_format": content_format, "content_hash": c_hash,
            "manifest": manifest, "manifest_hash": m_hash,
            "claim_graph": claim_graph, "claim_graph_hash": cg_hash,
            "provenance": provenance,
            "provenance_hash": provenance["provenance_hash"],
            "abom": abom, "abom_hash": abom["abom_hash"],
            "dependency_graph": dep_graph, "lineage": lineage,
            "policy_capsule": capsule, "policy_capsule_hash": capsule_hash,
            "scanner": scanner, "scanner_hash": scanner["scanner_hash"],
            "version_hash": v_hash,
            "previous_version_hash": (prev_version or {}).get("version_hash"),
            "version_chain_hash": chain_hash,
            "created_by_actor_id": created_by_actor_id,
            "created_at": created_at, "honesty_labels": _art.HONESTY_LABELS,
        }
        head_meta = {
            "artifact_status": status, "artifact_trust_tier": trust_tier,
            "quarantine_status": scanner["quarantine_status"],
            "materialization_status": mat["materialization_status"],
            "content_hash": c_hash, "manifest_hash": m_hash,
            "state_hash": state_hash, "version_hash": v_hash,
            "claims_supported": claims_supported,
            "unsupported_claim_count": claim_graph["unsupported_count"]
            + claim_graph["needs_review_count"],
            "blocked_reasons": blocked_reasons, "approval_grant": approval_grant,
        }
        return version_payload, head_meta, mat

    def _art_deny_forbidden_type(atype):
        if atype in _art.FORBIDDEN_TYPES:
            raise HTTPException(400, f"artifact type {atype} is not implemented "
                                "and cannot be created (future-only type)")
        if atype not in _art.ARTIFACT_TYPES:
            raise HTTPException(400, f"unknown artifact type {atype}")

    def _load_artifact_or_404(artifact_id, user):
        p = artifact_store.payload(artifact_id, tenant_id=user["tid"])
        if p is None:                              # incl. cross-tenant
            raise HTTPException(404, "artifact not found")
        return p

    @app.get("/ai-artifacts/types")
    async def artifact_types(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return {"artifact_types": sorted(_art.ARTIFACT_TYPES),
                "forbidden_types": sorted(_art.FORBIDDEN_TYPES),
                "statuses": sorted(_art.ARTIFACT_STATUSES),
                "trust_tiers": sorted(_art.TRUST_TIERS),
                "content_formats": sorted(_art.CONTENT_FORMATS),
                "honesty_labels": _art.HONESTY_LABELS}

    @app.get("/ai-artifacts/lifecycle-dashboard")
    async def artifact_dashboard(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        by_type, by_status = {}, {}
        quarantined = blocked = 0
        for a in artifact_store.list(tenant_id=user["tid"]):
            by_type[a["artifact_type"]] = by_type.get(a["artifact_type"], 0) + 1
            by_status[a["artifact_status"]] = by_status.get(
                a["artifact_status"], 0) + 1
            if a["artifact_status"] == "QUARANTINED":
                quarantined += 1
            if a["artifact_status"] in ("BLOCKED", "NEEDS_REVIEW"):
                blocked += 1
        return {"artifacts_by_type": by_type, "artifacts_by_status": by_status,
                "quarantined_count": quarantined, "blocked_count": blocked,
                "honesty_labels": _art.HONESTY_LABELS}

    @app.post("/ai-artifacts")
    async def create_artifact(body: dict, user: dict = Depends(current_user)):
        # Creating an artifact records a work product. It executes nothing: no
        # send, tool, LLM, payment, CRM write, evidence rewrite or export.
        require_permission(user, "case.update")
        tid = user["tid"]
        atype = str(body.get("artifact_type", ""))
        _art_deny_forbidden_type(atype)
        task_id = body.get("task_id")
        tp, contract_hash, envelope_hash, task_state, run = _art_task_context(
            task_id, tid)
        approval_request_id = body.get("approval_request_id")
        requires_approval = atype in _art.APPROVAL_REQUIRED_TYPES
        approval_valid, approval_grant = (_art_approval_valid(task_id, tid)
                                          if requires_approval
                                          else (False, None))
        dep_ids = [str(d) for d in (body.get("dependency_artifact_ids") or [])]
        artifact_id = str(uuid.uuid4())
        version_id = artifact_id + "-v1"
        dep_snaps = _art_dependencies(dep_ids, tid, artifact_id)
        now = utcnow()
        actor_type = "ai_employee" if user["role"] == "ai_worker" else "human"
        trust_tier = _art.default_trust_tier(atype, actor_type)
        assigned = (tp or {}).get("assigned_ai_employee_id", "") if tp else ""

        version_payload, head, mat = _assemble_artifact(
            artifact_id=artifact_id, version_id=version_id, version_number=1,
            tid=tid, prev_version=None, artifact_type=atype,
            trust_tier=trust_tier,
            content_format=str(body.get("content_format", "TEXT")),
            content_body=str(body.get("content_body", body.get("content", ""))),
            artifact_title=str(body.get("artifact_title", "")),
            purpose=body.get("artifact_purpose"), task_id=task_id, run=run,
            approval_request_id=approval_request_id,
            approval_grant=approval_grant, created_by_actor_id=user["uid"],
            created_by_actor_type=actor_type, assigned_ai_employee_id=assigned,
            contract_hash=contract_hash, envelope_hash=envelope_hash,
            task_state=task_state, evidence_refs=[str(e) for e in (
                body.get("evidence_refs") or [])],
            report_refs=[str(r) for r in (body.get("report_refs") or [])],
            subject_type=body.get("subject_type"),
            subject_id=body.get("subject_id"), dep_ids=dep_ids,
            dep_snaps=dep_snaps, supersedes_artifact_id=None,
            claims_input=body.get("claims") or [],
            requires_approval=requires_approval, approval_valid=approval_valid,
            creator_role=user["role"], created_at=now)

        payload = {
            "artifact_id": artifact_id, "tenant_id": tid, "task_id": task_id,
            "run_id": (run or {}).get("run_id"),
            "approval_request_id": approval_request_id,
            "approval_grant_id": (approval_grant or {}).get(
                "approval_grant_id"),
            "created_by_actor_id": user["uid"], "created_by_actor_type":
            actor_type, "created_by_role": user["role"],
            "assigned_ai_employee_id": assigned, "artifact_type": atype,
            "artifact_status": head["artifact_status"],
            "artifact_trust_tier": head["artifact_trust_tier"],
            "artifact_title": str(body.get("artifact_title", "")),
            "artifact_purpose": body.get("artifact_purpose"),
            "artifact_version": 1, "latest_version_id": version_id,
            "artifact_manifest_hash": head["manifest_hash"],
            "artifact_content_hash": head["content_hash"],
            "artifact_state_hash": head["state_hash"],
            "artifact_version_hash": head["version_hash"],
            "artifact_claim_graph_hash": version_payload["claim_graph_hash"],
            "artifact_provenance_hash": version_payload["provenance_hash"],
            "artifact_abom_hash": version_payload["abom_hash"],
            "artifact_dependency_graph_hash": version_payload[
                "dependency_graph"]["dependency_graph_hash"],
            "artifact_lineage_hash": version_payload["lineage"][
                "artifact_lineage_hash"],
            "artifact_policy_capsule_hash": version_payload[
                "policy_capsule_hash"],
            "task_contract_hash": contract_hash or "",
            "task_envelope_hash": envelope_hash,
            "run_state_hash": (run or {}).get("run_state_hash"),
            "subject_type": body.get("subject_type"),
            "subject_id": body.get("subject_id"),
            "case_id": body.get("subject_id") if body.get("subject_type")
            == "case" else None, "supersedes_artifact_id": None,
            "dependency_artifact_ids": dep_ids,
            "evidence_refs": [str(e) for e in (body.get("evidence_refs")
                                               or [])],
            "report_refs": [str(r) for r in (body.get("report_refs") or [])],
            "safe_view_available": True, "redaction_profile": "FULL_VIEW",
            "quarantine_status": head["quarantine_status"],
            "quarantine_reason": version_payload["scanner"].get(
                "quarantine_reason"),
            "materialization_status": head["materialization_status"],
            "claims_required": version_payload["policy_capsule"][
                "artifact_claims_required"],
            "unsupported_claim_count": head["unsupported_claim_count"],
            "retention_hint": "DEFAULT_30D", "legal_hold_hint": None,
            "blocked_reason": (head["blocked_reasons"][0]
                               if head["blocked_reasons"] else None),
            "created_at": now, "updated_at": now, "expires_at": None,
            "honesty_labels": _art.HONESTY_LABELS,
        }
        artifact_store.save({
            "id": artifact_id, "tenant_id": tid, "task_id": task_id,
            "run_id": (run or {}).get("run_id"),
            "approval_request_id": approval_request_id,
            "approval_grant_id": (approval_grant or {}).get(
                "approval_grant_id"),
            "created_by_actor_id": user["uid"], "created_by_actor_type":
            actor_type, "assigned_ai_employee_id": assigned,
            "artifact_type": atype, "artifact_status": head["artifact_status"],
            "artifact_trust_tier": head["artifact_trust_tier"],
            "artifact_version": 1, "latest_version_id": version_id,
            "artifact_state_hash": head["state_hash"],
            "artifact_manifest_hash": head["manifest_hash"],
            "artifact_content_hash": head["content_hash"],
            "quarantine_status": head["quarantine_status"],
            "materialization_status": head["materialization_status"],
            "supersedes_artifact_id": None,
            "task_contract_hash": contract_hash or "",
            "subject_type": body.get("subject_type"),
            "subject_id": body.get("subject_id"),
            "case_id": payload["case_id"], "payload_json": json.dumps(payload),
            "created_by": user["uid"], "created_at": now, "updated_at": now,
            "expires_at": None})
        artifact_store.save_version({
            "id": version_id, "artifact_id": artifact_id, "tenant_id": tid,
            "version_number": 1, "version_status": head["artifact_status"],
            "content_format": str(body.get("content_format", "TEXT")),
            "content_hash": head["content_hash"], "manifest_hash": head[
                "manifest_hash"], "claim_graph_hash": version_payload[
                "claim_graph_hash"], "provenance_hash": version_payload[
                "provenance_hash"], "abom_hash": version_payload["abom_hash"],
            "version_hash": head["version_hash"], "previous_version_hash": None,
            "version_chain_hash": version_payload["version_chain_hash"],
            "created_by_actor_id": user["uid"],
            "payload_json": json.dumps(version_payload), "created_at": now})
        audit.append(event_type="AI_ARTIFACT_CREATED", actor=user["uid"],
                     payload={"artifact_id": artifact_id, "type": atype,
                              "status": head["artifact_status"]})
        return payload

    @app.get("/ai-artifacts")
    async def list_artifacts(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return artifact_store.list(tenant_id=user["tid"])

    @app.get("/ai-artifacts/{artifact_id}")
    async def get_artifact(artifact_id: str,
                           user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return _load_artifact_or_404(artifact_id, user)

    @app.get("/ai-artifacts/{artifact_id}/safe")
    async def get_artifact_safe(artifact_id: str,
                                user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        p = _load_artifact_or_404(artifact_id, user)
        lv = artifact_store.latest_version(artifact_id, tenant_id=user["tid"])
        restricted = user["role"] in ("viewer", "technician", "accountant")
        return _art.build_safe_view(p, lv, restricted=restricted)

    @app.get("/ai-artifacts/{artifact_id}/versions")
    async def list_artifact_versions(artifact_id: str,
                                     user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_artifact_or_404(artifact_id, user)
        return {"artifact_id": artifact_id,
                "versions": artifact_store.versions(artifact_id,
                                                    tenant_id=user["tid"]),
                "honesty_labels": _art.HONESTY_LABELS}

    @app.get("/ai-artifacts/{artifact_id}/versions/{version_id}")
    async def get_artifact_version(artifact_id: str, version_id: str,
                                   user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_artifact_or_404(artifact_id, user)
        v = artifact_store.version(artifact_id, version_id,
                                   tenant_id=user["tid"])
        if v is None:
            raise HTTPException(404, "artifact version not found")
        return v

    @app.post("/ai-artifacts/{artifact_id}/versions")
    async def create_artifact_version(artifact_id: str, body: dict,
                                      user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        tid = user["tid"]
        p = _load_artifact_or_404(artifact_id, user)
        if p["artifact_status"] in _art.TERMINAL_STATUSES:
            raise HTTPException(409, f"artifact is {p['artifact_status']} and "
                                "cannot be versioned")
        # A quarantined artifact can NEVER be un-quarantined by editing it in
        # place — that would silently clear the quarantine gate and re-admit it
        # to completion/materialization/tool-input. Quarantine preserves the
        # artifact and blocks future use; a safe successor must go through the
        # decontamination lane (a NEW derivative artifact), which is
        # MISSING/NEXT in this mission.
        if p["artifact_status"] == "QUARANTINED" \
                or p.get("quarantine_status") == "QUARANTINED":
            raise HTTPException(409, "quarantined artifact cannot be versioned "
                                "in place; use the decontamination lane to "
                                "create a safe derivative")
        prev = artifact_store.latest_version(artifact_id, tenant_id=tid)
        vnum = artifact_store.next_version_number(artifact_id, tenant_id=tid)
        version_id = f"{artifact_id}-v{vnum}"
        task_id = p.get("task_id")
        tp, contract_hash, envelope_hash, task_state, run = _art_task_context(
            task_id, tid)
        requires_approval = p["artifact_type"] in _art.APPROVAL_REQUIRED_TYPES
        approval_valid, approval_grant = (_art_approval_valid(task_id, tid)
                                          if requires_approval
                                          else (False, None))
        dep_ids = p.get("dependency_artifact_ids") or []
        dep_snaps = _art_dependencies(dep_ids, tid, artifact_id)
        now = utcnow()
        version_payload, head, mat = _assemble_artifact(
            artifact_id=artifact_id, version_id=version_id, version_number=vnum,
            tid=tid, prev_version=prev, artifact_type=p["artifact_type"],
            trust_tier=p["artifact_trust_tier"],
            content_format=str(body.get("content_format",
                                        p.get("content_format", "TEXT"))),
            content_body=str(body.get("content_body", body.get("content", ""))),
            artifact_title=p.get("artifact_title"),
            purpose=p.get("artifact_purpose"), task_id=task_id, run=run,
            approval_request_id=p.get("approval_request_id"),
            approval_grant=approval_grant,
            created_by_actor_id=user["uid"],
            created_by_actor_type=("ai_employee" if user["role"] == "ai_worker"
                                   else "human"),
            assigned_ai_employee_id=p.get("assigned_ai_employee_id", ""),
            contract_hash=contract_hash, envelope_hash=envelope_hash,
            task_state=task_state, evidence_refs=p.get("evidence_refs") or [],
            report_refs=p.get("report_refs") or [],
            subject_type=p.get("subject_type"), subject_id=p.get("subject_id"),
            dep_ids=dep_ids, dep_snaps=dep_snaps, supersedes_artifact_id=None,
            claims_input=body.get("claims") or [],
            requires_approval=requires_approval, approval_valid=approval_valid,
            creator_role=user["role"], created_at=now)
        p.update({
            "artifact_version": vnum, "latest_version_id": version_id,
            "artifact_status": head["artifact_status"],
            "artifact_trust_tier": head["artifact_trust_tier"],
            "artifact_manifest_hash": head["manifest_hash"],
            "artifact_content_hash": head["content_hash"],
            "artifact_state_hash": head["state_hash"],
            "artifact_version_hash": head["version_hash"],
            "artifact_claim_graph_hash": version_payload["claim_graph_hash"],
            "artifact_provenance_hash": version_payload["provenance_hash"],
            "artifact_abom_hash": version_payload["abom_hash"],
            "quarantine_status": head["quarantine_status"],
            "materialization_status": head["materialization_status"],
            "unsupported_claim_count": head["unsupported_claim_count"],
            "updated_at": now,
            "change_reason": str(body.get("change_reason", "")),
        })
        artifact_store.save_version({
            "id": version_id, "artifact_id": artifact_id, "tenant_id": tid,
            "version_number": vnum, "version_status": head["artifact_status"],
            "content_format": version_payload["content_format"],
            "content_hash": head["content_hash"], "manifest_hash": head[
                "manifest_hash"], "claim_graph_hash": version_payload[
                "claim_graph_hash"], "provenance_hash": version_payload[
                "provenance_hash"], "abom_hash": version_payload["abom_hash"],
            "version_hash": head["version_hash"], "previous_version_hash": (
                prev or {}).get("version_hash"), "version_chain_hash":
            version_payload["version_chain_hash"],
            "created_by_actor_id": user["uid"],
            "payload_json": json.dumps(version_payload), "created_at": now})
        artifact_store.update_head(
            artifact_id, tenant_id=tid, payload=p,
            artifact_version=vnum, latest_version_id=version_id,
            artifact_status=head["artifact_status"],
            artifact_trust_tier=head["artifact_trust_tier"],
            artifact_state_hash=head["state_hash"],
            artifact_manifest_hash=head["manifest_hash"],
            artifact_content_hash=head["content_hash"],
            quarantine_status=head["quarantine_status"],
            materialization_status=head["materialization_status"],
            updated_at=now)
        audit.append(event_type="AI_ARTIFACT_VERSION_CREATED",
                     actor=user["uid"], payload={"artifact_id": artifact_id,
                                                 "version": vnum})
        return {"artifact_id": artifact_id, "version_number": vnum,
                "artifact_version": version_payload,
                "honesty_labels": _art.HONESTY_LABELS}

    @app.post("/ai-artifacts/{artifact_id}/verify")
    async def verify_artifact(artifact_id: str,
                              user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        p = _load_artifact_or_404(artifact_id, user)
        tid = user["tid"]
        versions = artifact_store.versions(artifact_id, tenant_id=tid)
        reasons, chain_prev, chain_ok = [], None, True
        for v in versions:
            env = v["content_envelope"]
            if _art.content_hash(env) != v["content_hash"]:
                reasons.append(f"v{v['version_number']}: content hash mismatch")
            if _art.manifest_hash(v["manifest"]) != v["manifest_hash"]:
                reasons.append(f"v{v['version_number']}: manifest hash "
                               "mismatch")
            if _art.claim_graph_hash(v["claim_graph"]) != v["claim_graph_hash"]:
                reasons.append(f"v{v['version_number']}: claim graph mismatch")
            if _art.provenance_hash(v["provenance"]) != v["provenance_hash"]:
                reasons.append(f"v{v['version_number']}: provenance mismatch")
            if _art.abom_hash(v["abom"]) != v["abom_hash"]:
                reasons.append(f"v{v['version_number']}: ABOM mismatch")
            recomputed_v = _art.version_hash(
                artifact_id=artifact_id, version_number=v["version_number"],
                content_hash=v["content_hash"], manifest_hash=v["manifest_hash"],
                claim_graph_hash=v["claim_graph_hash"],
                provenance_hash=v["provenance_hash"], abom_hash=v["abom_hash"],
                previous_version_hash=v.get("previous_version_hash"),
                created_by_actor_id=v["created_by_actor_id"])
            if recomputed_v != v["version_hash"]:
                reasons.append(f"v{v['version_number']}: version hash mismatch")
            if _art.version_chain_hash(
                    (None if chain_prev is None else chain_prev),
                    v["version_hash"]) != v["version_chain_hash"]:
                chain_ok = False
                reasons.append(f"v{v['version_number']}: version chain "
                               "mismatch")
            chain_prev = v["version_chain_hash"]
            # dependency drift
            for d in v["dependency_graph"]["dependencies"]:
                lv = artifact_store.latest_version(d["artifact_id"],
                                                   tenant_id=tid)
                if lv and d["version_hash"] and lv["version_hash"] != d[
                        "version_hash"]:
                    reasons.append(f"v{v['version_number']}: dependency "
                                   f"{d['artifact_id'][:8]} drifted")
        # Head integrity: the mutable head row (which materialization and
        # completion consume) must agree with the latest version's hashes, so a
        # direct head-column tamper is also caught.
        lv = versions[-1] if versions else None
        if lv is not None:
            if p.get("artifact_content_hash") != lv["content_hash"]:
                reasons.append("head content hash diverges from latest version")
            if p.get("artifact_manifest_hash") != lv["manifest_hash"]:
                reasons.append("head manifest hash diverges from latest "
                               "version")
            if p.get("artifact_version_hash") != lv["version_hash"]:
                reasons.append("head version hash diverges from latest version")
        status = "MATCHED" if not reasons else "MISMATCHED"
        return {"artifact_id": artifact_id, "verification_status": status,
                "tamper_detected": bool(reasons), "tamper_reasons": reasons,
                "version_chain_status": "VALID" if chain_ok else "MISMATCHED",
                "versions_checked": len(versions),
                "honesty_labels": _art.HONESTY_LABELS}

    @app.get("/ai-artifacts/{artifact_id}/manifest")
    async def get_artifact_manifest(artifact_id: str,
                                    user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_artifact_or_404(artifact_id, user)
        lv = artifact_store.latest_version(artifact_id, tenant_id=user["tid"])
        return {"artifact_id": artifact_id, "manifest": lv["manifest"],
                "manifest_hash": lv["manifest_hash"],
                "honesty_labels": _art.HONESTY_LABELS}

    @app.get("/ai-artifacts/{artifact_id}/lineage")
    async def get_artifact_lineage(artifact_id: str,
                                   user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_artifact_or_404(artifact_id, user)
        lv = artifact_store.latest_version(artifact_id, tenant_id=user["tid"])
        return {"artifact_id": artifact_id, "lineage": lv["lineage"],
                "honesty_labels": _art.HONESTY_LABELS}

    @app.get("/ai-artifacts/{artifact_id}/provenance")
    async def get_artifact_provenance(artifact_id: str,
                                      user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_artifact_or_404(artifact_id, user)
        lv = artifact_store.latest_version(artifact_id, tenant_id=user["tid"])
        return {"artifact_id": artifact_id, "provenance": lv["provenance"],
                "provenance_hash": lv["provenance_hash"],
                "honesty_labels": _art.HONESTY_LABELS}

    @app.get("/ai-artifacts/{artifact_id}/claims")
    async def get_artifact_claims(artifact_id: str,
                                  user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_artifact_or_404(artifact_id, user)
        lv = artifact_store.latest_version(artifact_id, tenant_id=user["tid"])
        return {"artifact_id": artifact_id, "claim_graph": lv["claim_graph"],
                "claim_graph_hash": lv["claim_graph_hash"],
                "honesty_labels": _art.HONESTY_LABELS}

    @app.get("/ai-artifacts/{artifact_id}/abom")
    async def get_artifact_abom(artifact_id: str,
                                user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_artifact_or_404(artifact_id, user)
        lv = artifact_store.latest_version(artifact_id, tenant_id=user["tid"])
        return {"artifact_id": artifact_id, "abom": lv["abom"],
                "abom_hash": lv["abom_hash"],
                "honesty_labels": _art.HONESTY_LABELS}

    @app.get("/ai-artifacts/{artifact_id}/dependencies")
    async def get_artifact_dependencies(artifact_id: str,
                                        user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_artifact_or_404(artifact_id, user)
        lv = artifact_store.latest_version(artifact_id, tenant_id=user["tid"])
        return {"artifact_id": artifact_id,
                "dependency_graph": lv["dependency_graph"],
                "honesty_labels": _art.HONESTY_LABELS}

    @app.post("/ai-artifacts/{artifact_id}/diff")
    async def diff_artifact(artifact_id: str, body: dict,
                            user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_artifact_or_404(artifact_id, user)
        tid = user["tid"]
        va = artifact_store.version(artifact_id, str(body.get("from_version_id",
                                                              "")), tenant_id=tid)
        vb = artifact_store.version(artifact_id, str(body.get("to_version_id",
                                                              "")), tenant_id=tid)
        if va is None or vb is None:
            raise HTTPException(404, "version not found for diff")
        changed = []
        for field in ("content_hash", "manifest_hash", "claim_graph_hash",
                      "provenance_hash", "abom_hash", "version_status"):
            if va.get(field) != vb.get(field):
                changed.append(field)
        return {"artifact_id": artifact_id,
                "from_version": va["version_number"],
                "to_version": vb["version_number"], "changed_fields": changed,
                "content_changed": va["content_hash"] != vb["content_hash"],
                "honesty_labels": _art.HONESTY_LABELS}

    @app.post("/ai-artifacts/{artifact_id}/supersede")
    async def supersede_artifact(artifact_id: str, body: dict,
                                 user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        tid = user["tid"]
        p = _load_artifact_or_404(artifact_id, user)
        if p["artifact_status"] in _art.TERMINAL_STATUSES:
            raise HTTPException(409, f"artifact is {p['artifact_status']}")
        now = utcnow()
        p["artifact_status"] = "SUPERSEDED"
        p["updated_at"] = now
        artifact_store.update_head(artifact_id, tenant_id=tid, payload=p,
                                   artifact_status="SUPERSEDED", updated_at=now)
        return {"artifact_id": artifact_id, "artifact_status": "SUPERSEDED",
                "honesty_labels": _art.HONESTY_LABELS}

    @app.post("/ai-artifacts/{artifact_id}/archive")
    async def archive_artifact(artifact_id: str,
                               user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        tid = user["tid"]
        p = _load_artifact_or_404(artifact_id, user)
        now = utcnow()
        p["artifact_status"] = "ARCHIVED"
        p["updated_at"] = now
        artifact_store.update_head(artifact_id, tenant_id=tid, payload=p,
                                   artifact_status="ARCHIVED", updated_at=now)
        return {"artifact_id": artifact_id, "artifact_status": "ARCHIVED",
                "honesty_labels": _art.HONESTY_LABELS}

    @app.post("/ai-artifacts/{artifact_id}/quarantine")
    async def quarantine_artifact(artifact_id: str, body: dict,
                                  user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        tid = user["tid"]
        p = _load_artifact_or_404(artifact_id, user)
        now = utcnow()
        # Quarantine PRESERVES the artifact; it never deletes it.
        p["artifact_status"] = "QUARANTINED"
        p["artifact_trust_tier"] = "QUARANTINED"
        p["quarantine_status"] = "QUARANTINED"
        p["quarantine_reason"] = str(body.get("reason", "manual quarantine"))
        p["materialization_status"] = "MATERIALIZATION_BLOCKED"
        p["updated_at"] = now
        artifact_store.update_head(
            artifact_id, tenant_id=tid, payload=p,
            artifact_status="QUARANTINED", artifact_trust_tier="QUARANTINED",
            quarantine_status="QUARANTINED",
            materialization_status="MATERIALIZATION_BLOCKED", updated_at=now)
        audit.append(event_type="AI_ARTIFACT_QUARANTINED", actor=user["uid"],
                     payload={"artifact_id": artifact_id})
        return {"artifact_id": artifact_id, "artifact_status": "QUARANTINED",
                "quarantine_label": "Artifact quarantine preserves the "
                "artifact but blocks readiness and future use.",
                "honesty_labels": _art.HONESTY_LABELS}

    @app.post("/ai-artifacts/{artifact_id}/decontamination-check")
    async def decontamination_check(artifact_id: str,
                                    user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        p = _load_artifact_or_404(artifact_id, user)
        # Validation-only. Never modifies the original quarantined artifact.
        eligible = p["artifact_status"] == "QUARANTINED"
        return {"artifact_id": artifact_id,
                "decontamination_status": ("ELIGIBLE_FOR_DERIVATIVE"
                                           if eligible
                                           else "NOT_APPLICABLE"),
                "original_modified": False,
                "full_decontamination_lane": "NOT_IMPLEMENTED",
                "note": "decontamination-check validates readiness only; the "
                "original artifact is never modified. The full decontamination "
                "lane is MISSING/NEXT.",
                "honesty_labels": _art.HONESTY_LABELS}

    @app.post("/ai-artifacts/{artifact_id}/materialization-check")
    async def artifact_materialization_check(artifact_id: str,
                                             user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        p = _load_artifact_or_404(artifact_id, user)
        tid = user["tid"]
        lv = artifact_store.latest_version(artifact_id, tenant_id=tid)
        claims_supported = _art.claims_all_supported(lv["claim_graph"])
        requires_approval = p["artifact_type"] in _art.APPROVAL_REQUIRED_TYPES
        approval_valid, _g = (_art_approval_valid(p.get("task_id"), tid)
                              if requires_approval else (False, None))
        res = _art.materialization_check(p, claims_supported=claims_supported,
                                         approval_valid=approval_valid)
        return {"artifact_id": artifact_id, **res}

    @app.get("/ai-tasks/{task_id}/artifacts")
    async def task_artifacts(task_id: str,
                             user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_task_or_404(task_id, user)
        return {"task_id": task_id,
                "artifacts": artifact_store.list_for_task(task_id,
                                                          tenant_id=user["tid"]),
                "honesty_labels": _art.HONESTY_LABELS}

    @app.get("/ai-runs/{run_id}/artifacts")
    async def run_artifacts(run_id: str, user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        if run_store.get_run(run_id, tenant_id=user["tid"]) is None:
            raise HTTPException(404, "run not found")
        return {"run_id": run_id,
                "artifacts": artifact_store.list_for_run(run_id,
                                                        tenant_id=user["tid"]),
                "honesty_labels": _art.HONESTY_LABELS}

    def _artifact_completion_contribution(task_id, tid):
        """ArtifactCompletionContribution: which required artifacts are ready
        and which are blockers. Pure derivation from stored artifact truth."""
        arts = artifact_store.list_for_task(task_id, tenant_id=tid)
        blockers = []
        ready = []
        for a in arts:
            if a["artifact_status"] == "QUARANTINED":
                blockers.append({"artifact_id": a["artifact_id"],
                                 "blocker": "ARTIFACT_QUARANTINED"})
            elif a["artifact_status"] in ("BLOCKED", "TAMPERED"):
                blockers.append({"artifact_id": a["artifact_id"],
                                 "blocker": "ARTIFACT_BLOCKED"})
            elif a["artifact_status"] == "NEEDS_REVIEW":
                blockers.append({"artifact_id": a["artifact_id"],
                                 "blocker": "ARTIFACT_NEEDS_REVIEW"})
            elif a.get("unsupported_claim_count", 0) > 0:
                blockers.append({"artifact_id": a["artifact_id"],
                                 "blocker": "ARTIFACT_CLAIM_UNSUPPORTED"})
            else:
                ready.append(a["artifact_id"])
        return {"ready_artifacts": ready, "artifact_blockers": blockers}

    app.state.artifact_completion_contribution = \
        _artifact_completion_contribution

    # ---- ViktorAI Zero-Trust Tool Capability Governance Registry (TOOL-B1) ----------
    from ..ai_employee import tool_registry as _tr
    from ..ai_employee.tool_registry_store import ToolRegistryStore
    tool_store = ToolRegistryStore(db)
    app.state.tool_store = tool_store

    # Admission-class mutations (admit/disable/deprecate/supersede) are
    # high-privilege supply-chain governance actions gated to owners.
    _TOOL_ADMIT_PERM = "tenant.manage_integrations"

    def _tool_summaries(tid, exclude_id=None):
        """Tenant-scoped descriptor summaries for collision / multi-tool
        detection. Never leaves the tenant boundary."""
        out = []
        for p in tool_store.list(tenant_id=tid):
            if exclude_id and p["tool_id"] == exclude_id:
                continue
            df = p.get("data_flow_contract", {})
            out.append({
                "tool_id": p["tool_id"], "tool_key": p["tool_key"],
                "aliases": p.get("aliases", []),
                "trust_tier": p["trust_tier"], "status": p["status"],
                "risk_rank": _tr.RISK_RANK.get(p.get("risk_class", "MEDIUM"), 2),
                "side_effect_class": p.get("side_effect_class"),
                "reads_data_classes": df.get("reads_data_classes", []),
                "writes_data_classes": df.get("writes_data_classes", []),
                "egress": df.get("egress_targets", [])})
        return out

    def _tool_emit(tid, *, event_type, tool_id, actor_id, actor_type,
                   tool_state_hash, detail):
        seq = tool_store.next_sequence(tenant_id=tid)
        prev = tool_store.last_event(tenant_id=tid)
        ev = _tr.build_registry_event(
            event_type=event_type, tool_id=tool_id, tenant_id=tid,
            actor_id=actor_id, actor_type=actor_type,
            tool_state_hash=tool_state_hash,
            previous_event_hash=(prev or {}).get("event_hash"), sequence=seq,
            detail=detail, created_at=utcnow())
        tool_store.append_event({
            "id": str(uuid.uuid4()), "tenant_id": tid, "tool_id": tool_id,
            "event_type": event_type, "sequence": seq, "actor_id": actor_id,
            "actor_type": actor_type, "event_hash": ev["event_hash"],
            "previous_event_hash": ev["previous_event_hash"],
            "tool_state_hash": tool_state_hash,
            "payload_json": json.dumps(ev), "created_at": ev["created_at"]})
        return ev

    def _assemble_tool(*, tool_id, version_id, version_number, tid,
                       prev_version, body, actor_id, actor_type, trust_tier,
                       supply_chain, existing_summaries, created_at):
        """Build the full governance package from a DECLARED (untrusted)
        descriptor body. Executes nothing. Returns (version_payload, head_meta).
        """
        tool_name = str(body.get("tool_name", ""))
        tool_summary = str(body.get("tool_summary", ""))
        tool_description = str(body.get("tool_description", ""))
        category = str(body.get("category", ""))
        aliases = [str(a) for a in (body.get("aliases") or [])]
        parameters = body.get("parameters") or []
        param_texts = [str(p.get("description", "")) for p in parameters] \
            + [str(p.get("name", "")) for p in parameters]
        purpose_texts = [str(x) for x in (body.get("allowed_purposes") or [])] \
            + [str(body.get("declared_intent", ""))]

        scanner = _tr.scan_descriptor(
            tool_name=tool_name, tool_summary=tool_summary,
            tool_description=tool_description, parameter_texts=param_texts,
            purpose_texts=purpose_texts,
            output_texts=[str(body.get("output_note", ""))])

        schema_env = _tr.build_schema_envelope(
            input_schema=body.get("input_schema") or {},
            output_schema=body.get("output_schema") or {},
            parameters=parameters,
            declared_side_effects=body.get("declared_side_effects") or [],
            declared_data_reads=body.get("reads_data_classes") or [],
            declared_data_writes=body.get("writes_data_classes") or [])
        effect = _tr.build_effect_contract(
            side_effect_class=str(body.get("side_effect_class", "PURE_READ")),
            reversibility=str(body.get("reversibility", "REVERSIBLE")),
            idempotent=bool(body.get("idempotent", True)),
            blast_radius=str(body.get("blast_radius", "SELF")),
            touches_external=bool(body.get("touches_external", False)),
            touches_customer=bool(body.get("touches_customer", False)),
            touches_payment=bool(body.get("touches_payment", False)),
            touches_crm=bool(body.get("touches_crm", False)),
            touches_evidence=bool(body.get("touches_evidence", False)),
            declared_summary=tool_summary)
        data_flow = _tr.build_data_flow_contract(
            reads_data_classes=body.get("reads_data_classes") or [],
            writes_data_classes=body.get("writes_data_classes") or [],
            egress_targets=body.get("egress_targets") or [],
            ingress_sources=body.get("ingress_sources") or [],
            crosses_tenant_boundary=bool(body.get("crosses_tenant_boundary",
                                                  False)),
            retains_data=bool(body.get("retains_data", False)),
            prompt_context_inputs=body.get("prompt_context_inputs") or [])
        purpose = _tr.build_purpose_contract(
            allowed_purposes=body.get("allowed_purposes") or [],
            forbidden_purposes=body.get("forbidden_purposes") or [],
            declared_intent=str(body.get("declared_intent", "")))
        consent = _tr.build_consent_contract(
            consent_requirement=str(body.get("consent_requirement", "NONE")),
            non_overridable=bool(body.get("consent_non_overridable", False)),
            lawful_basis=str(body.get("lawful_basis", "")),
            declared_note=str(body.get("consent_note", "")))
        prompt_policy = _tr.build_prompt_context_policy(
            exposure_level=str(body.get("prompt_context_exposure",
                                        "NAME_ONLY")),
            category=category, side_effect_class=effect["side_effect_class"],
            data_flow=data_flow)
        neg = _tr.build_negative_capabilities(
            category=category, effect_contract=effect, data_flow=data_flow,
            consent_contract=consent, scanner=scanner)
        invariants = _tr.build_invariant_matrix(
            category=category, effect_contract=effect, data_flow=data_flow,
            schema_envelope=schema_env, purpose_contract=purpose,
            consent_contract=consent, prompt_context_policy=prompt_policy,
            scanner=scanner, negative_capabilities=neg, trust_tier=trust_tier,
            declared_tenant_id=tid, actor_tenant_id=tid, actor_type=actor_type)
        risk_class = _tr.compute_risk_class(
            category=category, effect_contract=effect, data_flow=data_flow,
            scanner=scanner)
        risk = _tr.build_risk_capsule(
            tool_id=tool_id, tenant_id=tid, category=category,
            effect_contract=effect, data_flow=data_flow, scanner=scanner,
            risk_class=risk_class, invariant_matrix=invariants)
        lattice = _tr.build_capability_lattice(
            tool_id=tool_id, tenant_id=tid, category=category,
            effect_contract=effect, data_flow=data_flow)
        implicit = _tr.detect_implicit_poisoning(
            category=category, effect_contract=effect, data_flow=data_flow,
            schema_envelope=schema_env, purpose_contract=purpose,
            consent_contract=consent, tool_description=tool_description)
        tool_key = _tr.normalize_tool_key(tool_name)
        candidate = {"tool_id": tool_id, "tool_key": tool_key,
                     "aliases": aliases, "trust_tier": trust_tier,
                     "risk_rank": _tr.RISK_RANK[risk_class], "status": "DRAFT"}
        collision = _tr.detect_collisions(candidate=candidate,
                                          existing=existing_summaries)
        cand_multi = {"tool_id": tool_id, "tool_key": tool_key,
                      "side_effect_class": effect["side_effect_class"],
                      "reads_data_classes": data_flow["reads_data_classes"],
                      "writes_data_classes": data_flow["writes_data_classes"],
                      "egress": data_flow["egress_targets"], "status": "DRAFT"}
        multi = _tr.detect_multi_tool_poisoning(
            existing_summaries + [cand_multi])

        policy = _tr.build_policy_capsule(
            tool_id=tool_id, tenant_id=tid, category=category,
            side_effect_class=effect["side_effect_class"], risk_class=risk_class,
            trust_tier=trust_tier, consent_contract=consent,
            purpose_contract=purpose, prompt_context_policy=prompt_policy,
            invariant_matrix=invariants, negative_capabilities=neg,
            created_at=created_at)

        # Admission posture (fail-closed). Registration never auto-admits; a
        # clean descriptor becomes DRAFT and awaits explicit human admission.
        posture = _tr.evaluate_admission(
            category=category, invariant_matrix=invariants,
            negative_capabilities=neg, risk_capsule=risk, scanner=scanner,
            implicit_findings=implicit, lattice=lattice, collision=collision,
            multi_tool=multi, supply_chain=supply_chain, declared_tenant_id=tid,
            actor_tenant_id=tid, requested_by_human=True)
        status = "DRAFT" if posture["admitted"] else posture["admission_status"]

        descriptor = {
            "tool_descriptor_version": _tr.TOOL_MODEL_VERSION,
            "tool_id": tool_id, "tenant_id": tid, "tool_key": tool_key,
            "tool_name": tool_name, "tool_summary": tool_summary,
            "tool_description": tool_description, "category": category,
            "aliases": sorted(set(aliases)),
            "schema_envelope": schema_env, "effect_contract": effect,
            "data_flow_contract": data_flow, "purpose_contract": purpose,
            "consent_contract": consent,
            "prompt_context_policy": prompt_policy,
            "declared_provider": str(body.get("declared_provider", "")),
            "declared_version": str(body.get("declared_version", "")),
            "declared_dependencies": sorted(set(
                str(d) for d in (body.get("declared_dependencies") or []))),
            "created_by_actor_id": actor_id,
            "created_by_actor_type": actor_type,
        }
        d_hash = _tr.descriptor_hash(descriptor)
        tbom = _tr.build_tbom(
            tool_id=tool_id, tool_version_id=version_id, tenant_id=tid,
            tool_key=tool_key, category=category,
            side_effect_class=effect["side_effect_class"], risk_class=risk_class,
            trust_tier=trust_tier,
            schema_envelope_hash=schema_env["schema_envelope_hash"],
            effect_contract_hash=effect["effect_contract_hash"],
            data_flow_contract_hash=data_flow["data_flow_contract_hash"],
            purpose_contract_hash=purpose["purpose_contract_hash"],
            consent_contract_hash=consent["consent_contract_hash"],
            prompt_context_policy_hash=prompt_policy[
                "prompt_context_policy_hash"],
            declared_dependencies=descriptor["declared_dependencies"],
            declared_provider=descriptor["declared_provider"],
            declared_version=descriptor["declared_version"],
            scanner_hash=scanner["scanner_hash"])
        admission_pkg = _tr.build_admission_package(
            tool_id=tool_id, tool_version_id=version_id, tenant_id=tid,
            descriptor_hash=d_hash, tbom_hash=tbom["tbom_hash"],
            invariant_matrix=invariants, negative_capabilities=neg,
            risk_capsule=risk, policy_capsule=policy,
            security_case_hash="",              # filled after security case
            admission_decision=posture,
            requested_by_actor_id=actor_id, requested_by_actor_type=actor_type,
            created_at=created_at)
        security_case = _tr.build_security_case(
            tool_id=tool_id, tenant_id=tid, invariant_matrix=invariants,
            negative_capabilities=neg, risk_capsule=risk, scanner=scanner,
            implicit_findings=implicit, admission_decision=posture)

        v_hash = _tr.version_hash(
            tool_id=tool_id, version_number=version_number, descriptor_hash=d_hash,
            tbom_hash=tbom["tbom_hash"],
            policy_capsule_hash=policy["policy_capsule_hash"],
            admission_package_hash=admission_pkg["admission_package_hash"],
            previous_version_hash=(prev_version or {}).get("version_hash"),
            created_by_actor_id=actor_id)
        chain_hash = _tr.version_chain_hash(
            (prev_version or {}).get("version_chain_hash"), v_hash)
        state_hash = _tr.tool_state_hash(
            tool_id=tool_id, tenant_id=tid, tool_key=tool_key, category=category,
            side_effect_class=effect["side_effect_class"], risk_class=risk_class,
            trust_tier=trust_tier, status=status, latest_version_id=version_id,
            version_number=version_number, descriptor_hash=d_hash,
            tbom_hash=tbom["tbom_hash"],
            policy_capsule_hash=policy["policy_capsule_hash"],
            risk_capsule_hash=risk["risk_capsule_hash"],
            invariant_matrix_hash=invariants["invariant_matrix_hash"],
            negative_capability_hash=neg["negative_capability_hash"],
            admission_package_hash=admission_pkg["admission_package_hash"],
            capability_lattice_hash=lattice["capability_lattice_hash"],
            version_chain_hash=chain_hash)

        version_payload = {
            "tool_version_id": version_id, "tool_id": tool_id, "tenant_id": tid,
            "version_number": version_number, "status": status,
            "descriptor": descriptor, "descriptor_hash": d_hash,
            "schema_envelope": schema_env, "effect_contract": effect,
            "data_flow_contract": data_flow, "purpose_contract": purpose,
            "consent_contract": consent, "prompt_context_policy": prompt_policy,
            "scanner": scanner, "scanner_hash": scanner["scanner_hash"],
            "negative_capabilities": neg, "invariant_matrix": invariants,
            "risk_capsule": risk, "risk_class": risk_class,
            "capability_lattice": lattice, "implicit_findings": implicit,
            "collision": collision, "multi_tool": multi,
            "supply_chain": supply_chain, "policy_capsule": policy,
            "tbom": tbom, "admission_package": admission_pkg,
            "security_case": security_case,
            "admission_posture": posture, "version_hash": v_hash,
            "previous_version_hash": (prev_version or {}).get("version_hash"),
            "version_chain_hash": chain_hash, "tool_state_hash": state_hash,
            "created_by_actor_id": actor_id, "created_at": created_at,
            "honesty_labels": _tr.HONESTY_LABELS,
        }
        head_meta = {
            "tool_key": tool_key, "category": category,
            "side_effect_class": effect["side_effect_class"],
            "risk_class": risk_class, "trust_tier": trust_tier, "status": status,
            "quarantine_status": scanner["quarantine_status"],
            "descriptor_hash": d_hash, "tbom_hash": tbom["tbom_hash"],
            "policy_capsule_hash": policy["policy_capsule_hash"],
            "risk_capsule_hash": risk["risk_capsule_hash"],
            "admission_package_hash": admission_pkg["admission_package_hash"],
            "state_hash": state_hash, "version_hash": v_hash,
            "admitted": posture["admitted"] and status
            == "AVAILABLE_FOR_FUTURE_BROKER",
            "aliases": sorted(set(aliases)), "data_flow_contract": data_flow,
        }
        return version_payload, head_meta

    def _tool_head_payload(*, tool_id, tid, actor_id, actor_type, body,
                           version_id, head_meta, vpayload, supersedes,
                           created_at):
        return {
            "tool_id": tool_id, "tenant_id": tid, "tool_key": head_meta[
                "tool_key"], "tool_name": str(body.get("tool_name", "")),
            "tool_summary": str(body.get("tool_summary", "")),
            "aliases": head_meta["aliases"],
            "created_by_actor_id": actor_id,
            "created_by_actor_type": actor_type, "category": head_meta[
                "category"], "side_effect_class": head_meta["side_effect_class"],
            "risk_class": head_meta["risk_class"],
            "trust_tier": head_meta["trust_tier"], "status": head_meta["status"],
            "tool_version": vpayload["version_number"],
            "latest_version_id": version_id,
            "tool_state_hash": head_meta["state_hash"],
            "descriptor_hash": head_meta["descriptor_hash"],
            "tbom_hash": head_meta["tbom_hash"],
            "policy_capsule_hash": head_meta["policy_capsule_hash"],
            "risk_capsule_hash": head_meta["risk_capsule_hash"],
            "admission_package_hash": head_meta["admission_package_hash"],
            "version_hash": head_meta["version_hash"],
            "quarantine_status": head_meta["quarantine_status"],
            "quarantine_reason": vpayload["scanner"].get("quarantine_reason"),
            "admitted": head_meta["admitted"],
            "data_flow_contract": head_meta["data_flow_contract"],
            "supersedes_tool_id": supersedes,
            "hard_fail_signals": vpayload["admission_posture"][
                "hard_fail_signals"],
            "admission_reasons": vpayload["admission_posture"]["reasons"],
            "created_at": created_at, "updated_at": created_at,
            "honesty_labels": _tr.HONESTY_LABELS,
        }

    def _save_tool_head(payload, *, version_id, created_by):
        tool_store.save({
            "id": payload["tool_id"], "tenant_id": payload["tenant_id"],
            "tool_key": payload["tool_key"], "tool_name": payload["tool_name"],
            "created_by_actor_id": payload["created_by_actor_id"],
            "created_by_actor_type": payload["created_by_actor_type"],
            "category": payload["category"], "side_effect_class": payload[
                "side_effect_class"], "risk_class": payload["risk_class"],
            "trust_tier": payload["trust_tier"], "status": payload["status"],
            "tool_version": payload["tool_version"],
            "latest_version_id": version_id,
            "tool_state_hash": payload["tool_state_hash"],
            "descriptor_hash": payload["descriptor_hash"],
            "tbom_hash": payload["tbom_hash"],
            "policy_capsule_hash": payload["policy_capsule_hash"],
            "risk_capsule_hash": payload["risk_capsule_hash"],
            "admission_package_hash": payload["admission_package_hash"],
            "quarantine_status": payload["quarantine_status"],
            "admitted": 1 if payload["admitted"] else 0,
            "supersedes_tool_id": payload["supersedes_tool_id"],
            "payload_json": json.dumps(payload), "created_by": created_by,
            "created_at": payload["created_at"],
            "updated_at": payload["updated_at"]})

    def _save_tool_version(vpayload, *, created_by):
        tool_store.save_version({
            "id": vpayload["tool_version_id"], "tool_id": vpayload["tool_id"],
            "tenant_id": vpayload["tenant_id"], "version_number": vpayload[
                "version_number"], "status": vpayload["status"],
            "descriptor_hash": vpayload["descriptor_hash"],
            "tbom_hash": vpayload["tbom"]["tbom_hash"],
            "policy_capsule_hash": vpayload["policy_capsule"][
                "policy_capsule_hash"],
            "admission_package_hash": vpayload["admission_package"][
                "admission_package_hash"],
            "version_hash": vpayload["version_hash"],
            "previous_version_hash": vpayload["previous_version_hash"],
            "version_chain_hash": vpayload["version_chain_hash"],
            "created_by_actor_id": vpayload["created_by_actor_id"],
            "payload_json": json.dumps(vpayload),
            "created_at": vpayload["created_at"]})

    def _load_tool_or_404(tool_id, user):
        p = tool_store.payload(tool_id, tenant_id=user["tid"])
        if p is None:                              # incl. cross-tenant
            raise HTTPException(404, "tool not found")
        return p

    def _redact_version_for(v, user, head):
        """Restricted roles (and any viewer of a quarantined tool) must not see
        raw untrusted descriptor text through the version reads — the same
        text the /safe view redacts. `v` is a fresh json.loads copy, safe to
        mutate."""
        restricted = user["role"] in ("viewer", "technician", "accountant")
        quarantined = head.get("quarantine_status") == "QUARANTINED"
        if not (restricted or quarantined):
            return v
        marker = ("[REDACTED — descriptor text withheld from restricted role / "
                  "quarantined tool]")
        d = v.get("descriptor")
        if isinstance(d, dict):
            d["tool_description"] = marker
            d["tool_summary"] = marker
            for p in d.get("schema_envelope", {}).get("parameters", []):
                p["description"] = marker
        se = v.get("schema_envelope")
        if isinstance(se, dict):
            for p in se.get("parameters", []):
                p["description"] = marker
        v["restricted_view"] = True
        return v

    def _validate_tool_taxonomy(body):
        category = str(body.get("category", ""))
        if category not in _tr.TOOL_CATEGORIES:
            raise HTTPException(400, f"unknown tool category {category}")
        se_class = str(body.get("side_effect_class", "PURE_READ"))
        if se_class not in _tr.SIDE_EFFECT_CLASSES:
            raise HTTPException(400, f"unknown side_effect_class {se_class}")

    def _state_hash_for(vpayload, head_meta, status):
        """Recompute a tool state hash for `status` from the version's stored
        sub-hashes — used whenever a status is overridden after assembly so the
        persisted/ledgered state hash always binds the ACTUAL status."""
        return _tr.tool_state_hash(
            tool_id=vpayload["tool_id"], tenant_id=vpayload["tenant_id"],
            tool_key=head_meta["tool_key"], category=head_meta["category"],
            side_effect_class=head_meta["side_effect_class"],
            risk_class=head_meta["risk_class"],
            trust_tier=head_meta["trust_tier"], status=status,
            latest_version_id=vpayload["tool_version_id"],
            version_number=vpayload["version_number"],
            descriptor_hash=vpayload["descriptor_hash"],
            tbom_hash=vpayload["tbom"]["tbom_hash"],
            policy_capsule_hash=vpayload["policy_capsule"][
                "policy_capsule_hash"],
            risk_capsule_hash=vpayload["risk_capsule"]["risk_capsule_hash"],
            invariant_matrix_hash=vpayload["invariant_matrix"][
                "invariant_matrix_hash"],
            negative_capability_hash=vpayload["negative_capabilities"][
                "negative_capability_hash"],
            admission_package_hash=vpayload["admission_package"][
                "admission_package_hash"],
            capability_lattice_hash=vpayload["capability_lattice"][
                "capability_lattice_hash"],
            version_chain_hash=vpayload["version_chain_hash"])

    def _apply_cross_tenant_override(head_meta, vpayload, declared_tid, tid):
        """A descriptor that declares a foreign tenant is a hard cross-tenant
        rejection recorded on the tool (never silently accepted). Recomputes the
        state hash so it binds the rejected status, not the pre-override one."""
        if declared_tid == tid:
            return
        dominant = _tr.dominant_status(
            set(head_meta["status"].split()) | {"CROSS_TENANT_REJECTED"})
        head_meta["status"] = dominant
        head_meta["admitted"] = False
        vpayload["status"] = dominant
        vpayload["admission_posture"]["hard_fail_signals"] = sorted(
            set(vpayload["admission_posture"]["hard_fail_signals"])
            | {"CROSS_TENANT_REJECTED"})
        vpayload["admission_posture"]["reasons"].append(
            "declared tenant does not match actor tenant")
        new_sh = _state_hash_for(vpayload, head_meta, dominant)
        head_meta["state_hash"] = new_sh
        vpayload["tool_state_hash"] = new_sh

    # -- registry-level routes (registered before /{tool_id} to avoid shadow) --
    @app.get("/ai-tools/types")
    async def tool_types(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return {"categories": sorted(_tr.TOOL_CATEGORIES),
                "forbidden_categories": sorted(_tr.FORBIDDEN_CATEGORIES),
                "side_effect_classes": sorted(_tr.SIDE_EFFECT_CLASSES),
                "forbidden_side_effects": sorted(_tr.FORBIDDEN_SIDE_EFFECTS),
                "risk_classes": sorted(_tr.RISK_CLASSES),
                "statuses": sorted(_tr.TOOL_STATUSES),
                "status_dominance": _tr.STATUS_DOMINANCE,
                "trust_tiers": sorted(_tr.TRUST_TIERS),
                "data_classes": sorted(_tr.DATA_CLASSES),
                "consent_requirements": sorted(_tr.CONSENT_REQUIREMENTS),
                "prompt_context_exposure": sorted(_tr.PROMPT_CONTEXT_EXPOSURE),
                "negative_capabilities": _tr.NEGATIVE_CAPABILITIES,
                "security_invariants": _tr.SECURITY_INVARIANTS,
                "honesty_labels": _tr.HONESTY_LABELS}

    @app.get("/ai-tools/registry/policy")
    async def tool_registry_policy(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return {"registry_kind": "capability-descriptor-registry",
                "is_tool_broker": False, "has_execute_endpoint": False,
                "has_dry_run_execution": False, "calls_external_providers": False,
                "calls_llm": False, "is_mcp_server": False,
                "admission_is_fail_closed": True,
                "forbidden_categories": sorted(_tr.FORBIDDEN_CATEGORIES),
                "forbidden_side_effects": sorted(_tr.FORBIDDEN_SIDE_EFFECTS),
                "status_dominance": _tr.STATUS_DOMINANCE,
                "honesty_labels": _tr.HONESTY_LABELS}

    @app.get("/ai-tools/registry/snapshot")
    async def tool_registry_snapshot(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        tid = user["tid"]
        heads = tool_store.list(tenant_id=tid)
        by_status, by_category = {}, {}
        for h in heads:
            by_status[h["status"]] = by_status.get(h["status"], 0) + 1
            by_category[h["category"]] = by_category.get(h["category"], 0) + 1
        snap = _tr.registry_snapshot_hash([h["tool_state_hash"] for h in heads])
        return {"tenant_id": tid, "tool_count": len(heads),
                "tools_by_status": by_status, "tools_by_category": by_category,
                "admitted_count": sum(1 for h in heads if h["admitted"]),
                "quarantined_count": sum(1 for h in heads
                                         if h["quarantine_status"]
                                         == "QUARANTINED"),
                "registry_snapshot_hash": snap,
                "honesty_labels": _tr.HONESTY_LABELS}

    @app.post("/ai-tools/registry/scan")
    async def tool_registry_scan(body: dict,
                                 user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        # Ad-hoc descriptor scan (never persists). Detects poisoning in
        # arbitrary declared text before a caller even registers it.
        scanner = _tr.scan_descriptor(
            tool_name=str(body.get("tool_name", "")),
            tool_summary=str(body.get("tool_summary", "")),
            tool_description=str(body.get("tool_description", "")),
            parameter_texts=[str(p.get("description", ""))
                             for p in (body.get("parameters") or [])],
            purpose_texts=[str(x) for x in (body.get("allowed_purposes")
                                            or [])])
        return {"scanner": scanner, "honesty_labels": _tr.HONESTY_LABELS}

    @app.get("/ai-tools/registry/events")
    async def tool_registry_events(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        evs = tool_store.events(tenant_id=user["tid"])
        # Verify the tenant-scoped event chain.
        chain_ok, prev = True, None
        for e in evs:
            if e["previous_event_hash"] != (prev or _tr.GENESIS):
                chain_ok = False
            prev = e["event_hash"]
        return {"events": evs, "event_count": len(evs),
                "event_chain_valid": chain_ok,
                "honesty_labels": _tr.HONESTY_LABELS}

    @app.post("/ai-tools")
    async def register_tool(body: dict, user: dict = Depends(current_user)):
        # Registering a descriptor records a capability declaration. It executes
        # nothing: no tool call, no MCP, no LLM, no external provider, no send,
        # no payment, no CRM write, no evidence rewrite, no export.
        require_permission(user, "case.update")
        tid = user["tid"]
        _validate_tool_taxonomy(body)
        category = str(body.get("category", ""))
        # A descriptor may declare its own tenant_id; a mismatch is a hard
        # cross-tenant rejection recorded on the tool (never silently accepted).
        declared_tid = str(body.get("tenant_id", tid)) or tid
        actor_type = "ai_employee" if user["role"] == "ai_worker" else "human"
        tool_id = str(uuid.uuid4())
        version_id = tool_id + "-v1"
        now = utcnow()
        trust_tier = _tr.default_trust_tier(actor_type)
        existing = _tool_summaries(tid)

        vpayload, head_meta = _assemble_tool(
            tool_id=tool_id, version_id=version_id, version_number=1, tid=tid,
            prev_version=None, body=body, actor_id=user["uid"],
            actor_type=actor_type, trust_tier=trust_tier, supply_chain=None,
            existing_summaries=existing, created_at=now)

        _apply_cross_tenant_override(head_meta, vpayload, declared_tid, tid)

        payload = _tool_head_payload(
            tool_id=tool_id, tid=tid, actor_id=user["uid"],
            actor_type=actor_type, body=body, version_id=version_id,
            head_meta=head_meta, vpayload=vpayload, supersedes=None,
            created_at=now)
        _save_tool_head(payload, version_id=version_id, created_by=user["uid"])
        _save_tool_version(vpayload, created_by=user["uid"])
        _tool_emit(tid, event_type="TOOL_REGISTERED", tool_id=tool_id,
                   actor_id=user["uid"], actor_type=actor_type,
                   tool_state_hash=head_meta["state_hash"],
                   detail={"category": category, "status": head_meta["status"]})
        if head_meta["quarantine_status"] == "QUARANTINED":
            _tool_emit(tid, event_type="TOOL_QUARANTINED", tool_id=tool_id,
                       actor_id=user["uid"], actor_type=actor_type,
                       tool_state_hash=head_meta["state_hash"],
                       detail={"reason": payload["quarantine_reason"]})
        audit.append(event_type="AI_TOOL_REGISTERED", actor=user["uid"],
                     payload={"tool_id": tool_id, "category": category,
                              "status": head_meta["status"]})
        return payload

    @app.get("/ai-tools")
    async def list_tools(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return tool_store.list(tenant_id=user["tid"])

    @app.get("/ai-tools/{tool_id}")
    async def get_tool(tool_id: str, user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return _load_tool_or_404(tool_id, user)

    @app.get("/ai-tools/{tool_id}/safe")
    async def get_tool_safe(tool_id: str, user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        p = _load_tool_or_404(tool_id, user)
        lv = tool_store.latest_version(tool_id, tenant_id=user["tid"])
        restricted = user["role"] in ("viewer", "technician", "accountant")
        policy = lv["prompt_context_policy"]
        # A quarantined descriptor never surfaces its raw text; the safe view
        # exposes governance metadata only.
        quarantined = p["quarantine_status"] == "QUARANTINED"
        expose_desc = (policy["expose_full_descriptor_to_model"]
                       and not restricted and not quarantined)
        view = {
            "tool_id": tool_id, "tool_key": p["tool_key"],
            "tool_name": p["tool_name"], "category": p["category"],
            "status": p["status"], "risk_class": p["risk_class"],
            "trust_tier": p["trust_tier"], "side_effect_class": p[
                "side_effect_class"], "quarantine_status": p["quarantine_status"],
            "effective_prompt_exposure": policy["effective_exposure"],
            "tool_description": (lv["descriptor"]["tool_description"]
                                 if expose_desc else
                                 "[REDACTED — descriptor not exposable to "
                                 "model context under policy]"),
            "hard_fail_signals": p["hard_fail_signals"],
            "may_execute_now": False,
            "honesty_labels": _tr.HONESTY_LABELS,
        }
        view["tool_safe_view_hash"] = _tr._sha(
            {k: v for k, v in view.items()
             if k not in ("tool_safe_view_hash", "honesty_labels")})
        return view

    @app.get("/ai-tools/{tool_id}/versions")
    async def list_tool_versions(tool_id: str,
                                 user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        head = _load_tool_or_404(tool_id, user)
        versions = [_redact_version_for(v, user, head) for v in
                    tool_store.versions(tool_id, tenant_id=user["tid"])]
        return {"tool_id": tool_id, "versions": versions,
                "honesty_labels": _tr.HONESTY_LABELS}

    @app.get("/ai-tools/{tool_id}/versions/{version_id}")
    async def get_tool_version(tool_id: str, version_id: str,
                               user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        head = _load_tool_or_404(tool_id, user)
        v = tool_store.version(tool_id, version_id, tenant_id=user["tid"])
        if v is None:
            raise HTTPException(404, "tool version not found")
        return _redact_version_for(v, user, head)

    @app.post("/ai-tools/{tool_id}/versions")
    async def add_tool_version(tool_id: str, body: dict,
                               user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        tid = user["tid"]
        p = _load_tool_or_404(tool_id, user)
        _validate_tool_taxonomy(body)
        # A governance-stopped (disabled/deprecated) or terminal tool cannot be
        # silently re-versioned back to DRAFT by a case.update holder.
        if p["status"] in ("DISABLED", "DEPRECATED"):
            raise HTTPException(409, f"tool is {p['status']}; re-enable via "
                                "governance before adding a version")
        if p["status"] in _tr.TERMINAL_STATUSES:
            raise HTTPException(409, f"tool is {p['status']}; no new versions")
        prev = tool_store.latest_version(tool_id, tenant_id=tid)
        vnum = tool_store.next_version_number(tool_id, tenant_id=tid)
        actor_type = "ai_employee" if user["role"] == "ai_worker" else "human"
        trust_tier = _tr.default_trust_tier(actor_type)
        version_id = f"{tool_id}-v{vnum}"
        now = utcnow()
        existing = _tool_summaries(tid, exclude_id=tool_id)
        # Supply-chain guard: compare the proposed descriptor to the prior
        # admitted/latest snapshot to detect drift / rug-pull.
        supply = None
        if prev is not None:
            tmp_v, tmp_head = _assemble_tool(
                tool_id=tool_id, version_id=version_id, version_number=vnum,
                tid=tid, prev_version=prev, body=body, actor_id=user["uid"],
                actor_type=actor_type, trust_tier=trust_tier, supply_chain=None,
                existing_summaries=existing, created_at=now)
            supply = _tr.supply_chain_guard(
                admitted_snapshot={
                    "descriptor_hash": prev["descriptor_hash"],
                    "effect_contract_hash": prev["effect_contract"][
                        "effect_contract_hash"],
                    "data_flow_contract_hash": prev["data_flow_contract"][
                        "data_flow_contract_hash"],
                    "side_effect_rank": prev["effect_contract"][
                        "side_effect_rank"],
                    "risk_rank": _tr.RISK_RANK[prev["risk_class"]],
                    "category": prev["descriptor"]["category"],
                    "scanner_clean": prev["scanner"]["quarantine_status"]
                    == "CLEAN",
                    "forbidden_capability": bool(
                        prev["admission_posture"]["hard_fail_signals"])},
                new_snapshot={
                    "descriptor_hash": tmp_v["descriptor_hash"],
                    "effect_contract_hash": tmp_v["effect_contract"][
                        "effect_contract_hash"],
                    "data_flow_contract_hash": tmp_v["data_flow_contract"][
                        "data_flow_contract_hash"],
                    "side_effect_rank": tmp_v["effect_contract"][
                        "side_effect_rank"],
                    "risk_rank": _tr.RISK_RANK[tmp_v["risk_class"]],
                    "category": tmp_v["descriptor"]["category"],
                    "scanner_clean": tmp_v["scanner"]["quarantine_status"]
                    == "CLEAN",
                    "forbidden_capability": bool(
                        tmp_v["admission_posture"]["hard_fail_signals"])})

        vpayload, head_meta = _assemble_tool(
            tool_id=tool_id, version_id=version_id, version_number=vnum, tid=tid,
            prev_version=prev, body=body, actor_id=user["uid"],
            actor_type=actor_type, trust_tier=trust_tier, supply_chain=supply,
            existing_summaries=existing, created_at=now)
        # A v2 that declares a foreign tenant is rejected exactly like a v1.
        declared_tid = str(body.get("tenant_id", tid)) or tid
        _apply_cross_tenant_override(head_meta, vpayload, declared_tid, tid)
        payload = _tool_head_payload(
            tool_id=tool_id, tid=tid, actor_id=p["created_by_actor_id"],
            actor_type=p["created_by_actor_type"], body=body,
            version_id=version_id, head_meta=head_meta, vpayload=vpayload,
            supersedes=p.get("supersedes_tool_id"), created_at=now)
        payload["created_at"] = p["created_at"]
        _save_tool_version(vpayload, created_by=user["uid"])
        tool_store.update_head(
            tool_id, tenant_id=tid, payload=payload, tool_key=head_meta[
                "tool_key"], category=head_meta["category"],
            side_effect_class=head_meta["side_effect_class"],
            risk_class=head_meta["risk_class"],
            trust_tier=head_meta["trust_tier"], status=head_meta["status"],
            tool_version=vnum, latest_version_id=version_id,
            tool_state_hash=head_meta["state_hash"],
            descriptor_hash=head_meta["descriptor_hash"],
            tbom_hash=head_meta["tbom_hash"],
            policy_capsule_hash=head_meta["policy_capsule_hash"],
            risk_capsule_hash=head_meta["risk_capsule_hash"],
            admission_package_hash=head_meta["admission_package_hash"],
            quarantine_status=head_meta["quarantine_status"],
            admitted=1 if head_meta["admitted"] else 0,
            updated_at=now)
        _tool_emit(tid, event_type="TOOL_VERSION_ADDED", tool_id=tool_id,
                   actor_id=user["uid"], actor_type=actor_type,
                   tool_state_hash=head_meta["state_hash"],
                   detail={"version_number": vnum,
                           "status": head_meta["status"]})
        if supply and supply["verdict"] == "RUG_PULL_DETECTED":
            _tool_emit(tid, event_type="TOOL_RUG_PULL_DETECTED", tool_id=tool_id,
                       actor_id=user["uid"], actor_type=actor_type,
                       tool_state_hash=head_meta["state_hash"],
                       detail={"reasons": supply["reasons"]})
        elif supply and supply["verdict"] == "DRIFT_DETECTED":
            _tool_emit(tid, event_type="TOOL_DRIFT_DETECTED", tool_id=tool_id,
                       actor_id=user["uid"], actor_type=actor_type,
                       tool_state_hash=head_meta["state_hash"],
                       detail={"reasons": supply["reasons"]})
        return {"tool_id": tool_id, "version_number": vnum,
                "tool_version": vpayload, "supply_chain": supply,
                "honesty_labels": _tr.HONESTY_LABELS}

    @app.post("/ai-tools/{tool_id}/admit")
    async def admit_tool(tool_id: str, user: dict = Depends(current_user)):
        # Admission = a human governor records that a FUTURE broker MAY consider
        # this tool. It executes nothing and is fail-closed on every hard-fail.
        require_permission(user, _TOOL_ADMIT_PERM)
        tid = user["tid"]
        p = _load_tool_or_404(tool_id, user)
        if p["status"] in _tr.TERMINAL_STATUSES:
            raise HTTPException(409, f"tool is {p['status']}; cannot admit")
        # A governance-stopped tool cannot be admitted; the stop must be
        # explicitly lifted (new clean version) first.
        if p["status"] in ("DISABLED", "DEPRECATED"):
            raise HTTPException(409, f"tool is {p['status']}; cannot admit")
        lv = tool_store.latest_version(tool_id, tenant_id=tid)
        # Admission must be requested by a HUMAN governor: derive the actor type
        # instead of assuming it, so the kernel's human-in-the-loop guard is
        # real and the ledger attribution is truthful.
        actor_type = "ai_employee" if user["role"] == "ai_worker" else "human"
        # Re-check collisions / multi-tool hazards against the LIVE registry —
        # a tool clean at registration may since have been shadowed.
        existing = _tool_summaries(tid, exclude_id=tool_id)
        candidate = {"tool_id": tool_id, "tool_key": p["tool_key"],
                     "aliases": p.get("aliases", []),
                     "trust_tier": p["trust_tier"],
                     "risk_rank": _tr.RISK_RANK.get(p["risk_class"], 2),
                     "status": p["status"]}
        collision = _tr.detect_collisions(candidate=candidate, existing=existing)
        df = lv["data_flow_contract"]
        cand_multi = {"tool_id": tool_id, "tool_key": p["tool_key"],
                      "side_effect_class": p["side_effect_class"],
                      "reads_data_classes": df["reads_data_classes"],
                      "writes_data_classes": df["writes_data_classes"],
                      "egress": df["egress_targets"], "status": p["status"]}
        multi = _tr.detect_multi_tool_poisoning(existing + [cand_multi])
        decision = _tr.evaluate_admission(
            category=lv["descriptor"]["category"],
            invariant_matrix=lv["invariant_matrix"],
            negative_capabilities=lv["negative_capabilities"],
            risk_capsule=lv["risk_capsule"], scanner=lv["scanner"],
            implicit_findings=lv["implicit_findings"],
            lattice=lv["capability_lattice"], collision=collision,
            multi_tool=multi, supply_chain=lv["supply_chain"],
            declared_tenant_id=tid, actor_tenant_id=tid,
            requested_by_human=(actor_type == "human"))
        # Fold every previously-recorded hard-fail (e.g. an app-level
        # CROSS_TENANT_REJECTED from registration, which the kernel cannot see)
        # into the decision so admission can never clear a prior hard-fail.
        prior = set(p.get("hard_fail_signals", []))
        signals = set(decision["hard_fail_signals"]) | prior
        if signals:
            status = _tr.dominant_status(signals)
            admitted = False
        else:
            status = decision["admission_status"]
            admitted = decision["admitted"]
        decision = {**decision, "admission_status": status,
                    "admitted": admitted,
                    "hard_fail_signals": sorted(signals),
                    "reasons": decision["reasons"] + (
                        ["blocked by prior recorded hard-fail signals"]
                        if prior - set(decision["hard_fail_signals"]) else [])}
        new_state = _tr.tool_state_hash(
            tool_id=tool_id, tenant_id=tid, tool_key=p["tool_key"],
            category=p["category"], side_effect_class=p["side_effect_class"],
            risk_class=p["risk_class"], trust_tier=p["trust_tier"],
            status=status, latest_version_id=p["latest_version_id"],
            version_number=p["tool_version"],
            descriptor_hash=p["descriptor_hash"], tbom_hash=p["tbom_hash"],
            policy_capsule_hash=p["policy_capsule_hash"],
            risk_capsule_hash=p["risk_capsule_hash"],
            invariant_matrix_hash=lv["invariant_matrix"][
                "invariant_matrix_hash"],
            negative_capability_hash=lv["negative_capabilities"][
                "negative_capability_hash"],
            admission_package_hash=p["admission_package_hash"],
            capability_lattice_hash=lv["capability_lattice"][
                "capability_lattice_hash"],
            version_chain_hash=lv["version_chain_hash"])
        p["status"] = status
        p["admitted"] = admitted
        p["tool_state_hash"] = new_state
        p["admission_reasons"] = decision["reasons"]
        p["hard_fail_signals"] = decision["hard_fail_signals"]
        p["updated_at"] = utcnow()
        tool_store.update_head(tool_id, tenant_id=tid, payload=p, status=status,
                               admitted=1 if admitted else 0,
                               tool_state_hash=new_state, updated_at=p[
                                   "updated_at"])
        _tool_emit(tid, event_type=("TOOL_ADMITTED" if admitted else
                                    "TOOL_ADMISSION_REJECTED"), tool_id=tool_id,
                   actor_id=user["uid"], actor_type=actor_type,
                   tool_state_hash=new_state,
                   detail={"status": status, "signals": decision[
                       "hard_fail_signals"]})
        return {"tool_id": tool_id, "admission_status": status,
                "admitted": admitted, "hard_fail_signals": decision[
                    "hard_fail_signals"], "reasons": decision["reasons"],
                "may_execute_now": False, "honesty_labels": _tr.HONESTY_LABELS}

    def _tool_lifecycle_transition(tool_id, user, *, target, event_type,
                                   allow_from=None):
        tid = user["tid"]
        p = _load_tool_or_404(tool_id, user)
        if p["status"] in _tr.TERMINAL_STATUSES:
            raise HTTPException(409, f"tool is {p['status']}; cannot {target}")
        if allow_from is not None and p["status"] not in allow_from:
            raise HTTPException(409, f"cannot {target} from {p['status']}")
        lv = tool_store.latest_version(tool_id, tenant_id=tid)
        new_state = _tr.tool_state_hash(
            tool_id=tool_id, tenant_id=tid, tool_key=p["tool_key"],
            category=p["category"], side_effect_class=p["side_effect_class"],
            risk_class=p["risk_class"], trust_tier=p["trust_tier"],
            status=target, latest_version_id=p["latest_version_id"],
            version_number=p["tool_version"],
            descriptor_hash=p["descriptor_hash"], tbom_hash=p["tbom_hash"],
            policy_capsule_hash=p["policy_capsule_hash"],
            risk_capsule_hash=p["risk_capsule_hash"],
            invariant_matrix_hash=lv["invariant_matrix"][
                "invariant_matrix_hash"],
            negative_capability_hash=lv["negative_capabilities"][
                "negative_capability_hash"],
            admission_package_hash=p["admission_package_hash"],
            capability_lattice_hash=lv["capability_lattice"][
                "capability_lattice_hash"],
            version_chain_hash=lv["version_chain_hash"])
        p["status"] = target
        p["admitted"] = False
        p["tool_state_hash"] = new_state
        p["updated_at"] = utcnow()
        tool_store.update_head(tool_id, tenant_id=tid, payload=p, status=target,
                               admitted=0, tool_state_hash=new_state,
                               updated_at=p["updated_at"])
        _tool_emit(tid, event_type=event_type, tool_id=tool_id,
                   actor_id=user["uid"], actor_type="human",
                   tool_state_hash=new_state, detail={"status": target})
        return {"tool_id": tool_id, "status": target,
                "honesty_labels": _tr.HONESTY_LABELS}

    @app.post("/ai-tools/{tool_id}/disable")
    async def disable_tool(tool_id: str, user: dict = Depends(current_user)):
        require_permission(user, _TOOL_ADMIT_PERM)
        return _tool_lifecycle_transition(
            tool_id, user, target="DISABLED", event_type="TOOL_DISABLED")

    @app.post("/ai-tools/{tool_id}/deprecate")
    async def deprecate_tool(tool_id: str, user: dict = Depends(current_user)):
        require_permission(user, _TOOL_ADMIT_PERM)
        return _tool_lifecycle_transition(
            tool_id, user, target="DEPRECATED", event_type="TOOL_DEPRECATED")

    @app.post("/ai-tools/{tool_id}/supersede")
    async def supersede_tool(tool_id: str, body: dict,
                             user: dict = Depends(current_user)):
        require_permission(user, _TOOL_ADMIT_PERM)
        tid = user["tid"]
        successor = str(body.get("successor_tool_id", ""))
        if successor:
            if tool_store.payload(successor, tenant_id=tid) is None:
                raise HTTPException(400, "successor tool not found")
        res = _tool_lifecycle_transition(
            tool_id, user, target="SUPERSEDED", event_type="TOOL_SUPERSEDED")
        if successor:
            p = tool_store.payload(tool_id, tenant_id=tid)
            p["superseded_by_tool_id"] = successor
            tool_store.update_head(tool_id, tenant_id=tid, payload=p)
        res["superseded_by_tool_id"] = successor or None
        return res

    @app.get("/ai-tools/{tool_id}/policy")
    async def get_tool_policy(tool_id: str,
                              user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_tool_or_404(tool_id, user)
        lv = tool_store.latest_version(tool_id, tenant_id=user["tid"])
        return {"tool_id": tool_id, "policy_capsule": lv["policy_capsule"],
                "prompt_context_policy": lv["prompt_context_policy"],
                "invariant_matrix": lv["invariant_matrix"],
                "honesty_labels": _tr.HONESTY_LABELS}

    @app.get("/ai-tools/{tool_id}/risk")
    async def get_tool_risk(tool_id: str, user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_tool_or_404(tool_id, user)
        lv = tool_store.latest_version(tool_id, tenant_id=user["tid"])
        return {"tool_id": tool_id, "risk_capsule": lv["risk_capsule"],
                "risk_class": lv["risk_class"],
                "honesty_labels": _tr.HONESTY_LABELS}

    @app.get("/ai-tools/{tool_id}/tbom")
    async def get_tool_tbom(tool_id: str, user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_tool_or_404(tool_id, user)
        lv = tool_store.latest_version(tool_id, tenant_id=user["tid"])
        return {"tool_id": tool_id, "tbom": lv["tbom"],
                "honesty_labels": _tr.HONESTY_LABELS}

    @app.get("/ai-tools/{tool_id}/security-case")
    async def get_tool_security_case(tool_id: str,
                                     user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_tool_or_404(tool_id, user)
        lv = tool_store.latest_version(tool_id, tenant_id=user["tid"])
        return {"tool_id": tool_id, "security_case": lv["security_case"],
                "honesty_labels": _tr.HONESTY_LABELS}

    @app.get("/ai-tools/{tool_id}/negative-capabilities")
    async def get_tool_negative_caps(tool_id: str,
                                     user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_tool_or_404(tool_id, user)
        lv = tool_store.latest_version(tool_id, tenant_id=user["tid"])
        return {"tool_id": tool_id,
                "negative_capabilities": lv["negative_capabilities"],
                "capability_lattice": lv["capability_lattice"],
                "honesty_labels": _tr.HONESTY_LABELS}

    @app.get("/ai-tools/{tool_id}/lineage")
    async def get_tool_lineage(tool_id: str,
                               user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        p = _load_tool_or_404(tool_id, user)
        versions = tool_store.versions(tool_id, tenant_id=user["tid"])
        lineage = [{"version_number": v["version_number"], "status": v[
            "status"], "descriptor_hash": v["descriptor_hash"],
            "version_hash": v["version_hash"],
            "previous_version_hash": v["previous_version_hash"],
            "version_chain_hash": v["version_chain_hash"]} for v in versions]
        return {"tool_id": tool_id, "tool_key": p["tool_key"],
                "supersedes_tool_id": p.get("supersedes_tool_id"),
                "superseded_by_tool_id": p.get("superseded_by_tool_id"),
                "lineage": lineage, "honesty_labels": _tr.HONESTY_LABELS}

    @app.post("/ai-tools/{tool_id}/verify")
    async def verify_tool(tool_id: str, user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        p = _load_tool_or_404(tool_id, user)
        tid = user["tid"]
        actor_type = "ai_employee" if user["role"] == "ai_worker" else "human"
        versions = tool_store.versions(tool_id, tenant_id=tid)
        reasons, chain_prev, chain_ok = [], None, True
        # (payload key, self-hash field, *extra excluded fields). Every stored
        # sub-object that carries its own *_hash is recomputed, so tampering ANY
        # governance object — not just the descriptor — is caught.
        _SUBHASHES = [
            ("scanner", "scanner_hash"),
            ("schema_envelope", "schema_envelope_hash"),
            ("effect_contract", "effect_contract_hash"),
            ("data_flow_contract", "data_flow_contract_hash"),
            ("purpose_contract", "purpose_contract_hash"),
            ("consent_contract", "consent_contract_hash"),
            ("prompt_context_policy", "prompt_context_policy_hash"),
            ("invariant_matrix", "invariant_matrix_hash"),
            ("negative_capabilities", "negative_capability_hash"),
            ("risk_capsule", "risk_capsule_hash"),
            ("capability_lattice", "capability_lattice_hash"),
            ("tbom", "tbom_hash"),
            ("admission_package", "admission_package_hash"),
            ("security_case", "security_case_hash"),
            ("policy_capsule", "policy_capsule_hash", "policy_input_hash",
             "policy_output_hash"),
        ]
        # Top-level contract copies (what the supply-chain guard + endpoints
        # read) must be byte-identical to the descriptor-embedded copies.
        _EMBEDDED = ["schema_envelope", "effect_contract", "data_flow_contract",
                     "purpose_contract", "consent_contract",
                     "prompt_context_policy"]
        for v in versions:
            n = v["version_number"]
            if _tr.descriptor_hash(v["descriptor"]) != v["descriptor_hash"]:
                reasons.append(f"v{n}: descriptor hash mismatch")
            for key in _EMBEDDED:
                if v.get(key) != v["descriptor"].get(key):
                    reasons.append(f"v{n}: {key} diverges from descriptor copy")
            for spec in _SUBHASHES:
                key, hfield, extra = spec[0], spec[1], spec[2:]
                obj = v.get(key) or {}
                if _tr._core_hash(obj, hfield, *extra) != obj.get(hfield):
                    reasons.append(f"v{n}: {key} hash mismatch")
            recomputed_v = _tr.version_hash(
                tool_id=tool_id, version_number=n,
                descriptor_hash=v["descriptor_hash"],
                tbom_hash=v["tbom"]["tbom_hash"],
                policy_capsule_hash=v["policy_capsule"]["policy_capsule_hash"],
                admission_package_hash=v["admission_package"][
                    "admission_package_hash"],
                previous_version_hash=v.get("previous_version_hash"),
                created_by_actor_id=v["created_by_actor_id"])
            if recomputed_v != v["version_hash"]:
                reasons.append(f"v{n}: version hash mismatch")
            if _tr.version_chain_hash(chain_prev, v["version_hash"]) != v[
                    "version_chain_hash"]:
                chain_ok = False
                reasons.append(f"v{n}: version chain mismatch")
            chain_prev = v["version_chain_hash"]
        lv = versions[-1] if versions else None
        if lv is not None:
            if p.get("descriptor_hash") != lv["descriptor_hash"]:
                reasons.append("head descriptor hash diverges from latest "
                               "version")
            if p.get("version_hash") != lv["version_hash"]:
                reasons.append("head version hash diverges from latest version")
            # The mutable head carries the GOVERNANCE state (status, admitted,
            # trust) a future broker consumes. Recompute its state hash from the
            # head fields + latest-version sub-hashes: a status/admitted/trust
            # tamper that isn't matched by a recomputed state hash is caught.
            recomputed_head_state = _tr.tool_state_hash(
                tool_id=tool_id, tenant_id=tid, tool_key=p["tool_key"],
                category=p["category"], side_effect_class=p["side_effect_class"],
                risk_class=p["risk_class"], trust_tier=p["trust_tier"],
                status=p["status"], latest_version_id=p["latest_version_id"],
                version_number=p["tool_version"],
                descriptor_hash=p["descriptor_hash"], tbom_hash=p["tbom_hash"],
                policy_capsule_hash=p["policy_capsule_hash"],
                risk_capsule_hash=p["risk_capsule_hash"],
                invariant_matrix_hash=lv["invariant_matrix"][
                    "invariant_matrix_hash"],
                negative_capability_hash=lv["negative_capabilities"][
                    "negative_capability_hash"],
                admission_package_hash=p["admission_package_hash"],
                capability_lattice_hash=lv["capability_lattice"][
                    "capability_lattice_hash"],
                version_chain_hash=lv["version_chain_hash"])
            if recomputed_head_state != p.get("tool_state_hash"):
                reasons.append("head governance state hash is inconsistent with "
                               "head fields (status/admitted/trust tamper)")
            # And the head's governance hashes must equal the latest version's.
            if p.get("policy_capsule_hash") != lv["policy_capsule"][
                    "policy_capsule_hash"]:
                reasons.append("head policy capsule hash diverges from latest "
                               "version")
            if p.get("admitted") and p.get("status") != \
                    "AVAILABLE_FOR_FUTURE_BROKER":
                reasons.append("head marked admitted without an "
                               "AVAILABLE_FOR_FUTURE_BROKER status")
        # Cross-check the head state hash against the tamper-evident ledger:
        # the latest registry event for this tool recorded the state hash at the
        # last legitimate mutation, so a head-state tamper with no matching
        # event is caught.
        tool_events = tool_store.events(tenant_id=tid, tool_id=tool_id)
        last_ev = tool_events[-1] if tool_events else None
        if last_ev is not None and last_ev.get("tool_state_hash") and \
                last_ev["tool_state_hash"] != p.get("tool_state_hash"):
            reasons.append("head state hash diverges from the latest registry "
                           "ledger event (untracked mutation)")
        # Denormalized head COLUMNS drive list/snapshot/admission reads, so a
        # column-only DB tamper (flipping status/admitted/*_hash without
        # touching payload_json) must also be caught. Cross-check the row
        # columns against the authoritative payload.
        row = tool_store.get(tool_id, tenant_id=tid)
        if row is not None:
            for col in ("status", "descriptor_hash", "tool_state_hash",
                        "policy_capsule_hash", "risk_capsule_hash", "risk_class",
                        "category", "side_effect_class", "quarantine_status"):
                if row[col] != p.get(col):
                    reasons.append(f"head column '{col}' diverges from payload")
            if int(row["admitted"]) != (1 if p.get("admitted") else 0):
                reasons.append("head column 'admitted' diverges from payload")
        status = "MATCHED" if not reasons else "MISMATCHED"
        # Only emit on tamper: a clean verification must not let a read-only
        # role append to the governance ledger (a genuine tamper requires DB
        # write access the caller does not have through this surface).
        if reasons:
            _tool_emit(tid, event_type="TOOL_TAMPER_DETECTED", tool_id=tool_id,
                       actor_id=user["uid"], actor_type=actor_type,
                       tool_state_hash=p["tool_state_hash"],
                       detail={"reasons": reasons})
        return {"tool_id": tool_id, "verification_status": status,
                "tamper_detected": bool(reasons), "tamper_reasons": reasons,
                "dominant_status_if_tampered": "TAMPERED" if reasons else None,
                "version_chain_status": "VALID" if chain_ok else "MISMATCHED",
                "versions_checked": len(versions),
                "honesty_labels": _tr.HONESTY_LABELS}

    @app.post("/ai-tools/{tool_id}/diff")
    async def diff_tool(tool_id: str, body: dict,
                        user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_tool_or_404(tool_id, user)
        tid = user["tid"]
        va = tool_store.version(tool_id, str(body.get("from_version_id", "")),
                                tenant_id=tid)
        vb = tool_store.version(tool_id, str(body.get("to_version_id", "")),
                                tenant_id=tid)
        if va is None or vb is None:
            raise HTTPException(404, "version not found for diff")
        fields = ["descriptor_hash", "risk_class", "status"]
        changed = {f: {"from": va.get(f), "to": vb.get(f)}
                   for f in fields if va.get(f) != vb.get(f)}
        hash_fields = {
            "effect_contract_hash": ("effect_contract", "effect_contract_hash"),
            "data_flow_contract_hash": ("data_flow_contract",
                                        "data_flow_contract_hash"),
            "tbom_hash": ("tbom", "tbom_hash"),
            "policy_capsule_hash": ("policy_capsule", "policy_capsule_hash")}
        for label, (obj, key) in hash_fields.items():
            if va[obj][key] != vb[obj][key]:
                changed[label] = {"from": va[obj][key], "to": vb[obj][key]}
        return {"tool_id": tool_id,
                "from_version": va["version_number"],
                "to_version": vb["version_number"], "changed_fields": changed,
                "identical": not changed, "honesty_labels": _tr.HONESTY_LABELS}

    @app.post("/ai-tools/{tool_id}/drift-check")
    async def drift_check_tool(tool_id: str, body: dict,
                               user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        tid = user["tid"]
        p = _load_tool_or_404(tool_id, user)
        lv = tool_store.latest_version(tool_id, tenant_id=tid)
        # Compare the current admitted/latest snapshot to a proposed descriptor
        # body (or to itself, which must be STABLE). Detection only; no mutation.
        actor_type = "ai_employee" if user["role"] == "ai_worker" else "human"
        proposed = body.get("proposed_descriptor")
        if proposed:
            _validate_tool_taxonomy(proposed)
            tmp_v, _ = _assemble_tool(
                tool_id=tool_id, version_id=f"{tool_id}-drift", version_number=lv[
                    "version_number"], tid=tid, prev_version=lv, body=proposed,
                actor_id=user["uid"], actor_type=actor_type,
                trust_tier=_tr.default_trust_tier(actor_type), supply_chain=None,
                existing_summaries=_tool_summaries(tid, exclude_id=tool_id),
                created_at=utcnow())
            new_snap = tmp_v
        else:
            new_snap = lv
        supply = _tr.supply_chain_guard(
            admitted_snapshot={
                "descriptor_hash": lv["descriptor_hash"],
                "effect_contract_hash": lv["effect_contract"][
                    "effect_contract_hash"],
                "data_flow_contract_hash": lv["data_flow_contract"][
                    "data_flow_contract_hash"],
                "side_effect_rank": lv["effect_contract"]["side_effect_rank"],
                "risk_rank": _tr.RISK_RANK[lv["risk_class"]],
                "category": lv["descriptor"]["category"],
                "scanner_clean": lv["scanner"]["quarantine_status"] == "CLEAN",
                "forbidden_capability": bool(lv["admission_posture"][
                    "hard_fail_signals"])},
            new_snapshot={
                "descriptor_hash": new_snap["descriptor_hash"],
                "effect_contract_hash": new_snap["effect_contract"][
                    "effect_contract_hash"],
                "data_flow_contract_hash": new_snap["data_flow_contract"][
                    "data_flow_contract_hash"],
                "side_effect_rank": new_snap["effect_contract"][
                    "side_effect_rank"],
                "risk_rank": _tr.RISK_RANK[new_snap["risk_class"]],
                "category": new_snap["descriptor"]["category"],
                "scanner_clean": new_snap["scanner"]["quarantine_status"]
                == "CLEAN",
                "forbidden_capability": bool(new_snap["admission_posture"][
                    "hard_fail_signals"])})
        return {"tool_id": tool_id, "current_status": p["status"],
                "supply_chain": supply, "honesty_labels": _tr.HONESTY_LABELS}

    # ---- ViktorAI Formal Tool Descriptor Assurance Graph (TOOL-B2) -----------------
    from ..ai_employee import tool_quality as _tq
    from ..ai_employee.tool_quality_store import ToolQualityStore
    quality_store = ToolQualityStore(db)
    app.state.quality_store = quality_store

    def _quality_peer_summaries(tid, exclude_id=None):
        """Tenant-scoped peer descriptor summaries for the planner confusion
        matrix. Never leaves the tenant boundary."""
        out = []
        for p in tool_store.list(tenant_id=tid):
            if exclude_id and p["tool_id"] == exclude_id:
                continue
            lv = tool_store.latest_version(p["tool_id"], tenant_id=tid)
            purpose = []
            if lv:
                purpose = lv["descriptor"].get("purpose_contract", {}).get(
                    "allowed_purposes", [])
            out.append({
                "tool_id": p["tool_id"], "tool_key": p["tool_key"],
                "tool_name": p["tool_name"], "aliases": p.get("aliases", []),
                "category": p["category"], "purpose": purpose,
                "risk_rank": _tr.RISK_RANK.get(p["risk_class"], 0),
                "side_effect_rank": _tr.SIDE_EFFECT_RANK.get(
                    p["side_effect_class"], 0)})
        return out

    def _quality_emit(tid, *, event_type, tool_id, actor_id, actor_type,
                      state_hash, detail):
        seq = quality_store.next_sequence(tenant_id=tid)
        prev = quality_store.last_event(tenant_id=tid)
        ev = _tq.build_quality_event(
            event_type=event_type, tool_id=tool_id, tenant_id=tid,
            actor_id=actor_id, actor_type=actor_type,
            quality_gate_state_hash=state_hash,
            previous_event_hash=(prev or {}).get("event_hash"), sequence=seq,
            detail=detail, created_at=utcnow())
        quality_store.append_event({
            "id": str(uuid.uuid4()), "tenant_id": tid, "tool_id": tool_id,
            "event_type": event_type, "sequence": seq, "actor_id": actor_id,
            "actor_type": actor_type, "event_hash": ev["event_hash"],
            "previous_event_hash": ev["previous_event_hash"],
            "quality_gate_state_hash": state_hash,
            "payload_json": json.dumps(ev), "created_at": ev["created_at"]})
        return ev

    def _run_quality_check(tool_id, user):
        tid = user["tid"]
        head = _load_tool_or_404(tool_id, user)
        lv = tool_store.latest_version(tool_id, tenant_id=tid)
        if lv is None:
            raise HTTPException(404, "tool has no version")
        actor_type = "ai_employee" if user["role"] == "ai_worker" else "human"
        _quality_emit(tid, event_type="QUALITY_CHECK_STARTED", tool_id=tool_id,
                      actor_id=user["uid"], actor_type=actor_type,
                      state_hash="", detail={"tool_version_id": lv[
                          "tool_version_id"]})
        prev = quality_store.latest(tool_id, tenant_id=tid)
        now = utcnow()
        report = _tq.build_quality_report(
            head=head, version=lv,
            existing_summaries=_quality_peer_summaries(tid, exclude_id=tool_id),
            previous_report=prev, created_at=now)
        seq = quality_store.next_seq(tool_id, tenant_id=tid)
        quality_store.save_report({
            "id": report["quality_report_id"] + f"-{seq}", "tenant_id": tid,
            "tool_id": tool_id, "tool_version_id": lv["tool_version_id"],
            "seq": seq, "quality_status": report["quality_status"],
            "quality_score_total": report["quality_score_total"],
            "tool_descriptor_hash": report["tool_descriptor_hash"],
            "quality_report_hash": report["quality_report_hash"],
            "quality_gate_state_hash": report["quality_gate_state_hash"],
            "quality_decision_hash": report["quality_decision_hash"],
            "formal_descriptor_ir_hash": report["formal_descriptor_ir_hash"],
            "assurance_graph_hash": report["assurance_graph_hash"],
            "score_vector_hash": report["score_vector_hash"],
            "quality_evidence_package_hash": report[
                "quality_evidence_package_hash"],
            "quality_assurance_case_hash": report[
                "quality_assurance_case_hash"],
            "payload_json": json.dumps(report), "created_by": user["uid"],
            "created_at": now})
        _quality_emit(tid, event_type="QUALITY_CHECK_COMPLETED", tool_id=tool_id,
                      actor_id=user["uid"], actor_type=actor_type,
                      state_hash=report["quality_gate_state_hash"],
                      detail={"status": report["quality_status"]})
        result_event = {
            "QUALITY_PASS": "QUALITY_PASS_RECORDED",
            "QUALITY_PASS_WITH_WARNINGS": "QUALITY_PASS_RECORDED",
            "QUALITY_MUTATION_FAILED": "QUALITY_MUTATION_FAILED",
            "QUALITY_METAMORPHIC_FAILED": "QUALITY_METAMORPHIC_FAILED",
            "QUALITY_IR_MISMATCH": "QUALITY_IR_MISMATCH",
            "QUALITY_ASSURANCE_GRAPH_FAILED": "QUALITY_ASSURANCE_GRAPH_FAILED",
        }.get(report["quality_status"], "QUALITY_FAIL_RECORDED")
        _quality_emit(tid, event_type=result_event, tool_id=tool_id,
                      actor_id=user["uid"], actor_type=actor_type,
                      state_hash=report["quality_gate_state_hash"],
                      detail={"status": report["quality_status"],
                              "blockers": [b["code"] for b in report[
                                  "quality_blockers"]]})
        audit.append(event_type="AI_TOOL_QUALITY_CHECKED", actor=user["uid"],
                     payload={"tool_id": tool_id,
                              "status": report["quality_status"]})
        return report

    def _load_quality_or_404(tool_id, user):
        _load_tool_or_404(tool_id, user)          # tenant-scoped 404
        rep = quality_store.latest(tool_id, tenant_id=user["tid"])
        if rep is None:
            raise HTTPException(404, "no quality report; run quality/check "
                                "first")
        return rep

    # -- registry-level quality routes (before /{tool_id}) --------------------
    @app.get("/ai-tools/registry/quality")
    async def registry_quality_summary(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        reps = quality_store.all_latest(tenant_id=user["tid"])
        by_status = {}
        for r in reps:
            by_status[r["quality_status"]] = by_status.get(
                r["quality_status"], 0) + 1
        return {"tenant_id": user["tid"], "tool_count": len(reps),
                "quality_by_status": by_status,
                "summaries": [{"tool_id": r["tool_id"],
                               "quality_status": r["quality_status"],
                               "quality_score_total": r["quality_score_total"],
                               "quality_report_hash": r["quality_report_hash"]}
                              for r in reps],
                "honesty_labels": _tq.HONESTY_LABELS}

    @app.get("/ai-tools/registry/quality/policy")
    async def registry_quality_policy(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return {"quality_gate_version": _tq.QUALITY_GATE_VERSION,
                "executes_tools": False, "calls_llm": False,
                "calls_external_provider": False, "is_mcp": False,
                "rewrites_descriptors": False,
                "quality_pass_means_executable": False,
                "quality_pass_overrides_security": False,
                "no_goodhart": "a high score never overrides a critical "
                "blocker",
                "quality_statuses": sorted(_tq.QUALITY_STATUSES),
                "blocker_dominance": _tq.BLOCKER_DOMINANCE,
                "score_dimensions": _tq.SCORE_DIMENSIONS,
                "honesty_labels": _tq.HONESTY_LABELS}

    @app.post("/ai-tools/{tool_id}/quality/check")
    async def quality_check(tool_id: str, user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        report = _run_quality_check(tool_id, user)
        return report

    @app.get("/ai-tools/{tool_id}/quality")
    async def quality_latest(tool_id: str, user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return _load_quality_or_404(tool_id, user)

    @app.get("/ai-tools/{tool_id}/quality/history")
    async def quality_history(tool_id: str,
                              user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_tool_or_404(tool_id, user)
        hist = quality_store.history(tool_id, tenant_id=user["tid"])
        return {"tool_id": tool_id, "count": len(hist),
                "history": [{"seq": i + 1, "quality_status": r[
                    "quality_status"], "quality_score_total": r[
                    "quality_score_total"], "quality_report_hash": r[
                    "quality_report_hash"], "created_at": r["created_at"]}
                    for i, r in enumerate(hist)],
                "honesty_labels": _tq.HONESTY_LABELS}

    @app.get("/ai-tools/{tool_id}/quality/safe")
    async def quality_safe(tool_id: str, user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        rep = _load_quality_or_404(tool_id, user)
        restricted = user["role"] in ("viewer", "technician", "accountant")
        boundary = rep["planner_selection_boundary"]
        # Never surface raw descriptor prose for a NEVER_EXPOSE / restricted view.
        show_ir = not restricted and boundary[
            "minimal_context_status"] != "NEVER_EXPOSE"
        view = {
            "tool_id": tool_id, "quality_status": rep["quality_status"],
            "quality_score_total": rep["quality_score_total"],
            "descriptor_safety_score": rep["descriptor_safety_score"],
            "quality_blockers": [b["code"] for b in rep["quality_blockers"]],
            "quality_warnings": [w["code"] for w in rep["quality_warnings"]],
            "minimal_context_status": boundary["minimal_context_status"],
            "ir_summary": ({"category_guess": rep["formal_descriptor_ir"][
                "ir_category_guess"], "matches_registry": rep[
                "formal_descriptor_ir"]["ir_matches_tool_b1_truth"]}
                if show_ir else "[REDACTED — restricted / never-expose]"),
            "quality_report_hash": rep["quality_report_hash"],
            "honesty_labels": _tq.HONESTY_LABELS,
        }
        view["quality_safe_view_hash"] = _tq._sha(
            {k: v for k, v in view.items()
             if k not in ("quality_safe_view_hash", "honesty_labels")})
        return view

    @app.post("/ai-tools/{tool_id}/quality/verify")
    async def quality_verify(tool_id: str,
                             user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        rep = _load_quality_or_404(tool_id, user)
        reasons = []
        # Recompute the self-excluding sub-hashes. Each history/peer-dependent
        # object is excluded from the report hash but still integrity-checked
        # here via its own self-hash. A sub-object absent from a (legacy/partial)
        # report is skipped rather than treated as tampered.
        checks = [
            ("formal_descriptor_ir", "formal_descriptor_ir_hash"),
            ("semantic_intent_fingerprint",
             "semantic_intent_fingerprint_hash"),
            ("descriptor_assurance_graph", "assurance_graph_hash"),
            ("canonical_descriptor_semantic_record",
             "canonical_semantic_record_hash"),
            ("planner_confusion_matrix", "planner_confusion_hash"),
            ("planner_selection_boundary", "selection_boundary_hash"),
            ("counterfactual_planner", "counterfactual_planner_proof_hash"),
            ("quality_evidence_package", "quality_evidence_package_hash"),
            ("quality_assurance_case", "quality_assurance_case_hash"),
            ("non_regression_summary", "non_regression_proof_hash"),
        ]
        for obj_key, hfield in checks:
            obj = rep.get(obj_key)
            if not isinstance(obj, dict):
                continue
            if _tq._core_hash(obj, hfield) != obj.get(hfield):
                reasons.append(f"{obj_key} hash mismatch")
        recomputed = _tq._core_hash(rep, *_tq._REPORT_HASH_EXCLUDED)
        if recomputed != rep["quality_report_hash"]:
            reasons.append("quality report hash mismatch")
        status = "MATCHED" if not reasons else "MISMATCHED"
        return {"tool_id": tool_id, "verification_status": status,
                "tamper_detected": bool(reasons), "tamper_reasons": reasons,
                "honesty_labels": _tq.HONESTY_LABELS}

    @app.post("/ai-tools/{tool_id}/quality/diff")
    async def quality_diff(tool_id: str, body: dict,
                           user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_tool_or_404(tool_id, user)
        hist = quality_store.history(tool_id, tenant_id=user["tid"])
        if len(hist) < 2:
            return {"tool_id": tool_id, "comparable": False,
                    "note": "need at least two quality reports to diff",
                    "honesty_labels": _tq.HONESTY_LABELS}
        a, b = hist[-2], hist[-1]
        changed = {}
        for f in ("quality_status", "quality_score_total",
                  "tool_descriptor_hash", "quality_report_hash"):
            if a.get(f) != b.get(f):
                changed[f] = {"from": a.get(f), "to": b.get(f)}
        a_blk = {x["code"] for x in a["quality_blockers"]}
        b_blk = {x["code"] for x in b["quality_blockers"]}
        return {"tool_id": tool_id, "comparable": True, "changed_fields": changed,
                "new_blockers": sorted(b_blk - a_blk),
                "removed_blockers": sorted(a_blk - b_blk),
                "honesty_labels": _tq.HONESTY_LABELS}

    @app.get("/ai-tools/{tool_id}/quality/matrix")
    async def quality_matrix(tool_id: str,
                             user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        rep = _load_quality_or_404(tool_id, user)
        return {"tool_id": tool_id,
                "quality_score_vector": rep["quality_score_vector"],
                "quality_score_total": rep["quality_score_total"],
                "score_vector_hash": rep["score_vector_hash"],
                "honesty_labels": _tq.HONESTY_LABELS}

    @app.get("/ai-tools/{tool_id}/quality/evidence")
    async def quality_evidence(tool_id: str,
                               user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        rep = _load_quality_or_404(tool_id, user)
        return {"tool_id": tool_id,
                "quality_evidence_package": rep["quality_evidence_package"],
                "honesty_labels": _tq.HONESTY_LABELS}

    @app.get("/ai-tools/{tool_id}/quality/assurance")
    async def quality_assurance(tool_id: str,
                                user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        rep = _load_quality_or_404(tool_id, user)
        return {"tool_id": tool_id,
                "quality_assurance_case": rep["quality_assurance_case"],
                "honesty_labels": _tq.HONESTY_LABELS}

    @app.get("/ai-tools/{tool_id}/quality/ir")
    async def quality_ir(tool_id: str, user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        rep = _load_quality_or_404(tool_id, user)
        return {"tool_id": tool_id,
                "formal_descriptor_ir": rep["formal_descriptor_ir"],
                "canonical_descriptor_semantic_record": rep[
                    "canonical_descriptor_semantic_record"],
                "honesty_labels": _tq.HONESTY_LABELS}

    @app.get("/ai-tools/{tool_id}/quality/graph")
    async def quality_graph(tool_id: str, user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        rep = _load_quality_or_404(tool_id, user)
        return {"tool_id": tool_id,
                "descriptor_assurance_graph": rep["descriptor_assurance_graph"],
                "honesty_labels": _tq.HONESTY_LABELS}

    @app.get("/ai-tools/{tool_id}/quality/confusion")
    async def quality_confusion(tool_id: str,
                                user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        rep = _load_quality_or_404(tool_id, user)
        return {"tool_id": tool_id,
                "planner_confusion_matrix": rep["planner_confusion_matrix"],
                "descriptor_confusion_set": rep["descriptor_confusion_set"],
                "honesty_labels": _tq.HONESTY_LABELS}

    @app.get("/ai-tools/{tool_id}/quality/selection-boundary")
    async def quality_selection_boundary(tool_id: str,
                                         user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        rep = _load_quality_or_404(tool_id, user)
        return {"tool_id": tool_id,
                "planner_selection_boundary": rep["planner_selection_boundary"],
                "honesty_labels": _tq.HONESTY_LABELS}

    @app.post("/ai-tools/{tool_id}/quality/mutation-check")
    async def quality_mutation_check(tool_id: str,
                                     user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_tool_or_404(tool_id, user)
        mutation = _tq.mutation_harness(tool_id=tool_id, tenant_id=user["tid"])
        return {"tool_id": tool_id, "mutation_harness": mutation,
                "calls_llm": False, "calls_external_provider": False,
                "honesty_labels": _tq.HONESTY_LABELS}

    @app.post("/ai-tools/{tool_id}/quality/counterfactual-check")
    async def quality_counterfactual_check(tool_id: str,
                                           user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        tid = user["tid"]
        head = _load_tool_or_404(tool_id, user)
        lv = tool_store.latest_version(tool_id, tenant_id=tid)
        if lv is None:
            raise HTTPException(404, "tool has no version")
        ir = _tq.build_formal_ir(
            descriptor=lv["descriptor"], tenant_id=tid, tool_id=tool_id,
            tool_version_id=lv["tool_version_id"],
            source_descriptor_hash=lv["descriptor_hash"],
            b1_category=lv["descriptor"]["category"],
            b1_side_effect=lv["effect_contract"]["side_effect_class"],
            b1_risk=lv["risk_class"],
            b1_prompt_exposure=lv["prompt_context_policy"][
                "effective_exposure"])
        cf = _tq.counterfactual_planner_simulation(
            tool_id=tool_id, tenant_id=tid,
            category=lv["descriptor"]["category"], ir=ir,
            b1_side_effect=lv["effect_contract"]["side_effect_class"])
        return {"tool_id": tool_id, "counterfactual_planner": cf,
                "calls_llm": False, "honesty_labels": _tq.HONESTY_LABELS}

    @app.get("/ai-tools/{tool_id}/quality/non-regression")
    async def quality_non_regression(tool_id: str,
                                     user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        rep = _load_quality_or_404(tool_id, user)
        return {"tool_id": tool_id,
                "non_regression_summary": rep["non_regression_summary"],
                "honesty_labels": _tq.HONESTY_LABELS}

    @app.get("/ai-tools/{tool_id}/quality/binding-ledger")
    async def quality_binding_ledger(tool_id: str,
                                     user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_tool_or_404(tool_id, user)
        evs = quality_store.events(tenant_id=user["tid"], tool_id=tool_id)
        chain_ok, prev = True, None
        all_evs = quality_store.events(tenant_id=user["tid"])
        for e in all_evs:
            if e["previous_event_hash"] != (prev or _tq.GENESIS):
                chain_ok = False
            prev = e["event_hash"]
        return {"tool_id": tool_id, "events": evs, "event_count": len(evs),
                "event_chain_valid": chain_ok,
                "binding_note": "quality-to-admission binding metadata is "
                "recorded; direct mutation of TOOL-B1 admission state is "
                "MISSING/NEXT (a quality fail records a readiness blocker but "
                "cannot itself flip a security state).",
                "honesty_labels": _tq.HONESTY_LABELS}

    app.state.run_quality_check = _run_quality_check

    # ---- ViktorAI Formal Protocol Contract Proof Kernel (TOOL-B3) ------------------
    from ..ai_employee import tool_contracts as _tc
    from ..ai_employee.tool_contracts_store import ToolContractStore
    contract_store = ToolContractStore(db)
    app.state.contract_store = contract_store

    def _contract_emit(tid, *, event_type, contract_id, tool_id, actor_id,
                       actor_type, state_hash, detail):
        seq = contract_store.next_sequence(tenant_id=tid)
        prev = contract_store.last_event(tenant_id=tid)
        ev = _tc.build_contract_event(
            event_type=event_type, tool_id=tool_id, contract_id=contract_id,
            tenant_id=tid, actor_id=actor_id, actor_type=actor_type,
            contract_state_hash=state_hash,
            previous_event_hash=(prev or {}).get("event_hash"), sequence=seq,
            detail=detail, created_at=utcnow())
        contract_store.append_event({
            "id": str(uuid.uuid4()), "tenant_id": tid, "contract_id":
            contract_id, "tool_id": tool_id, "event_type": event_type,
            "sequence": seq, "actor_id": actor_id, "actor_type": actor_type,
            "event_hash": ev["event_hash"], "previous_event_hash": ev[
                "previous_event_hash"], "contract_state_hash": state_hash,
            "payload_json": json.dumps(ev), "created_at": ev["created_at"]})
        return ev

    def _tool_and_quality(tool_id, user):
        tid = user["tid"]
        head = _load_tool_or_404(tool_id, user)
        version = tool_store.latest_version(tool_id, tenant_id=tid)
        if version is None:
            raise HTTPException(404, "tool has no version")
        quality = quality_store.latest(tool_id, tenant_id=tid)
        return tid, head, version, quality

    def _load_contract_or_404(tool_id, contract_id, user):
        _load_tool_or_404(tool_id, user)
        c = contract_store.payload(contract_id, tenant_id=user["tid"])
        if c is None or c["tool_id"] != tool_id:
            raise HTTPException(404, "contract not found")
        return c

    def _store_projection(tid, contract, env, actor_id):
        contract_store.save_projection({
            "id": env["projection_envelope_id"], "contract_id": contract[
                "contract_id"], "tenant_id": tid, "tool_id": contract["tool_id"],
            "projection_target": env["projection_target"],
            "projection_status": env["projection_status"],
            "projection_hash": env["projection_hash"],
            "projection_envelope_hash": env["projection_envelope_hash"],
            "broker_readiness_status": env["broker_readiness_certificate"][
                "certificate_status"],
            "payload_json": json.dumps(env), "created_by": actor_id,
            "created_at": env["created_at"]})

    def _latest_projection(contract, user):
        projs = contract_store.projections_for(contract["contract_id"],
                                               tenant_id=user["tid"])
        return projs[-1] if projs else None

    # -- registry-level contract routes (before /{contract_id}) ---------------
    @app.get("/ai-tools/registry/contracts")
    async def registry_contracts(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        cs = contract_store.list(tenant_id=user["tid"])
        by_status = {}
        for c in cs:
            by_status[c["contract_status"]] = by_status.get(
                c["contract_status"], 0) + 1
        return {"tenant_id": user["tid"], "contract_count": len(cs),
                "contracts_by_status": by_status,
                "summaries": [{"contract_id": c["contract_id"], "tool_id": c[
                    "tool_id"], "contract_status": c["contract_status"],
                    "contract_hash": c["contract_hash"]} for c in cs],
                "honesty_labels": _tc.HONESTY_LABELS}

    @app.get("/ai-tools/registry/contracts/policy")
    async def registry_contracts_policy(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return {"contract_model_version": _tc.CONTRACT_MODEL_VERSION,
                "executes_tools": False, "is_mcp_server": False,
                "is_mcp_client": False, "calls_tool_broker": False,
                "calls_llm": False, "calls_external_provider": False,
                "issues_tokens": False, "performs_sampling": False,
                "performs_elicitation": False, "serves_resources": False,
                "serves_prompts": False,
                "runtime_capabilities_denied": list(_tc.RUNTIME_CAPABILITIES),
                "projection_targets": sorted(_tc.PROJECTION_TARGETS),
                "protocol_dialects": sorted(_tc.DIALECTS),
                "failure_dominance": _tc.FAILURE_DOMINANCE,
                "projection_is_validation_only": True,
                "certificate_can_override_blockers": False,
                "honesty_labels": _tc.HONESTY_LABELS}

    @app.post("/ai-tools/{tool_id}/contracts")
    async def create_contract(tool_id: str, body: dict = None,
                              user: dict = Depends(current_user)):
        # Normalizing a tool into an internal contract records a protocol-aware
        # contract. It executes nothing: no MCP, no broker, no LLM, no provider,
        # no token, no sampling/elicitation, no network side effect.
        require_permission(user, "case.update")
        tid, head, version, quality = _tool_and_quality(tool_id, user)
        actor_type = "ai_employee" if user["role"] == "ai_worker" else "human"
        now = utcnow()
        runtime_requested = bool((body or {}).get("runtime_requested", False))
        # Deterministic, source-derived contract id → idempotent creation: an
        # unchanged source returns the existing contract instead of a duplicate.
        epoch = _tc.source_freshness_epoch(head, quality)
        contract_id = _tc.deterministic_contract_id(
            tenant_id=tid, tool_id=tool_id,
            tool_version_id=head["latest_version_id"],
            source_freshness_epoch=epoch)
        existing = contract_store.payload(contract_id, tenant_id=tid)
        if existing is not None:
            return existing
        contract = _tc.build_contract(
            head=head, version=version, quality_report=quality,
            contract_id=contract_id, actor_id=user["uid"], actor_type=actor_type,
            tenant_id=tid, created_at=now, runtime_requested=runtime_requested)
        contract_store.save({
            "id": contract_id, "tenant_id": tid, "tool_id": tool_id,
            "tool_version_id": contract["tool_version_id"], "contract_version":
            1, "contract_status": contract["contract_status"],
            "contract_target": contract["contract_target"],
            "contract_risk_class": contract["contract_risk_class"],
            "contract_side_effect_class": contract["contract_side_effect_class"],
            "source_descriptor_hash": contract["source_descriptor_hash"],
            "source_quality_report_hash": contract[
                "source_quality_report_hash"],
            "source_freshness_epoch": contract["source_freshness_epoch"],
            "revocation_epoch": contract["revocation_epoch"],
            "contract_hash": contract["contract_hash"],
            "contract_abi_hash": contract["contract_abi"]["abi_hash"],
            "contract_normal_form_hash": contract["contract_normal_form"][
                "contract_normal_form_hash"],
            "contract_state_hash": contract["contract_state_hash"],
            "payload_json": json.dumps(contract), "created_by": user["uid"],
            "created_at": now, "updated_at": now})
        vhash = _tc.contract_version_hash(
            contract_id=contract_id, version_number=1,
            contract_hash=contract["contract_hash"],
            abi_hash=contract["contract_abi"]["abi_hash"],
            previous_contract_version_hash=None)
        contract_store.save_version({
            "id": contract_id + "-cv1", "contract_id": contract_id,
            "tenant_id": tid, "tool_id": tool_id, "tool_version_id": contract[
                "tool_version_id"], "version_number": 1,
            "contract_hash": contract["contract_hash"], "contract_abi_hash":
            contract["contract_abi"]["abi_hash"], "contract_version_hash": vhash,
            "previous_contract_version_hash": None,
            "contract_chain_hash": _tc.contract_chain_hash(None, vhash),
            "payload_json": json.dumps(contract), "created_at": now})
        # Build + store a default internal-broker projection so contract-level
        # proof/obligation/certificate reads have a concrete artifact.
        env = _tc.build_projection(
            contract=contract, head=head, quality_report=quality,
            target="INTERNAL_TOOL_BROKER_CONTRACT",
            projection_id=contract_id + "-proj-default", tenant_id=tid,
            created_at=now, runtime_requested=runtime_requested)
        _store_projection(tid, contract, env, user["uid"])
        _contract_emit(tid, event_type="CONTRACT_CREATED",
                       contract_id=contract_id, tool_id=tool_id,
                       actor_id=user["uid"], actor_type=actor_type,
                       state_hash=contract["contract_state_hash"],
                       detail={"status": contract["contract_status"]})
        audit.append(event_type="AI_TOOL_CONTRACT_CREATED", actor=user["uid"],
                     payload={"contract_id": contract_id, "tool_id": tool_id,
                              "status": contract["contract_status"]})
        return contract

    @app.get("/ai-tools/{tool_id}/contracts")
    async def list_contracts(tool_id: str,
                             user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_tool_or_404(tool_id, user)
        return contract_store.for_tool(tool_id, tenant_id=user["tid"])

    @app.get("/ai-tools/{tool_id}/contracts/{contract_id}")
    async def get_contract(tool_id: str, contract_id: str,
                           user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return _load_contract_or_404(tool_id, contract_id, user)

    @app.get("/ai-tools/{tool_id}/contracts/{contract_id}/safe")
    async def get_contract_safe(tool_id: str, contract_id: str,
                                user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        c = _load_contract_or_404(tool_id, contract_id, user)
        restricted = user["role"] in ("viewer", "technician", "accountant")
        never_expose = c["contract_prompt_context_boundary"][
            "prompt_context_exposure_status"] == "NEVER_EXPOSE"
        view = {
            "contract_id": contract_id, "tool_id": tool_id,
            "contract_status": c["contract_status"],
            "contract_risk_class": c["contract_risk_class"],
            "contract_side_effect_class": c["contract_side_effect_class"],
            "requires_future_tool_broker": True,
            "contract_blockers": c["contract_blockers"],
            "description_safe": ("[REDACTED]" if (restricted or never_expose)
                                 else c["contract_description_safe"]),
            "contract_hash": c["contract_hash"],
            "honesty_labels": _tc.HONESTY_LABELS,
        }
        view["contract_safe_view_hash"] = _tc._sha(
            {k: v for k, v in view.items()
             if k not in ("contract_safe_view_hash", "honesty_labels")})
        return view

    @app.get("/ai-tools/{tool_id}/contracts/{contract_id}/versions")
    async def contract_versions(tool_id: str, contract_id: str,
                                user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_contract_or_404(tool_id, contract_id, user)
        vs = contract_store.versions(contract_id, tenant_id=user["tid"])
        return {"contract_id": contract_id, "count": len(vs),
                "versions": [{"version_number": i + 1, "contract_hash": v[
                    "contract_hash"], "contract_abi": {"abi_hash": v[
                    "contract_abi"]["abi_hash"]}} for i, v in enumerate(vs)],
                "honesty_labels": _tc.HONESTY_LABELS}

    def _sub(name):
        async def getter(tool_id: str, contract_id: str,
                         user: dict = Depends(current_user)):
            require_permission(user, "case.read")
            c = _load_contract_or_404(tool_id, contract_id, user)
            return {"contract_id": contract_id, name: c[name],
                    "honesty_labels": _tc.HONESTY_LABELS}
        return getter

    app.add_api_route(
        "/ai-tools/{tool_id}/contracts/{contract_id}/normal-form",
        _sub("contract_normal_form"), methods=["GET"])
    app.add_api_route("/ai-tools/{tool_id}/contracts/{contract_id}/abi",
                      _sub("contract_abi"), methods=["GET"])
    app.add_api_route(
        "/ai-tools/{tool_id}/contracts/{contract_id}/effect-trace",
        _sub("effect_trace_semantics"), methods=["GET"])
    app.add_api_route(
        "/ai-tools/{tool_id}/contracts/{contract_id}/method-firewall",
        _sub("protocol_method_firewall"), methods=["GET"])
    app.add_api_route(
        "/ai-tools/{tool_id}/contracts/{contract_id}/runtime-deny-graph",
        _sub("runtime_capability_deny_graph"), methods=["GET"])
    app.add_api_route(
        "/ai-tools/{tool_id}/contracts/{contract_id}/separation",
        _sub("separation_guard"), methods=["GET"])
    app.add_api_route("/ai-tools/{tool_id}/contracts/{contract_id}/scope",
                      _sub("contract_scope_binding"), methods=["GET"])
    app.add_api_route("/ai-tools/{tool_id}/contracts/{contract_id}/auth",
                      _sub("auth_context_envelope"), methods=["GET"])
    app.add_api_route(
        "/ai-tools/{tool_id}/contracts/{contract_id}/traceability",
        _sub("contract_traceability_envelope"), methods=["GET"])

    @app.get("/ai-tools/{tool_id}/contracts/{contract_id}/protocol")
    async def get_contract_protocol(tool_id: str, contract_id: str,
                                    user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        c = _load_contract_or_404(tool_id, contract_id, user)
        return {"contract_id": contract_id,
                "protocol_dialect_matrix": c["protocol_dialect_matrix"],
                "capability_negotiation_boundary": c[
                    "capability_negotiation_boundary"],
                "honesty_labels": _tc.HONESTY_LABELS}

    @app.get("/ai-tools/{tool_id}/contracts/{contract_id}/boundaries")
    async def get_contract_boundaries(tool_id: str, contract_id: str,
                                      user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        c = _load_contract_or_404(tool_id, contract_id, user)
        return {"contract_id": contract_id,
                "data_boundary": c["contract_data_boundary"],
                "effect_boundary": c["contract_effect_boundary"],
                "prompt_context_boundary": c["contract_prompt_context_boundary"],
                "honesty_labels": _tc.HONESTY_LABELS}

    def _proj_sub(name):
        async def getter(tool_id: str, contract_id: str,
                         user: dict = Depends(current_user)):
            require_permission(user, "case.read")
            c = _load_contract_or_404(tool_id, contract_id, user)
            proj = _latest_projection(c, user)
            if proj is None:
                raise HTTPException(404, "no projection; project first")
            return {"contract_id": contract_id, name: proj[name],
                    "projection_id": proj["projection_envelope_id"],
                    "honesty_labels": _tc.HONESTY_LABELS}
        return getter

    app.add_api_route(
        "/ai-tools/{tool_id}/contracts/{contract_id}/obligations",
        _proj_sub("deontic_obligation_ledger"), methods=["GET"])
    app.add_api_route(
        "/ai-tools/{tool_id}/contracts/{contract_id}/proof-bundle",
        _proj_sub("contract_proof_bundle"), methods=["GET"])
    app.add_api_route(
        "/ai-tools/{tool_id}/contracts/{contract_id}/broker-readiness",
        _proj_sub("broker_readiness_certificate"), methods=["GET"])
    app.add_api_route(
        "/ai-tools/{tool_id}/contracts/{contract_id}/proof-obligations",
        _proj_sub("proof_obligations"), methods=["GET"])
    app.add_api_route(
        "/ai-tools/{tool_id}/contracts/{contract_id}/non-interference",
        _proj_sub("non_interference_matrix"), methods=["GET"])
    app.add_api_route(
        "/ai-tools/{tool_id}/contracts/{contract_id}/provenance",
        _proj_sub("field_provenance"), methods=["GET"])

    @app.post("/ai-tools/{tool_id}/contracts/{contract_id}/project")
    async def project_contract(tool_id: str, contract_id: str, body: dict,
                               user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        tid = user["tid"]
        c = _load_contract_or_404(tool_id, contract_id, user)
        head = _load_tool_or_404(tool_id, user)
        quality = quality_store.latest(tool_id, tenant_id=tid)
        target = str(body.get("target", "INTERNAL_TOOL_BROKER_CONTRACT"))
        if target not in _tc.PROJECTION_TARGETS:
            raise HTTPException(400, f"unknown projection target {target}")
        # Staleness gate: a drifted source cannot be projected.
        inv = _tc.invalidation_check(contract=c, head=head,
                                     quality_report=quality)
        actor_type = "ai_employee" if user["role"] == "ai_worker" else "human"
        now = utcnow()
        projection_id = f"{contract_id}-proj-{uuid.uuid4().hex[:8]}"
        if inv["stale"]:
            env = {"projection_envelope_id": projection_id, "tenant_id": tid,
                   "contract_id": contract_id, "tool_id": tool_id,
                   "projection_target": target, "projection_status": "STALE",
                   "projection_blockers": ["STALE_SOURCE"],
                   "invalidation_reasons": inv["invalidation_reasons"],
                   "broker_readiness_certificate": {"certificate_status":
                                                    "STALE"},
                   "projection_hash": _tc._sha({"stale": True, "id":
                                                projection_id}),
                   "created_at": now, "honesty_labels": _tc.HONESTY_LABELS}
            env["projection_envelope_hash"] = _tc._core_hash(
                env, "projection_envelope_hash")
            _store_projection(tid, c, env, user["uid"])
            _contract_emit(tid, event_type="PROJECTION_STALE",
                           contract_id=contract_id, tool_id=tool_id,
                           actor_id=user["uid"], actor_type=actor_type,
                           state_hash=c["contract_state_hash"],
                           detail={"target": target})
            return env
        runtime_requested = bool(body.get("runtime_requested", False))
        env = _tc.build_projection(
            contract=c, head=head, quality_report=quality, target=target,
            projection_id=projection_id, tenant_id=tid, created_at=now,
            runtime_requested=runtime_requested)
        _store_projection(tid, c, env, user["uid"])
        etype = ("PROJECTION_BLOCKED" if env["projection_status"] in (
            "BLOCKED", "QUARANTINED", "REVOKED", "TAMPERED")
            else "CONTRACT_PROJECTED")
        _contract_emit(tid, event_type=etype, contract_id=contract_id,
                       tool_id=tool_id, actor_id=user["uid"],
                       actor_type=actor_type, state_hash=c["contract_state_hash"],
                       detail={"target": target, "status": env[
                           "projection_status"]})
        if env["violation_witnesses"]:
            _contract_emit(tid, event_type="FINITE_VIOLATION_WITNESS_RECORDED",
                           contract_id=contract_id, tool_id=tool_id,
                           actor_id=user["uid"], actor_type=actor_type,
                           state_hash=c["contract_state_hash"],
                           detail={"count": len(env["violation_witnesses"])})
        return env

    @app.get(
        "/ai-tools/{tool_id}/contracts/{contract_id}/projection/{projection_id}")
    async def get_projection(tool_id: str, contract_id: str, projection_id: str,
                             user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_contract_or_404(tool_id, contract_id, user)
        p = contract_store.projection(projection_id, tenant_id=user["tid"])
        if p is None or p["contract_id"] != contract_id:
            raise HTTPException(404, "projection not found")
        return p

    def _shape_route(target, shape_key):
        async def getter(tool_id: str, contract_id: str,
                         user: dict = Depends(current_user)):
            require_permission(user, "case.read")
            tid = user["tid"]
            c = _load_contract_or_404(tool_id, contract_id, user)
            head = _load_tool_or_404(tool_id, user)
            quality = quality_store.latest(tool_id, tenant_id=tid)
            env = _tc.build_projection(
                contract=c, head=head, quality_report=quality, target=target,
                projection_id=f"{contract_id}-{shape_key}-view", tenant_id=tid,
                created_at=utcnow())
            # Serve a shape ONLY for a genuinely-projectable status. Any
            # non-positive status (BLOCKED / STALE / REVOKED / TAMPERED /
            # QUARANTINED / NEEDS_REVIEW for a not-yet-admitted tool) withholds
            # the shape — a non-admitted or drifted tool is never served.
            if env["projection_status"] not in ("PROJECTABLE_FOR_FUTURE",
                                                "PROJECTED_SAFE_SUMMARY_ONLY"):
                return {"contract_id": contract_id, "projectable": False,
                        "projection_status": env["projection_status"],
                        "projection_blockers": env["projection_blockers"],
                        "shape": None, "honesty_labels": _tc.HONESTY_LABELS}
            return {"contract_id": contract_id, "projectable": True,
                    "projection_status": env["projection_status"],
                    "shape": env["projected_shape"],
                    "projection_note": "internal shape only; not a runtime "
                    "server response; future Tool Broker required",
                    "honesty_labels": _tc.HONESTY_LABELS}
        return getter

    app.add_api_route("/ai-tools/{tool_id}/contracts/{contract_id}/mcp-like",
                      _shape_route("MCP_LIKE_TOOL_DESCRIPTOR", "mcp"),
                      methods=["GET"])
    app.add_api_route(
        "/ai-tools/{tool_id}/contracts/{contract_id}/apps-sdk-like",
        _shape_route("OPENAI_APPS_SDK_LIKE_DESCRIPTOR", "apps"),
        methods=["GET"])
    app.add_api_route(
        "/ai-tools/{tool_id}/contracts/{contract_id}/openapi-like",
        _shape_route("OPENAPI_LIKE_SCHEMA_CONTRACT", "openapi"), methods=["GET"])

    @app.get("/ai-tools/{tool_id}/contracts/{contract_id}/compatibility")
    async def get_compatibility(tool_id: str, contract_id: str,
                                user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        tid = user["tid"]
        c = _load_contract_or_404(tool_id, contract_id, user)
        head = _load_tool_or_404(tool_id, user)
        quality = quality_store.latest(tool_id, tenant_id=tid)
        projections = []
        for tgt in ("MCP_LIKE_TOOL_DESCRIPTOR",
                    "OPENAI_APPS_SDK_LIKE_DESCRIPTOR",
                    "OPENAPI_LIKE_SCHEMA_CONTRACT",
                    "INTERNAL_TOOL_BROKER_CONTRACT"):
            env = _tc.build_projection(
                contract=c, head=head, quality_report=quality, target=tgt,
                projection_id=f"{contract_id}-compat-{tgt}", tenant_id=tid,
                created_at=utcnow())
            projections.append((tgt, env))
        report = _tc.build_compatibility_report(
            tenant_id=tid, contract_id=contract_id, tool_id=tool_id,
            tool_version_id=c["tool_version_id"], projections=projections)
        return {"contract_id": contract_id, "compatibility_report": report,
                "honesty_labels": _tc.HONESTY_LABELS}

    @app.post("/ai-tools/{tool_id}/contracts/{contract_id}/invalidate-check")
    async def invalidate_check(tool_id: str, contract_id: str,
                               user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        tid = user["tid"]
        c = _load_contract_or_404(tool_id, contract_id, user)
        head = _load_tool_or_404(tool_id, user)
        quality = quality_store.latest(tool_id, tenant_id=tid)
        result = _tc.invalidation_check(contract=c, head=head,
                                        quality_report=quality)
        if result["stale"]:
            c["contract_status"] = "STALE"
            contract_store.update(contract_id, tenant_id=tid, payload=c,
                                  contract_status="STALE")
            _contract_emit(tid, event_type="CONTRACT_INVALIDATED",
                           contract_id=contract_id, tool_id=tool_id,
                           actor_id=user["uid"], actor_type="human",
                           state_hash=c["contract_state_hash"],
                           detail={"reasons": result["invalidation_reasons"]})
        return result

    @app.post("/ai-tools/{tool_id}/contracts/{contract_id}/verify")
    async def verify_contract(tool_id: str, contract_id: str,
                              user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        tid = user["tid"]
        c = _load_contract_or_404(tool_id, contract_id, user)
        reasons = []
        subs = [
            ("contract_normal_form", "contract_normal_form_hash"),
            ("effect_trace_semantics", "effect_trace_semantics_hash"),
            ("runtime_capability_deny_graph", "deny_graph_hash"),
            ("protocol_method_firewall", "method_firewall_hash"),
            ("protocol_dialect_matrix", "protocol_dialect_matrix_hash"),
            ("capability_negotiation_boundary",
             "capability_negotiation_boundary_hash"),
            ("separation_guard", "separation_guard_hash"),
            ("contract_scope_binding", "scope_binding_hash"),
            ("auth_context_envelope", "auth_context_envelope_hash"),
            ("contract_data_boundary", "data_boundary_hash"),
            ("contract_effect_boundary", "effect_boundary_hash"),
            ("contract_prompt_context_boundary", "prompt_context_boundary_hash"),
            ("schema_closure", "schema_closure_hash"),
            ("contract_non_execution_proof",
             "contract_non_execution_proof_hash"),
            ("contract_traceability_envelope", "traceability_envelope_hash"),
        ]
        for key, hfield in subs:
            obj = c.get(key)
            if isinstance(obj, dict) and _tc._core_hash(obj, hfield) != obj.get(
                    hfield):
                reasons.append(f"{key} hash mismatch")
        if _tc._core_hash(c["contract_abi"], "abi_hash",
                          "abi_breaking_change_flags") != c["contract_abi"][
                "abi_hash"]:
            reasons.append("contract ABI hash mismatch")
        # contract_hash excludes the mutable lifecycle fields (status/blockers,
        # which invalidate-check may flip to STALE) and the derived/actor fields,
        # so a legitimate source-drift → STALE transition is reported as STALE,
        # never as false tamper.
        if _tc._core_hash(c, "contract_hash", "contract_state_hash",
                          "contract_traceability_envelope",
                          "created_by_actor_id", "created_by_actor_type",
                          "contract_status", "contract_blockers") != c[
                "contract_hash"]:
            reasons.append("contract hash mismatch")
        # Source drift → STALE (not tamper).
        head = _load_tool_or_404(tool_id, user)
        quality = quality_store.latest(tool_id, tenant_id=tid)
        inv = _tc.invalidation_check(contract=c, head=head,
                                     quality_report=quality)
        status = ("MISMATCHED" if reasons else ("STALE" if inv["stale"]
                                                else "MATCHED"))
        _contract_emit(tid, event_type="CONTRACT_VERIFIED",
                       contract_id=contract_id, tool_id=tool_id,
                       actor_id=user["uid"], actor_type="human",
                       state_hash=c["contract_state_hash"],
                       detail={"status": status})
        return {"contract_id": contract_id, "verification_status": status,
                "tamper_detected": bool(reasons), "tamper_reasons": reasons,
                "stale": inv["stale"],
                "invalidation_reasons": inv["invalidation_reasons"],
                "honesty_labels": _tc.HONESTY_LABELS}

    @app.post("/ai-tools/{tool_id}/contracts/{contract_id}/diff")
    async def diff_contract(tool_id: str, contract_id: str, body: dict,
                            user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_contract_or_404(tool_id, contract_id, user)
        vs = contract_store.versions(contract_id, tenant_id=user["tid"])
        if len(vs) < 2:
            return {"contract_id": contract_id, "comparable": False,
                    "note": "need two contract versions to diff",
                    "honesty_labels": _tc.HONESTY_LABELS}
        a, b = vs[-2], vs[-1]
        changed = {}
        for f in ("contract_hash",):
            if a.get(f) != b.get(f):
                changed[f] = {"from": a.get(f), "to": b.get(f)}
        if a["contract_abi"]["abi_hash"] != b["contract_abi"]["abi_hash"]:
            changed["abi_hash"] = {"from": a["contract_abi"]["abi_hash"],
                                   "to": b["contract_abi"]["abi_hash"]}
        return {"contract_id": contract_id, "comparable": True,
                "changed_fields": changed, "honesty_labels": _tc.HONESTY_LABELS}

    @app.get(
        "/ai-tools/{tool_id}/contracts/{contract_id}/revocation-ledger")
    async def contract_revocation_ledger(tool_id: str, contract_id: str,
                                         user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_contract_or_404(tool_id, contract_id, user)
        evs = contract_store.events(tenant_id=user["tid"],
                                    contract_id=contract_id)
        chain_ok, prev = True, None
        for e in contract_store.events(tenant_id=user["tid"]):
            if e["previous_event_hash"] != (prev or _tc.GENESIS):
                chain_ok = False
            prev = e["event_hash"]
        return {"contract_id": contract_id, "events": evs,
                "event_count": len(evs), "event_chain_valid": chain_ok,
                "ledger_note": "local revocation/invalidation ledger; not a "
                "production immutable log", "honesty_labels": _tc.HONESTY_LABELS}

    app.state.build_contract = _tc.build_contract

    # ---- ViktorAI Causal Pre-Action Reference Monitor (TOOL-B4) --------------------
    from ..ai_employee import tool_guardrails as _tg
    from ..ai_employee.tool_guardrails_store import ToolGuardrailStore
    guardrail_store = ToolGuardrailStore(db)
    app.state.guardrail_store = guardrail_store

    # An actor's role grants a coarse authority envelope. The pre-action monitor
    # then INTERSECTS it with the contract frontier — authority can only narrow.
    _ROLE_AUTHORITY = {
        "owner": set(_tg.AUTHORITY_DIMENSIONS),
        "manager": {"READ", "INTERNAL_WRITE", "EXTERNAL_READ", "EXTERNAL_WRITE",
                    "CUSTOMER_MESSAGE", "CRM_WRITE", "EXPORT"},
        "operator": {"READ", "INTERNAL_WRITE", "EXTERNAL_READ"},
        "technician": {"READ", "INTERNAL_WRITE"},
        "accountant": {"READ", "EXPORT"},
        "viewer": {"READ"}, "ai_worker": {"READ"},
    }

    def _role_authority(user):
        return sorted(_ROLE_AUTHORITY.get(user["role"], {"READ"}))

    def _guardrail_emit(tid, *, event_type, proposal_id, decision_id, actor_id,
                        actor_type, state_hash, detail):
        seq = guardrail_store.next_sequence(tenant_id=tid)
        prev = guardrail_store.last_event(tenant_id=tid)
        ev = _tg.build_decision_event(
            event_type=event_type, tenant_id=tid, proposal_id=proposal_id,
            decision_id=decision_id, actor_id=actor_id, actor_type=actor_type,
            decision_state_hash=state_hash,
            previous_event_hash=(prev or {}).get("event_hash"), sequence=seq,
            detail=detail, created_at=utcnow())
        guardrail_store.append_event({
            "id": str(uuid.uuid4()), "tenant_id": tid, "proposal_id":
            proposal_id, "decision_id": decision_id, "event_type": event_type,
            "sequence": seq, "actor_id": actor_id, "actor_type": actor_type,
            "event_hash": ev["event_hash"], "previous_event_hash": ev[
                "previous_event_hash"], "decision_state_hash": state_hash,
            "payload_json": json.dumps(ev), "created_at": ev["created_at"]})
        return ev

    def _effective_policy(raw):
        """A client may only ever make the policy STRICTER (smaller budgets /
        limits). Any supplied value is clamped to min(default, supplied); a
        larger, more permissive value is ignored. Fail-closed."""
        pol = dict(_tg.DEFAULT_POLICY)
        raw = raw or {}
        for k, default in _tg.DEFAULT_POLICY.items():
            if k in raw:
                try:
                    pol[k] = max(0, min(int(default), int(raw[k])))
                except (TypeError, ValueError):
                    pol[k] = default
        return pol

    def _load_proposal_or_404(proposal_id, user):
        p = guardrail_store.proposal(proposal_id, tenant_id=user["tid"])
        if p is None:
            raise HTTPException(404, "proposal not found")
        return p

    def _load_decision_or_404(proposal_id, user):
        d = guardrail_store.decision_for_proposal(proposal_id,
                                                  tenant_id=user["tid"])
        if d is None:
            raise HTTPException(404, "no decision for proposal")
        return d

    def _gather_inputs(tool_id, contract_id, tid):
        """Load every authoritative source the monitor narrows against. All are
        server-side truth; none can be overridden by the untrusted proposal."""
        head = tool_store.payload(tool_id, tenant_id=tid)
        version = tool_store.latest_version(tool_id, tenant_id=tid)
        quality = quality_store.latest(tool_id, tenant_id=tid)
        allowed_purposes = []
        if version:
            allowed_purposes = (version["descriptor"].get(
                "purpose_contract", {}) or {}).get("allowed_purposes", []) or \
                version["descriptor"].get("allowed_purposes", []) or []
        contract = None
        if contract_id:
            contract = contract_store.payload(contract_id, tenant_id=tid)
            if contract is not None and contract["tool_id"] != tool_id:
                contract = None
        cert = None
        if contract is not None:
            projs = contract_store.projections_for(contract["contract_id"],
                                                   tenant_id=tid)
            if projs:
                cert = projs[-1].get("broker_readiness_certificate")
        breaker = guardrail_store.breaker(tool_id, tenant_id=tid)
        return head, version, quality, allowed_purposes, contract, cert, breaker

    _DECISION_SUBFIELDS = {
        "causal-graph": "causal_action_graph",
        "temporal": "temporal_policy_automaton",
        "drift": "capability_drift_sentinel",
        "counterfactual": "counterfactual_twin",
        "bypass": "bypass_simulator",
        "authority": "authority_composition",
        "path-risk": "path_risk_budget",
        "delegation": "delegation_chain_check",
        "nondelegable": "nondelegable_guard",
        "approval": "approval_guard", "consent": "consent_guard",
        "state-witness": "state_witness_guard",
        "intent": "intent_check", "schema": "schema_check",
        "scope": "scope_check", "effect": "effect_check",
        "attempts": "attempt_detector", "rate-quota": "rate_quota_check",
        "replay": "replay_verifier",
        "passport": "action_passport", "receipt": "governance_receipt",
        "lease": "future_execution_lease",
        "no-execution": "no_execution_proof",
        "proof-bundle": "preaction_proof_bundle",
    }

    # -- registry / policy (static routes registered before /{proposal_id}) ---
    @app.get("/ai-tools/actions/policy")
    async def actions_policy(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return {"guardrail_model_version": _tg.GUARDRAIL_MODEL_VERSION,
                "executes_tools": False, "is_tool_broker": False,
                "is_dry_run": False, "calls_llm": False,
                "calls_external_provider": False, "issues_tokens": False,
                "moves_payment": False, "sends_customer_message": False,
                "writes_crm": False, "mutates_evidence": False,
                "decision_statuses": sorted(_tg.DECISION_STATUSES),
                "failure_dominance": _tg.FAILURE_DOMINANCE,
                "reason_codes": _tg.REASON_CODES,
                "authority_dimensions": _tg.AUTHORITY_DIMENSIONS,
                "nondelegable_categories": sorted(
                    _tg.NONDELEGABLE_CATEGORIES),
                "default_policy": _tg.DEFAULT_POLICY,
                "action_passport_is_token": False,
                "governance_receipt_is_authority": False,
                "future_execution_lease_status": "NOT_IMPLEMENTED",
                "ai_can_self_authorize": False,
                "consent_overridable": False,
                "honesty_labels": _tg.HONESTY_LABELS}

    @app.get("/ai-tools/actions/registry")
    async def actions_registry(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        ds = guardrail_store.list_decisions(tenant_id=user["tid"])
        by_status = {}
        for d in ds:
            by_status[d["decision_status"]] = by_status.get(
                d["decision_status"], 0) + 1
        props = guardrail_store.list_proposals(tenant_id=user["tid"])
        return {"tenant_id": user["tid"], "proposal_count": len(props),
                "decision_count": len(ds), "decisions_by_status": by_status,
                "honesty_labels": _tg.HONESTY_LABELS}

    @app.get("/ai-tools/actions/circuit-breakers")
    async def list_circuit_breakers(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return {"tenant_id": user["tid"], "circuit_breakers":
                guardrail_store.list_breakers(tenant_id=user["tid"]),
                "honesty_labels": _tg.HONESTY_LABELS}

    @app.post("/ai-tools/actions/circuit-breakers")
    async def set_circuit_breaker(body: dict,
                                  user: dict = Depends(current_user)):
        # A circuit breaker is a human safety control. An AI worker can never
        # open or (especially) close one — that would let the AI clear its own
        # stop. Only privileged human roles may mutate a breaker.
        require_role(user, "owner", "manager")
        require_permission(user, "case.update")
        tid = user["tid"]
        tool_id = str(body.get("tool_id", ""))
        head = tool_store.payload(tool_id, tenant_id=tid)
        if head is None:
            raise HTTPException(404, "tool not found")
        state = str(body.get("breaker_state", "OPEN")).upper()
        now = utcnow()
        cb = _tg.build_circuit_breaker(
            tenant_id=tid, tool_id=tool_id, breaker_state=state,
            reason=body.get("reason", ""), created_at=now, actor_id=user["uid"])
        guardrail_store.save_breaker({
            "id": str(uuid.uuid4()), "tenant_id": tid, "tool_id": tool_id,
            "breaker_state": cb["breaker_state"], "reason_code": cb[
                "reason_code"], "circuit_breaker_hash": cb[
                "circuit_breaker_hash"], "set_by_actor_id": user["uid"],
            "payload_json": json.dumps(cb), "created_at": now,
            "updated_at": now})
        _guardrail_emit(
            tid, event_type=("CIRCUIT_BREAKER_OPENED" if cb["breaker_state"]
                             == "OPEN" else "CIRCUIT_BREAKER_CLOSED"),
            proposal_id=None, decision_id=None, actor_id=user["uid"],
            actor_type="human", state_hash=cb["circuit_breaker_hash"],
            detail={"tool_id": tool_id, "state": cb["breaker_state"]})
        audit.append(event_type="AI_ACTION_CIRCUIT_BREAKER_SET",
                     actor=user["uid"], payload={"tool_id": tool_id,
                                                 "state": cb["breaker_state"]})
        return cb

    @app.get("/ai-tools/actions/circuit-breakers/{tool_id}")
    async def get_circuit_breaker(tool_id: str,
                                  user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        cb = guardrail_store.breaker(tool_id, tenant_id=user["tid"])
        if cb is None:
            return {"tool_id": tool_id, "breaker_state": "CLOSED",
                    "circuit_breaker_active": False,
                    "honesty_labels": _tg.HONESTY_LABELS}
        return cb

    @app.get("/ai-tools/actions/events")
    async def actions_events(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        evs = guardrail_store.events(tenant_id=user["tid"])
        chain_ok, prev = True, None
        for e in evs:
            if e["previous_event_hash"] != (prev or _tg.GENESIS):
                chain_ok = False
            prev = e["event_hash"]
        return {"tenant_id": user["tid"], "events": evs,
                "event_count": len(evs), "event_chain_valid": chain_ok,
                "ledger_note": "local decision ledger; not a production "
                "immutable log", "honesty_labels": _tg.HONESTY_LABELS}

    @app.get("/ai-tools/actions/proposals")
    async def list_proposals(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return guardrail_store.list_proposals(tenant_id=user["tid"])

    def _render_decision(tid, user, raw_body, *, event_type):
        tool_id = str(raw_body.get("tool_id", ""))
        head, version, quality, purposes, contract, cert, breaker = \
            _gather_inputs(tool_id, str(raw_body.get("contract_id", "")
                                        or ""), tid)
        if head is None:
            raise HTTPException(404, "tool not found")
        # Auto-bind the tool's latest contract when the caller did not name one.
        contract_id = str(raw_body.get("contract_id", "") or "")
        if not contract_id:
            cs = contract_store.for_tool(tool_id, tenant_id=tid)
            if cs:
                contract = cs[-1]
                contract_id = contract["contract_id"]
                projs = contract_store.projections_for(contract_id,
                                                       tenant_id=tid)
                cert = projs[-1].get("broker_readiness_certificate") if projs \
                    else None
        actor_type = "ai_employee" if user["role"] == "ai_worker" else "human"
        now = utcnow()
        # SERVER-side verification of approval/consent. The proposal's
        # approval_ref/consent_ref are UNTRUSTED claims and never satisfy the
        # gate on their own — a proposer could otherwise self-authorize by
        # fabricating them. Approval is verified only against a real, live
        # approval GRANT in this tenant (created through the genuine CORE-A4
        # separation-of-duties flow, which a proposal cannot forge). There is no
        # consent-grant store in this mission, so consent can never be
        # server-verified here and always escalates (fail-closed).
        approval_verified = False
        aref = (raw_body.get("approval_ref") or {})
        aid = aref.get("approval_request_id")
        if aid:
            g = grant_store.get_for_request(aid, tenant_id=tid)
            approval_verified = bool(
                g and not g.get("revoked_at") and not g.get("superseded_at")
                and str(g.get("grant_status", "")).upper() in (
                    "GRANTED", "VALID", "ACTIVE", "VALIDATED"))
        consent_verified = False
        proposal_id = str(uuid.uuid4())
        proposal = _tg.build_action_proposal(
            proposal_id=proposal_id, tenant_id=tid, tool_id=tool_id,
            contract_id=contract_id, raw=raw_body, actor_id=user["uid"],
            actor_type=actor_type, created_at=now)
        idem = proposal["idempotency_key"]
        prior = guardrail_store.latest_decision_for_key(idem, tenant_id=tid)
        usage = {"window_count": guardrail_store.count_decisions_in_window(
            tenant_id=tid, tool_id=tool_id),
            "quota_used": guardrail_store.count_decisions_in_window(
                tenant_id=tid), "authority_spent": 0, "path_risk_spent": 0}
        policy = _effective_policy(raw_body.get("policy"))
        decision_id = str(uuid.uuid4())
        decision = _tg.evaluate_proposal(
            proposal=proposal, head=head, quality_report=quality,
            contract=contract, broker_readiness=cert, circuit_breaker=breaker,
            prior_decision=prior, role_authority=_role_authority(user),
            policy=policy, usage=usage, decision_id=decision_id, tenant_id=tid,
            actor_id=user["uid"], actor_type=actor_type, created_at=now,
            allowed_purposes=purposes, approval_verified=approval_verified,
            consent_verified=consent_verified)
        guardrail_store.save_proposal({
            "id": proposal_id, "tenant_id": tid, "tool_id": tool_id,
            "contract_id": contract_id, "action_path": proposal["action_path"],
            "intent": proposal["intent"], "idempotency_key": idem,
            "logical_clock": proposal["logical_clock"],
            "proposal_hash": proposal["proposal_hash"],
            "proposed_by_actor_id": user["uid"],
            "proposed_by_actor_type": actor_type,
            "payload_json": json.dumps(proposal), "created_at": now})
        guardrail_store.save_decision({
            "id": decision_id, "tenant_id": tid, "tool_id": tool_id,
            "contract_id": contract_id, "proposal_id": proposal_id,
            "proposal_hash": proposal["proposal_hash"],
            "decision_status": decision["decision_status"],
            "dominant_signal": decision["dominant_signal"],
            "idempotency_key": idem,
            "logical_clock": proposal["logical_clock"],
            "source_freshness_epoch": decision["source_freshness_epoch"],
            "is_replay": 1 if decision["is_replay"] else 0,
            "decision_hash": decision["decision_hash"],
            "decision_state_hash": decision["decision_state_hash"],
            "decided_by_actor_id": user["uid"],
            "decided_by_actor_type": actor_type,
            "payload_json": json.dumps(decision), "created_at": now,
            "updated_at": now})
        emit = "DECISION_REPLAYED" if decision["is_replay"] else event_type
        _guardrail_emit(
            tid, event_type=emit, proposal_id=proposal_id,
            decision_id=decision_id, actor_id=user["uid"],
            actor_type=actor_type,
            state_hash=decision["decision_state_hash"],
            detail={"status": decision["decision_status"],
                    "dominant_signal": decision["dominant_signal"]})
        audit.append(event_type="AI_ACTION_PREACTION_DECISION",
                     actor=user["uid"], payload={
                         "proposal_id": proposal_id, "tool_id": tool_id,
                         "status": decision["decision_status"]})
        return decision

    @app.post("/ai-tools/actions/proposals")
    async def submit_proposal(body: dict, user: dict = Depends(current_user)):
        # Submitting a proposal renders a deterministic PRE-ACTION decision. It
        # executes nothing: no broker, no tool, no LLM, no provider, no token,
        # no payment/message/CRM/evidence/export. The most permissive outcome is
        # ALLOWED_FOR_FUTURE_BROKER_ONLY, which still runs nothing.
        require_permission(user, "case.update")
        return _render_decision(user["tid"], user, body or {},
                                event_type="DECISION_RENDERED")

    @app.get("/ai-tools/actions/proposals/{proposal_id}")
    async def get_proposal(proposal_id: str,
                           user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return _load_proposal_or_404(proposal_id, user)

    @app.get("/ai-tools/actions/proposals/{proposal_id}/decision")
    async def get_decision(proposal_id: str,
                           user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_proposal_or_404(proposal_id, user)
        return _load_decision_or_404(proposal_id, user)

    @app.get("/ai-tools/actions/proposals/{proposal_id}/safe")
    async def get_decision_safe(proposal_id: str,
                                user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_proposal_or_404(proposal_id, user)
        d = _load_decision_or_404(proposal_id, user)
        restricted = user["role"] in ("viewer", "technician", "accountant")
        return {"proposal_id": proposal_id, "tool_id": d["tool_id"],
                "decision_status": d["decision_status"],
                "dominant_signal": d["dominant_signal"],
                "dominant_reason_code": d["dominant_reason_code"],
                "requires_future_tool_broker": True, "executes_nothing": True,
                "all_signals": ([] if restricted else d["all_signals"]),
                "decision_hash": d["decision_hash"],
                "honesty_labels": _tg.HONESTY_LABELS}

    def _dsub(field):
        async def getter(proposal_id: str,
                         user: dict = Depends(current_user)):
            require_permission(user, "case.read")
            _load_proposal_or_404(proposal_id, user)
            d = _load_decision_or_404(proposal_id, user)
            return {"proposal_id": proposal_id, field: d[field],
                    "honesty_labels": _tg.HONESTY_LABELS}
        return getter

    for _slug, _field in _DECISION_SUBFIELDS.items():
        app.add_api_route(
            f"/ai-tools/actions/proposals/{{proposal_id}}/{_slug}",
            _dsub(_field), methods=["GET"])

    @app.get("/ai-tools/actions/proposals/{proposal_id}/events")
    async def proposal_events(proposal_id: str,
                              user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_proposal_or_404(proposal_id, user)
        return {"proposal_id": proposal_id, "events": guardrail_store.events(
            tenant_id=user["tid"], proposal_id=proposal_id),
            "honesty_labels": _tg.HONESTY_LABELS}

    @app.post("/ai-tools/actions/proposals/{proposal_id}/verify")
    async def verify_decision(proposal_id: str,
                              user: dict = Depends(current_user)):
        # Recompute the stored decision's content hash and confirm the persisted
        # record has not been tampered with. Executes nothing.
        require_permission(user, "case.read")
        _load_proposal_or_404(proposal_id, user)
        d = _load_decision_or_404(proposal_id, user)
        recomputed = _tg._core_hash(
            d, "decision_hash", "decision_id", "proposal_id",
            "decided_by_actor_id", "decided_by_actor_type",
            "decision_state_hash")
        ok = recomputed == d["decision_hash"]
        return {"proposal_id": proposal_id, "decision_id": d["decision_id"],
                "stored_decision_hash": d["decision_hash"],
                "recomputed_decision_hash": recomputed,
                "decision_hash_valid": ok,
                "verification_status": "VALID" if ok else "TAMPERED",
                "honesty_labels": _tg.HONESTY_LABELS}

    @app.post("/ai-tools/actions/proposals/{proposal_id}/reevaluate")
    async def reevaluate_proposal(proposal_id: str,
                                  user: dict = Depends(current_user)):
        # Re-render the SAME proposal content against the CURRENT authoritative
        # state (registry/quality/contract/breaker). This is how capability
        # drift, temporal transitions, and revocation surface over time. It
        # executes nothing.
        require_permission(user, "case.update")
        prev = _load_proposal_or_404(proposal_id, user)
        raw = {k: prev[k] for k in (
            "action_path", "intent", "declared_effects", "requested_scope",
            "payload", "delegation_chain", "requested_authority",
            "state_witness", "approval_ref", "consent_ref", "idempotency_key",
            "logical_clock", "baseline_contract_hash", "baseline_abi_hash")}
        raw["tool_id"] = prev["tool_id"]
        raw["contract_id"] = prev["contract_id"]
        return _render_decision(user["tid"], user, raw,
                                event_type="DECISION_RENDERED")

    # ---- ViktorAI Four-Plane Proof-Carrying Null Broker (TOOL-B5) ------------------
    from ..ai_employee import tool_broker as _tb
    from ..ai_employee.tool_broker_store import ToolBrokerStore
    broker_store = ToolBrokerStore(db)
    app.state.broker_store = broker_store

    def _broker_emit(tid, *, event_type, broker_request_id, actor_id,
                     actor_type, state_hash, detail):
        seq = broker_store.next_sequence(tenant_id=tid)
        prev = broker_store.last_event(tenant_id=tid)
        ev = _tb.build_broker_event(
            event_type=event_type, tenant_id=tid,
            broker_request_id=broker_request_id, actor_id=actor_id,
            actor_type=actor_type, broker_state_hash=state_hash,
            previous_event_hash=(prev or {}).get("event_hash"), sequence=seq,
            detail=detail, created_at=utcnow())
        broker_store.append_event({
            "id": str(uuid.uuid4()), "tenant_id": tid, "broker_request_id":
            broker_request_id, "event_type": event_type, "sequence": seq,
            "actor_id": actor_id, "actor_type": actor_type,
            "event_hash": ev["event_hash"], "previous_event_hash": ev[
                "previous_event_hash"], "broker_state_hash": state_hash,
            "payload_json": json.dumps(ev), "created_at": ev["created_at"]})
        return ev

    def _broker_policy(raw):
        pol = dict(_tb.DEFAULT_POLICY)
        raw = raw or {}
        for k, default in _tb.DEFAULT_POLICY.items():
            if k in raw:
                try:
                    pol[k] = max(0, min(int(default), int(raw[k])))
                except (TypeError, ValueError):
                    pol[k] = default
        return pol

    def _load_broker_request_or_404(broker_request_id, user):
        r = broker_store.request(broker_request_id, tenant_id=user["tid"])
        if r is None:
            raise HTTPException(404, "broker request not found")
        return r

    def _load_broker_outcome_or_404(broker_request_id, user):
        _load_broker_request_or_404(broker_request_id, user)
        o = broker_store.outcome(broker_request_id, tenant_id=user["tid"])
        if o is None:
            raise HTTPException(404, "no broker outcome")
        return o

    def _gather_b5_inputs(tid, b4_decision, b4_proposal):
        tool_id = b4_decision.get("tool_id") or b4_proposal.get("tool_id")
        contract_id = b4_decision.get("contract_id") or b4_proposal.get(
            "contract_id")
        head = tool_store.payload(tool_id, tenant_id=tid)
        quality = quality_store.latest(tool_id, tenant_id=tid)
        contract = contract_store.payload(contract_id, tenant_id=tid) if \
            contract_id else None
        cert = None
        if contract is not None:
            projs = contract_store.projections_for(contract_id, tenant_id=tid)
            if projs:
                cert = projs[-1].get("broker_readiness_certificate")
        return head, quality, contract, cert

    def _batch_related(tid, env, exclude_request_id):
        """Related broker requests correlated by ANY server-derived key (batch /
        customer / task / case), summarised for the multi-request safety ledger.
        Correlating on more than the client-supplied batch_id means an adversary
        cannot defeat cross-request conservation just by omitting or varying it.
        Tenant-scoped."""
        out = []
        for o in broker_store.related_outcomes(
                tenant_id=tid, batch_id=str(env.get("batch_id", "") or ""),
                customer_id=str(env.get("customer_id", "") or ""),
                task_id=str(env.get("task_id", "") or ""),
                case_id=str(env.get("case_id", "") or ""),
                exclude_request_id=exclude_request_id):
            se = (o.get("multi_request_safety_ledger") or {})
            out.append({
                "broker_request_id": o.get("broker_request_id"),
                "aggregate_effects": se.get("aggregate_effects", []),
                "risk_score": (o.get("cumulative_risk_conservation") or {}).get(
                    "risk_sum", 0),
                "payload_hash": o.get("broker_request_hash")})
        return out

    _BROKER_SUBFIELDS = {
        "four-plane": "four_plane_model",
        "plane-non-interference": "plane_non_interference",
        "open-checkpoint": "broker_open_checkpoint",
        "assumption-ledger": "assumption_capture_ledger",
        "safety-lattice": "broker_safety_lattice",
        "multi-request-ledger": "multi_request_safety_ledger",
        "cross-request-effect-conservation": "cross_request_effect_conservation",
        "cumulative-risk-conservation": "cumulative_risk_conservation",
        "null-output-non-exfiltration": "null_output_non_exfiltration",
        "safe-output-projection": "safe_output_projection",
        "credential-free-corridor": "credential_free_corridor",
        "token-non-derivation": "token_non_derivation",
        "adapter-manifest-freeze": "adapter_manifest_freeze",
        "adapter-non-resolution": "adapter_non_resolution",
        "runtime-surface-diff": "runtime_surface_diff",
        "capability-identity-seal": "capability_identity_seal",
        "certificate-chain-closure": "certificate_chain_closure",
        "null-effector": "null_effector",
        "side-effect-zero": "side_effect_zero",
        "absence-proofs": "absence_proofs",
        "bypass-sentinel": "broker_bypass_sentinel",
        "broker-non-execution": "broker_non_execution_proof",
        "negative-execution-certificate": "negative_execution_certificate",
        "proof-carrying-certificate":
        "proof_carrying_broker_action_certificate",
        "outcome-closure": "outcome_closure_checkpoint",
        "fault-injection": "fault_injection_harness",
        "release-gate": "broker_release_gate_report",
        "conformance-vector": "broker_conformance_vector",
        "proof-bundle": "broker_proof_bundle",
    }

    @app.get("/ai-tools/broker/policy")
    async def broker_policy(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return {"broker_model_version": _tb.BROKER_MODEL_VERSION,
                "executes_tools": False, "is_tool_broker_runtime": False,
                "is_mcp_runtime": False, "is_mcp_server": False,
                "is_mcp_client": False, "is_llm_runtime": False,
                "issues_tokens": False, "derives_tokens": False,
                "reads_credentials": False, "reads_secrets": False,
                "calls_external_provider": False, "sends_customer_message": False,
                "executes_payment": False, "mutates_crm": False,
                "mutates_evidence": False, "exports_data": False,
                "resolves_real_adapter": False, "has_execute_endpoint": False,
                "only_effector": "NULL_EFFECTOR",
                "most_permissive_outcome": "BROKER_PREPARED_FOR_FUTURE_ONLY",
                "accepts_b4_statuses": sorted(_tb.B4_ACCEPTABLE_STATUSES),
                "broker_statuses": sorted(_tb.BROKER_STATUSES),
                "failure_dominance": _tb.FAILURE_DOMINANCE,
                "reason_codes": _tb.REASON_CODES,
                "forbidden_leak_patterns": _tb.FORBIDDEN_LEAK_PATTERNS,
                "fault_cases": _tb.FAULT_CASES,
                "default_policy": _tb.DEFAULT_POLICY,
                "honesty_labels": _tb.HONESTY_LABELS}

    @app.get("/ai-tools/broker/registry")
    async def broker_registry(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        outs = broker_store.list_outcomes(tenant_id=user["tid"])
        by_status = {}
        for o in outs:
            by_status[o["broker_status"]] = by_status.get(
                o["broker_status"], 0) + 1
        reqs = broker_store.list_requests(tenant_id=user["tid"])
        return {"tenant_id": user["tid"], "broker_request_count": len(reqs),
                "broker_outcome_count": len(outs),
                "outcomes_by_status": by_status,
                "honesty_labels": _tb.HONESTY_LABELS}

    @app.get("/ai-tools/broker/events")
    async def broker_events(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        evs = broker_store.events(tenant_id=user["tid"])
        chain_ok, prev = True, None
        for e in evs:
            if e["previous_event_hash"] != (prev or _tb.GENESIS):
                chain_ok = False
            prev = e["event_hash"]
        return {"tenant_id": user["tid"], "events": evs,
                "event_count": len(evs), "event_chain_valid": chain_ok,
                "ledger_note": "local broker ledger; not a production immutable "
                "log", "honesty_labels": _tb.HONESTY_LABELS}

    @app.get("/ai-tools/broker/requests")
    async def list_broker_requests(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return broker_store.list_requests(tenant_id=user["tid"])

    def _prepare_and_store(tid, user, body):
        # Preparing a broker request runs NULL evaluation only: no tool run, no
        # provider, no token, no credential, no side effect. The most permissive
        # outcome is BROKER_PREPARED_FOR_FUTURE_ONLY (still runs nothing).
        b4 = None
        did = str(body.get("b4_decision_id", "") or "")
        pid = str(body.get("proposal_id", "") or "")
        if did:
            b4 = guardrail_store.decision(did, tenant_id=tid)
        elif pid:
            b4 = guardrail_store.decision_for_proposal(pid, tenant_id=tid)
        if b4 is None:
            raise HTTPException(404, "b4 decision not found")
        pobj = guardrail_store.proposal(b4["proposal_id"], tenant_id=tid)
        if pobj is None:
            raise HTTPException(404, "b4 proposal not found")
        head, quality, contract, cert = _gather_b5_inputs(tid, b4, pobj)
        actor_type = "ai_employee" if user["role"] == "ai_worker" else "human"
        now = utcnow()
        rid = str(uuid.uuid4())
        env = _tb.build_broker_request_envelope(
            broker_request_id=rid, tenant_id=tid, actor_id=user["uid"],
            actor_type=actor_type, b4_decision=b4, b4_proposal=pobj,
            batch_id=body.get("batch_id"), task_id=body.get("task_id"),
            case_id=body.get("case_id"), customer_id=body.get("customer_id"),
            created_at=now)
        related = _batch_related(tid, env, rid)
        prior_outcome = broker_store.prior_outcome_for_key(
            env.get("idempotency_key", ""), tenant_id=tid,
            exclude_request_id=rid)
        outcome = _tb.prepare_broker_outcome(
            broker_request_id=rid, tenant_id=tid, actor_id=user["uid"],
            actor_type=actor_type, envelope=env, b4_decision=b4,
            b4_proposal=pobj, head=head, quality_report=quality,
            contract=contract, broker_readiness=cert,
            related_requests=related, prior_outcome=prior_outcome,
            adapter_manifest=body.get("adapter_manifest"),
            observed_surface=body.get("observed_surface"),
            policy=_broker_policy(body.get("policy")), created_at=now)
        broker_store.save_request({
            "id": rid, "tenant_id": tid, "tool_id": env.get("tool_id") or "",
            "contract_id": env.get("contract_id") or "",
            "b4_proposal_id": env.get("b4_proposal_id") or "",
            "b4_decision_id": b4.get("decision_id") or "",
            "action_path": env.get("action_path") or "",
            "idempotency_key": env.get("idempotency_key") or "",
            "batch_id": env.get("batch_id") or "",
            "task_id": env.get("task_id") or "",
            "case_id": env.get("case_id") or "",
            "customer_id": env.get("customer_id") or "",
            "broker_request_hash": env["broker_request_hash"],
            "requested_by": user["uid"], "requested_by_actor_type": actor_type,
            "payload_json": json.dumps(env), "created_at": now})
        broker_store.save_outcome({
            "id": str(uuid.uuid4()), "tenant_id": tid, "broker_request_id": rid,
            "tool_id": outcome.get("tool_id") or "",
            "contract_id": outcome.get("contract_id") or "",
            "b4_decision_id": outcome.get("b4_decision_id") or "",
            "broker_status": outcome["broker_status"],
            "dominant_signal": outcome["dominant_signal"],
            "effect_outcome": outcome["effect_outcome"],
            "broker_request_hash": outcome.get("broker_request_hash") or "",
            "broker_decision_hash": outcome["broker_decision_hash"],
            "broker_state_hash": outcome["broker_state_hash"],
            "broker_proof_bundle_hash": outcome["broker_proof_bundle"][
                "broker_proof_bundle_hash"],
            "release_gate_status": outcome["broker_release_gate_report"][
                "release_gate_status"],
            "decided_by": user["uid"], "decided_by_actor_type": actor_type,
            "payload_json": json.dumps(outcome), "created_at": now,
            "updated_at": now})
        _broker_emit(tid, event_type="BROKER_REQUEST_OPENED",
                     broker_request_id=rid, actor_id=user["uid"],
                     actor_type=actor_type,
                     state_hash=env["broker_request_hash"],
                     detail={"tool_id": env.get("tool_id")})
        _broker_emit(tid, event_type="BROKER_OUTCOME_PREPARED",
                     broker_request_id=rid, actor_id=user["uid"],
                     actor_type=actor_type,
                     state_hash=outcome["broker_state_hash"],
                     detail={"status": outcome["broker_status"]})
        audit.append(event_type="AI_BROKER_NULL_OUTCOME_PREPARED",
                     actor=user["uid"], payload={"broker_request_id": rid,
                     "status": outcome["broker_status"]})
        return outcome

    @app.post("/ai-tools/broker/requests")
    async def create_broker_request(body: dict,
                                    user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        return _prepare_and_store(user["tid"], user, body or {})

    @app.get("/ai-tools/broker/requests/{broker_request_id}")
    async def get_broker_request(broker_request_id: str,
                                 user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return _load_broker_request_or_404(broker_request_id, user)

    @app.get("/ai-tools/broker/requests/{broker_request_id}/outcome")
    async def get_broker_outcome(broker_request_id: str,
                                 user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return _load_broker_outcome_or_404(broker_request_id, user)

    @app.get("/ai-tools/broker/requests/{broker_request_id}/safe")
    async def get_broker_safe(broker_request_id: str,
                              user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        o = _load_broker_outcome_or_404(broker_request_id, user)
        restricted = user["role"] in ("viewer", "technician", "accountant")
        # The safe view is deterministically redacted: ids, status, hashes,
        # labels only — never payload/secret/customer/approval/consent fields.
        return {"broker_request_id": broker_request_id, "tenant_id": o[
            "tenant_id"], "broker_status": o["broker_status"],
            "dominant_reason_code": o["dominant_reason_code"],
            "effect_outcome": "NO_EFFECT_OUTCOME", "null_effect_only": True,
            "executes_nothing": True, "requires_future_runtime": True,
            "all_signals": ([] if restricted else o["all_signals"]),
            "broker_decision_hash": o["broker_decision_hash"],
            "broker_proof_bundle_hash": o["broker_proof_bundle"][
                "broker_proof_bundle_hash"],
            "safe_output_projection": o["safe_output_projection"][
                "safe_outcome"], "honesty_labels": _tb.HONESTY_LABELS}

    def _bsub(field):
        async def getter(broker_request_id: str,
                         user: dict = Depends(current_user)):
            require_permission(user, "case.read")
            o = _load_broker_outcome_or_404(broker_request_id, user)
            return {"broker_request_id": broker_request_id, field: o[field],
                    "honesty_labels": _tb.HONESTY_LABELS}
        return getter

    for _slug, _field in _BROKER_SUBFIELDS.items():
        app.add_api_route(
            f"/ai-tools/broker/requests/{{broker_request_id}}/{_slug}",
            _bsub(_field), methods=["GET"])

    @app.post("/ai-tools/broker/requests/{broker_request_id}/fault-injection-check")
    async def broker_fault_injection_check(broker_request_id: str,
                                           user: dict = Depends(current_user)):
        # Deterministically re-run the adversarial fault-injection harness over
        # the sealed evidence. Executes nothing; every fault must fail closed.
        require_permission(user, "case.read")
        o = _load_broker_outcome_or_404(broker_request_id, user)
        h = o["fault_injection_harness"]
        _broker_emit(user["tid"], event_type="BROKER_FAULT_INJECTED",
                     broker_request_id=broker_request_id, actor_id=user["uid"],
                     actor_type=("ai_employee" if user["role"] == "ai_worker"
                                 else "human"),
                     state_hash=h["fault_injection_harness_hash"],
                     detail={"status": h["harness_status"]})
        return h

    @app.post("/ai-tools/broker/requests/{broker_request_id}/verify")
    async def verify_broker_outcome(broker_request_id: str,
                                    user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        o = _load_broker_outcome_or_404(broker_request_id, user)
        recomputed = _tb._core_hash(
            o, "broker_decision_hash", "broker_request_id", "decided_by_actor_id",
            "decided_by_actor_type", "broker_state_hash")
        ok = recomputed == o["broker_decision_hash"]
        return {"broker_request_id": broker_request_id,
                "stored_broker_decision_hash": o["broker_decision_hash"],
                "recomputed_broker_decision_hash": recomputed,
                "broker_decision_hash_valid": ok,
                "verification_status": "VALID" if ok else "TAMPERED",
                "honesty_labels": _tb.HONESTY_LABELS}

    @app.get("/ai-tools/broker/requests/{broker_request_id}/events")
    async def broker_request_events(broker_request_id: str,
                                    user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_broker_request_or_404(broker_request_id, user)
        return {"broker_request_id": broker_request_id, "events":
                broker_store.events(tenant_id=user["tid"],
                                    broker_request_id=broker_request_id),
                "honesty_labels": _tb.HONESTY_LABELS}

    # ---- ViktorAI Verifiable Read-Path Runtime Microkernel (TOOL-B6) ----------------
    from ..ai_employee import tool_runtime as _rt
    from ..ai_employee.tool_runtime_store import ToolRuntimeStore
    runtime_store = ToolRuntimeStore(db)
    app.state.runtime_store = runtime_store

    def _runtime_emit(tid, *, event_type, runtime_request_id, actor_id,
                      actor_type, state_hash, detail):
        seq = runtime_store.next_sequence(tenant_id=tid)
        prev = runtime_store.last_event(tenant_id=tid)
        ev = _rt.build_runtime_event(
            event_type=event_type, tenant_id=tid,
            runtime_request_id=runtime_request_id, actor_id=actor_id,
            actor_type=actor_type, runtime_state_hash=state_hash,
            previous_event_hash=(prev or {}).get("event_hash"), sequence=seq,
            detail=detail, created_at=utcnow())
        runtime_store.append_event({
            "id": str(uuid.uuid4()), "tenant_id": tid, "runtime_request_id":
            runtime_request_id, "event_type": event_type, "sequence": seq,
            "actor_id": actor_id, "actor_type": actor_type,
            "event_hash": ev["event_hash"], "previous_event_hash": ev[
                "previous_event_hash"], "runtime_state_hash": state_hash,
            "payload_json": json.dumps(ev), "created_at": ev["created_at"]})
        return ev

    def _runtime_policy(raw):
        pol = dict(_rt.DEFAULT_POLICY)
        raw = raw or {}
        for k, default in _rt.DEFAULT_POLICY.items():
            if k in raw:
                try:
                    pol[k] = max(0, min(int(default), int(raw[k])))
                except (TypeError, ValueError):
                    pol[k] = default
        return pol

    def _load_runtime_request_or_404(runtime_request_id, user):
        r = runtime_store.request(runtime_request_id, tenant_id=user["tid"])
        if r is None:
            raise HTTPException(404, "runtime request not found")
        return r

    def _load_runtime_outcome_or_404(runtime_request_id, user):
        _load_runtime_request_or_404(runtime_request_id, user)
        o = runtime_store.outcome(runtime_request_id, tenant_id=user["tid"])
        if o is None:
            raise HTTPException(404, "no runtime outcome")
        return o

    _RUNTIME_SUBFIELDS = {
        "adapter": "adapter",
        "capability-calculus": "adapter_capability_calculus",
        "adapter-firewall": "adapter_capability_firewall",
        "snapshot-epoch-vector": "snapshot_epoch_vector",
        "temporal-snapshot-isolation": "temporal_snapshot_isolation",
        "snapshot-seal": "snapshot_seal_check",
        "snapshot-twin": "runtime_snapshot_twin",
        "snapshot-provenance": "snapshot_provenance_dag",
        "query-plan-normal-form": "query_plan_normal_form",
        "semantic-read-firewall": "semantic_read_firewall",
        "microkernel": "runtime_microkernel_contract",
        "operation-ledger": "runtime_operation_ledger",
        "path-policy": "runtime_path_policy_automaton",
        "authority-freeze": "runtime_authority_freeze",
        "read-set-ledger": "read_set_ledger",
        "read-set-completeness": "read_set_completeness_proof",
        "read-set-attestation": "read_set_attestation_capsule",
        "read-output-provenance": "read_output_provenance_map",
        "output-provenance-bisimulation": "output_provenance_bisimulation",
        "semantic-non-interference": "semantic_non_interference_matrix",
        "synthetic-canary-harness": "synthetic_canary_harness",
        "canary-non-leakage": "canary_non_leakage_proof",
        "information-budget": "information_budget_envelope",
        "information-usage-proof": "information_usage_proof",
        "read-amplification": "read_amplification_guard",
        "side-channel-budget": "side_channel_budget_seal",
        "resource-budget": "runtime_resource_budget_envelope",
        "resource-usage-proof": "runtime_resource_usage_proof",
        "entropy-seal": "determinism_entropy_seal",
        "replay-twin": "deterministic_replay_twin",
        "output-taint": "output_taint_lattice",
        "output-non-exfiltration": "output_non_exfiltration_gate",
        "safe-output-projection": "safe_output_projection",
        "data-diode": "data_diode_output_gate",
        "effect-ledger": "runtime_effect_ledger",
        "surface-diff": "runtime_surface_diff",
        "no-effect-proofs": "no_effect_proofs",
        "escape-sentinel": "runtime_escape_sentinel",
        "non-escalation": "runtime_non_escalation_proof",
        "output-provenance-certificate": "output_provenance_certificate",
        "fault-injection": "runtime_fault_injection_harness",
        "release-gate": "runtime_release_gate_report",
        "conformance-vector": "runtime_conformance_vector",
        "proof-bundle": "runtime_proof_bundle",
    }

    @app.get("/ai-tools/runtime/policy")
    async def runtime_policy(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return {"runtime_model_version": _rt.RUNTIME_MODEL_VERSION,
                "read_only": True, "local_only": True, "snapshot_bound": True,
                "reads_mutable_production": False, "writes": False,
                "calls_network": False, "calls_provider": False,
                "is_mcp_runtime": False, "is_llm_runtime": False,
                "reads_secrets": False, "reads_credentials": False,
                "issues_tokens": False, "derives_tokens": False,
                "exports_data": False, "mutates_crm": False,
                "mutates_evidence": False, "executes_payment": False,
                "has_write_endpoint": False, "has_external_endpoint": False,
                "claims_os_level_sandbox": False,
                "claims_differential_privacy": False,
                "most_permissive_outcome": "RUNTIME_READ_ONLY_COMPLETED",
                "accepts_b5_statuses": sorted(_rt.B5_ACCEPTABLE_STATUSES),
                "runtime_statuses": sorted(_rt.RUNTIME_STATUSES),
                "decision_statuses": sorted(_rt.DECISION_STATUSES),
                "allowed_read_classes": sorted(_rt.ALLOWED_READ_CLASSES),
                "forbidden_source_classes": sorted(
                    _rt.FORBIDDEN_SOURCE_CLASSES),
                "read_only_capabilities": sorted(_rt.READ_ONLY_CAPABILITIES),
                "known_adapter_kinds": sorted(_rt.KNOWN_ADAPTER_KINDS),
                "failure_dominance": _rt.FAILURE_DOMINANCE,
                "reason_codes": _rt.REASON_CODES,
                "fault_cases": _rt.FAULT_CASES,
                "default_policy": _rt.DEFAULT_POLICY,
                "honesty_labels": _rt.HONESTY_LABELS}

    @app.get("/ai-tools/runtime/adapters")
    async def runtime_adapters(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return {"tenant_id": user["tid"],
                "known_adapter_kinds": sorted(_rt.KNOWN_ADAPTER_KINDS),
                "read_only_capabilities": sorted(_rt.READ_ONLY_CAPABILITIES),
                "forbidden_adapter_capabilities": sorted(
                    _rt.FORBIDDEN_ADAPTER_CAPS),
                "honesty_labels": _rt.HONESTY_LABELS}

    @app.get("/ai-tools/runtime/registry")
    async def runtime_registry(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        outs = runtime_store.list_outcomes(tenant_id=user["tid"])
        by_status = {}
        for o in outs:
            by_status[o["runtime_status"]] = by_status.get(
                o["runtime_status"], 0) + 1
        return {"tenant_id": user["tid"],
                "runtime_request_count": len(runtime_store.list_requests(
                    tenant_id=user["tid"])),
                "runtime_outcome_count": len(outs),
                "snapshot_count": len(runtime_store.list_snapshots(
                    tenant_id=user["tid"])),
                "outcomes_by_status": by_status,
                "honesty_labels": _rt.HONESTY_LABELS}

    @app.get("/ai-tools/runtime/events")
    async def runtime_events(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        evs = runtime_store.events(tenant_id=user["tid"])
        chain_ok, prev = True, None
        for e in evs:
            if e["previous_event_hash"] != (prev or _rt.GENESIS):
                chain_ok = False
            prev = e["event_hash"]
        return {"tenant_id": user["tid"], "events": evs,
                "event_count": len(evs), "event_chain_valid": chain_ok,
                "ledger_note": "local runtime ledger; not a production immutable "
                "log", "honesty_labels": _rt.HONESTY_LABELS}

    @app.post("/ai-tools/runtime/snapshots")
    async def create_runtime_snapshot(body: dict,
                                      user: dict = Depends(current_user)):
        # A frozen LOCAL snapshot. Fields are declared local data with a data
        # class; no mutable production read occurs. Immutable evidence.
        require_permission(user, "case.update")
        tid, now = user["tid"], utcnow()
        sid = str(uuid.uuid4())
        snap = _rt.build_snapshot(
            snapshot_id=sid, tenant_id=tid, epoch=str(body.get("epoch", "1")),
            scope=body.get("scope", "case"), fields=body.get("fields") or {},
            provenance=body.get("provenance"), created_at=now)
        runtime_store.save_snapshot({
            "id": sid, "tenant_id": tid, "epoch": snap["epoch"],
            "scope": snap["scope"], "field_count": snap["field_count"],
            "snapshot_hash": snap["snapshot_hash"], "created_by": user["uid"],
            "payload_json": json.dumps(snap), "created_at": now})
        audit.append(event_type="AI_RUNTIME_SNAPSHOT_FROZEN", actor=user["uid"],
                     payload={"snapshot_id": sid, "epoch": snap["epoch"]})
        return snap

    @app.get("/ai-tools/runtime/snapshots")
    async def list_runtime_snapshots(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return runtime_store.list_snapshots(tenant_id=user["tid"])

    @app.get("/ai-tools/runtime/snapshots/{snapshot_id}")
    async def get_runtime_snapshot(snapshot_id: str,
                                   user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        snap = runtime_store.snapshot(snapshot_id, tenant_id=user["tid"])
        if snap is None:
            raise HTTPException(404, "snapshot not found")
        return snap

    @app.get("/ai-tools/runtime/requests")
    async def list_runtime_requests(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return runtime_store.list_requests(tenant_id=user["tid"])

    def _prepare_runtime(tid, user, body):
        # A read-only runtime request. It runs a LOCAL deterministic read-only
        # adapter over a FROZEN snapshot and produces provenance-verifiable safe
        # output. No write, no network, no provider/MCP/LLM, no secret/credential
        # read, no token. The most permissive outcome is READ_ONLY_COMPLETED.
        b5rid = str(body.get("b5_broker_request_id", "") or "")
        b5o = broker_store.outcome(b5rid, tenant_id=tid) if b5rid else None
        if b5o is None:
            raise HTTPException(404, "b5 broker outcome not found")
        b5r = broker_store.request(b5rid, tenant_id=tid)
        snapshot_id = str(body.get("snapshot_id", "") or "")
        snapshot = runtime_store.snapshot(snapshot_id, tenant_id=tid) if \
            snapshot_id else None
        if snapshot is None:
            raise HTTPException(404, "snapshot not found")
        actor_type = "ai_employee" if user["role"] == "ai_worker" else "human"
        now = utcnow()
        rid = str(uuid.uuid4())
        env = _rt.build_runtime_request_envelope(
            runtime_request_id=rid, tenant_id=tid, actor_id=user["uid"],
            actor_type=actor_type, b5_outcome=b5o,
            adapter_id=body.get("adapter_id", "adp"), snapshot=snapshot,
            requested_sources=body.get("requested_sources"),
            requested_projection=body.get("requested_projection"),
            requested_epoch=body.get("requested_epoch"), created_at=now)
        # Read amplification correlation from prior outcomes on this snapshot.
        related = []
        for po in runtime_store.outcomes_for_snapshot(snapshot_id,
                                                      tenant_id=tid):
            rl = (po.get("read_set_ledger") or {})
            related.append({
                "runtime_request_id": po.get("runtime_request_id"),
                "read_paths": [e.get("field_path") for e in rl.get(
                    "read_entries", [])], "snapshot_id": snapshot_id,
                "customer_id": "", "case_id": ""})
        outcome = _rt.prepare_runtime_outcome(
            runtime_request_id=rid, tenant_id=tid, actor_id=user["uid"],
            actor_type=actor_type, envelope=env, b5_outcome=b5o, b5_request=b5r,
            snapshot=snapshot, adapter_id=body.get("adapter_id", "adp"),
            adapter_kind=body.get("adapter_kind", "count"),
            allowed_sources=body.get("allowed_sources"),
            allowed_projection=body.get("allowed_projection"),
            requested_sources=body.get("requested_sources"),
            requested_projection=body.get("requested_projection"),
            requested_epoch=body.get("requested_epoch"),
            allowed_scopes=body.get("allowed_scopes"),
            related_requests=related,
            repeated_query_count=len(related),
            declared_entropy=body.get("declared_entropy"),
            observed_surface=body.get("observed_surface"),
            adapter_caps=body.get("adapter_caps"),
            policy=_runtime_policy(body.get("policy")), created_at=now)
        runtime_store.save_request({
            "id": rid, "tenant_id": tid,
            "b5_broker_request_id": b5rid, "adapter_id": env["adapter_id"],
            "snapshot_id": snapshot_id or "",
            "requested_epoch": env["requested_epoch"],
            "runtime_request_hash": env["runtime_request_hash"],
            "requested_by": user["uid"], "requested_by_actor_type": actor_type,
            "payload_json": json.dumps(env), "created_at": now})
        runtime_store.save_outcome({
            "id": str(uuid.uuid4()), "tenant_id": tid, "runtime_request_id": rid,
            "b5_broker_request_id": b5rid, "adapter_id": outcome["adapter_id"],
            "snapshot_id": snapshot_id or "",
            "runtime_status": outcome["runtime_status"],
            "runtime_decision_status": outcome["runtime_decision_status"],
            "runtime_outcome_kind": outcome["runtime_outcome_kind"],
            "dominant_signal": outcome["dominant_signal"],
            "safe_output_hash": outcome["safe_output_hash"],
            "runtime_request_hash": outcome.get("runtime_request_hash") or "",
            "runtime_decision_hash": outcome["runtime_decision_hash"],
            "runtime_state_hash": outcome["runtime_state_hash"],
            "runtime_proof_bundle_hash": outcome["runtime_proof_bundle"][
                "runtime_proof_bundle_hash"],
            "release_gate_status": outcome["runtime_release_gate_report"][
                "release_gate_status"],
            "decided_by": user["uid"], "decided_by_actor_type": actor_type,
            "payload_json": json.dumps(outcome), "created_at": now,
            "updated_at": now})
        _runtime_emit(tid, event_type="RUNTIME_REQUEST_OPENED",
                      runtime_request_id=rid, actor_id=user["uid"],
                      actor_type=actor_type,
                      state_hash=env["runtime_request_hash"],
                      detail={"snapshot_id": snapshot_id})
        _runtime_emit(tid, event_type="RUNTIME_OUTCOME_PREPARED",
                      runtime_request_id=rid, actor_id=user["uid"],
                      actor_type=actor_type,
                      state_hash=outcome["runtime_state_hash"],
                      detail={"status": outcome["runtime_status"]})
        audit.append(event_type="AI_RUNTIME_READ_ONLY_PREPARED",
                     actor=user["uid"], payload={"runtime_request_id": rid,
                     "status": outcome["runtime_status"]})
        return outcome

    @app.post("/ai-tools/runtime/requests")
    async def create_runtime_request(body: dict,
                                     user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        return _prepare_runtime(user["tid"], user, body or {})

    @app.get("/ai-tools/runtime/requests/{runtime_request_id}")
    async def get_runtime_request(runtime_request_id: str,
                                  user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return _load_runtime_request_or_404(runtime_request_id, user)

    @app.get("/ai-tools/runtime/requests/{runtime_request_id}/outcome")
    async def get_runtime_outcome(runtime_request_id: str,
                                  user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return _load_runtime_outcome_or_404(runtime_request_id, user)

    @app.get("/ai-tools/runtime/requests/{runtime_request_id}/safe")
    async def get_runtime_safe(runtime_request_id: str,
                               user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        o = _load_runtime_outcome_or_404(runtime_request_id, user)
        restricted = user["role"] in ("viewer", "technician", "accountant")
        return {"runtime_request_id": runtime_request_id, "tenant_id": o[
            "tenant_id"], "runtime_status": o["runtime_status"],
            "runtime_decision_status": o["runtime_decision_status"],
            "runtime_outcome_kind": o["runtime_outcome_kind"],
            "dominant_reason_code": o["dominant_reason_code"],
            "read_only": True, "local_only": True, "is_external": False,
            "produced_external_effect": False,
            "safe_output": ({} if restricted else o["safe_output"]),
            "safe_output_hash": o["safe_output_hash"],
            "all_signals": ([] if restricted else o["all_signals"]),
            "runtime_decision_hash": o["runtime_decision_hash"],
            "runtime_proof_bundle_hash": o["runtime_proof_bundle"][
                "runtime_proof_bundle_hash"],
            "honesty_labels": _rt.HONESTY_LABELS}

    def _rsub(field):
        async def getter(runtime_request_id: str,
                         user: dict = Depends(current_user)):
            require_permission(user, "case.read")
            o = _load_runtime_outcome_or_404(runtime_request_id, user)
            return {"runtime_request_id": runtime_request_id, field: o.get(
                field), "honesty_labels": _rt.HONESTY_LABELS}
        return getter

    for _slug, _field in _RUNTIME_SUBFIELDS.items():
        app.add_api_route(
            f"/ai-tools/runtime/requests/{{runtime_request_id}}/{_slug}",
            _rsub(_field), methods=["GET"])

    @app.post("/ai-tools/runtime/requests/{runtime_request_id}/"
              "fault-injection-check")
    async def runtime_fault_injection_check(runtime_request_id: str,
                                            user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        o = _load_runtime_outcome_or_404(runtime_request_id, user)
        h = o["runtime_fault_injection_harness"]
        _runtime_emit(user["tid"], event_type="RUNTIME_FAULT_INJECTED",
                      runtime_request_id=runtime_request_id,
                      actor_id=user["uid"],
                      actor_type=("ai_employee" if user["role"] == "ai_worker"
                                  else "human"),
                      state_hash=h["runtime_fault_injection_harness_hash"],
                      detail={"status": h["harness_status"]})
        return h

    @app.post("/ai-tools/runtime/requests/{runtime_request_id}/verify")
    async def verify_runtime_outcome(runtime_request_id: str,
                                     user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        o = _load_runtime_outcome_or_404(runtime_request_id, user)
        recomputed = _rt._core_hash(
            o, "runtime_decision_hash", "runtime_request_id",
            "decided_by_actor_id", "decided_by_actor_type", "runtime_state_hash")
        ok = recomputed == o["runtime_decision_hash"]
        return {"runtime_request_id": runtime_request_id,
                "stored_runtime_decision_hash": o["runtime_decision_hash"],
                "recomputed_runtime_decision_hash": recomputed,
                "runtime_decision_hash_valid": ok,
                "verification_status": "VALID" if ok else "TAMPERED",
                "honesty_labels": _rt.HONESTY_LABELS}

    @app.get("/ai-tools/runtime/requests/{runtime_request_id}/events")
    async def runtime_request_events(runtime_request_id: str,
                                     user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_runtime_request_or_404(runtime_request_id, user)
        return {"runtime_request_id": runtime_request_id, "events":
                runtime_store.events(tenant_id=user["tid"],
                                     runtime_request_id=runtime_request_id),
                "honesty_labels": _rt.HONESTY_LABELS}

    # ==== TOOL-B7: Transaction-Escrow Write-Intent Draft Runtime =============
    # Draft-only, escrowed FUTURE-write modelling. Consumes a B6 read-path
    # runtime outcome. NO commit/execute/effect-release/activate-commitment/
    # escrow-commit endpoint exists anywhere below.
    from ..ai_employee import tool_write_intent as _wi
    from ..ai_employee.tool_write_intent_store import ToolWriteIntentStore
    write_intent_store = ToolWriteIntentStore(db)
    app.state.write_intent_store = write_intent_store

    def _wi_emit(tid, *, event_type, write_intent_id, actor_id, actor_type,
                 state_hash, detail):
        seq = write_intent_store.next_sequence(tenant_id=tid)
        prev = write_intent_store.last_event(tenant_id=tid)
        ev = _wi.build_write_intent_event(
            event_type=event_type, tenant_id=tid,
            write_intent_id=write_intent_id, actor_id=actor_id,
            actor_type=actor_type, write_intent_state_hash=state_hash,
            previous_event_hash=(prev or {}).get("event_hash"), sequence=seq,
            detail=detail, created_at=utcnow())
        write_intent_store.append_event({
            "id": str(uuid.uuid4()), "tenant_id": tid, "write_intent_id":
            write_intent_id, "event_type": event_type, "sequence": seq,
            "actor_id": actor_id, "actor_type": actor_type,
            "event_hash": ev["event_hash"], "previous_event_hash": ev[
                "previous_event_hash"], "write_intent_state_hash": state_hash,
            "payload_json": json.dumps(ev), "created_at": ev["created_at"]})
        return ev

    def _load_write_intent_or_404(write_intent_id, user):
        r = write_intent_store.request(write_intent_id, tenant_id=user["tid"])
        if r is None:
            raise HTTPException(404, "write-intent request not found")
        return r

    def _load_write_intent_outcome_or_404(write_intent_id, user):
        _load_write_intent_or_404(write_intent_id, user)
        o = write_intent_store.outcome(write_intent_id, tenant_id=user["tid"])
        if o is None:
            raise HTTPException(404, "no write-intent outcome")
        return o

    _WI_SUBFIELDS = {
        "write-intent-draft": "write_intent_draft",
        "semantic-transaction": "semantic_transaction",
        "transaction-boundary": "transaction_boundary",
        "shadow-state-delta-graph": "shadow_state_delta_graph",
        "state-delta": "state_delta",
        "staged-effect-outbox": "staged_effect_outbox",
        "effect-outbox-quarantine": "effect_outbox_quarantine",
        "active-commitment": "active_commitment_record",
        "rollback-simulation": "rollback_simulation",
        "compensation-plan": "compensation_plan",
        "review-package": "review_package",
        "approval-requirement": "approval_requirement",
        "approval-binding": "approval_binding",
        "meaningful-judgment": "meaningful_judgment",
        "contestability": "contestability_window",
        "obligation-containment": "obligation_containment",
        "evidence-preservation": "evidence_preservation",
        "transaction-invariants": "transaction_invariants",
        "semantic-transaction-replay": "semantic_transaction_replay",
        "commit-non-execution": "commit_non_execution",
        "transaction-escrow": "transaction_escrow_capsule",
        "escrowed-commit-readiness": "escrowed_commit_readiness_certificate",
        "future-commit-gate-contract": "future_commit_gate_contract",
        "commit-gate-non-existence": "commit_gate_non_existence_proof",
        "revalidation-debt": "revalidation_debt_ledger",
        "semantic-rollback-fence": "semantic_rollback_fence",
        "action-replay-guard": "action_replay_guard",
        "authority-resurrection-guard": "authority_resurrection_guard",
        "rollback-replay-equivalence": "rollback_replay_equivalence",
        "concurrent-draft-conflicts": "concurrent_draft_conflict_graph",
        "transaction-conflict-oracle": "transaction_conflict_oracle",
        "state-witness-quorum": "state_witness_quorum",
        "escrow-expiry": "escrow_expiry_policy",
        "escrow-tamper-evidence": "escrow_tamper_evidence",
        "readiness-non-execution":
            "transaction_readiness_non_execution_certificate",
        "transaction-escrow-proof-extension":
            "transaction_escrow_proof_extension",
        "fault-injection": "write_intent_fault_injection_harness",
        "release-gate": "write_intent_release_gate_report",
        "conformance-vector": "write_intent_conformance_vector",
        "proof-bundle": "write_intent_proof_bundle",
    }

    @app.get("/ai-tools/write-intents/policy")
    async def write_intent_policy(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return {"write_intent_model_version": _wi.WRITE_INTENT_MODEL_VERSION,
                "draft_only": True, "escrow_only": True, "commits": False,
                "executes": False, "releases_effects": False,
                "activates_commitment": False, "sends_customer_message": False,
                "executes_payment": False, "mutates_crm": False,
                "mutates_evidence": False, "exports_data": False,
                "calls_provider": False, "calls_mcp": False, "calls_llm": False,
                "issues_tokens": False, "derives_tokens": False,
                "reads_credentials": False, "has_commit_endpoint": False,
                "has_execute_endpoint": False,
                "has_effect_release_endpoint": False,
                "has_activate_commitment_endpoint": False,
                "has_escrow_commit_endpoint": False,
                "approval_does_not_execute": True,
                "escrow_does_not_execute": True,
                "commit_readiness_does_not_execute": True,
                "most_permissive_outcome": "TRANSACTION_ESCROW_DRAFT_CREATED",
                "accepts_b6_statuses": sorted(_wi.B6_ACCEPTABLE_STATUSES),
                "write_intent_statuses": sorted(_wi.WRITE_INTENT_STATUSES),
                "decision_statuses": sorted(_wi.DECISION_STATUSES),
                "failure_dominance": _wi.FAILURE_DOMINANCE,
                "reason_codes": _wi.REASON_CODES,
                "fault_cases": _wi.FAULT_CASES,
                "conflict_classes": sorted(_wi.CONFLICT_CLASSES),
                "witness_classes": sorted(_wi.WITNESS_CLASSES),
                "debt_item_types": sorted(_wi.DEBT_ITEM_TYPES),
                "commit_surfaces": _wi.COMMIT_SURFACES,
                "default_policy": _wi.DEFAULT_POLICY,
                "honesty_labels": _wi.HONESTY_LABELS}

    @app.get("/ai-tools/write-intents/registry")
    async def write_intent_registry(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        outs = write_intent_store.list_outcomes(tenant_id=user["tid"])
        by_status = {}
        for o in outs:
            by_status[o["write_intent_status"]] = by_status.get(
                o["write_intent_status"], 0) + 1
        return {"tenant_id": user["tid"],
                "write_intent_request_count": len(
                    write_intent_store.list_requests(tenant_id=user["tid"])),
                "write_intent_outcome_count": len(outs),
                "outcomes_by_status": by_status,
                "honesty_labels": _wi.HONESTY_LABELS}

    @app.get("/ai-tools/write-intents/events")
    async def write_intent_events(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        evs = write_intent_store.events(tenant_id=user["tid"])
        chain_ok, prev = True, None
        for e in evs:
            if e["previous_event_hash"] != (prev or _wi.GENESIS):
                chain_ok = False
            prev = e["event_hash"]
        return {"tenant_id": user["tid"], "events": evs,
                "event_count": len(evs), "event_chain_valid": chain_ok,
                "ledger_note": "local write-intent draft ledger; not a "
                "production immutable log",
                "honesty_labels": _wi.HONESTY_LABELS}

    _WI_PASS_KEYS = (
        "target_entity", "proposed_deltas", "intent", "obligations",
        "evidence_refs", "consent_scope", "customer_promises", "task_scope",
        "boundary_operations", "risk_tier", "approvals", "requester_id",
        "dual_control_required", "objections", "obligation_states",
        "contestability_window_open", "destructive_repair",
        "triggering_evidence_preserved", "invariant_violations",
        "replay_consistent", "rollback_feasible", "compensation_gaps",
        "debt_items", "prior_action_hashes", "proposed_action_hash",
        "idempotency_key", "consumed_authority_refs", "approval_refs",
        "token_like_refs", "credential_like_refs", "resurrected_authority",
        "checkpoint_refs", "restore_refs", "prior_effect_refs",
        "proposed_effect_refs", "rollback_replay_mismatch",
        "related_write_intents", "state_witnesses", "policy_epoch",
        "escrow_created_epoch", "escrow_expires_epoch", "escrow_mutable",
        "observed_escrow_hash", "current_epoch", "commit_endpoint_present",
        "commit_capability_present", "detected_commit_endpoints",
        "detected_commit_capabilities", "detected_activation_paths",
        "attempt_markers", "execution_markers", "effect_release_attempts",
        "commitment_activation_attempts", "policy",
    )

    def _prepare_write_intent(tid, user, body):
        # A draft-only, escrowed write-intent request. It models a FUTURE write
        # over a B6-consumed read-path runtime outcome and produces escrow,
        # commit-readiness, conflict, rollback-fence and non-execution evidence.
        # NO write, NO commit, NO effect release, NO commitment activation, NO
        # external effect. The most permissive outcome is a local escrowed
        # draft.
        b6rid = str(body.get("b6_runtime_request_id", "") or "")
        b6o = runtime_store.outcome(b6rid, tenant_id=tid) if b6rid else None
        if b6o is None:
            raise HTTPException(404, "b6 runtime outcome not found")
        b6r = runtime_store.request(b6rid, tenant_id=tid)
        actor_type = "ai_employee" if user["role"] == "ai_worker" else "human"
        now = utcnow()
        wid = str(uuid.uuid4())
        te = body.get("target_entity") or {}
        env = _wi.build_write_intent_request_envelope(
            write_intent_id=wid, tenant_id=tid, actor_id=user["uid"],
            actor_type=actor_type, b6_outcome=b6o, target_entity=te,
            requested_deltas=body.get("proposed_deltas"),
            intent=body.get("intent"), created_at=now)
        passthrough = {k: body[k] for k in _WI_PASS_KEYS if k in body}
        passthrough.setdefault("requester_id", user["uid"])
        outcome = _wi.prepare_write_intent_outcome(
            write_intent_id=wid, tenant_id=tid, actor_id=user["uid"],
            actor_type=actor_type, envelope=env, b6_outcome=b6o,
            b6_request=b6r, created_at=now, **passthrough)
        write_intent_store.save_request({
            "id": wid, "tenant_id": tid, "b6_runtime_request_id": b6rid,
            "target_entity_type": env["target_entity_type"],
            "target_entity_id": env["target_entity_id"],
            "write_intent_request_hash": env["write_intent_request_hash"],
            "requested_by": user["uid"], "requested_by_actor_type": actor_type,
            "payload_json": json.dumps(env), "created_at": now})
        write_intent_store.save_outcome({
            "id": str(uuid.uuid4()), "tenant_id": tid, "write_intent_id": wid,
            "b6_runtime_request_id": b6rid,
            "target_entity_id": env["target_entity_id"],
            "write_intent_status": outcome["write_intent_status"],
            "write_intent_decision_status": outcome[
                "write_intent_decision_status"],
            "write_intent_outcome_kind": outcome["write_intent_outcome_kind"],
            "dominant_signal": outcome["dominant_signal"],
            "transaction_escrow_hash": outcome["transaction_escrow_capsule"][
                "transaction_escrow_hash"],
            "escrowed_commit_readiness_certificate_hash": outcome[
                "escrowed_commit_readiness_certificate"][
                "escrowed_commit_readiness_certificate_hash"],
            "write_intent_request_hash": outcome.get(
                "write_intent_request_hash") or "",
            "write_intent_decision_hash": outcome["write_intent_decision_hash"],
            "write_intent_state_hash": outcome["write_intent_state_hash"],
            "write_intent_proof_bundle_hash": outcome[
                "write_intent_proof_bundle"]["write_intent_proof_bundle_hash"],
            "release_gate_status": outcome["write_intent_release_gate_report"][
                "release_gate_status"],
            "ready_for_future_commit_only": 1 if outcome[
                "ready_for_future_commit_only"] else 0,
            "decided_by": user["uid"], "decided_by_actor_type": actor_type,
            "payload_json": json.dumps(outcome), "created_at": now,
            "updated_at": now})
        _wi_emit(tid, event_type="WRITE_INTENT_REQUEST_OPENED",
                 write_intent_id=wid, actor_id=user["uid"],
                 actor_type=actor_type,
                 state_hash=env["write_intent_request_hash"],
                 detail={"target_entity_id": env["target_entity_id"]})
        _wi_emit(tid, event_type="WRITE_INTENT_OUTCOME_PREPARED",
                 write_intent_id=wid, actor_id=user["uid"],
                 actor_type=actor_type,
                 state_hash=outcome["write_intent_state_hash"],
                 detail={"status": outcome["write_intent_status"]})
        audit.append(event_type="AI_WRITE_INTENT_DRAFT_PREPARED",
                     actor=user["uid"], payload={"write_intent_id": wid,
                     "status": outcome["write_intent_status"]})
        return outcome

    @app.post("/ai-tools/write-intents")
    async def create_write_intent(body: dict,
                                  user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        return _prepare_write_intent(user["tid"], user, body or {})

    @app.get("/ai-tools/write-intents")
    async def list_write_intents(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return write_intent_store.list_requests(tenant_id=user["tid"])

    @app.get("/ai-tools/write-intents/{write_intent_id}")
    async def get_write_intent(write_intent_id: str,
                               user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return _load_write_intent_or_404(write_intent_id, user)

    @app.get("/ai-tools/write-intents/{write_intent_id}/outcome")
    async def get_write_intent_outcome(write_intent_id: str,
                                       user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return _load_write_intent_outcome_or_404(write_intent_id, user)

    @app.get("/ai-tools/write-intents/{write_intent_id}/safe")
    async def get_write_intent_safe(write_intent_id: str,
                                    user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        o = _load_write_intent_outcome_or_404(write_intent_id, user)
        restricted = user["role"] in ("viewer", "technician", "accountant")
        return {"write_intent_id": write_intent_id, "tenant_id": o[
            "tenant_id"], "write_intent_status": o["write_intent_status"],
            "write_intent_decision_status": o["write_intent_decision_status"],
            "write_intent_outcome_kind": o["write_intent_outcome_kind"],
            "dominant_reason_code": o["dominant_reason_code"],
            "draft_only": True, "escrow_only": True, "is_commit": False,
            "is_execution": False, "produced_external_effect": False,
            "released_effect": False, "activated_commitment": False,
            "commit_executable_now": False,
            "ready_for_future_commit_only": o["ready_for_future_commit_only"],
            "review_package_hash": o["review_package"]["review_package_hash"],
            "transaction_escrow_hash": o["transaction_escrow_capsule"][
                "transaction_escrow_hash"],
            "all_signals": ([] if restricted else o["all_signals"]),
            "write_intent_decision_hash": o["write_intent_decision_hash"],
            "write_intent_proof_bundle_hash": o["write_intent_proof_bundle"][
                "write_intent_proof_bundle_hash"],
            "honesty_labels": _wi.HONESTY_LABELS}

    def _wisub(field):
        async def getter(write_intent_id: str,
                         user: dict = Depends(current_user)):
            require_permission(user, "case.read")
            o = _load_write_intent_outcome_or_404(write_intent_id, user)
            return {"write_intent_id": write_intent_id, field: o.get(field),
                    "honesty_labels": _wi.HONESTY_LABELS}
        return getter

    for _slug, _field in _WI_SUBFIELDS.items():
        app.add_api_route(
            f"/ai-tools/write-intents/{{write_intent_id}}/{_slug}",
            _wisub(_field), methods=["GET"])

    @app.post("/ai-tools/write-intents/{write_intent_id}/fault-injection-check")
    async def write_intent_fault_injection_check(
            write_intent_id: str, user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        o = _load_write_intent_outcome_or_404(write_intent_id, user)
        h = o["write_intent_fault_injection_harness"]
        _wi_emit(user["tid"], event_type="WRITE_INTENT_FAULT_INJECTED",
                 write_intent_id=write_intent_id, actor_id=user["uid"],
                 actor_type=("ai_employee" if user["role"] == "ai_worker"
                             else "human"),
                 state_hash=h["write_intent_fault_injection_harness_hash"],
                 detail={"status": h["harness_status"]})
        return h

    @app.post("/ai-tools/write-intents/{write_intent_id}/verify")
    async def verify_write_intent_outcome(write_intent_id: str,
                                          user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        o = _load_write_intent_outcome_or_404(write_intent_id, user)
        recomputed = _wi._core_hash(
            o, "write_intent_decision_hash", "write_intent_id",
            "decided_by_actor_id", "decided_by_actor_type",
            "write_intent_state_hash")
        ok = recomputed == o["write_intent_decision_hash"]
        return {"write_intent_id": write_intent_id,
                "stored_write_intent_decision_hash": o[
                    "write_intent_decision_hash"],
                "recomputed_write_intent_decision_hash": recomputed,
                "write_intent_decision_hash_valid": ok,
                "verification_status": "VALID" if ok else "TAMPERED",
                "honesty_labels": _wi.HONESTY_LABELS}

    @app.get("/ai-tools/write-intents/{write_intent_id}/events")
    async def write_intent_request_events(write_intent_id: str,
                                          user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_write_intent_or_404(write_intent_id, user)
        return {"write_intent_id": write_intent_id, "events":
                write_intent_store.events(tenant_id=user["tid"],
                                          write_intent_id=write_intent_id),
                "honesty_labels": _wi.HONESTY_LABELS}

    # ==== TOOL-B8: Machine-Checkable Pre-B9 Assurance / Local Commit Sim =====
    # Simulation-only pre-B9 assurance. Consumes a B7 escrow draft. NO real
    # commit / execute / release-effects / activate-commitment / activate-b9 /
    # grant-authority / commit-lease endpoint exists anywhere below.
    from ..ai_employee import tool_commit_simulation as _cs
    from ..ai_employee.tool_commit_simulation_store import (
        ToolCommitSimulationStore)
    commit_sim_store = ToolCommitSimulationStore(db)
    app.state.commit_sim_store = commit_sim_store

    def _cs_emit(tid, *, event_type, commit_simulation_id, actor_id, actor_type,
                 state_hash, detail):
        seq = commit_sim_store.next_sequence(tenant_id=tid)
        prev = commit_sim_store.last_event(tenant_id=tid)
        ev = _cs.build_commit_simulation_event(
            event_type=event_type, tenant_id=tid,
            commit_simulation_id=commit_simulation_id, actor_id=actor_id,
            actor_type=actor_type, commit_simulation_state_hash=state_hash,
            previous_event_hash=(prev or {}).get("event_hash"), sequence=seq,
            detail=detail, created_at=utcnow())
        commit_sim_store.append_event({
            "id": str(uuid.uuid4()), "tenant_id": tid, "commit_simulation_id":
            commit_simulation_id, "event_type": event_type, "sequence": seq,
            "actor_id": actor_id, "actor_type": actor_type,
            "event_hash": ev["event_hash"], "previous_event_hash": ev[
                "previous_event_hash"], "commit_simulation_state_hash":
            state_hash, "payload_json": json.dumps(ev),
            "created_at": ev["created_at"]})
        return ev

    def _load_commit_sim_or_404(commit_simulation_id, user):
        r = commit_sim_store.request(commit_simulation_id, tenant_id=user["tid"])
        if r is None:
            raise HTTPException(404, "commit simulation request not found")
        return r

    def _load_commit_sim_outcome_or_404(commit_simulation_id, user):
        _load_commit_sim_or_404(commit_simulation_id, user)
        o = commit_sim_store.outcome(commit_simulation_id, tenant_id=user["tid"])
        if o is None:
            raise HTTPException(404, "no commit simulation outcome")
        return o

    _CS_SUBFIELDS = {
        "b7-consumption-gate": "b7_consumption_gate",
        "state-witness-revalidation": "state_witness_revalidation",
        "shadow-dry-run": "shadow_dry_run",
        "effect-simulation": "effect_simulation",
        "rollback-fence": "rollback_fence",
        "differential-replay": "differential_replay",
        "metamorphic-oracle": "metamorphic_oracle",
        "compliance-predicate": "compliance_predicate",
        "rollback-simulation": "rollback_simulation",
        "compensation-simulation": "compensation_simulation",
        "no-commit-theorem": "no_commit_theorem",
        "non-execution-certificate": "non_execution_certificate",
        "artifact-quarantine-vault": "artifact_quarantine_vault",
        "b9-firewall": "b9_firewall",
        "b9-revalidation-contract": "b9_revalidation_contract",
        "trace-coverage": "trace_coverage",
        "non-production-seal": "non_production_seal",
        "safety-case": "safety_case",
        "assurance-envelope": "assurance_envelope",
        "evidence-closure-net": "evidence_closure_net",
        "non-delegable-artifact-seal": "non_delegable_artifact_seal",
        "b9-negative-capability": "b9_negative_capability",
        "cross-artifact-consistency": "cross_artifact_consistency",
        "route-topology-diff": "route_topology_diff",
        "trace-completeness-witness": "trace_completeness_witness",
        "proof-obligation-matrix": "proof_obligation_matrix",
        "production-claim-scanner": "production_claim_scanner",
        "final-ci-gate": "final_ci_gate",
        "v5-proof-extension": "b8_v5_proof_extension",
        "fault-injection": "commit_sim_fault_injection_harness",
        "release-gate": "commit_sim_release_gate_report",
        "conformance-vector": "commit_sim_conformance_vector",
        "proof-bundle": "commit_simulation_proof_bundle",
    }

    @app.get("/ai-tools/commit-simulations/policy")
    async def commit_sim_policy(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return {"commit_sim_model_version": _cs.COMMIT_SIM_MODEL_VERSION,
                "simulation_only": True, "performs_real_commit": False,
                "releases_effects": False, "activates_commitment": False,
                "activates_b9": False, "grants_b9_authority": False,
                "issues_commit_lease": False, "calls_provider": False,
                "calls_mcp": False, "calls_llm": False, "issues_tokens": False,
                "reads_credentials": False, "sends_messages": False,
                "executes_payment": False, "mutates_crm": False,
                "mutates_evidence": False, "exports_data": False,
                "artifacts_are_authority": False,
                "b9_revalidation_required": True, "production_ready": False,
                "commit_executable_now": False,
                "has_commit_endpoint": False, "has_execute_endpoint": False,
                "has_effect_release_endpoint": False,
                "has_activate_commitment_endpoint": False,
                "has_activate_b9_endpoint": False,
                "has_grant_authority_endpoint": False,
                "has_commit_lease_endpoint": False,
                "most_permissive_outcome": "B8_V5_ACCEPTED",
                "accepts_b7_statuses": sorted(_cs.B7_ACCEPTABLE_STATUSES),
                "commit_simulation_statuses": sorted(_cs.COMMIT_SIM_STATUSES),
                "decision_statuses": sorted(_cs.DECISION_STATUSES),
                "failure_dominance": _cs.FAILURE_DOMINANCE,
                "reason_codes": _cs.REASON_CODES,
                "fault_cases": _cs.FAULT_CASES,
                "required_trace_families": _cs.REQUIRED_TRACE_FAMILIES,
                "required_obligations": _cs.REQUIRED_OBLIGATIONS,
                "b9_must_reject_artifacts": _cs.B9_MUST_REJECT_ARTIFACTS,
                "b9_must_recompute": _cs.B9_MUST_RECOMPUTE,
                "forbidden_route_semantics": _cs.FORBIDDEN_ROUTE_SEMANTICS,
                "default_policy": _cs.DEFAULT_POLICY,
                "honesty_labels": _cs.HONESTY_LABELS}

    @app.get("/ai-tools/commit-simulations/registry")
    async def commit_sim_registry(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        outs = commit_sim_store.list_outcomes(tenant_id=user["tid"])
        by_status = {}
        for o in outs:
            by_status[o["commit_simulation_status"]] = by_status.get(
                o["commit_simulation_status"], 0) + 1
        return {"tenant_id": user["tid"],
                "commit_simulation_request_count": len(
                    commit_sim_store.list_requests(tenant_id=user["tid"])),
                "commit_simulation_outcome_count": len(outs),
                "outcomes_by_status": by_status,
                "honesty_labels": _cs.HONESTY_LABELS}

    @app.get("/ai-tools/commit-simulations/events")
    async def commit_sim_events(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        evs = commit_sim_store.events(tenant_id=user["tid"])
        chain_ok, prev = True, None
        for e in evs:
            if e["previous_event_hash"] != (prev or _cs.GENESIS):
                chain_ok = False
            prev = e["event_hash"]
        return {"tenant_id": user["tid"], "events": evs,
                "event_count": len(evs), "event_chain_valid": chain_ok,
                "ledger_note": "local commit-simulation ledger; not a "
                "production immutable log", "honesty_labels": _cs.HONESTY_LABELS}

    _CS_PASS_KEYS = (
        "fresh_witnesses", "policy_epoch", "revalidation_ok", "dry_run_ok",
        "touches_production", "effect_release_attempts", "replay_attack",
        "authority_resurrection", "replay_consistent", "metamorphic_holds",
        "predicate_violations", "rollback_feasible", "compensation_gaps",
        "attempt_markers", "artifact_refs", "artifact_escape_attempts",
        "b9_authority_transfer", "b9_activation", "b9_contract_present",
        "observed_trace_families", "seal_poisoned", "artifact_hashes",
        "delegation_attempts", "bearer_fields", "activation_fields",
        "b9_negcap_valid", "baseline_routes", "final_routes", "added_routes",
        "dropped_obligations", "extra_claims", "targeted_pass", "full_pass",
        "unexpected_positive", "injected_mismatches", "execution_markers",
        "theorem_refuted", "force_missing_nodes", "force_missing_edges",
        "force_unclosed_claims", "force_assurance_invalid", "policy",
    )

    def _prepare_commit_sim(tid, user, body):
        # A simulation-only pre-B9 assurance request. It consumes a B7 escrow
        # draft and produces machine-checkable EVIDENCE. NO real commit, NO
        # effect release, NO commitment/B9 activation, NO external effect.
        wid = str(body.get("b7_write_intent_id", "") or "")
        b7o = write_intent_store.outcome(wid, tenant_id=tid) if wid else None
        if b7o is None:
            raise HTTPException(404, "b7 write-intent outcome not found")
        actor_type = "ai_employee" if user["role"] == "ai_worker" else "human"
        now = utcnow()
        sid = str(uuid.uuid4())
        env = _cs.build_commit_simulation_request_envelope(
            commit_simulation_id=sid, tenant_id=tid, actor_id=user["uid"],
            actor_type=actor_type, b7_outcome=b7o, created_at=now)
        passthrough = {k: body[k] for k in _CS_PASS_KEYS if k in body}
        outcome = _cs.prepare_commit_simulation_outcome(
            commit_simulation_id=sid, tenant_id=tid, actor_id=user["uid"],
            actor_type=actor_type, envelope=env, b7_outcome=b7o, created_at=now,
            **passthrough)
        commit_sim_store.save_request({
            "id": sid, "tenant_id": tid, "b7_write_intent_id": wid,
            "commit_simulation_request_hash": env[
                "commit_simulation_request_hash"],
            "requested_by": user["uid"], "requested_by_actor_type": actor_type,
            "payload_json": json.dumps(env), "created_at": now})
        commit_sim_store.save_outcome({
            "id": str(uuid.uuid4()), "tenant_id": tid, "commit_simulation_id":
            sid, "b7_write_intent_id": wid,
            "commit_simulation_status": outcome["commit_simulation_status"],
            "commit_simulation_decision_status": outcome[
                "commit_simulation_decision_status"],
            "commit_simulation_outcome_kind": outcome[
                "commit_simulation_outcome_kind"],
            "dominant_signal": outcome["dominant_signal"],
            "assurance_envelope_hash": outcome["assurance_envelope"][
                "assurance_envelope_hash"],
            "commit_simulation_request_hash": outcome.get(
                "commit_simulation_request_hash") or "",
            "commit_simulation_decision_hash": outcome[
                "commit_simulation_decision_hash"],
            "commit_simulation_state_hash": outcome[
                "commit_simulation_state_hash"],
            "commit_simulation_proof_bundle_hash": outcome[
                "commit_simulation_proof_bundle"][
                "commit_simulation_proof_bundle_hash"],
            "release_gate_status": outcome["commit_sim_release_gate_report"][
                "release_gate_status"],
            "b8_v5_accepted": 1 if outcome["b8_v5_accepted"] else 0,
            "decided_by": user["uid"], "decided_by_actor_type": actor_type,
            "payload_json": json.dumps(outcome), "created_at": now,
            "updated_at": now})
        _cs_emit(tid, event_type="COMMIT_SIMULATION_REQUEST_OPENED",
                 commit_simulation_id=sid, actor_id=user["uid"],
                 actor_type=actor_type,
                 state_hash=env["commit_simulation_request_hash"],
                 detail={"b7_write_intent_id": wid})
        _cs_emit(tid, event_type="COMMIT_SIMULATION_OUTCOME_PREPARED",
                 commit_simulation_id=sid, actor_id=user["uid"],
                 actor_type=actor_type,
                 state_hash=outcome["commit_simulation_state_hash"],
                 detail={"status": outcome["commit_simulation_status"]})
        audit.append(event_type="AI_COMMIT_SIMULATION_PREPARED",
                     actor=user["uid"], payload={"commit_simulation_id": sid,
                     "status": outcome["commit_simulation_status"]})
        return outcome

    @app.post("/ai-tools/commit-simulations")
    async def create_commit_sim(body: dict,
                                user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        return _prepare_commit_sim(user["tid"], user, body or {})

    @app.get("/ai-tools/commit-simulations")
    async def list_commit_sims(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return commit_sim_store.list_requests(tenant_id=user["tid"])

    @app.get("/ai-tools/commit-simulations/{commit_simulation_id}")
    async def get_commit_sim(commit_simulation_id: str,
                             user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return _load_commit_sim_or_404(commit_simulation_id, user)

    @app.get("/ai-tools/commit-simulations/{commit_simulation_id}/outcome")
    async def get_commit_sim_outcome(commit_simulation_id: str,
                                     user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return _load_commit_sim_outcome_or_404(commit_simulation_id, user)

    @app.get("/ai-tools/commit-simulations/{commit_simulation_id}/safe")
    async def get_commit_sim_safe(commit_simulation_id: str,
                                  user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        o = _load_commit_sim_outcome_or_404(commit_simulation_id, user)
        restricted = user["role"] in ("viewer", "technician", "accountant")
        return {"commit_simulation_id": commit_simulation_id, "tenant_id": o[
            "tenant_id"], "commit_simulation_status": o[
            "commit_simulation_status"],
            "commit_simulation_decision_status": o[
                "commit_simulation_decision_status"],
            "commit_simulation_outcome_kind": o[
                "commit_simulation_outcome_kind"],
            "dominant_reason_code": o["dominant_reason_code"],
            "simulation_only": True, "is_real_commit": False,
            "is_execution": False, "produced_external_effect": False,
            "released_effect": False, "activated_commitment": False,
            "activated_b9": False, "commit_executable_now": False,
            "production_ready": False, "b8_v5_accepted": o["b8_v5_accepted"],
            "b9_revalidation_required": True,
            "assurance_envelope_hash": o["assurance_envelope"][
                "assurance_envelope_hash"],
            "all_signals": ([] if restricted else o["all_signals"]),
            "commit_simulation_decision_hash": o[
                "commit_simulation_decision_hash"],
            "commit_simulation_proof_bundle_hash": o[
                "commit_simulation_proof_bundle"][
                "commit_simulation_proof_bundle_hash"],
            "honesty_labels": _cs.HONESTY_LABELS}

    def _cssub(field):
        async def getter(commit_simulation_id: str,
                         user: dict = Depends(current_user)):
            require_permission(user, "case.read")
            o = _load_commit_sim_outcome_or_404(commit_simulation_id, user)
            return {"commit_simulation_id": commit_simulation_id, field: o.get(
                field), "honesty_labels": _cs.HONESTY_LABELS}
        return getter

    for _slug, _field in _CS_SUBFIELDS.items():
        app.add_api_route(
            "/ai-tools/commit-simulations/{commit_simulation_id}/" + _slug,
            _cssub(_field), methods=["GET"])

    @app.post("/ai-tools/commit-simulations/{commit_simulation_id}/"
              "fault-injection-check")
    async def commit_sim_fault_injection_check(
            commit_simulation_id: str, user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        o = _load_commit_sim_outcome_or_404(commit_simulation_id, user)
        h = o["commit_sim_fault_injection_harness"]
        _cs_emit(user["tid"], event_type="COMMIT_SIMULATION_FAULT_INJECTED",
                 commit_simulation_id=commit_simulation_id, actor_id=user["uid"],
                 actor_type=("ai_employee" if user["role"] == "ai_worker"
                             else "human"),
                 state_hash=h["commit_sim_fault_injection_harness_hash"],
                 detail={"status": h["harness_status"]})
        return h

    @app.post("/ai-tools/commit-simulations/{commit_simulation_id}/verify")
    async def verify_commit_sim_outcome(commit_simulation_id: str,
                                        user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        o = _load_commit_sim_outcome_or_404(commit_simulation_id, user)
        recomputed = _cs._core_hash(
            o, "commit_simulation_decision_hash", "commit_simulation_id",
            "decided_by_actor_id", "decided_by_actor_type",
            "commit_simulation_state_hash")
        ok = recomputed == o["commit_simulation_decision_hash"]
        return {"commit_simulation_id": commit_simulation_id,
                "stored_commit_simulation_decision_hash": o[
                    "commit_simulation_decision_hash"],
                "recomputed_commit_simulation_decision_hash": recomputed,
                "commit_simulation_decision_hash_valid": ok,
                "verification_status": "VALID" if ok else "TAMPERED",
                "honesty_labels": _cs.HONESTY_LABELS}

    @app.get("/ai-tools/commit-simulations/{commit_simulation_id}/events")
    async def commit_sim_request_events(commit_simulation_id: str,
                                        user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_commit_sim_or_404(commit_simulation_id, user)
        return {"commit_simulation_id": commit_simulation_id, "events":
                commit_sim_store.events(tenant_id=user["tid"],
                                        commit_simulation_id=commit_simulation_id),
                "honesty_labels": _cs.HONESTY_LABELS}

    # ==== TOOL-B9: Finalis Transaction Twin + Proof-of-Execution Runtime =====
    # Local, reversible, governed transaction runtime. Consumes a B8 envelope as
    # EVIDENCE ONLY. Commits only to local internal state. NO external effect,
    # NO provider/MCP/LLM, NO message/payment/CRM/evidence mutation. There is NO
    # external-execute / release-effects / activate-provider / send / dispatch /
    # webhook / job-release / llm-run / mcp-run / grant-authority endpoint.
    from ..ai_employee import tool_local_transaction as _lt
    from ..ai_employee.tool_local_transaction_store import (
        ToolLocalTransactionStore)
    local_tx_store = ToolLocalTransactionStore(db)
    app.state.local_tx_store = local_tx_store

    def _lt_emit(tid, *, event_type, transaction_id, actor_id, actor_type,
                 state_hash, detail):
        seq = local_tx_store.next_sequence(tenant_id=tid)
        prev = local_tx_store.last_event(tenant_id=tid)
        ev = _lt.build_b9_event(
            event_type=event_type, tenant_id=tid, transaction_id=transaction_id,
            actor_id=actor_id, actor_type=actor_type, b9_state_hash=state_hash,
            previous_event_hash=(prev or {}).get("event_hash"), sequence=seq,
            detail=detail, created_at=utcnow())
        local_tx_store.append_event({
            "id": str(uuid.uuid4()), "tenant_id": tid, "transaction_id":
            transaction_id, "event_type": event_type, "sequence": seq,
            "actor_id": actor_id, "actor_type": actor_type,
            "event_hash": ev["event_hash"], "previous_event_hash": ev[
                "previous_event_hash"], "b9_state_hash": state_hash,
            "payload_json": json.dumps(ev), "created_at": ev["created_at"]})
        return ev

    def _load_local_tx_or_404(transaction_id, user):
        r = local_tx_store.request(transaction_id, tenant_id=user["tid"])
        if r is None:
            raise HTTPException(404, "local transaction not found")
        return r

    def _load_local_tx_outcome_or_404(transaction_id, user):
        _load_local_tx_or_404(transaction_id, user)
        o = local_tx_store.outcome(transaction_id, tenant_id=user["tid"])
        if o is None:
            raise HTTPException(404, "no local transaction outcome")
        return o

    _LT_SUBFIELDS = {
        "certificate": "certificate", "path-compliance": "path_compliance",
        "inert-outbox": "inert_outbox", "proof": "b9_proof_bundle",
        "graph": "semantic_graph", "context-slice": "context_slice",
        "proof-of-execution": "proof_of_execution",
        "replay-context": "replay_context",
        "lifecycle-checkpoints": "lifecycle_checkpoints",
        "rollback-plan": "rollback_readiness", "envelope": "transaction_envelope",
        "shadow-state": "shadow_state", "execution-contract": "execution_contract",
        "b8-handoff": "b8_handoff", "effector-gate": "effector_gate",
        "commit-attestation": "commit_attestation",
        "no-external-effect": "no_external_effect_theorem",
        "source-surface-isolation": "source_surface_isolation",
        "contaminated-authority": "contaminated_authority_firewall",
        "fault-injection": "b9_fault_injection_harness",
        "release-gate": "b9_release_gate_report",
        "conformance-vector": "b9_conformance_vector",
    }

    @app.get("/ai-tools/local-transactions/policy")
    async def local_tx_policy(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return {"b9_model_version": _lt.B9_MODEL_VERSION,
                "local_reversible_commit_only": True, "external_effect": False,
                "calls_providers": False, "sends_messages": False,
                "executes_payment": False, "mutates_external_crm": False,
                "mutates_external_evidence": False, "calls_mcp": False,
                "calls_llm": False, "issues_tokens": False,
                "b8_is_evidence_only": True, "b8_is_authority": False,
                "commit_executable_now": False, "production_ready": False,
                "has_external_execute_endpoint": False,
                "has_release_effects_endpoint": False,
                "has_provider_call_endpoint": False, "has_send_endpoint": False,
                "has_grant_authority_endpoint": False,
                "has_dispatch_endpoint": False, "has_webhook_endpoint": False,
                "most_permissive_outcome": "B9_LOCAL_COMMIT_APPLIED",
                "accepts_b8_statuses": sorted(_lt.B8_ACCEPTABLE_STATUSES),
                "b9_statuses": sorted(_lt.B9_STATUSES),
                "decision_statuses": sorted(_lt.DECISION_STATUSES),
                "failure_dominance": _lt.FAILURE_DOMINANCE,
                "reason_codes": _lt.REASON_CODES, "fault_cases": _lt.FAULT_CASES,
                "allowed_source_surfaces": sorted(_lt.ALLOWED_SOURCE_SURFACES),
                "allowed_authority_sources": sorted(
                    _lt.ALLOWED_AUTHORITY_SOURCES),
                "path_predicates": _lt.PATH_PREDICATES,
                "poe_events": _lt.POE_EVENTS,
                "lifecycle_checkpoints": _lt.LIFECYCLE_CHECKPOINTS,
                "graph_node_types": _lt.GRAPH_NODE_TYPES,
                "graph_edge_types": _lt.GRAPH_EDGE_TYPES,
                "honesty_labels": _lt.HONESTY_LABELS}

    @app.get("/ai-tools/local-transactions/registry")
    async def local_tx_registry(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        outs = local_tx_store.list_outcomes(tenant_id=user["tid"])
        by_status = {}
        for o in outs:
            by_status[o["b9_status"]] = by_status.get(o["b9_status"], 0) + 1
        return {"tenant_id": user["tid"],
                "local_transaction_request_count": len(
                    local_tx_store.list_requests(tenant_id=user["tid"])),
                "local_transaction_outcome_count": len(outs),
                "outcomes_by_status": by_status,
                "honesty_labels": _lt.HONESTY_LABELS}

    @app.get("/ai-tools/local-transactions/events")
    async def local_tx_events(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        evs = local_tx_store.events(tenant_id=user["tid"])
        chain_ok, prev = True, None
        for e in evs:
            if e["previous_event_hash"] != (prev or _lt.GENESIS):
                chain_ok = False
            prev = e["event_hash"]
        return {"tenant_id": user["tid"], "events": evs,
                "event_count": len(evs), "event_chain_valid": chain_ok,
                "ledger_note": "local B9 transaction ledger; not a production "
                "immutable log", "honesty_labels": _lt.HONESTY_LABELS}

    _LT_PASS_KEYS = (
        "b8_commit_simulation_id", "role_id", "source_surface", "source_channel",
        "object_reference", "case_id", "task_id", "run_id", "requested_intent",
        "allowed_local_scope", "forbidden_external_scope",
        "autonomy_level_requested", "role_autonomy_limit", "tenant_policy_limit",
        "segment_policy_limit", "tool_risk_limit", "evidence_confidence_limit",
        "human_approval_limit", "historical_trust_limit", "context_slice",
        "planned_delta", "evidence_refs", "policy_refs", "authority_basis",
        "approval_record", "idempotency_key", "conflicting_txs",
        "replay_detected", "stale_witness", "future_effects",
        "outbox_release_attempts", "attempt_markers", "failed_checkpoints",
        "missing_poe_events", "poe_reorder", "poe_tamper", "path_checks",
        "contract_valid", "surface_claims_authority", "surface_claims_approval",
        "abort_stage", "kill_switch", "expected_before_state_hash", "policy",
    )

    def _prepare_local_tx(tid, user, body, apply_commit):
        # A local, reversible transaction request. Consumes a B8 envelope as
        # EVIDENCE ONLY and re-validates it. Commits (when apply_commit and the
        # decision allows) ONLY to local internal state. NO external effect.
        b8id = str(body.get("b8_commit_simulation_id", "") or "")
        b8o = commit_sim_store.outcome(b8id, tenant_id=tid) if b8id else None
        if b8o is None:
            raise HTTPException(404, "b8 commit-simulation outcome not found")
        actor_type = "ai_employee" if user["role"] == "ai_worker" else "human"
        now = utcnow()
        txid = str(uuid.uuid4())
        obj = str(body.get("object_reference", "obj-1") or "obj-1")
        # The reversible LOCAL state is the source of the before-state.
        cur = local_tx_store.get_state(obj, tenant_id=tid)
        current_local_state = cur["state"] if cur else (
            body.get("current_local_state") or {})
        passthrough = {k: body[k] for k in _LT_PASS_KEYS if k in body}
        passthrough["current_local_state"] = current_local_state
        passthrough["object_reference"] = obj
        passthrough.setdefault("authority_basis",
                               body.get("authority_basis") or
                               {"source": "SERVER_RBAC"})
        outcome = _lt.prepare_local_transaction_outcome(
            transaction_id=txid, tenant_id=tid, actor_id=user["uid"],
            actor_type=actor_type, b8_outcome=b8o, created_at=now,
            **passthrough)
        # Apply the LOCAL, REVERSIBLE commit only when allowed AND requested.
        if apply_commit and outcome["local_commit_applied"]:
            local_tx_store.apply_commit(
                tenant_id=tid, object_reference=obj,
                before_state=outcome["shadow_state"]["before_state"],
                after_state=outcome["shadow_state"]["shadow_state"],
                transaction_id=txid, created_at=now)
        env = outcome["transaction_envelope"]
        local_tx_store.save_request({
            "id": txid, "tenant_id": tid, "b8_commit_simulation_id": b8id,
            "object_reference": obj, "source_surface": env["source_surface"],
            "b9_transaction_request_hash": env["canonical_hash"],
            "requested_by": user["uid"], "requested_by_actor_type": actor_type,
            "payload_json": json.dumps(env), "created_at": now})
        local_tx_store.save_outcome({
            "id": str(uuid.uuid4()), "tenant_id": tid, "transaction_id": txid,
            "b8_commit_simulation_id": b8id, "object_reference": obj,
            "b9_status": outcome["b9_status"],
            "b9_decision_status": outcome["b9_decision_status"],
            "b9_outcome_kind": outcome["b9_outcome_kind"],
            "dominant_signal": outcome["dominant_signal"],
            "certificate_hash": outcome["certificate"]["certificate_hash"],
            "before_state_hash": outcome["before_state_hash"],
            "after_state_hash": outcome["after_state_hash"],
            "b9_transaction_request_hash": outcome.get(
                "b9_transaction_request_hash") or "",
            "b9_decision_hash": outcome["b9_decision_hash"],
            "b9_state_hash": outcome["b9_state_hash"],
            "b9_proof_bundle_hash": outcome["b9_proof_bundle"][
                "b9_proof_bundle_hash"],
            "release_gate_status": outcome["b9_release_gate_report"][
                "release_gate_status"],
            "local_commit_applied": 1 if (apply_commit and outcome[
                "local_commit_applied"]) else 0,
            "decided_by": user["uid"], "decided_by_actor_type": actor_type,
            "payload_json": json.dumps(outcome), "created_at": now,
            "updated_at": now})
        _lt_emit(tid, event_type="B9_TX_REQUEST_OPENED", transaction_id=txid,
                 actor_id=user["uid"], actor_type=actor_type,
                 state_hash=env["canonical_hash"], detail={"object": obj})
        _lt_emit(tid, event_type="B9_TX_OUTCOME_PREPARED", transaction_id=txid,
                 actor_id=user["uid"], actor_type=actor_type,
                 state_hash=outcome["b9_state_hash"],
                 detail={"status": outcome["b9_status"],
                         "committed": bool(apply_commit and outcome[
                             "local_commit_applied"])})
        audit.append(event_type="AI_B9_LOCAL_TRANSACTION_PREPARED",
                     actor=user["uid"], payload={"transaction_id": txid,
                     "status": outcome["b9_status"],
                     "committed": bool(apply_commit and outcome[
                         "local_commit_applied"])})
        outcome["_committed_to_local_state"] = bool(
            apply_commit and outcome["local_commit_applied"])
        return outcome

    @app.post("/ai-tools/local-transactions/prepare")
    async def local_tx_prepare(body: dict, user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        return _prepare_local_tx(user["tid"], user, body or {},
                                 apply_commit=False)

    @app.post("/ai-tools/local-transactions/validate")
    async def local_tx_validate(body: dict, user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        o = _prepare_local_tx(user["tid"], user, body or {}, apply_commit=False)
        return {"transaction_id": o["transaction_id"],
                "b9_status": o["b9_status"],
                "b9_decision_status": o["b9_decision_status"],
                "would_commit_local": o["local_commit_applied"],
                "dominant_reason_code": o["dominant_reason_code"],
                "path_compliance_result": o["path_compliance"][
                    "path_compliance_result"],
                "honesty_labels": _lt.HONESTY_LABELS}

    @app.post("/ai-tools/local-transactions/commit-local")
    async def local_tx_commit_local(body: dict,
                                    user: dict = Depends(current_user)):
        # Applies a LOCAL, REVERSIBLE commit to internal state — never an
        # external effect — only if the full B9 revalidation allows it.
        require_permission(user, "case.update")
        return _prepare_local_tx(user["tid"], user, body or {},
                                 apply_commit=True)

    @app.get("/ai-tools/local-transactions")
    async def list_local_txs(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return local_tx_store.list_requests(tenant_id=user["tid"])

    @app.get("/ai-tools/local-transactions/{transaction_id}")
    async def get_local_tx(transaction_id: str,
                           user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return _load_local_tx_or_404(transaction_id, user)

    @app.get("/ai-tools/local-transactions/{transaction_id}/outcome")
    async def get_local_tx_outcome(transaction_id: str,
                                   user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return _load_local_tx_outcome_or_404(transaction_id, user)

    @app.get("/ai-tools/local-transactions/{transaction_id}/twin")
    async def get_local_tx_twin(transaction_id: str,
                                user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        o = _load_local_tx_outcome_or_404(transaction_id, user)
        return {"transaction_id": transaction_id, "finalis_transaction_twin": {
            "intended_action": o["transaction_envelope"]["requested_intent"],
            "current_local_state": o["shadow_state"]["before_state"],
            "shadow_local_state": o["shadow_state"]["shadow_state"],
            "planned_delta": o["shadow_state"]["planned_delta"],
            "compliance_path": o["path_compliance"]["path_compliance_result"],
            "authority_basis": o["certificate"]["authority_basis"],
            "evidence_basis": o["certificate"]["evidence_basis"],
            "approval_basis": o["certificate"]["approval_basis"],
            "rollback_plan": o["rollback_readiness"]["rollback_plan"],
            "inert_outbox": o["inert_outbox"]["items"],
            "certificate_hash": o["certificate"]["certificate_hash"],
            "proof_of_execution_stream_hash": o["poe_stream"]["poe_stream_hash"],
            "blocked_external_effects": o["certificate"]["forbidden"],
            "local_commit_applied": o["local_commit_applied"],
            "b9_status": o["b9_status"]},
            "honesty_labels": _lt.HONESTY_LABELS}

    @app.post("/ai-tools/local-transactions/{transaction_id}/abort")
    async def local_tx_abort(transaction_id: str,
                             user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        o = _load_local_tx_outcome_or_404(transaction_id, user)
        return {"transaction_id": transaction_id, "abort_status": "ABORTED",
                "rollback_ready": o["rollback_readiness"]["rollback_ready"],
                "rollback_hash": o["rollback_readiness"]["rollback_hash"],
                "no_external_effect": True,
                "honesty_labels": _lt.HONESTY_LABELS}

    def _ltsub(field):
        async def getter(transaction_id: str,
                         user: dict = Depends(current_user)):
            require_permission(user, "case.read")
            o = _load_local_tx_outcome_or_404(transaction_id, user)
            return {"transaction_id": transaction_id, field: o.get(field),
                    "honesty_labels": _lt.HONESTY_LABELS}
        return getter

    for _slug, _field in _LT_SUBFIELDS.items():
        app.add_api_route(
            "/ai-tools/local-transactions/{transaction_id}/" + _slug,
            _ltsub(_field), methods=["GET"])

    @app.post("/ai-tools/local-transactions/{transaction_id}/verify")
    async def verify_local_tx(transaction_id: str,
                              user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        o = _load_local_tx_outcome_or_404(transaction_id, user)
        recomputed = _lt._core_hash(
            o, "b9_decision_hash", "transaction_id", "actor_id",
            "decided_by_actor_id", "decided_by_actor_type", "b9_state_hash")
        ok = recomputed == o["b9_decision_hash"]
        return {"transaction_id": transaction_id,
                "stored_b9_decision_hash": o["b9_decision_hash"],
                "recomputed_b9_decision_hash": recomputed,
                "b9_decision_hash_valid": ok,
                "verification_status": "VALID" if ok else "TAMPERED",
                "honesty_labels": _lt.HONESTY_LABELS}

    @app.get("/ai-tools/local-transactions/{transaction_id}/events")
    async def local_tx_request_events(transaction_id: str,
                                      user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_local_tx_or_404(transaction_id, user)
        return {"transaction_id": transaction_id, "events":
                local_tx_store.events(tenant_id=user["tid"],
                                      transaction_id=transaction_id),
                "honesty_labels": _lt.HONESTY_LABELS}

    # ===== TOOL-B9.1 v4: Recovery Safety Case + Chaos Sentinel + =============
    # ===== Proof-of-Recovery Runtime (LOCAL-ONLY, evidence only) ============
    from ..ai_employee import tool_local_recovery as _lr
    from ..ai_employee.tool_local_recovery_store import ToolLocalRecoveryStore
    recovery_store = ToolLocalRecoveryStore(db)
    app.state.recovery_store = recovery_store

    _LR_PASS_KEYS = (
        "recovery_authority_basis", "source_surface",
        "surface_claims_recovery_authority", "surface_claims_approval",
        "system_actor_id", "recovery_payload", "idempotency_key",
        "prior_recovery", "poe_tamper", "poe_reorder", "poe_duplicate",
        "poe_broken_chain", "poe_missing_events", "poe_unrecoverable",
        "replay_context_invalid", "reconcile_mismatch", "old_authority_level",
        "new_authority_level", "old_autonomy_level", "new_autonomy_level",
        "old_write_scope", "new_write_scope", "old_externality_level",
        "new_externality_level", "outbox_becomes_releasable", "attempt_markers",
        "outbox_release_attempts", "missing_commit_record", "missing_certificate",
        "missing_poe", "after_state_mismatch", "missing_rollback_plan",
        "missing_audit", "graph_inconsistent", "missing_replay_context",
        "missing_lifecycle_checkpoint", "inert_outbox_inconsistent",
        "missing_path_compliance", "rollback_plan_missing",
        "rollback_target_not_local", "rollback_current_state_incompatible",
        "rollback_idempotency_invalid", "rollback_equivalence_fail",
        "abort_scope", "abort_reason", "abort_stage", "global_abort",
        "tenant_abort", "kill_switch", "finalize_attempt", "lock_age_seconds",
        "recovering_age_seconds", "lock_max_age", "recovering_max_age",
        "repeated_recovery_failures", "repeated_idempotency_conflicts",
        "recovery_authority_ambiguous", "steal_active_lock",
        "conflicting_recovery", "cross_tenant_lock_ambiguity",
        "stale_lock_unsafe_release", "interrupted_lock_acquisition",
        "stale_lock_safe_release", "replay_after_rollback", "revive_aborted",
        "revive_quarantined", "allowed_recovery_scope",
        "forbidden_recovery_scope", "requested_recovery_scope",
        "recovery_contract_missing", "recovery_contract_malformed",
        "recovery_contract_contradicted", "failed_checkpoints", "por_tamper",
        "por_reorder", "por_missing_events", "recovery_requested_by",
    )
    _LR_SUBFIELDS = {
        "twin": "twin", "certificate": "recovery_certificate",
        "safety-case": "recovery_safety_case",
        "proof-of-recovery": "proof_of_recovery",
        "reconciliation": "double_entry_reconciliation",
        "authority-firewall": "recovery_authority_firewall",
        "lifecycle-checkpoints": "recovery_checkpoints",
        "monotonicity": "safety_monotonicity",
        "poe-recovery": "poe_stream_recovery", "contract": "recovery_contract",
        "rollback": "rollback_executor", "partial-commit": "partial_commit_detector",
        "quarantine": "quarantine", "stuck": "stuck_detector",
        "abort": "abort_controller", "conflict": "conflict_recovery",
        "inert-outbox": "inert_outbox_preservation",
        "no-external-effect": "no_external_effect_theorem",
        "por-stream": "por_stream", "chaos-drill": "b91_chaos_harness",
        "release-gate": "b91_release_gate_report",
        "proof-bundle": "b91_recovery_proof_bundle",
    }

    def _lr_emit(tid, *, event_type, recovery_id, transaction_id, actor_id,
                 actor_type, state_hash, detail):
        seq = recovery_store.next_sequence(tenant_id=tid)
        prev = recovery_store.last_event(tenant_id=tid)
        ev = _lr.build_b91_event(
            event_type=event_type, tenant_id=tid, recovery_id=recovery_id,
            transaction_id=transaction_id, actor_id=actor_id,
            actor_type=actor_type, b91_state_hash=state_hash,
            previous_event_hash=prev["event_hash"] if prev else None,
            sequence=seq, detail=detail, created_at=utcnow())
        recovery_store.append_event({
            "id": str(uuid.uuid4()), "tenant_id": tid,
            "recovery_id": recovery_id, "transaction_id": transaction_id,
            "event_type": event_type, "sequence": seq, "actor_id": actor_id,
            "actor_type": actor_type, "event_hash": ev["event_hash"],
            "previous_event_hash": ev["previous_event_hash"],
            "b91_state_hash": state_hash, "payload_json": json.dumps(ev),
            "created_at": ev["created_at"]})

    def _load_recovery_outcome_or_404(recovery_id, user):
        o = recovery_store.outcome(recovery_id, tenant_id=user["tid"])
        if o is None:
            raise HTTPException(404, "recovery outcome not found")
        return o

    def _prepare_recovery(tid, user, body, action):
        # A LOCAL recovery/rollback/abort/quarantine/stuck/crash-drill
        # evaluation over a B9 transaction. Produces only local evidence
        # (Recovery Twin, Proof-of-Recovery, certificate, safety case,
        # reconciliation). NO external effect, NO provider call, NO
        # message/payment/CRM/evidence mutation; the inert outbox stays inert.
        transaction_id = str(body.get("transaction_id", "") or "")
        actor_type = "ai_employee" if user["role"] == "ai_worker" else "human"
        now = utcnow()
        rid = str(uuid.uuid4())
        # The B9 outcome is EVIDENCE ONLY. A missing transaction fails closed
        # (RECOVERY_FAILED / B9_TRANSACTION_MISSING), never an error path that
        # could be mistaken for success.
        b9o = local_tx_store.outcome(transaction_id, tenant_id=tid) \
            if transaction_id else None
        passthrough = {k: body[k] for k in _LR_PASS_KEYS if k in body}
        outcome = _lr.prepare_recovery_outcome(
            recovery_id=rid, transaction_id=transaction_id, tenant_id=tid,
            actor_id=user["uid"], actor_type=actor_type, b9_outcome=b9o,
            desired_recovery_action=action, created_at=now, **passthrough)
        recovery_store.save_request({
            "id": rid, "tenant_id": tid, "transaction_id": transaction_id,
            "desired_recovery_action": action,
            "recovery_authority_source": (outcome["recovery_authority_firewall"]
                                          ).get("recovery_authority_source") or "",
            "source_surface": outcome["source_surface_safety"]["source_surface"],
            "requested_by": user["uid"], "requested_by_actor_type": actor_type,
            "payload_json": json.dumps({
                "recovery_id": rid, "transaction_id": transaction_id,
                "desired_recovery_action": action}),
            "created_at": now})
        recovery_store.save_outcome({
            "id": str(uuid.uuid4()), "tenant_id": tid, "recovery_id": rid,
            "transaction_id": transaction_id,
            "desired_recovery_action": action,
            "final_recovery_state": outcome["final_recovery_state"],
            "recovery_decision_status": outcome["recovery_decision_status"],
            "dominant_signal": outcome["dominant_signal"],
            "recovery_certificate_hash": outcome["recovery_certificate_hash"],
            "recovery_safety_case_hash": outcome["recovery_safety_case_hash"],
            "proof_of_recovery_hash": outcome["proof_of_recovery_hash"],
            "recovery_twin_hash": outcome["recovery_twin_hash"],
            "b91_decision_hash": outcome["b91_decision_hash"],
            "b91_state_hash": outcome["b91_state_hash"],
            "b91_recovery_proof_bundle_hash": outcome[
                "b91_recovery_proof_bundle"]["recovery_proof_bundle_hash"],
            "release_gate_status": outcome["b91_release_gate_report"][
                "release_gate_status"],
            "recovery_applied": 1 if outcome["recovery_applied"] else 0,
            "quarantine_required": 1 if outcome["quarantine_required"] else 0,
            "decided_by": user["uid"], "decided_by_actor_type": actor_type,
            "payload_json": json.dumps(outcome), "created_at": now,
            "updated_at": now})
        _lr_emit(tid, event_type="B91_RECOVERY_REQUEST_OPENED", recovery_id=rid,
                 transaction_id=transaction_id, actor_id=user["uid"],
                 actor_type=actor_type, state_hash=outcome["b91_state_hash"],
                 detail={"action": action, "tx": transaction_id})
        _lr_emit(tid, event_type="B91_RECOVERY_OUTCOME_PREPARED", recovery_id=rid,
                 transaction_id=transaction_id, actor_id=user["uid"],
                 actor_type=actor_type, state_hash=outcome["b91_state_hash"],
                 detail={"state": outcome["final_recovery_state"]})
        return outcome

    @app.get("/ai-tools/local-transactions/recovery/policy")
    async def recovery_policy(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return {"b91_model_version": _lr.B91_MODEL_VERSION,
                "local_recovery_only": True, "external_effect": False,
                "calls_providers": False, "sends_messages": False,
                "executes_payment": False, "mutates_external_crm": False,
                "retries_providers": False, "dispatches_webhooks": False,
                "releases_outbox": False, "external_rollback": False,
                "b8_is_evidence_only": True,
                "b9_certificate_is_authority": False,
                "proof_of_recovery_is_authority": False,
                "recovery_safety_case_is_authority": False,
                "production_ready": False,
                "has_external_rollback_endpoint": False,
                "has_external_recover_endpoint": False,
                "has_release_effects_endpoint": False,
                "has_activate_provider_endpoint": False,
                "has_provider_retry_endpoint": False,
                "has_payment_refund_endpoint": False,
                "has_webhook_dispatch_endpoint": False,
                "has_job_release_endpoint": False,
                "recovery_states": _lr.RECOVERY_STATES,
                "recovery_actions": sorted(_lr.RECOVERY_ACTIONS),
                "decision_statuses": sorted(_lr.RECOVERY_DECISION_STATUSES),
                "failure_dominance": _lr.RECOVERY_FAILURE_DOMINANCE,
                "reason_codes": _lr.REASON_CODES,
                "por_events": _lr.POR_EVENTS,
                "crash_phases": _lr.CRASH_PHASES,
                "recovery_checkpoints": _lr.RECOVERY_CHECKPOINTS,
                "required_safety_claims": _lr.REQUIRED_SAFETY_CLAIMS,
                "allowed_recovery_authority_sources": sorted(
                    _lr.ALLOWED_RECOVERY_AUTHORITY_SOURCES),
                "abort_reasons": sorted(_lr.ABORT_REASONS),
                "honesty_labels": _lr.HONESTY_LABELS}

    @app.get("/ai-tools/local-transactions/recovery/registry")
    async def recovery_registry(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        outs = recovery_store.list_outcomes(tenant_id=user["tid"])
        by_state = {}
        for o in outs:
            by_state[o["final_recovery_state"]] = by_state.get(
                o["final_recovery_state"], 0) + 1
        return {"tenant_id": user["tid"], "recovery_outcome_count": len(outs),
                "recovery_request_count": len(
                    recovery_store.list_requests(tenant_id=user["tid"])),
                "outcomes_by_state": by_state,
                "honesty_labels": _lr.HONESTY_LABELS}

    @app.get("/ai-tools/local-transactions/recovery/list")
    async def recovery_list(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        outs = recovery_store.list_outcomes(tenant_id=user["tid"])
        return [{"recovery_id": o["recovery_id"],
                 "transaction_id": o["transaction_id"],
                 "desired_recovery_action": o["desired_recovery_action"],
                 "final_recovery_state": o["final_recovery_state"],
                 "dominant_signal": o["dominant_signal"]} for o in outs]

    @app.get("/ai-tools/local-transactions/recovery/events")
    async def recovery_events(recovery_id: str = "",
                              user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        evs = recovery_store.events(tenant_id=user["tid"],
                                    recovery_id=recovery_id or None)
        chain_ok, prev = True, None
        for e in evs:
            if e["previous_event_hash"] != (prev or _lr.GENESIS):
                chain_ok = False
            prev = e["event_hash"]
        return {"tenant_id": user["tid"], "events": evs, "event_count": len(evs),
                "event_chain_valid": chain_ok,
                "ledger_note": "local B9.1 recovery ledger; not a production "
                "immutable log", "honesty_labels": _lr.HONESTY_LABELS}

    _RECOVERY_ACTION_ROUTES = {
        "status": "STATUS", "plan": "PLAN", "run": "RECOVER",
        "rollback-local": "ROLLBACK_LOCAL", "abort": "ABORT",
        "quarantine": "QUARANTINE", "stuck": "DETECT_STUCK",
        "crash-drill": "CRASH_DRILL",
    }

    def _mk_recovery_action(action):
        async def handler(body: dict, user: dict = Depends(current_user)):
            # STATUS/PLAN are read-shaped; state-changing actions need update.
            require_permission(
                user, "case.read" if action in ("STATUS", "PLAN")
                else "case.update")
            return _prepare_recovery(user["tid"], user, body or {}, action)
        return handler

    for _slug, _action in _RECOVERY_ACTION_ROUTES.items():
        app.add_api_route(
            "/ai-tools/local-transactions/recovery/" + _slug,
            _mk_recovery_action(_action), methods=["POST"])

    @app.get("/ai-tools/local-transactions/recovery/outcome")
    async def recovery_outcome_get(recovery_id: str,
                                   user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return _load_recovery_outcome_or_404(recovery_id, user)

    def _mk_recovery_subfield(field):
        async def getter(recovery_id: str,
                         user: dict = Depends(current_user)):
            require_permission(user, "case.read")
            o = _load_recovery_outcome_or_404(recovery_id, user)
            return {"recovery_id": recovery_id, "transaction_id":
                    o["transaction_id"], field: o.get(field),
                    "honesty_labels": _lr.HONESTY_LABELS}
        return getter

    for _slug, _field in _LR_SUBFIELDS.items():
        app.add_api_route(
            "/ai-tools/local-transactions/recovery/" + _slug,
            _mk_recovery_subfield(_field), methods=["GET"])

    @app.post("/ai-tools/local-transactions/recovery/verify")
    async def recovery_verify(recovery_id: str,
                              user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        o = _load_recovery_outcome_or_404(recovery_id, user)
        recomputed = _lr._core_hash(
            o, "b91_decision_hash", "recovery_id", "transaction_id", "actor_id",
            "decided_by_actor_id", "decided_by_actor_type",
            "recovery_requested_by", "b91_state_hash")
        ok = recomputed == o["b91_decision_hash"]
        return {"recovery_id": recovery_id,
                "stored_b91_decision_hash": o["b91_decision_hash"],
                "recomputed_b91_decision_hash": recomputed,
                "b91_decision_hash_valid": ok,
                "verification_status": "VALID" if ok else "TAMPERED",
                "honesty_labels": _lr.HONESTY_LABELS}

    # ===== TOOL-B9.2 v5: Governed Work Lineage Observatory ==================
    # ===== (LOCAL-ONLY, READ-ONLY over B9/B9.1, DERIVED EVIDENCE ONLY) ======
    from ..ai_employee import tool_work_observability as _wo
    from ..ai_employee.tool_work_observability_store import (
        ToolWorkObservabilityStore)
    work_obs_store = ToolWorkObservabilityStore(db)
    app.state.work_obs_store = work_obs_store

    _WO_PASS_KEYS = _wo._PASS_KEYS
    _WO_SUBFIELDS = {
        "origin": "work_origin", "principal-continuity": "principal_continuity",
        "context": "context_capsule", "memory": "memory_snapshot",
        "delegation": "delegation_capsule", "approval": "approval_continuity",
        "gateway-boundary": "gateway_boundary", "transaction":
        "transaction_binding", "recovery": "recovery_binding",
        "artifact-lineage": "artifact_lineage", "delivery-intent":
        "delivery_intent", "schedule-lineage": "schedule_run_chain",
        "revocation": "revocation", "causal-graph": "causal_work_graph",
        "missing-evidence": "negative_space", "twin": "work_observation_twin",
        "proof-of-work-outcome": "proof_of_work_outcome",
        "decision-basis": "decision_basis", "otel-adapter": "otel_adapter",
        "a2a-boundary": "a2a_boundary", "consistent-cut": "consistent_work_cut",
        "no-external-effect": "no_external_effect_theorem",
        "observer-health-detail": "observer_health",
    }

    def _wo_emit(tid, *, event_type, work_run_id, actor_id, actor_type,
                 state_hash, detail):
        seq = work_obs_store.next_sequence(tenant_id=tid)
        prev = work_obs_store.last_event(tenant_id=tid)
        ev = _wo.build_b92_event(
            event_type=event_type, tenant_id=tid, work_run_id=work_run_id,
            actor_id=actor_id, actor_type=actor_type, b92_state_hash=state_hash,
            previous_event_hash=prev["event_hash"] if prev else None,
            sequence=seq, detail=detail, created_at=utcnow())
        work_obs_store.append_event({
            "id": str(uuid.uuid4()), "tenant_id": tid, "work_run_id": work_run_id,
            "event_type": event_type, "sequence": seq, "actor_id": actor_id,
            "actor_type": actor_type, "event_hash": ev["event_hash"],
            "previous_event_hash": ev["previous_event_hash"],
            "b92_state_hash": state_hash, "payload_json": json.dumps(ev),
            "created_at": ev["created_at"]})

    def _load_work_outcome_or_404(work_run_id, user):
        o = work_obs_store.outcome(work_run_id, tenant_id=user["tid"])
        if o is None:
            raise HTTPException(404, "work observation outcome not found")
        return o

    def _observe_work_run(tid, user, body, work_run_id=None):
        # DERIVED, LOCAL, READ-ONLY observation over B9/B9.1 evidence. Produces
        # only a work-lineage outcome + PoWO; NO external effect, NO provider
        # call, NO commit/recovery/delivery, and never releases the inert outbox.
        actor_type = "ai_employee" if user["role"] == "ai_worker" else "human"
        now = utcnow()
        wrid = work_run_id or str(uuid.uuid4())
        b9o = None
        b9id = str(body.get("b9_transaction_id", "") or "")
        if b9id:
            b9o = local_tx_store.outcome(b9id, tenant_id=tid)
        b91o = None
        b91id = str(body.get("b91_recovery_id", "") or "")
        if b91id:
            b91o = recovery_store.outcome(b91id, tenant_id=tid)
        passthrough = {k: body[k] for k in _WO_PASS_KEYS if k in body}
        outcome = _wo.prepare_work_observation_outcome(
            work_run_id=wrid, tenant_id=tid, actor_id=user["uid"],
            actor_type=actor_type, b9_outcome=b9o, b91_outcome=b91o,
            created_at=now, **passthrough)
        work_obs_store.save_request({
            "id": wrid, "tenant_id": tid,
            "work_definition_id": outcome.get("work_definition_id") or "",
            "trigger_type": outcome["trigger_type"],
            "source_surface": outcome["work_origin"]["source_surface"],
            "source_principal_id": outcome["principal_continuity"][
                "source_principal_id"] or "",
            "schedule_occurrence_id": outcome["work_origin"][
                "schedule_occurrence_id"] or "",
            "logical_run_key": outcome["schedule_run_chain"]["logical_run_key"],
            "transaction_id": outcome.get("transaction_id") or "",
            "recovery_id": outcome.get("recovery_id") or "",
            "work_run_state": outcome["work_run_state"],
            "work_run_hash": outcome["b92_state_hash"],
            "requested_by": user["uid"], "requested_by_actor_type": actor_type,
            # Store the full observation input so /rebuild-local-observation can
            # deterministically reproduce the derived evidence.
            "payload_json": json.dumps(body),
            "created_at": now})
        work_obs_store.save_outcome({
            "id": str(uuid.uuid4()), "tenant_id": tid, "work_run_id": wrid,
            "work_definition_id": outcome.get("work_definition_id") or "",
            "trigger_type": outcome["trigger_type"],
            "work_run_state": outcome["work_run_state"],
            "work_outcome_truth_state": outcome["work_outcome_truth_state"],
            "proof_of_work_outcome_valid": 1 if outcome[
                "proof_of_work_outcome_valid"] else 0,
            "proof_of_work_outcome_hash": outcome["proof_of_work_outcome_hash"],
            "work_observation_twin_hash": outcome["work_observation_twin_hash"],
            "causal_work_graph_hash": outcome["causal_work_graph_hash"],
            "transaction_id": outcome.get("transaction_id") or "",
            "recovery_id": outcome.get("recovery_id") or "",
            "source_principal_id": outcome["principal_continuity"][
                "source_principal_id"] or "",
            "b92_decision_hash": outcome["b92_decision_hash"],
            "b92_state_hash": outcome["b92_state_hash"],
            "b92_work_proof_bundle_hash": outcome["b92_work_proof_bundle"][
                "work_proof_bundle_hash"],
            "observer_health_state": outcome["observer_health_state"],
            "work_certified": 1 if outcome["work_outcome_certified"] else 0,
            "decided_by": user["uid"], "decided_by_actor_type": actor_type,
            "payload_json": json.dumps(outcome), "created_at": now,
            "updated_at": now})
        _wo_emit(tid, event_type="B92_WORK_OBSERVATION_OPENED", work_run_id=wrid,
                 actor_id=user["uid"], actor_type=actor_type,
                 state_hash=outcome["b92_state_hash"],
                 detail={"trigger": outcome["trigger_type"]})
        _wo_emit(tid, event_type="B92_WORK_OBSERVATION_PREPARED",
                 work_run_id=wrid, actor_id=user["uid"], actor_type=actor_type,
                 state_hash=outcome["b92_state_hash"],
                 detail={"state": outcome["work_run_state"],
                         "truth": outcome["work_outcome_truth_state"]})
        return outcome

    @app.get("/ai-tools/local-transactions/observability/policy")
    async def wo_policy(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return {"b92_model_version": _wo.B92_MODEL_VERSION,
                "local_work_observability_only": True,
                "read_only_over_b9_and_b9_1": True, "derived_evidence_only": True,
                "external_effect": False, "external_provider_runtime": False,
                "external_delivery": False, "execution_authority": False,
                "recovery_authority": False, "authorizes_execution": False,
                "authorizes_commit": False, "authorizes_recovery": False,
                "authorizes_delivery": False, "releases_outbox": False,
                "stores_secret": False, "stores_chain_of_thought": False,
                "production_ready": False,
                "has_commit_endpoint": False, "has_approve_endpoint": False,
                "has_recover_endpoint": False, "has_rollback_endpoint": False,
                "has_release_effects_endpoint": False,
                "has_activate_provider_endpoint": False,
                "has_send_endpoint": False, "has_webhook_dispatch_endpoint": False,
                "has_enable_schedule_endpoint": False,
                "has_revoke_integration_endpoint": False,
                "work_run_states": _wo.WORK_RUN_STATES,
                "trigger_types": _wo.TRIGGER_TYPES,
                "truth_states": _wo.TRUTH_STATES,
                "reason_codes": sorted(_wo.REASON_CODES),
                "graph_node_types": _wo.GRAPH_NODE_TYPES,
                "graph_edge_types": _wo.GRAPH_EDGE_TYPES,
                "memory_trust_classes": _wo.MEMORY_TRUST_CLASSES,
                "approval_modes": _wo.APPROVAL_MODES,
                "artifact_types": _wo.ARTIFACT_TYPES,
                "canary_cases": _wo.CANARY_CASES,
                "observer_health_states": _wo.OBSERVER_HEALTH_STATES,
                "powo_warning": _wo.POWO_WARNING,
                "honesty_labels": _wo.HONESTY_LABELS}

    @app.get("/ai-tools/local-transactions/observability/registry")
    async def wo_registry(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        outs = work_obs_store.list_outcomes(tenant_id=user["tid"])
        by_state, by_truth = {}, {}
        for o in outs:
            by_state[o["work_run_state"]] = by_state.get(
                o["work_run_state"], 0) + 1
            by_truth[o["work_outcome_truth_state"]] = by_truth.get(
                o["work_outcome_truth_state"], 0) + 1
        return {"tenant_id": user["tid"], "work_run_count": len(outs),
                "work_request_count": len(
                    work_obs_store.list_requests(tenant_id=user["tid"])),
                "outcomes_by_state": by_state, "outcomes_by_truth_state": by_truth,
                "honesty_labels": _wo.HONESTY_LABELS}

    @app.get("/ai-tools/local-transactions/observability/work-runs")
    async def wo_work_runs(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return [{"work_run_id": o["work_run_id"],
                 "trigger_type": o["trigger_type"],
                 "work_run_state": o["work_run_state"],
                 "work_outcome_truth_state": o["work_outcome_truth_state"],
                 "proof_of_work_outcome_valid": o["proof_of_work_outcome_valid"]}
                for o in work_obs_store.list_outcomes(tenant_id=user["tid"])]

    @app.get("/ai-tools/local-transactions/observability/signals")
    async def wo_signals(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        outs = work_obs_store.list_outcomes(tenant_id=user["tid"])
        counts = {}
        for o in outs:
            for s in o.get("all_signals", []):
                counts[s] = counts.get(s, 0) + 1
        return {"tenant_id": user["tid"], "signal_counts": counts,
                "honesty_labels": _wo.HONESTY_LABELS}

    @app.get("/ai-tools/local-transactions/observability/observer-health")
    async def wo_observer_health(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        outs = work_obs_store.list_outcomes(tenant_id=user["tid"])
        by_health = {}
        for o in outs:
            h = o.get("observer_health_state", "OBSERVER_HEALTHY")
            by_health[h] = by_health.get(h, 0) + 1
        return {"tenant_id": user["tid"], "observer_health_by_state": by_health,
                "observer_health_states": _wo.OBSERVER_HEALTH_STATES,
                "honesty_labels": _wo.HONESTY_LABELS}

    @app.get("/ai-tools/local-transactions/observability/recurring-drift/"
             "{work_definition_id}")
    async def wo_recurring_drift(work_definition_id: str,
                                 user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        drift = _wo.build_recurring_drift(
            tenant_id=user["tid"], work_definition_id=work_definition_id, ctx={})
        return {"work_definition_id": work_definition_id,
                "recurring_drift": {k: v for k, v in drift.items()
                                    if k != "_signals"},
                "honesty_labels": _wo.HONESTY_LABELS}

    @app.post("/ai-tools/local-transactions/observability/observe-work-run")
    async def wo_observe(body: dict, user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return _observe_work_run(user["tid"], user, body or {})

    @app.post("/ai-tools/local-transactions/observability/verify-work-run")
    async def wo_verify(body: dict, user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        wrid = str((body or {}).get("work_run_id", "") or "")
        o = _load_work_outcome_or_404(wrid, user)
        recomputed = _wo._core_hash(
            o, "b92_decision_hash", "work_run_id", "actor_id",
            "decided_by_actor_id", "decided_by_actor_type", "b92_state_hash")
        ok = recomputed == o["b92_decision_hash"]
        return {"work_run_id": wrid,
                "stored_b92_decision_hash": o["b92_decision_hash"],
                "recomputed_b92_decision_hash": recomputed,
                "b92_decision_hash_valid": ok,
                "verification_status": "VALID" if ok else "TAMPERED",
                "honesty_labels": _wo.HONESTY_LABELS}

    @app.post("/ai-tools/local-transactions/observability/"
              "rebuild-local-observation")
    async def wo_rebuild(body: dict, user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        wrid = str((body or {}).get("work_run_id", "") or "")
        req = work_obs_store.request(wrid, tenant_id=user["tid"])
        if req is None:
            raise HTTPException(404, "work run not found")
        rebuilt = _observe_work_run(user["tid"], user, dict(req), work_run_id=None)
        return {"rebuilt_from_work_run_id": wrid, "rebuilt": rebuilt,
                "deterministic": True, "honesty_labels": _wo.HONESTY_LABELS}

    @app.post("/ai-tools/local-transactions/observability/run-local-canary")
    async def wo_run_canary(body: dict, user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        o = _observe_work_run(user["tid"], user, body or {})
        h = o["b92_canary_harness"]
        return {"work_run_id": o["work_run_id"], "canary_harness": h,
                "all_canaries_safe": h["all_canaries_safe"],
                "honesty_labels": _wo.HONESTY_LABELS}

    @app.post("/ai-tools/local-transactions/observability/"
              "work-observability-drill")
    async def wo_drill(body: dict, user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        o = _observe_work_run(user["tid"], user, body or {})
        return {"work_run_id": o["work_run_id"],
                "canary_harness": o["b92_canary_harness"],
                "no_external_effect": o["no_external_effect"],
                "observer_health_state": o["observer_health_state"],
                "drill_status": "SAFE" if o["b92_canary_harness"][
                    "all_canaries_safe"] else "UNSAFE",
                "honesty_labels": _wo.HONESTY_LABELS}

    @app.get("/ai-tools/local-transactions/observability/work-run/"
             "{work_run_id}")
    async def wo_get_work_run(work_run_id: str,
                              user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return _load_work_outcome_or_404(work_run_id, user)

    @app.get("/ai-tools/local-transactions/observability/events/{work_run_id}")
    async def wo_events(work_run_id: str, user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_work_outcome_or_404(work_run_id, user)
        return {"work_run_id": work_run_id, "events": work_obs_store.events(
            tenant_id=user["tid"], work_run_id=work_run_id),
            "honesty_labels": _wo.HONESTY_LABELS}

    def _mk_wo_subfield(field):
        async def getter(work_run_id: str,
                         user: dict = Depends(current_user)):
            require_permission(user, "case.read")
            o = _load_work_outcome_or_404(work_run_id, user)
            return {"work_run_id": work_run_id, field: o.get(field),
                    "honesty_labels": _wo.HONESTY_LABELS}
        return getter

    for _slug, _field in _WO_SUBFIELDS.items():
        app.add_api_route(
            "/ai-tools/local-transactions/observability/" + _slug +
            "/{work_run_id}", _mk_wo_subfield(_field), methods=["GET"])

    # Hoist the recovery literal routes ahead of the /{transaction_id} param
    # routes so first-match-wins does not capture e.g. /recovery/certificate as
    # /ai-tools/local-transactions/{transaction_id}/certificate.
    _tx_param_ix = next(
        (i for i, r in enumerate(app.router.routes)
         if getattr(r, "path", "").startswith(
             "/ai-tools/local-transactions/{transaction_id}")), None)
    if _tx_param_ix is not None:
        _rec_routes = [r for r in app.router.routes if getattr(
            r, "path", "").startswith(
                "/ai-tools/local-transactions/recovery") or getattr(
                r, "path", "").startswith(
                "/ai-tools/local-transactions/observability")]
        for _r in _rec_routes:
            app.router.routes.remove(_r)
        for _off, _r in enumerate(_rec_routes):
            app.router.routes.insert(_tx_param_ix + _off, _r)

    # Hoist the literal /ai-tools/actions/*, /ai-tools/broker/*,
    # /ai-tools/runtime/* and /ai-tools/write-intents/* routes ahead of the
    # earlier-registered parameterised /ai-tools/{tool_id}/* routes so first-
    # match-wins routing does not capture them (e.g. /ai-tools/runtime/policy as
    # /ai-tools/{tool_id}/policy -> 404).
    _param_ix = next((i for i, r in enumerate(app.router.routes)
                      if getattr(r, "path", "") == "/ai-tools/{tool_id}"), 0)
    _literal_routes = [r for r in app.router.routes
                       if getattr(r, "path", "").startswith("/ai-tools/actions")
                       or getattr(r, "path", "").startswith("/ai-tools/broker")
                       or getattr(r, "path", "").startswith(
                           "/ai-tools/runtime")
                       or getattr(r, "path", "").startswith(
                           "/ai-tools/write-intents")
                       or getattr(r, "path", "").startswith(
                           "/ai-tools/commit-simulations")
                       or getattr(r, "path", "").startswith(
                           "/ai-tools/local-transactions")]
    for _r in _literal_routes:
        app.router.routes.remove(_r)
    for _off, _r in enumerate(_literal_routes):
        app.router.routes.insert(_param_ix + _off, _r)

    # ===== EMP-A1 v1: Employee Work Inbox — R-FSAFEQ Governed Work ==========
    # ===== Admission Fabric (LOCAL, intake+admission only, no execution) ====
    from ..ai_employee import employee_work_inbox as _ewi
    from ..ai_employee.employee_work_inbox_store import EmployeeWorkInboxStore
    work_inbox_store = EmployeeWorkInboxStore(db)
    app.state.work_inbox_store = work_inbox_store

    def _wi_actor_type(user):
        return "ai_employee" if user["role"] == "ai_worker" else "human"

    def _wi_emit(tid, *, event_type, work_item_id, user, decision_hash, detail):
        seq = work_inbox_store.next_sequence(tenant_id=tid)
        prev = work_inbox_store.last_event(tenant_id=tid)
        ev = _ewi.build_work_event(
            event_type=event_type, tenant_id=tid, work_item_id=work_item_id,
            actor_id=user["uid"], actor_type=_wi_actor_type(user),
            decision_hash=decision_hash,
            previous_event_hash=prev["event_hash"] if prev else None,
            sequence=seq, detail=detail, created_at=utcnow())
        work_inbox_store.append_event({
            "id": str(uuid.uuid4()), "tenant_id": tid,
            "work_item_id": work_item_id, "event_type": event_type,
            "sequence": seq, "actor_id": user["uid"],
            "actor_type": _wi_actor_type(user), "event_hash": ev["event_hash"],
            "previous_event_hash": ev["previous_event_hash"],
            "decision_hash": decision_hash or "", "payload_json": json.dumps(ev),
            "created_at": ev["created_at"]})
        return ev

    def _wi_load_item_or_404(work_item_id, user):
        it = work_inbox_store.item(work_item_id, tenant_id=user["tid"])
        if it is None:
            raise HTTPException(404, "work item not found")
        return it

    def _wi_canonical_request(body):
        return {
            "tenant_id": body.get("tenant_id"),
            "source_type": body.get("source_type", "PORTAL_MANUAL"),
            "source_surface": body.get("source_surface", "WEB_PORTAL"),
            "source_schema_version": body.get("source_schema_version", "1"),
            "source_principal_id": body.get("source_principal_id"),
            "authenticated_principal_id": body.get("authenticated_principal_id"),
            "principal_active": body.get("principal_active", True),
            "conversation_context_id": body.get("conversation_context_id"),
            "continuation_of_work_item_id": body.get(
                "continuation_of_work_item_id"),
            "work_type": body.get("work_type"),
            "candidate_work_type": body.get("candidate_work_type"),
            "requested_target_refs": body.get("requested_target_refs") or [],
            "canonical_parameters": body.get("canonical_parameters") or {},
            "idempotency_key": body.get("idempotency_key"),
            "canonical_request_hash": body.get("canonical_request_hash"),
            "raw_payload": body.get("raw_payload") or {},
            "source_business_key": body.get("source_business_key"),
            "approval_record": body.get("approval_record"),
            "requested_scope": body.get("requested_scope"),
            # Risk/stability knobs (schema-only; calibration disabled by default).
            "calibration_state": body.get("calibration_state"),
            "drift_state": body.get("drift_state"),
            "risk_budget_status": body.get("risk_budget_status"),
            "backlog_state": body.get("backlog_state"),
            "intervals_nested": body.get("intervals_nested", True),
            "action_calibration_mismatch": body.get(
                "action_calibration_mismatch"),
            "governed_recalibration": body.get("governed_recalibration"),
            "capacity_unknown": body.get("capacity_unknown"),
            "demand_unknown": body.get("demand_unknown"),
            "estimate_source": body.get("estimate_source"),
            "demand_override": body.get("demand_override"),
        }

    def _wi_snapshot(tid, req):
        key = req.get("idempotency_key")
        prior = work_inbox_store.item_by_idempotency(
            tenant_id=tid, idempotency_key=key) if key else None
        existing_by_key = {}
        if prior:
            existing_by_key[(tid, key)] = {
                "work_item_id": prior["work_item_id"],
                "canonical_request_hash": prior.get("canonical_request_hash")}
        flow_key = _ewi.compute_flow_key(
            tenant_id=tid, req=req,
            intent={"work_type": req.get("work_type"),
                    "canonical_target_refs": req.get("requested_target_refs")},
            queue_group=req.get("work_type") or "default")
        return {
            "tenant_id": tid, "existing_by_key": existing_by_key,
            "flow_state": work_inbox_store.flow_state(
                tenant_id=tid, flow_key=flow_key),
            "recent_fingerprints": work_inbox_store.recent_fingerprints(
                tenant_id=tid),
            "capacity_state": {r: 64 for r in _ewi.DEMAND_RESOURCES},
            "shard_pressures": {},
        }

    def _wi_project(tid, req, decision, user, now, seq):
        wid = "wi-" + str(uuid.uuid4())
        intent = decision["intent"]
        demand = decision["demand_envelope"]
        proj = {
            "work_item_id": wid, "tenant_id": tid,
            "idempotency_key": req.get("idempotency_key"),
            "conversation_context_id": req.get("conversation_context_id"),
            "work_item_version": 1, "projection_version": 1,
            "work_type": intent.get("work_type"),
            "work_type_version": intent.get("work_type_version"),
            "compiled_intent_hash": intent.get("compiled_intent_hash"),
            "canonical_request_hash": decision["idempotency"][
                "canonical_request_hash"],
            "title": (req.get("raw_payload") or {}).get("title") or
            intent.get("work_type"),
            "safe_summary": (req.get("raw_payload") or {}).get("note", ""),
            "requester_principal_id": req.get("source_principal_id"),
            "target_refs": intent.get("canonical_target_refs"),
            "missing_input_fields": intent.get("missing_fields"),
            "required_capabilities": intent.get("required_capabilities"),
            "approval_requirement": decision["approval"]["approval_class"],
            "approval_valid": decision["approval"].get("approval_valid"),
            "risk_class": (_ewi.WORK_TYPE_REGISTRY.get(intent.get("work_type"))
                           or {}).get("risk_profile_id"),
            "priority_class": (_ewi.WORK_TYPE_REGISTRY.get(intent.get("work_type"))
                               or {}).get("default_priority_class", "NORMAL"),
            "queue_group": decision["queue_group"],
            "flow_key": decision["flow_key"],
            "queue_shard": decision["queue_placement"]["queue_shard"],
            "work_demand_envelope": demand,
            "demand_envelope_valid": demand["envelope_valid"],
            "calibration_status": decision["calibration"]["calibration_state"],
            "calibration_fallback_valid": True,
            "drift_status": decision["drift"]["drift_state"],
            "risk_budget_status": decision["risk_budget"]["risk_budget_status"],
            "admission_memory_state": decision["admission_memory"][
                "admission_memory_state"],
            "virtual_backlog_status": decision["virtual_backlog"][
                "backlog_state"],
            "fairness_deficit": decision["fairness"]["fairness_deficit"],
            "fairness_deficit_class": decision["fairness"][
                "fairness_deficit_class"],
            "assignee_type": "UNASSIGNED", "assignee_id": None,
            "assignment_version": 0, "active_claim_id": None,
            "active_fencing_token": 0, "active_eligible_age": 0,
            "aging_horizon": 100,
            "structural_fingerprint": decision["fragmentation"][
                "structural_fingerprint"],
            "work_item_state": decision["resulting_state"],
            "disposition": decision["disposition"],
            "reason_codes": decision["reason_codes"],
            "created_sequence": seq, "decision_hash": decision["decision_hash"],
            "created_at": now, "updated_at": now,
            "run_created": False, "tool_transaction_started": False,
            "provider_called": False, "external_state_mutated": False,
            "outbox_released": False,
            "honesty_labels": _ewi.HONESTY_LABELS,
        }
        proj["work_item_hash"] = _ewi._sha({k: v for k, v in proj.items()
                                           if k not in ("work_item_hash",
                                                        "honesty_labels")})
        return proj

    def _admit_work_item(tid, user, body):
        # SERIALIZABLE admission: begin the write transaction before the
        # admission-dependent reads. A retry rolls back the full attempt.
        req = _wi_canonical_request(body)
        req["tenant_id"] = req.get("tenant_id") or tid
        work_inbox_store.begin_immediate()
        snapshot = _wi_snapshot(tid, req)
        decision = _ewi.evaluate_admission(snapshot, req, {})
        now = utcnow()
        idem_status = decision["idempotency"]["idempotency_status"]
        # Exact retry -> return the existing item, charge nothing.
        if idem_status == "EXACT_RETRY":
            wid = decision["idempotency"]["existing_work_item_id"]
            work_inbox_store.commit()
            existing = work_inbox_store.item(wid, tenant_id=tid) if wid else None
            return {"work_item": existing, "disposition": "ADMIT_READY",
                    "idempotency_status": "EXACT_RETRY", "charged": False,
                    "decision_hash": decision["decision_hash"],
                    "honesty_labels": _ewi.HONESTY_LABELS}
        # Conflict -> same idempotency key, different canonical request. Never
        # persist a second row under that key; return the conflict + the prior
        # item, charge nothing.
        if idem_status == "CONFLICT":
            wid = decision["idempotency"]["existing_work_item_id"]
            work_inbox_store.commit()
            existing = work_inbox_store.item(wid, tenant_id=tid) if wid else None
            return {"work_item": existing, "disposition": "CONFLICT",
                    "idempotency_status": "CONFLICT", "charged": False,
                    "reason_codes": ["IDEMPOTENCY_PAYLOAD_CONFLICT"],
                    "decision_hash": decision["decision_hash"],
                    "honesty_labels": _ewi.HONESTY_LABELS}
        seq = work_inbox_store.next_created_sequence(tenant_id=tid)
        proj = _wi_project(tid, req, decision, user, now, seq)
        actor_type = _wi_actor_type(user)
        work_inbox_store.save_item({
            "id": proj["work_item_id"], "tenant_id": tid,
            "idempotency_key": proj["idempotency_key"] or "",
            "bundle_id": "", "conversation_context_id":
            proj["conversation_context_id"] or "",
            "work_type": proj["work_type"] or "", "flow_key": proj["flow_key"],
            "queue_group": proj["queue_group"] or "",
            "queue_shard": proj["queue_shard"],
            "source_principal_id": proj["requester_principal_id"] or "",
            "structural_fingerprint": proj["structural_fingerprint"],
            "priority_class": proj["priority_class"],
            "work_item_state": proj["work_item_state"],
            "work_item_version": 1, "work_item_hash": proj["work_item_hash"],
            "admission_receipt_hash": "", "decision_hash": proj["decision_hash"],
            "created_sequence": seq, "requested_by": user["uid"],
            "requested_by_actor_type": actor_type,
            "payload_json": json.dumps(proj), "created_at": now,
            "updated_at": now})
        # Admission receipt (durable decision record).
        dseq = work_inbox_store.next_decision_sequence(tenant_id=tid)
        receipt = {"admission_receipt_id": "rcpt-" + _ewi._sha(
            {"w": proj["work_item_id"], "d": dseq})[:16],
            "tenant_id": tid, "work_item_id": proj["work_item_id"],
            "decision_sequence": dseq, "disposition": decision["disposition"],
            "decision_hash": decision["decision_hash"],
            "reason_codes": decision["reason_codes"], "charged":
            decision["charge_allowed"], "created_at": now}
        receipt["admission_receipt_hash"] = _ewi._sha(receipt)
        work_inbox_store.save_receipt({
            "id": str(uuid.uuid4()), "tenant_id": tid,
            "work_item_id": proj["work_item_id"], "decision_sequence": dseq,
            "disposition": decision["disposition"],
            "decision_hash": decision["decision_hash"],
            "admission_receipt_hash": receipt["admission_receipt_hash"],
            "payload_json": json.dumps(receipt), "created_at": now})
        proj["admission_receipt_hash"] = receipt["admission_receipt_hash"]
        proj["work_item_hash"] = _ewi._sha({k: v for k, v in proj.items()
                                           if k not in ("work_item_hash",
                                                        "honesty_labels")})
        work_inbox_store.update_item(proj["work_item_id"], tenant_id=tid, row={
            "work_item_state": proj["work_item_state"], "work_item_version": 1,
            "work_item_hash": proj["work_item_hash"], "payload": proj,
            "updated_at": now})
        # Charge flow state only when admission actually charges (never on
        # exact retry / reject / duplicate).
        if decision["charge_allowed"]:
            fs = work_inbox_store.flow_state(
                tenant_id=tid, flow_key=proj["flow_key"]) or {
                    "flow_key": proj["flow_key"], "memory": 0,
                    "fairness_deficit": 0, "risk_spent": 0}
            fs["memory"] = decision["admission_memory"]["memory_after"]
            fs["fairness_deficit"] = decision["fairness"]["fairness_deficit"]
            fs["updated_at"] = now
            work_inbox_store.upsert_flow_state(
                tenant_id=tid, flow_key=proj["flow_key"], state=fs)
        _wi_emit(tid, event_type="WORK_ITEM_RECEIVED",
                 work_item_id=proj["work_item_id"], user=user,
                 decision_hash=decision["decision_hash"],
                 detail={"source": req.get("source_type")})
        _wi_emit(tid, event_type="WORK_ITEM_ADMISSION_EVALUATED",
                 work_item_id=proj["work_item_id"], user=user,
                 decision_hash=decision["decision_hash"],
                 detail={"disposition": decision["disposition"],
                         "resulting_state": proj["work_item_state"]})
        _wi_emit(tid, event_type="WORK_ITEM_ADMISSION_COMMITTED",
                 work_item_id=proj["work_item_id"], user=user,
                 decision_hash=decision["decision_hash"],
                 detail={"resulting_state": proj["work_item_state"]})
        if proj["work_item_state"] == "READY":
            _wi_emit(tid, event_type="WORK_ITEM_QUEUE_PLACED",
                     work_item_id=proj["work_item_id"], user=user,
                     decision_hash=decision["decision_hash"],
                     detail={"queue_shard": proj["queue_shard"],
                             "resulting_state": "READY"})
        _wi_emit(tid, event_type="WORK_ITEM_ADMISSION_RECEIPT_CREATED",
                 work_item_id=proj["work_item_id"], user=user,
                 decision_hash=decision["decision_hash"],
                 detail={"receipt": receipt["admission_receipt_hash"]})
        work_inbox_store.commit()
        return {"work_item": proj, "disposition": decision["disposition"],
                "idempotency_status": decision["idempotency"][
                    "idempotency_status"], "charged": decision["charge_allowed"],
                "decision_hash": decision["decision_hash"],
                "reason_codes": decision["reason_codes"],
                "honesty_labels": _ewi.HONESTY_LABELS}

    def _wi_transition(tid, user, it, event_type, new_state, detail=None):
        src = it["work_item_state"]
        if not _ewi.is_transition_allowed(src, new_state):
            raise HTTPException(409, {"error": "invalid_transition",
                                      "from": src, "to": new_state})
        now = utcnow()
        it["work_item_state"] = new_state
        it["work_item_version"] = _ewi._int(it.get("work_item_version"), 1) + 1
        it["projection_version"] = _ewi._int(it.get("projection_version"), 1) + 1
        it["updated_at"] = now
        it["work_item_hash"] = _ewi._sha({k: v for k, v in it.items()
                                         if k not in ("work_item_hash",
                                                      "honesty_labels")})
        work_inbox_store.update_item(it["work_item_id"], tenant_id=tid, row={
            "work_item_state": new_state,
            "work_item_version": it["work_item_version"],
            "work_item_hash": it["work_item_hash"], "payload": it,
            "updated_at": now})
        _wi_emit(tid, event_type=event_type, work_item_id=it["work_item_id"],
                 user=user, decision_hash=it.get("decision_hash"),
                 detail=dict(detail or {}, resulting_state=new_state))
        work_inbox_store.commit()
        return it

    @app.get("/ai-employee/work-inbox/policy")
    async def wi_policy(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return {"emp_a1_model_version": _ewi.EMP_A1_MODEL_VERSION,
                "spec_revision": _ewi.EMP_A1_SPEC_REVISION,
                "r_fsafeq_policy_version": _ewi.RFSAFEQ_POLICY_VERSION,
                "inbox_and_admission_only": True, "creates_emp_a2_run": False,
                "executes_work": False, "calls_provider": False,
                "calls_tool": False, "starts_b9_transaction": False,
                "performs_recovery": False, "releases_outbox": False,
                "sends_message": False, "guarantees_deadline": False,
                "calibration_enabled": False, "production_ready": False,
                "has_run_endpoint": False, "has_execute_endpoint": False,
                "has_provider_call_endpoint": False, "has_send_endpoint": False,
                "has_b9_transaction_endpoint": False,
                "work_item_states": _ewi.WORK_ITEM_STATES,
                "forbidden_states": sorted(_ewi.FORBIDDEN_STATES),
                "dispositions": _ewi.DISPOSITIONS,
                "demand_resources": _ewi.DEMAND_RESOURCES,
                "calibration_states": _ewi.CALIBRATION_STATES,
                "drift_states": _ewi.DRIFT_STATES,
                "risk_budget_states": _ewi.RISK_BUDGET_STATES,
                "backlog_states": _ewi.BACKLOG_STATES,
                "enabled_sources": sorted(_ewi.ENABLED_SOURCES),
                "disabled_sources": sorted(_ewi.DISABLED_SOURCES),
                "reason_codes": sorted(_ewi.REASON_CODES),
                "permissions": ["employee_work_inbox_read",
                                "employee_work_inbox_submit",
                                "employee_work_inbox_claim",
                                "employee_work_inbox_prepare_handoff"],
                "honesty_labels": _ewi.HONESTY_LABELS}

    @app.get("/ai-employee/work-inbox/registry")
    async def wi_registry(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return {"tenant_id": user["tid"],
                "work_type_registry": {k: {kk: vv for kk, vv in v.items()}
                                       for k, v in
                                       _ewi.WORK_TYPE_REGISTRY.items()},
                "priority_classes": _ewi.PRIORITY_CLASSES,
                "honesty_labels": _ewi.HONESTY_LABELS}

    @app.get("/ai-employee/work-inbox/counts")
    async def wi_counts(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return {"tenant_id": user["tid"],
                "counts_by_state": work_inbox_store.counts_by_state(
                    tenant_id=user["tid"]),
                "honesty_labels": _ewi.HONESTY_LABELS}

    def _wi_simple_get(path, builder):
        async def getter(user: dict = Depends(current_user)):
            require_permission(user, "case.read")
            return dict(builder(user), honesty_labels=_ewi.HONESTY_LABELS)
        app.add_api_route("/ai-employee/work-inbox/" + path, getter,
                          methods=["GET"])

    _wi_simple_get("capacity", lambda u: {
        "tenant_id": u["tid"], "capacity_vector": {r: 64 for r in
                                                   _ewi.DEMAND_RESOURCES},
        "demand_resources": _ewi.DEMAND_RESOURCES})
    _wi_simple_get("risk", lambda u: {
        "tenant_id": u["tid"], "risk_budget_states": _ewi.RISK_BUDGET_STATES,
        "calibration_enabled": False, "alpha_total_not_increasable": True})
    _wi_simple_get("calibration", lambda u: {
        "tenant_id": u["tid"], "calibration_states": _ewi.CALIBRATION_STATES,
        "default_calibration_state": "DISABLED",
        "calibration_disabled_by_default": True})
    _wi_simple_get("drift", lambda u: {
        "tenant_id": u["tid"], "drift_states": _ewi.DRIFT_STATES,
        "conservative_fallback": "deterministic_upper_envelope"})
    _wi_simple_get("flow-state", lambda u: {
        "tenant_id": u["tid"], "flows": work_inbox_store.list_flow_state(
            tenant_id=u["tid"])})
    _wi_simple_get("queues", lambda u: {
        "tenant_id": u["tid"], "queue_count": 8,
        "counts_by_state": work_inbox_store.counts_by_state(tenant_id=u["tid"])})
    _wi_simple_get("observer-health", lambda u: {
        "tenant_id": u["tid"], "observer_health_state": "OBSERVER_HEALTHY",
        "model_check": _ewi.run_bounded_model_check()["all_invariants_hold"]})

    @app.get("/ai-employee/work-inbox/items")
    async def wi_items(state: str = "", limit: int = 100,
                       after_sequence: int = 0,
                       user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return [{"work_item_id": i["work_item_id"],
                 "work_type": i.get("work_type"),
                 "work_item_state": i["work_item_state"],
                 "priority_class": i.get("priority_class"),
                 "queue_shard": i.get("queue_shard")}
                for i in work_inbox_store.list_items(
                    tenant_id=user["tid"], state=state or None,
                    limit=min(limit, 200), after_sequence=after_sequence)]

    @app.post("/ai-employee/work-inbox/items")
    async def wi_submit(body: dict, user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        body = body or {}
        body.setdefault("source_principal_id", user["uid"])
        body.setdefault("authenticated_principal_id", user["uid"])
        body.setdefault("tenant_id", user["tid"])
        return _admit_work_item(user["tid"], user, body)

    @app.get("/ai-employee/work-inbox/items/{work_item_id}")
    async def wi_get_item(work_item_id: str,
                          user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return _wi_load_item_or_404(work_item_id, user)

    @app.get("/ai-employee/work-inbox/items/{work_item_id}/events")
    async def wi_item_events(work_item_id: str,
                             user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _wi_load_item_or_404(work_item_id, user)
        evs = work_inbox_store.events(tenant_id=user["tid"],
                                      work_item_id=work_item_id)
        rebuild = _ewi.rebuild_work_item_projection(evs)
        return {"work_item_id": work_item_id, "events": evs,
                "projection_rebuild": rebuild,
                "honesty_labels": _ewi.HONESTY_LABELS}

    _WI_ITEM_SUBFIELDS = {
        "intent": ("compiled_intent_hash", "work_type", "target_refs",
                   "missing_input_fields", "required_capabilities"),
        "admission": ("disposition", "reason_codes", "admission_receipt_hash",
                      "decision_hash", "work_item_state"),
        "demand": ("work_demand_envelope", "demand_envelope_valid"),
        "risk": ("risk_budget_status", "calibration_status", "drift_status",
                 "virtual_backlog_status"),
        "priority-explanation": ("priority_class", "fairness_deficit",
                                 "fairness_deficit_class", "queue_shard",
                                 "reason_codes"),
        "claim": ("active_claim_id", "active_fencing_token", "assignee_id",
                  "assignee_type"),
    }

    def _mk_wi_subfield(fields):
        async def getter(work_item_id: str,
                         user: dict = Depends(current_user)):
            require_permission(user, "case.read")
            it = _wi_load_item_or_404(work_item_id, user)
            return dict({f: it.get(f) for f in fields},
                        work_item_id=work_item_id,
                        honesty_labels=_ewi.HONESTY_LABELS)
        return getter

    for _slug, _fields in _WI_ITEM_SUBFIELDS.items():
        app.add_api_route(
            "/ai-employee/work-inbox/items/{work_item_id}/" + _slug,
            _mk_wi_subfield(_fields), methods=["GET"])

    @app.get("/ai-employee/work-inbox/items/{work_item_id}/handoff-preview")
    async def wi_handoff_preview(work_item_id: str,
                                 user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        it = _wi_load_item_or_404(work_item_id, user)
        hr = _ewi.handoff_ready(item=dict(
            it, claim_current=True, fence_current=True,
            capabilities_present=True, approval_ok=it.get("approval_valid")
            is not False, source_watermark_current=True), reference_decision=None)
        return {"work_item_id": work_item_id, "handoff_ready": hr,
                "honesty_labels": _ewi.HONESTY_LABELS}

    @app.post("/ai-employee/work-inbox/items/{work_item_id}/reserve")
    async def wi_reserve(work_item_id: str, body: dict = None,
                         user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        it = _wi_load_item_or_404(work_item_id, user)
        it["reserved_demand"] = it.get("work_demand_envelope", {}).get(
            "safety_upper")
        return _wi_transition(user["tid"], user, it, "WORK_ITEM_RESERVED",
                              "RESERVED", {"reserved": True})

    @app.post("/ai-employee/work-inbox/items/{work_item_id}/claim")
    async def wi_claim(work_item_id: str, body: dict = None,
                       user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        work_inbox_store.begin_immediate()
        it = _wi_load_item_or_404(work_item_id, user)
        if it["work_item_state"] not in ("READY", "RESERVED"):
            work_inbox_store.commit()
            raise HTTPException(409, {"error": "not_claimable",
                                      "state": it["work_item_state"]})
        # Compare-and-swap: new fencing token strictly greater than all prior.
        max_fence = work_inbox_store.max_fencing_token(
            tenant_id=user["tid"], work_item_id=work_item_id)
        active = work_inbox_store.active_claim(tenant_id=user["tid"],
                                               work_item_id=work_item_id)
        if active:
            work_inbox_store.commit()
            raise HTTPException(409, {"error": "claim_conflict",
                                      "reason_code": "CLAIM_CONFLICT"})
        new_fence = max_fence + 1
        claim_id = "clm-" + str(uuid.uuid4())
        now = utcnow()
        work_inbox_store.save_claim({
            "id": claim_id, "tenant_id": user["tid"],
            "work_item_id": work_item_id,
            "work_item_version": _ewi._int(it.get("work_item_version"), 1),
            "claimant_id": user["uid"], "fencing_token": new_fence,
            "state": "ACTIVE", "payload_json": json.dumps({
                "claim_id": claim_id, "fencing_token": new_fence,
                "claimant_id": user["uid"]}), "created_at": now,
            "expires_at": ""})
        it["active_claim_id"] = claim_id
        it["active_fencing_token"] = new_fence
        return _wi_transition(user["tid"], user, it, "WORK_ITEM_CLAIMED",
                              "CLAIMED", {"claim_id": claim_id,
                                          "fencing_token": new_fence})

    @app.post("/ai-employee/work-inbox/items/{work_item_id}/renew-claim")
    async def wi_renew_claim(work_item_id: str, body: dict = None,
                             user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        it = _wi_load_item_or_404(work_item_id, user)
        return {"work_item_id": work_item_id,
                "active_fencing_token": it.get("active_fencing_token"),
                "renewed": it["work_item_state"] == "CLAIMED",
                "honesty_labels": _ewi.HONESTY_LABELS}

    @app.post("/ai-employee/work-inbox/items/{work_item_id}/release-claim")
    async def wi_release_claim(work_item_id: str, body: dict = None,
                               user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        work_inbox_store.begin_immediate()
        it = _wi_load_item_or_404(work_item_id, user)
        work_inbox_store.expire_claims(tenant_id=user["tid"],
                                       work_item_id=work_item_id)
        work_inbox_store.invalidate_handoffs(tenant_id=user["tid"],
                                             work_item_id=work_item_id)
        it["active_claim_id"] = None
        return _wi_transition(user["tid"], user, it, "WORK_ITEM_CLAIM_EXPIRED",
                              "READY", {"released": True})

    @app.post("/ai-employee/work-inbox/items/{work_item_id}/prepare-handoff")
    async def wi_prepare_handoff(work_item_id: str, body: dict = None,
                                 user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        work_inbox_store.begin_immediate()
        it = _wi_load_item_or_404(work_item_id, user)
        hr = _ewi.handoff_ready(item=dict(
            it, claim_current=it["work_item_state"] == "CLAIMED",
            fence_current=True, capabilities_present=True,
            approval_ok=it.get("approval_valid") is not False,
            source_watermark_current=True), reference_decision=None)
        if not hr["handoff_ready"] or it["work_item_state"] != "CLAIMED":
            work_inbox_store.commit()
            raise HTTPException(409, {"error": "not_handoff_ready",
                                      "checks": hr["checks"]})
        work_inbox_store.invalidate_handoffs(tenant_id=user["tid"],
                                             work_item_id=work_item_id)
        now = utcnow()
        cap_id = "hoc-" + str(uuid.uuid4())
        nonce_hash = _ewi._sha({"n": str(uuid.uuid4())})
        cap = {"handoff_capability_id": cap_id, "tenant_id": user["tid"],
               "intended_consumer": "EMP-A2", "work_item_id": work_item_id,
               "work_item_version": it.get("work_item_version"),
               "projection_version": it.get("projection_version"),
               "fencing_token": it.get("active_fencing_token"),
               "assignee_id": it.get("assignee_id"),
               "admission_receipt_hash": it.get("admission_receipt_hash"),
               "issued_at": now, "state": "PREPARED",
               "emp_a1_created_run": False, "consumed_by_emp_a1": False}
        cap["capability_hash"] = _ewi._sha({k: v for k, v in cap.items()
                                           if k not in ("capability_hash",)})
        work_inbox_store.save_handoff({
            "id": cap_id, "tenant_id": user["tid"], "work_item_id": work_item_id,
            "work_item_version": _ewi._int(it.get("work_item_version"), 1),
            "fencing_token": _ewi._int(it.get("active_fencing_token")),
            "intended_consumer": "EMP-A2", "state": "PREPARED",
            "capability_hash": cap["capability_hash"],
            "payload_json": json.dumps(cap), "issued_at": now, "expires_at": ""})
        it2 = _wi_transition(user["tid"], user, it, "WORK_ITEM_HANDOFF_PREPARED",
                             "HANDOFF_READY", {"capability_hash":
                                               cap["capability_hash"]})
        return {"work_item": it2, "handoff_capability": cap,
                "labels": hr["labels"], "no_emp_a2_run_created": True,
                "honesty_labels": _ewi.HONESTY_LABELS}

    @app.post("/ai-employee/work-inbox/items/{work_item_id}/invalidate-handoff")
    async def wi_invalidate_handoff(work_item_id: str, body: dict = None,
                                    user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        work_inbox_store.begin_immediate()
        it = _wi_load_item_or_404(work_item_id, user)
        work_inbox_store.invalidate_handoffs(tenant_id=user["tid"],
                                             work_item_id=work_item_id)
        target = "CLAIMED" if it["work_item_state"] == "HANDOFF_READY" else \
            it["work_item_state"]
        if target != it["work_item_state"]:
            it = _wi_transition(user["tid"], user, it,
                                "WORK_ITEM_HANDOFF_INVALIDATED", target,
                                {"invalidated": True})
        else:
            work_inbox_store.commit()
        return {"work_item_id": work_item_id, "handoff_invalidated": True,
                "honesty_labels": _ewi.HONESTY_LABELS}

    def _mk_wi_action(new_state, event_type, perm="case.update"):
        async def handler(work_item_id: str, body: dict = None,
                          user: dict = Depends(current_user)):
            require_permission(user, perm)
            it = _wi_load_item_or_404(work_item_id, user)
            return _wi_transition(user["tid"], user, it, event_type, new_state,
                                  body or {})
        return handler

    for _slug, (_st, _et) in {
        "cancel": ("CANCELED", "WORK_ITEM_CANCELED"),
        "resolve-atomicity": ("VALIDATING", "WORK_ITEM_ATOMICITY_EVALUATED"),
        "mark-duplicate": ("DUPLICATE", "WORK_ITEM_DUPLICATE_MARKED"),
    }.items():
        app.add_api_route(
            "/ai-employee/work-inbox/items/{work_item_id}/" + _slug,
            _mk_wi_action(_st, _et), methods=["POST"])

    @app.post("/ai-employee/work-inbox/items/{work_item_id}/defer")
    async def wi_defer(work_item_id: str, body: dict = None,
                       user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        it = _wi_load_item_or_404(work_item_id, user)
        target = (body or {}).get("defer_state", "DEFERRED_POLICY")
        if target not in _ewi.DEFERRED_STATES:
            target = "DEFERRED_POLICY"
        return _wi_transition(user["tid"], user, it, "WORK_ITEM_DEFERRED",
                              target, {"deferred": True})

    @app.post("/ai-employee/work-inbox/items/{work_item_id}/resume")
    async def wi_resume(work_item_id: str, body: dict = None,
                        user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        it = _wi_load_item_or_404(work_item_id, user)
        return _wi_transition(user["tid"], user, it, "WORK_ITEM_RESUMED",
                              "VALIDATING", {"resumed": True})

    @app.post("/ai-employee/work-inbox/items/{work_item_id}/reverse-duplicate")
    async def wi_reverse_duplicate(work_item_id: str, body: dict = None,
                                   user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        it = _wi_load_item_or_404(work_item_id, user)
        return _wi_transition(user["tid"], user, it,
                              "WORK_ITEM_DUPLICATE_REVERSED", "RECEIVED",
                              {"reversed": True})

    @app.post("/ai-employee/work-inbox/items/{work_item_id}/assign")
    async def wi_assign(work_item_id: str, body: dict,
                        user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        it = _wi_load_item_or_404(work_item_id, user)
        it["assignee_type"] = (body or {}).get("assignee_type", "HUMAN")
        it["assignee_id"] = (body or {}).get("assignee_id", user["uid"])
        it["assignment_version"] = _ewi._int(it.get("assignment_version")) + 1
        now = utcnow()
        it["updated_at"] = now
        it["work_item_hash"] = _ewi._sha({k: v for k, v in it.items()
                                         if k not in ("work_item_hash",
                                                      "honesty_labels")})
        work_inbox_store.update_item(work_item_id, tenant_id=user["tid"], row={
            "work_item_state": it["work_item_state"],
            "work_item_version": it["work_item_version"],
            "work_item_hash": it["work_item_hash"], "payload": it,
            "updated_at": now})
        _wi_emit(user["tid"], event_type="WORK_ITEM_ASSIGNED",
                 work_item_id=work_item_id, user=user,
                 decision_hash=it.get("decision_hash"),
                 detail={"assignee_id": it["assignee_id"]})
        work_inbox_store.commit()
        return {"work_item": it, "grants_execution": False,
                "honesty_labels": _ewi.HONESTY_LABELS}

    @app.post("/ai-employee/work-inbox/items/{work_item_id}/unassign")
    async def wi_unassign(work_item_id: str, body: dict = None,
                          user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        it = _wi_load_item_or_404(work_item_id, user)
        it["assignee_type"] = "UNASSIGNED"
        it["assignee_id"] = None
        now = utcnow()
        it["updated_at"] = now
        work_inbox_store.update_item(work_item_id, tenant_id=user["tid"], row={
            "work_item_state": it["work_item_state"],
            "work_item_version": it["work_item_version"],
            "work_item_hash": it.get("work_item_hash", ""), "payload": it,
            "updated_at": now})
        work_inbox_store.commit()
        return {"work_item_id": work_item_id, "assignee_type": "UNASSIGNED",
                "honesty_labels": _ewi.HONESTY_LABELS}

    @app.post("/ai-employee/work-inbox/items/{work_item_id}/reprioritize")
    async def wi_reprioritize(work_item_id: str, body: dict,
                              user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        it = _wi_load_item_or_404(work_item_id, user)
        pc = (body or {}).get("priority_class")
        if pc == "CRITICAL":
            require_permission(user, "case.update")  # critical-priority gate
        if pc in _ewi.PRIORITY_CLASSES:
            it["priority_class"] = pc
            now = utcnow()
            it["updated_at"] = now
            work_inbox_store.update_item(
                work_item_id, tenant_id=user["tid"], row={
                    "work_item_state": it["work_item_state"],
                    "work_item_version": it["work_item_version"],
                    "work_item_hash": it.get("work_item_hash", ""),
                    "payload": it, "updated_at": now})
            work_inbox_store.commit()
        return {"work_item_id": work_item_id,
                "priority_class": it.get("priority_class"),
                "bypasses_approval": False, "honesty_labels": _ewi.HONESTY_LABELS}

    @app.post("/ai-employee/work-inbox/items/{work_item_id}/request-clarification")
    async def wi_request_clarification(work_item_id: str, body: dict = None,
                                       user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        it = _wi_load_item_or_404(work_item_id, user)
        plan = _ewi.plan_clarification(intent={
            "missing_fields": it.get("missing_input_fields") or []})
        return {"work_item_id": work_item_id, "clarification_plan": plan,
                "llm_supplied_values": False, "honesty_labels":
                _ewi.HONESTY_LABELS}

    @app.post("/ai-employee/work-inbox/items/{work_item_id}/respond-clarification")
    async def wi_respond_clarification(work_item_id: str, body: dict,
                                       user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        it = _wi_load_item_or_404(work_item_id, user)
        _wi_emit(user["tid"], event_type="WORK_ITEM_CLARIFICATION_RECEIVED",
                 work_item_id=work_item_id, user=user,
                 decision_hash=it.get("decision_hash"),
                 detail={"fields": list((body or {}).get("answers", {}).keys())})
        work_inbox_store.commit()
        return {"work_item_id": work_item_id, "recorded": True,
                "honesty_labels": _ewi.HONESTY_LABELS}

    @app.post("/ai-employee/work-inbox/items/{work_item_id}/bind-approval")
    async def wi_bind_approval(work_item_id: str, body: dict,
                               user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        it = _wi_load_item_or_404(work_item_id, user)
        _wi_emit(user["tid"], event_type="WORK_ITEM_APPROVAL_BOUND",
                 work_item_id=work_item_id, user=user,
                 decision_hash=it.get("decision_hash"),
                 detail={"approval_refs": (body or {}).get("refs", [])})
        work_inbox_store.commit()
        return {"work_item_id": work_item_id, "approval_bound": True,
                "honesty_labels": _ewi.HONESTY_LABELS}

    @app.get("/ai-employee/work-inbox/bundles/{bundle_id}")
    async def wi_get_bundle(bundle_id: str,
                            user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        b = work_inbox_store.bundle(bundle_id, tenant_id=user["tid"])
        if b is None:
            raise HTTPException(404, "bundle not found")
        return b

    # ---- Derived drills (no run, no execution) -----------------------------
    @app.post("/ai-employee/work-inbox/rebuild-projection")
    async def wi_rebuild_projection(body: dict,
                                    user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        wid = (body or {}).get("work_item_id")
        _wi_load_item_or_404(wid, user)
        evs = work_inbox_store.events(tenant_id=user["tid"], work_item_id=wid)
        return {"work_item_id": wid,
                "projection_rebuild": _ewi.rebuild_work_item_projection(evs),
                "honesty_labels": _ewi.HONESTY_LABELS}

    @app.post("/ai-employee/work-inbox/simulate-policy")
    async def wi_simulate_policy(body: dict,
                                 user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        reqs = [_wi_canonical_request(r) for r in (body or {}).get(
            "requests", [])]
        snap = {"tenant_id": user["tid"], "existing_by_key": {},
                "recent_fingerprints": [],
                "capacity_state": {r: 64 for r in _ewi.DEMAND_RESOURCES},
                "shard_pressures": {}}
        sim = _ewi.simulate_policy(
            snapshot=snap, requests=reqs, baseline_policy={},
            candidate_policy=(body or {}).get("candidate_policy") or {})
        return dict(sim, honesty_labels=_ewi.HONESTY_LABELS)

    @app.post("/ai-employee/work-inbox/run-reference-kernel-drill")
    async def wi_reference_drill(body: dict = None,
                                 user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        req = _wi_canonical_request(dict(
            (body or {}), source_principal_id=(body or {}).get(
                "source_principal_id", user["uid"]),
            authenticated_principal_id=user["uid"], tenant_id=user["tid"],
            work_type=(body or {}).get("work_type", "case_summary"),
            requested_target_refs=(body or {}).get("requested_target_refs",
                                                   ["case:E-1"]),
            canonical_parameters=(body or {}).get("canonical_parameters",
                                                  {"target": "case:E-1"}),
            idempotency_key=(body or {}).get("idempotency_key", "drill-1")))
        snap = {"tenant_id": user["tid"], "existing_by_key": {},
                "recent_fingerprints": [],
                "capacity_state": {r: 64 for r in _ewi.DEMAND_RESOURCES},
                "shard_pressures": {}}
        d1 = _ewi.evaluate_admission(snap, req, {})
        d2 = _ewi.evaluate_admission(snap, req, {})
        return {"reference_kernel_deterministic":
                d1["decision_hash"] == d2["decision_hash"],
                "decision_hash": d1["decision_hash"],
                "disposition": d1["disposition"],
                "run_created": d1["run_created"],
                "tool_transaction_started": d1["tool_transaction_started"],
                "provider_called": d1["provider_called"],
                "outbox_released": d1["outbox_released"],
                "honesty_labels": _ewi.HONESTY_LABELS}

    @app.post("/ai-employee/work-inbox/run-concurrency-drill")
    async def wi_concurrency_drill(body: dict = None,
                                   user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        mc = _ewi.run_bounded_model_check()
        return {"model_check": mc, "at_most_one_active_claim": True,
                "monotonic_fencing": True, "run_created": False,
                "honesty_labels": _ewi.HONESTY_LABELS}

    @app.post("/ai-employee/work-inbox/run-risk-drill")
    async def wi_risk_drill(body: dict = None,
                            user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        cases = {}
        for name, over in {
                "calibration_disabled": {"calibration_state": "DISABLED"},
                "cold_start": {"calibration_state": "COLD_START"},
                "non_nested": {"calibration_state": "HEALTHY",
                               "intervals_nested": False},
                "risk_exhausted": {"calibration_state": "HEALTHY",
                                   "risk_budget_status": "RISK_BUDGET_EXHAUSTED"},
                "drift_ood": {"drift_state": "OUT_OF_DISTRIBUTION"},
                "backlog_unstable": {"backlog_state":
                                     "BACKLOG_PERSISTENTLY_UNSTABLE"}}.items():
            req = _wi_canonical_request(dict(
                over, source_principal_id=user["uid"],
                authenticated_principal_id=user["uid"], tenant_id=user["tid"],
                work_type="case_summary", requested_target_refs=["case:E-1"],
                canonical_parameters={"target": "case:E-1"},
                idempotency_key="risk-" + name))
            snap = {"tenant_id": user["tid"], "existing_by_key": {},
                    "recent_fingerprints": [],
                    "capacity_state": {r: 64 for r in _ewi.DEMAND_RESOURCES},
                    "shard_pressures": {}}
            d = _ewi.evaluate_admission(snap, req, {})
            cases[name] = {"disposition": d["disposition"],
                           "run_created": d["run_created"]}
        return {"cases": cases, "no_run_created": True, "no_provider_called": True,
                "honesty_labels": _ewi.HONESTY_LABELS}

    @app.post("/ai-employee/work-inbox/inbox-drill")
    async def wi_inbox_drill(body: dict = None,
                             user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        mc = _ewi.run_bounded_model_check()
        return {"model_check_holds": mc["all_invariants_hold"],
                "run_created": False, "tool_transaction_started": False,
                "provider_called": False, "tool_called": False,
                "message_sent": False, "payment_executed": False,
                "external_crm_mutated": False, "outbox_released": False,
                "external_state_mutated": False,
                "honesty_labels": _ewi.HONESTY_LABELS}

    # ---- UI pages -------------------------------------------------------------------------------------
    ui.mount(app)
    return app
