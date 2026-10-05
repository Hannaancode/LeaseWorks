# Validation results

Checked on 5 October 2026 with Python 3.12. The outputs below describe tests actually run in the development environment.

| Check | Result |
|---|---|
| Automated application/agent tests | 160 passed (including 500 generated monetary combinations) |
| Python lint | Passed |
| Python compilation | Passed |
| JavaScript syntax | Passed |
| Offline Chromium owner walkthrough | Passed with no JavaScript errors |
| Live Chromium owner walkthrough | Passed with real lease and photo inference, no JavaScript errors |
| Adversarial Chromium walkthrough | Passed; see EXTENDED_VALIDATION.md |
| Responsive layout | No document-level overflow at widths 320, 390, 768 and 1440 with long text |
| Supplied unit file | Byte-for-byte unchanged |
| Supplied owner rules | Byte-for-byte unchanged |
| Live provider contract | Mock HTTP contract test passed |
| Paid live text/vision inference | Original regression 12/12; broader public-form/photo cases 17/17; added boundary cases 25/25 (54/54 combined); see LIVE_VALIDATION.md and REALISTIC_VALIDATION.md |
| Docker startup | Not run in this environment |
| Hosted deployment | Not provided; not required by the brief |

The browser walkthrough uses isolated temporary storage and covers a valid lease, source rent evidence, seven policy passes, two-photo and four-photo reports, an owner condition override, a work-order edit/approval, 18 individual field approvals, two signature-flag acknowledgements, lease activation, occupancy, audit history and JSON export. Screenshots are included in `docs/screenshots/`, with live-mode screenshots and the downloaded record in `docs/screenshots/live/`.

The concurrent approval test submits two reviewed drafts for the same available unit. Exactly one activation succeeds and the other receives a conflict response. The database contains one active lease for that unit.

Known test-environment warning: the installed Starlette release emits a deprecation warning for its HTTPX TestClient adapter. It does not affect the passing checks. A framework upgrade should retest the adapter rather than suppressing the warning.

The offline model is deterministic. Its passing tests establish implementation behavior, not a statistical claim about extraction or vision quality. The evaluation plan describes the next checks needed with a real provider and held-out documents/photos.

## Supplied fixture fingerprints

| File | SHA-256 |
|---|---|
| `data/units.json` | `c0a94975e47759381c9e10896fe6b86512d6b44fe2b10376ba2f2a6be4dcb985` |
| `data/owner_ruleset.json` | `78f2b8ab26b54edf1cb536c323be7a9fe7a1c7e03c15b9ef6dfe7a8cbe42c0e3` |

The broader validation pass and fixes are documented in [EXTENDED_VALIDATION.md](EXTENDED_VALIDATION.md). Both offline and live browser workflows and the adversarial browser checks were rerun after the public-form and real-photo fixes; the screenshots reflect that revision. The follow-on report is [REALISTIC_VALIDATION.md](REALISTIC_VALIDATION.md).

The complete numbered scenario record is [test_cases.txt](../test_cases.txt). Final-run receipts are in `results/live/fifty_case_final/`, `results/realistic/fifty-case-final-summary.json` and `results/expanded/final-summary.json`.

The final rerun restored the official Playwright headless browser after a truncated local binary prevented startup. Browser launch/download failures were environment issues; application results are recorded separately.
