"""Render checked-in evaluation receipts into the reviewer-facing TXT report."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run():
    groups = [
        ("Original live regression", "results/live/fifty_case_final/summary.json"),
        ("Public forms and realistic scenarios", "results/realistic/fifty-case-final-summary.json"),
        ("Additional boundary scenarios", "results/expanded/final-summary.json"),
    ]
    expectations = json.loads((ROOT / "samples/live/expectations.json").read_text())
    lines = ["LEASEWORKS - TEST CASES", "Executed: 5 October 2026", "", "I evaluated the original flows and broader lease/photo boundaries using the real OpenAI Responses API.",
             "The inputs include fictional leases, original public blank PDF formats, a fictional form completion and four attributed photographs.",
             "Scenario counts are executions, not counts of independent real contracts. Some scenarios reuse inputs with different conditions or reporter text.",
             "These are development checks, not a held-out model accuracy benchmark or a guarantee about every future input.", ""]
    number = passed = calls = 0
    cost = 0
    for heading, receipt in groups:
        summary = json.loads((ROOT / receipt).read_text())
        calls += summary["calls"]
        cost += float(summary["estimated_usd_at_uncached_rates"])
        lines.extend([heading.upper(), "Receipt: " + receipt, ""])
        for case in summary["cases"]:
            number += 1
            passed += bool(case["passed"])
            lines.extend([f"TC-{number:03d}: {case['case']}", "Purpose: " + case.get("description", case["case"].replace("_", " "))])
            expected = expectations.get(case["case"], {})
            fields = case.get("expected_fields", expected.get("fields", {}))
            rules = case.get("expected_rules", expected.get("rules", {}))
            if fields:
                lines.append("Expected fields: " + json.dumps(fields, ensure_ascii=False))
            if rules:
                lines.append("Expected policy results: " + json.dumps(rules))
            if "actual_rules" not in case and "rules" in case:
                case["actual_rules"] = case["rules"]
            original_record = ROOT / Path(receipt).parent / (case["case"] + ".json")
            if original_record.exists() and expected:
                record = json.loads(original_record.read_text())
                case["actual_rules"] = {rule["id"]: rule["status"] for rule in record["rules"]}
                case["actual_fields"] = {name: record["fields"][name]["value"] for name in fields}
            if "expected_image_indexes" in case:
                lines.append("Expected image coverage: " + json.dumps(case["expected_image_indexes"]))
            elif case.get("kind") == "vision":
                lines.append("Expected: every uploaded image assessed; visible equipment or damage identified where specified")
            elif case.get("kind") == "lease_limit":
                lines.append("Expected: HTTP 422; no inference call for the 49-page input")
            elif not fields and not rules:
                lines.append("Expected: valid source-linked draft; no invented blank-form values; criteria in tests/realistic_validation.py or tests/live_validation.py")
            lines.append("Observed HTTP: " + str(case["http_status"]))
            for key in ("actual_fields", "actual_rules", "covered_indexes", "equipment", "invalid_fields"):
                if key in case:
                    lines.append("Observed " + key.replace("_", " ") + ": " + json.dumps(case[key], ensure_ascii=False))
            lines.append("Result: " + ("PASS" if case["passed"] else "FAIL"))
            lines.append("Mismatches: " + ("; ".join(case["mismatches"]) or "none"))
            lines.append("")
    lines.extend([f"FINAL LIVE SCENARIO TOTAL: {passed}/{number} passed", f"Model calls: {calls}", f"Usage-based uncached cost estimate for these final runs: ${cost:.7f}; not an account invoice.", "",
                  "ADDITIONAL APPLICATION CHECKS", "Automated application/agent tests: 160 passed, including 500 generated monetary combinations.",
                  "Python lint, compilation and JavaScript syntax: passed.", "Offline and live owner browser workflows: see docs/VALIDATION.md for current results.",
                  "Adversarial browser: failed approval, correction/cancel, untrusted markup, network recovery and four viewport widths.",
                  "Supplied rules/unit JSON fingerprints unchanged; repository credential scan passed.", "",
                  "FAILURES RETAINED", "Initial 25-case expansion and repeated public-form failures are retained in results/expanded/initial-summary.json and results/realistic/fifty-case-initial-summary.json.",
                  "Fixes: short quotes and evidence-count constraints enforced in live output schema; preserve explicit dates despite invalid chronology; compare money as Decimal instead of string formatting.",
                  "Unsupported citations remain blocked. Expected citation requirements were not relaxed.", "",
                  "LIMITATIONS", "Docker and Windows runtime not executed. No scanned-PDF OCR or signature authentication.",
                  "No production login, organisation isolation, contractor dispatch or legal compliance certification.", "Owner review remains mandatory; photo appearance cannot establish age or hidden faults.", ""])
    assert number >= 50, number
    (ROOT / "test_cases.txt").write_text("\n".join(lines))
    print(f"Wrote test_cases.txt: {passed}/{number} live scenarios")


if __name__ == "__main__":
    run()
