"""Browser E2E — the portal driven through a real Chromium browser.

Starts uvicorn on a seeded SQLite DB, then via Playwright: login → dashboard
loads from real APIs → open case → run loop → request photos → follow the
client upload link → upload → missing item resolves → close WON → audit
chain shows VALID. Skips cleanly if Playwright/Chromium are unavailable.
"""
import os
import socket
import subprocess
import sys
import time

import pytest

playwright = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402

PORT = 8765
BASE = f"http://127.0.0.1:{PORT}"


def _port_open() -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", PORT)) == 0


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    if _port_open():   # a zombie from a previous run would poison the test
        pytest.fail(f"port {PORT} already in use — kill stale servers first")
    db = str(tmp_path_factory.mktemp("e2e") / "portal.db")
    env = {**os.environ, "FINALIS_DB": db}
    proc = subprocess.Popen(
        [sys.executable, "-m", "finalis.portal.serve", db, str(PORT)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    for _ in range(60):
        if _port_open():
            break
        time.sleep(0.25)
    else:
        proc.kill()
        pytest.skip("server did not start")
    yield BASE
    proc.kill()
    proc.wait(timeout=5)


def _chromium_path() -> str | None:
    import glob
    for pattern in ("/opt/pw-browsers/chromium-*/chrome-linux/chrome",
                    "/opt/pw-browsers/chromium/chrome-linux/chrome"):
        hits = glob.glob(pattern)
        if hits:
            return hits[0]
    return None


@pytest.fixture(scope="module")
def page(server):
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(executable_path=_chromium_path())
        except Exception as e:  # chromium missing in this environment
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page()
        yield page
        browser.close()


def test_full_portal_flow_in_browser(server, page):
    # 1. Login page → sign in with demo credentials.
    page.goto(server + "/")
    page.fill("#email", "owner@demo.finalis")
    page.fill("#password", "demo1234")
    page.click("#login-form button[type=submit]")
    page.wait_for_url("**/portal")

    # 2. Dashboard renders from real APIs (summary cards + case list).
    page.wait_for_selector("#app:not([hidden])", timeout=15000)
    assert page.locator("#summary-cards .card").count() >= 4
    assert "Heat pump install" in page.content()

    # 3. Open the stuck case with missing photos.
    page.wait_for_selector("#cases table", timeout=15000)
    rows = page.locator("#cases table tr", has_text="AC replacement")
    rows.locator("button").click()
    page.wait_for_selector("#case-title")
    assert "Anna Nowak" in page.text_content("#case-detail")
    assert "installation_photo" in page.text_content("#case-detail")
    # Audit chain badge is VALID.
    assert "VALID" in page.text_content("#case-detail")

    # 4. Run the completion loop → next action shown in business language.
    page.click("text=Run completion loop")
    page.wait_for_selector("#case-msg:has-text('Next action')")
    assert "send_photo_request" in page.text_content("#case-msg")

    # 5. Request photos → upload link appears (mock WhatsApp send).
    page.click("text=Request photos")
    page.wait_for_selector("#upload-url", timeout=15000)
    href = page.get_attribute("#upload-url", "href")
    assert href.startswith("/u/")

    # 6. Client-side: open the upload page and upload the photo.
    page.goto(server + href)
    page.wait_for_selector("#form:not([hidden])", timeout=10000)
    assert "installation photo" in page.text_content("#status")
    page.click("#upload-btn")
    page.wait_for_selector("#done:not([hidden])")

    # 7. Back to the portal: the missing item is resolved.
    page.goto(server + "/portal")
    page.wait_for_selector("#app:not([hidden])", timeout=15000)
    page.locator("#cases table tr", has_text="AC replacement") \
        .locator("button").click()
    page.wait_for_selector("#case-title")
    detail = page.text_content("#case-detail")
    assert "boiler-nameplate.jpg" in detail          # document attached
    assert "Missing:" in detail
    missing_line = page.text_content("#case-detail")
    assert "installation_photo" not in missing_line.split("Promises:")[0]

    # 8. Illegal direct close is BLOCKED in the browser (state machine holds).
    page.click("text=Close WON")
    page.wait_for_selector("#case-msg:has-text('Error')", timeout=10000)

    # 9. Walk the LEGAL path through the UI transition control:
    #    WAITING_FOR_DOCUMENTS → DOCUMENT_ANALYSIS → QUOTE_PREPARATION →
    #    OFFER_SENT → WON.
    for state in ["DOCUMENT_ANALYSIS", "QUOTE_PREPARATION", "OFFER_SENT"]:
        page.select_option("#state-select", state)
        page.click("text=Transition")
        page.wait_for_selector(f"#case-state:has-text('{state}')",
                               timeout=10000)
    page.click("text=Close WON")
    page.wait_for_selector("#case-state:has-text('WON')", timeout=10000)

    # 10. Audit stays VALID after the full journey.
    assert "VALID" in page.text_content("#case-detail")


# ---------------------------------------------------------------------------
# W3 — Portal Wiring browser E2E: admin/RBAC, scheduling, governance UI.
# Tests share the module-scoped server+browser; each starts with a login.
# ---------------------------------------------------------------------------
def _login(page, server, email="owner@demo.finalis"):
    page.goto(server + "/")
    page.fill("#email", email)
    page.fill("#password", "demo1234")
    page.click("#login-form button[type=submit]")
    page.wait_for_url("**/portal")
    page.wait_for_selector("#app:not([hidden])", timeout=15000)


def test_admin_rbac_ui_in_browser(server, page):
    _login(page, server)

    # Tenant / role / permissions visible.
    page.wait_for_selector("#admin-me:has-text('demo-hvac')", timeout=15000)
    assert "owner" in page.text_content("#me-role")
    assert "permissions" in page.text_content("#admin-me")
    assert "re-checked server-side" in page.content()

    # User list from the real API.
    page.wait_for_selector("#admin-users table")
    users = page.text_content("#admin-users")
    for email in ("owner@demo.finalis", "manager@demo.finalis",
                  "viewer@demo.finalis"):
        assert email in users
    assert "demo1234" not in page.content()          # no secrets anywhere

    # Invite (honestly labeled simulated).
    assert "simulated email" in page.text_content("#invite-btn")
    page.fill("#invite-email", "invited@demo.finalis")
    page.click("#invite-btn")
    page.wait_for_selector("#invite-msg:has-text('Invitation pending')")

    # Role change from the UI: manager → operator (server persists it).
    row = page.locator("#admin-users tr", has_text="manager@demo.finalis")
    row.locator("select").select_option("operator")
    row.locator("button").click()
    page.wait_for_selector("#invite-msg:has-text('Role updated to operator')")
    page.wait_for_selector(
        "#admin-users tr:has-text('manager@demo.finalis'):has-text('operator')")

    # Access log renders real decisions.
    assert "ALLOW" in page.text_content("#admin-logs")


def test_scheduling_ui_full_flow_in_browser(server, page):
    _login(page, server)
    page.wait_for_selector("#sched-book:not([hidden])", timeout=15000)

    # Honest labels: mocks, restart caveat, providers not connected.
    sched_text = " ".join(page.text_content("#sched-section").split())
    assert "mock" in sched_text
    assert "persisted locally" in sched_text     # v4: survives restart
    assert "BLOCKED_BY_CREDENTIALS" in sched_text

    # 1. Availability from the API → book a VIDEO_CALL.
    page.select_option("#sched-type", "VIDEO_CALL")
    page.fill("#sched-day", "2030-03-13")
    page.click("#find-slots")
    page.wait_for_selector("#sched-slots button", timeout=10000)
    page.locator("#sched-slots button").first.click()
    page.wait_for_selector("#booked-status", timeout=10000)
    assert page.text_content("#booked-status") == "PENDING_CLIENT_CONFIRMATION"
    msg = page.text_content("#sched-msg")
    assert "meet.finalis.example" in msg and "mock" in msg
    confirm_href = page.get_attribute("#confirm-link", "href")
    assert confirm_href.startswith("/confirm/")

    # 2. Client confirms on the public page (no auth needed — same
    #    navigation pattern as the upload-link flow above).
    page.goto(server + confirm_href)
    page.click("#confirm-btn")
    page.wait_for_selector("#done:not([hidden])", timeout=10000)

    # 3. Portal shows the confirmed appointment; completing a VIDEO_CALL
    #    must NOT claim the case is fulfilled (fulfillment untouched).
    page.goto(server + "/portal")
    page.wait_for_selector("#app:not([hidden])", timeout=15000)
    page.wait_for_selector(
        "#sched-appts tr:has-text('VIDEO_CALL'):has-text('CONFIRMED')",
        timeout=10000)
    page.locator("#sched-appts tr", has_text="VIDEO_CALL").first \
        .locator("button", has_text="Complete").click()
    page.wait_for_selector("#sched-msg:has-text('complete → COMPLETED')",
                           timeout=10000)
    assert "WON_COMPLETED" not in page.text_content("#sched-msg")

    # 4. Reschedule + cancel-with-reason + no-show via UI dialogs.
    page.select_option("#sched-type", "CALLBACK")
    page.click("#find-slots")
    page.wait_for_selector("#sched-slots button", timeout=10000)
    page.locator("#sched-slots button").first.click()
    page.wait_for_selector(
        "#sched-appts tr:has-text('CALLBACK'):has-text('CONFIRMED')",
        timeout=10000)
    cb_row = page.locator("#sched-appts tr", has_text="CALLBACK").first
    page.once("dialog", lambda d: d.accept("2030-03-14T11:00:00"))
    cb_row.locator("button", has_text="Reschedule").click()
    page.wait_for_selector("#sched-appts tr:has-text('RESCHEDULED')",
                           timeout=10000)
    page.once("dialog", lambda d: d.accept("client asked to cancel"))
    page.locator("#sched-appts tr", has_text="RESCHEDULED").first \
        .locator("button", has_text="Cancel").click()
    page.wait_for_selector("#sched-appts tr:has-text('CANCELLED_BY_COMPANY')",
                           timeout=10000)
    # Fresh callback for the no-show path.
    page.click("#find-slots")
    page.wait_for_selector("#sched-slots button", timeout=10000)
    page.locator("#sched-slots button").first.click()
    page.wait_for_selector(
        "#sched-appts tr:has-text('CALLBACK'):has-text('CONFIRMED')",
        timeout=10000)
    page.locator("#sched-appts tr:has-text('CALLBACK'):has-text('CONFIRMED')") \
        .first.locator("button", has_text="No-show").click()
    page.wait_for_selector("#sched-appts tr:has-text('NO_SHOW')",
                           timeout=10000)

    # 5. Technician visit completes fulfillment → WON_COMPLETED.
    #    Deal/payment prep uses the portal's own mock lifecycle endpoints,
    #    driven from the browser session (fetch with the session token).
    page.evaluate("""async () => {
      const caseId = document.getElementById('sched-case').value;
      const H = {'Authorization': 'Bearer ' +
                 localStorage.getItem('finalis_token'),
                 'Content-Type': 'application/json'};
      for (const step of ['accept-offer', 'invoice', 'payment']) {
        const r = await fetch(`/cases/${caseId}/lifecycle/${step}`,
                              {method: 'POST', headers: H, body: '{}'});
        if (!r.ok) throw new Error(step);
      }
    }""")
    page.select_option("#sched-type", "TECHNICIAN_VISIT")
    page.fill("#sched-resource", "tech-1")
    page.click("#find-slots")
    page.wait_for_selector("#sched-slots button", timeout=10000)
    page.locator("#sched-slots button").first.click()
    page.wait_for_selector("#sched-appts tr:has-text('TECHNICIAN_VISIT')",
                           timeout=10000)
    page.locator("#sched-appts tr", has_text="TECHNICIAN_VISIT").first \
        .locator("button", has_text="Complete").click()
    page.wait_for_selector("#sched-msg:has-text('WON_COMPLETED')",
                           timeout=10000)


def test_governance_ui_in_browser(server, page):
    _login(page, server)
    page.wait_for_selector("#gov-section:not([hidden])", timeout=15000)

    # Traces area is honestly labeled while the producer is scaffolded.
    assert "SCAFFOLDED_ONLY" in page.text_content("#gov-traces-note")
    page.wait_for_selector("#gov-traces:has-text('No agent traces yet')")

    # Produce a REAL rate-limit block through the UI: the second photo
    # request within the cooldown is refused by the ACE spam guard.
    page.locator("#cases table tr", has_text="Boiler service") \
        .locator("button").click()
    page.wait_for_selector("#case-title")
    page.click("text=Request photos")
    page.wait_for_selector("#case-msg:has-text('Upload link')",
                           timeout=10000)
    page.click("text=Request photos")
    page.wait_for_selector("#case-msg:has-text('rate_limited')",
                           timeout=10000)

    # The governance section explains the block in business language.
    page.evaluate("loadGov()")
    page.wait_for_selector(
        "#gov-blocked:has-text('contact limit or cooldown')", timeout=10000)
    assert "policy_denied" not in page.text_content("#gov-blocked")


# ---------------------------------------------------------------------------
# Q-D — Quote Builder browser E2E: owner flow, approval path, negatives,
# restricted users. Real clicks through the Q-C UI over the Q-B APIs.
# ---------------------------------------------------------------------------
def _new_quote_with_line(page, *, cost="1000", price="2000", **fills):
    """Create draft + approved terms + one line through the UI."""
    page.wait_for_selector("#quote-create:not([hidden])", timeout=15000)
    page.click("#quote-create-btn")
    page.wait_for_selector("#quote-state:has-text('DRAFT')", timeout=10000)
    page.click("text=Set assumptions/exclusions/terms")
    page.wait_for_selector("text=approved terms template set")
    page.fill("#ql-desc", fills.get("desc", "heat pump 12kW"))
    page.fill("#ql-cost", cost)
    page.fill("#ql-price", price)
    if fills.get("discount"):
        page.fill("#ql-discount", fills["discount"])
    if fills.get("reason"):
        page.fill("#ql-reason", fills["reason"])
    page.click("#ql-add")
    page.wait_for_selector(
        f"#quote-detail td:has-text('{fills.get('desc', 'heat pump 12kW')}')")


def test_quote_owner_flow_in_browser(server, page):
    _login(page, server)

    # Section banner carries the honesty labels.
    page.wait_for_selector("#quotes-section", timeout=15000)
    banner = " ".join(page.text_content("#quotes-section").split())
    for label in ("MOCKED_AND_TESTED", "SCAFFOLDED_ONLY",
                  "Change-order approval API is MISSING",
                  "no real Stripe / invoicing / payment provider",
                  "accepted quote does not mean the case is completed"):
        assert label in banner, label

    # Case detail links into the quote section.
    page.locator("#cases table tr", has_text="Heat pump install") \
        .locator("button").click()
    page.wait_for_selector("#case-title")
    page.click("text=Quotes…")

    # Draft → terms → line → deposit → calculate.
    _new_quote_with_line(page)
    page.click("text=Set 30% deposit schedule")
    page.wait_for_selector("text=Deposit schedule set")
    page.click("text=Calculate")
    page.wait_for_selector("#calc-totals", timeout=10000)
    totals = page.text_content("#calc-totals")
    assert "2000.00" in totals and "460.00" in totals \
        and "2460.00" in totals and "mock" in totals
    gates = page.text_content("#calc-gates")
    for gate in ("readiness", "margin", "discount"):
        assert gate in gates, gate
    assert "SAFE" in gates and "READY" in gates
    scores = " ".join(page.text_content("#calc-scores").split())
    assert "Price confidence" in scores and "Evidence coverage" in scores
    assert "SCAFFOLDED_ONLY" in scores          # risk/clarity labeled honest
    assert "0.5000" in page.text_content("#quote-detail")  # 50% margin shown

    # Send → immutable message; line editor gone.
    page.click("button:has-text('Send')")
    page.wait_for_selector("#quote-state:has-text('SENT')", timeout=10000)
    assert "cannot be edited. Create a revision" in \
        page.text_content("#quote-state-help")
    assert page.locator("#quote-line-form").count() == 0

    # Accept → payment requirements + NOT completed + change order path.
    page.click("text=Client accepts (simulated)")
    page.wait_for_selector("#quote-state:has-text('ACCEPTED')",
                           timeout=10000)
    msg = " ".join(page.text_content("#quote-msg").split())
    assert "NOT completed" in msg and "WON_NOT_FULFILLED" in msg
    assert "deposit 738.00" in msg
    detail = page.text_content("#quote-detail")
    assert "fulfillment blocked until paid" in detail
    assert "Use a change order" in page.text_content("#quote-state-help")
    page.fill("#co-desc", "extra duct run")
    page.fill("#co-price", "450")
    page.fill("#co-cost", "300")
    page.click("#co-add")
    page.wait_for_selector("#quote-detail li:has-text('extra duct run')",
                           timeout=10000)
    detail = page.text_content("#quote-detail")
    assert "PENDING_APPROVAL" in detail
    assert "0.3333" in detail                   # margin impact of the delta
    assert "approval API is MISSING" in detail

    # Mock PDF + events.
    page.click("text=Generate mock PDF")
    page.wait_for_selector("#pdf-label:has-text('MOCK_PDF_PROVIDER')",
                           timeout=10000)
    assert "not a real PDF" in page.text_content("#pdf-label")
    events = page.text_content("#quote-events")
    assert "QUOTE_ACCEPTED" in events and "QUOTE_SENT" in events


def test_quote_approval_and_self_approval_in_browser(server, page):
    # Restore the manager role (an earlier admin test demoted it) —
    # through the real role-change UI, which is extra coverage by itself.
    _login(page, server)
    page.wait_for_selector("#admin-users table", timeout=15000)
    row = page.locator("#admin-users tr", has_text="manager@demo.finalis")
    row.locator("select").select_option("manager")
    row.locator("button").click()
    page.wait_for_selector("#invite-msg:has-text('Role updated to manager')")

    # Manager drafts a quote with an over-threshold discount.
    _login(page, server, email="manager@demo.finalis")
    _new_quote_with_line(page, discount="500", reason="negotiation")
    page.click("text=Calculate")
    page.wait_for_selector("#calc-gates", timeout=10000)
    gates = page.text_content("#calc-gates")
    assert "REQUIRE_APPROVAL" in gates
    assert "exceeds the auto-approval threshold" in gates  # business words
    quote_ref = page.text_content("#quote-detail h3")[6:14]

    # Self-approval refused; send refused while approval is pending.
    page.click("button:has-text('Approve')")
    page.wait_for_selector("#quote-msg:has-text('own quote')")
    page.click("button:has-text('Send')")
    page.wait_for_selector("#quote-msg:has-text('Refused')")
    page.wait_for_selector("#quote-state:has-text('PRICE_CALCULATED')")

    # Owner approves (different human), then the quote can be sent.
    _login(page, server)
    page.wait_for_selector("#quote-list table", timeout=15000)
    page.locator("#quote-list tr", has_text=quote_ref) \
        .locator("button").click()
    page.wait_for_selector("button:has-text('Approve')", timeout=10000)
    page.click("button:has-text('Approve')")
    page.wait_for_selector("#quote-state:has-text('APPROVED')",
                           timeout=10000)
    page.click("button:has-text('Send')")
    page.wait_for_selector("#quote-state:has-text('SENT')", timeout=10000)


def test_quote_negative_paths_in_browser(server, page):
    _login(page, server)
    _new_quote_with_line(page, desc="boiler swap")
    page.click("text=Calculate")
    page.wait_for_selector("#calc-totals", timeout=10000)
    page.click("button:has-text('Send')")
    page.wait_for_selector("#quote-state:has-text('SENT')", timeout=10000)

    # Decline without a reason → readable refusal, state unchanged.
    page.once("dialog", lambda d: d.accept(""))
    page.click("text=Client declines…")
    page.wait_for_selector("#quote-msg:has-text('requires a reason')",
                           timeout=10000)
    page.wait_for_selector("#quote-state:has-text('SENT')")

    # Expire → the UI stops inviting acceptance (button gone), offers
    # revision instead (the API 409 for accept-after-expiry is API-tested).
    page.click("button:has-text('Expire')")
    page.wait_for_selector("#quote-state:has-text('EXPIRED')",
                           timeout=10000)
    assert page.locator("text=Client accepts (simulated)").count() == 0
    page.click("button:has-text('Revise')")
    page.wait_for_selector("#quote-detail h3:has-text('v2')",
                           timeout=10000)
    page.wait_for_selector("#quote-state:has-text('DRAFT')")


def test_quote_viewer_and_cross_tenant_in_browser(server, page):
    # Viewer: read-only — no create, no pricing admin, no action buttons.
    _login(page, server, email="viewer@demo.finalis")
    page.wait_for_selector("#quote-list table", timeout=15000)
    assert page.is_hidden("#quote-create")
    assert page.is_hidden("#pricing-admin")
    page.locator("#quote-list button").first.click()
    page.wait_for_selector("#quote-state", timeout=10000)
    detail = page.text_content("#quote-detail")
    for forbidden in ("Calculate", "Approve", "Send",
                      "Client accepts", "Add line"):
        assert forbidden not in detail, forbidden
    assert "not editable" in detail or "change orders" in detail

    # Other tenant sees no quotes at all.
    _login(page, server, email="owner@other.finalis")
    page.wait_for_selector("#quote-list:has-text('No quotes yet')",
                           timeout=15000)


def test_viewer_restricted_ui_in_browser(server, page):
    _login(page, server, email="viewer@demo.finalis")
    page.wait_for_selector("#admin-denied:not([hidden])", timeout=15000)

    # Admin management, governance, and booking controls are hidden;
    # the restriction message is in business language.
    assert "cannot manage users" in page.text_content("#admin-denied")
    assert page.is_hidden("#admin-manage")
    assert page.is_hidden("#admin-logs-wrap")
    assert page.is_hidden("#gov-section")
    assert page.is_hidden("#sched-book")

    # Appointment list is read-only: no operation buttons rendered.
    page.wait_for_selector("#sched-appts table", timeout=10000)
    appts = page.text_content("#sched-appts")
    for forbidden in ("Complete", "No-show", "Reschedule", "Cancel"):
        assert forbidden not in appts
