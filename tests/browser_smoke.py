"""Real browser walkthrough. Optional CHROMIUM_EXECUTABLE for an installed browser."""

import os
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path
import uvicorn
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    with tempfile.TemporaryDirectory() as directory:
        os.environ["APP_STORAGE"] = directory
        live = os.environ.get("BROWSER_MODEL_PROVIDER") == "openai"
        os.environ["MODEL_PROVIDER"] = "openai" if live else "demo"
        from app.main import create_app

        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(create_app(), log_level="warning"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.05)
        errors = []
        screenshot_dir = Path(os.environ.get("SCREENSHOT_DIR", ROOT / "test-results"))
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        try:
            with sync_playwright() as playwright:
                launch = {
                    "headless": True,
                    "args": ["--no-sandbox", "--disable-dev-shm-usage", "--use-gl=angle", "--use-angle=swiftshader", "--disable-gpu"],
                }
                if os.environ.get("CHROMIUM_EXECUTABLE"):
                    launch["executable_path"] = os.environ["CHROMIUM_EXECUTABLE"]
                browser = playwright.chromium.launch(**launch)
                page = browser.new_page(viewport={"width": 1440, "height": 1100})
                page.set_default_timeout(90000 if live else 30000)
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{port}/")
                page.locator("#message").wait_for(state="hidden")
                assert "Apartment 1204" in page.locator("h1").inner_text()
                assert page.locator(".unit-nav").count() == 5
                page.get_by_role("button", name="Prose lease" if live else "Valid lease", exact=True).click()
                page.locator("#message").wait_for(state="hidden")
                assert page.locator(".field").count() == 18
                assert page.locator(".rule .badge.pass").count() == 7
                page.locator('[data-evidence="monthly_rent"]').click()
                assert ("8,500" if live else "Monthly rent: 8500") in page.locator("#evidence-body").inner_text()
                page.locator("#close-evidence").click()
                page.get_by_role("button", name="Use real sample photos").click()
                page.locator("#message").wait_for(state="hidden")
                assert page.locator(".photos img").count() == 2
                assert (
                    "air" in page.locator("#issues").inner_text().lower()
                    if live
                    else "Wall-mounted AC unit" in page.locator("#issues").inner_text()
                )
                page.locator("[data-observation]").last.click()
                page.locator("#observation-condition").select_option("unknown")
                page.locator("#observation-damage").fill("Inspect the housing; visible mark is uncertain")
                page.locator("#review-reason").fill("Owner requests an inspection to resolve visual uncertainty")
                page.locator("#confirm-review").click()
                page.locator("#review-dialog").wait_for(state="hidden")
                page.locator("#message").wait_for(state="hidden")
                assert "Owner assessment" in page.locator("#issues").inner_text()
                page.locator('.issue-card [data-decision="edit"][data-work]').click()
                page.locator("#work-title").fill("Inspect wall AC and corroded coil")
                page.locator("#review-reason").fill("Checked both fixture images and corrected the scope")
                page.locator("#confirm-review").click()
                page.locator("#review-dialog").wait_for(state="hidden")
                page.locator("#message").wait_for(state="hidden")
                assert page.locator(".issue-card .badge.accepted").count() == 1
                for _ in range(18):
                    page.locator('.field:has(.badge.pending) [data-decision="accepted"]').first.click()
                    page.locator("#review-reason").fill("Verified this field against the sample source")
                    page.locator("#confirm-review").click()
                    page.locator("#review-dialog").wait_for(state="hidden")
                    page.locator("#message").wait_for(state="hidden")
                for _ in range(2):
                    page.locator('.flag:has(.badge.pending) [data-decision="accepted"]').first.click()
                    page.locator("#review-reason").fill("Inspected original fixture signature marker")
                    page.locator("#confirm-review").click()
                    page.locator("#review-dialog").wait_for(state="hidden")
                    page.locator("#message").wait_for(state="hidden")
                page.locator("#activate").click()
                page.locator("#message").wait_for(state="hidden")
                assert page.locator("#status").inner_text() == "OCCUPIED"
                page.get_by_role("button", name="Use all four photos").click()
                page.locator("#message").wait_for(state="hidden")
                assert page.locator(".photos img").count() == 6
                assert page.locator(".issue-card").count() == 2
                assert "heater" in page.locator("#issues").inner_text().lower()
                assert any(word in page.locator("#issues").inner_text().lower() for word in ("faucet", "tap", "sink"))
                page.evaluate("window.scrollTo(0,0)")
                page.screenshot(path=str(screenshot_dir / "desktop.png"), full_page=False)
                with page.expect_download() as downloaded:
                    page.locator("#export").click()
                assert downloaded.value.suggested_filename == "MC-B-1204-record.json"
                downloaded.value.save_as(str(screenshot_dir / "unit-record.json"))
                page.locator("[data-audit]").first.click()
                page.locator("#message").wait_for(state="hidden")
                assert "lease_activated" in page.locator("#evidence-body").inner_text()
                page.locator("#close-evidence").click()
                page.evaluate("window.scrollTo(0,700)")
                page.screenshot(path=str(screenshot_dir / "review-detail.png"), full_page=False)
                page.set_viewport_size({"width": 390, "height": 844})
                page.evaluate("window.scrollTo(0,0)")
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                page.screenshot(path=str(screenshot_dir / "mobile.png"), full_page=False)
                assert not errors, errors
                browser.close()
                print(
                    "Browser walkthrough PASS: lease upload, evidence, 7 rules, two-photo and four-photo issues, work-order edit, 18 field approvals, 2 flag approvals, occupancy, audit, export and mobile layout; no JavaScript errors."
                )
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            listener.close()


if __name__ == "__main__":
    main()
