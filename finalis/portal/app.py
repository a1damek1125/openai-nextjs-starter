"""Finalis Portal API — FastAPI over the tested domain core.

UI → these endpoints → domain services (unchanged, 212-test core) →
PortalStore persistence → DbAuditLog (chain in SQL). Providers are the
existing mocks behind real interfaces (env-configurable later).
"""
from __future__ import annotations

import json
import os
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
                 "status": p.status, "case_id": p.case_id}
                for p in crm.promises
                if p.party_id == party_id and p.tenant_id == user["tid"]]

    @app.post("/crm/parties/{party_id}/promises")
    async def crm_add_promise(party_id: str, body: dict,
                              user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        load_crm_party_or_404(party_id, user)
        try:
            promise = crm.record_promise(CustomerPromise(
                tenant_id=user["tid"], party_id=party_id,
                promisor=body.get("promisor", ""),
                what=body.get("what", ""),
                case_id=body.get("case_id")))
        except ValueError as e:
            raise HTTPException(400, str(e))
        crm_store.save_promise(promise)
        return {"id": promise.id, "promisor": promise.promisor}

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

    # ---- UI pages -------------------------------------------------------------------------------------
    ui.mount(app)
    return app
