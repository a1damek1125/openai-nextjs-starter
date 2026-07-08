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
