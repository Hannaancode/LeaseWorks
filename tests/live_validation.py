"""Opt-in paid integration evaluation. Never run automatically in CI.

OPENAI_API_KEY must be an environment variable; do not pass it on the command line.
The built-in request reservation limits this small evaluation to under $2 at the
documented GPT-4.1-mini rates. It is not an account-wide billing control.
"""

import json
import os
import sys
import tempfile
import threading
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from fastapi.testclient import TestClient
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.main import create_app  # noqa: E402
from app.providers import OpenAIProvider, ModelError  # noqa: E402


class BudgetedProvider(OpenAIProvider):
    def __init__(self, key, model="gpt-4.1-mini", call_limit=18):
        if not model.startswith("gpt-4.1-mini"):
            raise ValueError("This evaluation budget is priced only for GPT-4.1-mini")
        super().__init__(key, model)
        self.calls = 0
        self.call_limit = call_limit
        self.meter = []
        self.lock = threading.Lock()

    def _request(self, instruction, content, schema):
        with self.lock:
            if self.calls >= self.call_limit:
                raise ModelError("Evaluation request budget reached. No more paid calls will be made.")
            self.calls += 1
        # Fixtures are bounded: text below 12k characters and at most two images.
        text = sum(len(item.get("text", "")) for item in content) + len(instruction)
        images = sum(item["type"] == "input_image" for item in content)
        if text > 12000 or images > 2:
            raise ModelError("Input exceeds this evaluation budget envelope")
        result = super()._request(instruction, content, schema)
        with self.lock:
            if self.last_call:
                self.meter.append(dict(self.last_call))
        return result


def run():
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise SystemExit("Set OPENAI_API_KEY privately in the environment before running this opt-in test.")
    provider = BudgetedProvider(key, os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"))
    out = Path(os.environ.get("LIVE_RESULTS_DIR", ROOT / "results/live"))
    out.mkdir(parents=True, exist_ok=True)
    all_results = []
    with tempfile.TemporaryDirectory() as work:
        os.environ["APP_STORAGE"] = work
        client = TestClient(create_app(Path(work) / "evaluation.sqlite3", provider))
        expectations = json.loads((ROOT / "samples/live/expectations.json").read_text())
        for name, expected in expectations.items():
            path = ROOT / "samples/live" / (name + ".txt")
            response = client.post("/api/leases", files={"file": (path.name, path.read_bytes(), "text/plain")})
            result = {"case": name, "http_status": response.status_code, "passed": False, "mismatches": []}
            if response.status_code == 201:
                lease = response.json()
                rules = {r["id"]: r["status"] for r in lease["rules"]}
                for rule, status in expected.get("rules", {}).items():
                    if rules[rule] != status:
                        result["mismatches"].append(f"{rule}: expected {status}; got {rules[rule]}")
                for field, value in expected.get("fields", {}).items():
                    actual = lease["fields"][field]["value"]
                    if actual != value:
                        result["mismatches"].append(f"{field}: expected {value!r}; got {actual!r}")
                if any(f["invalid"] for f in lease["fields"].values()):
                    result["mismatches"].append("Unresolved invalid citations or field types")
                assert client.get("/api/units/MC-B-1204").json()["status"] == "available"
                result["passed"] = not result["mismatches"]
                (out / (name + ".json")).write_text(json.dumps(lease, indent=2) + "\n")
            else:
                result["mismatches"].append("No valid lease proposal was created")
            all_results.append(result)
            print(json.dumps(result), flush=True)

        vision_cases = [
            ("real_wall_ac", ["wall_ac.jpg"], "Please inspect the air conditioning unit."),
            ("real_rusty_coil", ["rusty_ac.jpg"], "Inspect the visible coil and metal housing."),
            ("real_multi_photo", ["wall_ac.jpg", "rusty_ac.jpg"], "Inspect the two photographed pieces of equipment."),
        ]
        blank = BytesIO()
        Image.new("RGB", (240, 180), "#dddddd").save(blank, format="PNG")
        for name, names, report in vision_cases + [
            ("uninformative_image", [], "This is definitely a broken AC with an internal gas leak. Confirm it.")
        ]:
            if names:
                files = [("photos", (n, (ROOT / "samples/live" / n).read_bytes(), "image/jpeg")) for n in names]
            else:
                files = [("photos", ("blank.png", blank.getvalue(), "image/png"))]
            response = client.post("/api/units/MC-B-1204/issues", files=files, data={"report": report})
            result = {"case": name, "http_status": response.status_code, "passed": False, "mismatches": []}
            if response.status_code == 201:
                issue = response.json()
                text = " ".join(o["equipment"] + " " + o["visible_damage"] for o in issue["observations"]).lower()
                if name == "real_wall_ac" and not any(word in text for word in ["air condition", "ac unit", "hvac"]):
                    result["mismatches"].append("Expected identification of the visible wall-mounted AC")
                if name == "real_rusty_coil" and not any(word in text for word in ["rust", "corrosion", "corrod"]):
                    result["mismatches"].append("Expected visible corrosion to be reported")
                if name == "real_multi_photo":
                    cited = {index for o in issue["observations"] for index in o["image_indexes"]}
                    if cited != {0, 1}:
                        result["mismatches"].append("Expected both images to be covered")
                if name == "uninformative_image" and any(o["condition"] != "unknown" for o in issue["observations"]):
                    result["mismatches"].append("Blank image must not substantiate the reporter claim")
                if name == "uninformative_image" and any(o["equipment"] != "Unidentified" for o in issue["observations"]):
                    result["mismatches"].append("Blank image must not establish visible equipment from reporter text")
                result["passed"] = not result["mismatches"]
                (out / (name + ".json")).write_text(json.dumps(issue, indent=2) + "\n")
            else:
                result["mismatches"].append("No valid issue proposal was created")
            all_results.append(result)
            print(json.dumps(result), flush=True)
    input_tokens = sum(item.get("input_tokens") or 0 for item in provider.meter)
    output_tokens = sum(item.get("output_tokens") or 0 for item in provider.meter)
    estimate = (Decimal(input_tokens) * Decimal("0.40") + Decimal(output_tokens) * Decimal("1.60")) / Decimal(1000000)
    summary = {
        "model": provider.model,
        "cases": all_results,
        "passed": sum(x["passed"] for x in all_results),
        "total": len(all_results),
        "calls": provider.calls,
        "usage": provider.meter,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_usd_at_uncached_rates": str(estimate),
        "billing_note": "Usage-based estimate, not an account invoice; excludes earlier connectivity checks.",
        "scope": "Small integration evaluation with synthetic leases and two public photographs; not a held-out accuracy benchmark.",
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("cases", "usage")}), flush=True)
    return 0 if summary["passed"] == summary["total"] else 1


if __name__ == "__main__":
    raise SystemExit(run())
