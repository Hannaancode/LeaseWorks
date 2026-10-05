"""Browser failure/recovery and untrusted text checks; always uses the offline provider."""

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
        os.environ["MODEL_PROVIDER"] = "demo"
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
        try:
            with sync_playwright() as p:
                launch = {
                    "headless": True,
                    "args": ["--no-sandbox", "--disable-dev-shm-usage", "--use-gl=angle", "--use-angle=swiftshader", "--disable-gpu"],
                }
                if os.environ.get("CHROMIUM_EXECUTABLE"):
                    launch["executable_path"] = os.environ["CHROMIUM_EXECUTABLE"]
                browser = p.chromium.launch(**launch)
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                page.set_default_timeout(30000)
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(f"http://127.0.0.1:{port}/")
                page.locator("#message").wait_for(state="hidden")
                page.get_by_role("button", name="With problems", exact=True).click()
                page.locator("#message").wait_for(state="hidden")
                assert page.locator(".rule .badge.fail").count() == 5
                page.locator("#activate").click()
                page.locator("#message.error").wait_for(state="visible")
                assert "Review required" in page.locator("#message").inner_text()
                assert page.locator("#status").inner_text() == "AVAILABLE"
                # Cancel and Escape must not record a decision.
                page.locator('[data-field="tenant"][data-decision="accepted"]').click()
                page.locator("#cancel-review").click()
                page.locator("#review-dialog").wait_for(state="hidden")
                page.locator('[data-field="tenant"][data-decision="accepted"]').click()
                page.keyboard.press("Escape")
                page.locator("#review-dialog").wait_for(state="hidden")
                assert page.locator('.field:has([data-field="tenant"]) .badge.pending').count() == 1
                # Invalid correction stays uncommitted and can be retried.
                page.locator('[data-field="deposit_amount"][data-decision="edit"]').click()
                page.locator("#corrected-value").fill("-1")
                page.locator("#review-reason").fill("Try invalid correction")
                page.locator("#confirm-review").click()
                page.locator("#message.error").wait_for(state="visible")
                assert page.locator("#review-dialog").is_visible()
                page.locator("#corrected-value").fill("8500")
                page.locator("#confirm-review").click()
                page.locator("#review-dialog").wait_for(state="hidden")
                page.locator("#message").wait_for(state="hidden")
                assert page.locator('.field:has([data-field="deposit_amount"]) .field-value').inner_text() == "8500"
                # Script/markup in uploads and owner changes must remain literal text.
                payload = '<img src=x onerror="window.UNTRUSTED_EXECUTED=1"><script>window.UNTRUSTED_EXECUTED=2</script>'
                raw = (ROOT / "samples/lease_valid.txt").read_text().replace("Tenant: Sample Tenant One", "Tenant: " + payload)
                page.locator("#lease-file").set_input_files({"name": "untrusted.txt", "mimeType": "text/plain", "buffer": raw.encode()})
                page.get_by_role("button", name="Extract lease", exact=True).click()
                page.locator("#message").wait_for(state="hidden")
                assert payload in page.locator('.field:has([data-field="tenant"]) .field-value').inner_text()
                assert page.locator("#lease img, #lease script").count() == 0
                page.locator('[data-source="all"]').click()
                assert page.locator("#evidence-body img, #evidence-body script").count() == 0
                page.locator("#close-evidence").click()
                page.locator("#photos").set_input_files(str(ROOT / "samples/live/wall_ac.jpg"))
                page.locator("#report").fill(payload)
                page.get_by_role("button", name="Assess and draft", exact=True).click()
                page.locator("#message").wait_for(state="hidden")
                assert payload in page.locator("#issues").inner_text()
                assert page.locator('#issues script, #issues img[src="x"]').count() == 0
                assert page.evaluate("window.UNTRUSTED_EXECUTED") is None
                # Recovery after a network failure must leave controls usable.
                page.route("**/api/leases", lambda route: route.abort() if route.request.method == "POST" else route.continue_())
                page.get_by_role("button", name="Valid lease", exact=True).click()
                page.locator("#message.error").wait_for(state="visible")
                assert page.get_by_role("button", name="Valid lease", exact=True).is_enabled()
                page.unroute("**/api/leases")
                page.get_by_role("button", name="Valid lease", exact=True).click()
                page.locator("#message").wait_for(state="hidden")
                assert page.locator(".rule .badge.pass").count() == 7
                # Narrow and tablet layouts, with long untrusted text already present.
                for width in [320, 390, 768, 1440]:
                    page.set_viewport_size({"width": width, "height": 900})
                    assert page.evaluate("document.documentElement.scrollWidth<=window.innerWidth"), width
                assert not errors, errors
                browser.close()
                print(
                    "Adversarial browser PASS: failed approval, cancel/Escape, invalid correction and retry, literal untrusted text, network recovery, four viewport widths; no JavaScript errors."
                )
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            listener.close()


if __name__ == "__main__":
    main()
