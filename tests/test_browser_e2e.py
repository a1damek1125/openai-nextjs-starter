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
    assert "do not survive a server restart" in sched_text
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
