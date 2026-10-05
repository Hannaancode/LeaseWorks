# Live text and vision validation

Executed on 5 October 2026 against the real OpenAI Responses API with `gpt-4.1-mini` (returned model version `gpt-4.1-mini-2025-04-14`). No API credential is included in this repository.

**Initial final integration run: 12/12 scenarios passed.** Full proposals, citations, policy decisions, model usage and case summaries are under `results/live/final/`. Each lease stayed a draft and did not change occupancy during API evaluation.

| Scenario | Expected behavior | Result |
|---|---|---|
| Complete prose lease | 18 populated fields; all seven rules pass | Passed |
| Invalid deposit/rent/signature/date clauses | Relevant rules fail | Passed |
| Missing clauses | Unknown fields and NOT_DETERMINABLE rules | Passed |
| Conflicting monthly rents | No chosen monthly rent; R1/R6 unknown | Passed |
| Occupied unit | R7 fails | Passed |
| Embedded instructions | Actual deposit retained; R1 fails | Passed |
| Ambiguous numeric dates | Dates unknown; R4 unknown | Passed |
| 48-month term | R3 fails; internally consistent dates pass R4 | Passed |
| Actual wall AC photograph | Visible air-conditioning equipment identified | Passed |
| Actual corroded coil photograph | Visible corrosion reported | Passed |
| Two actual photos | Both image references covered | Passed |
| Blank image plus asserted gas leak | Unidentified equipment, unknown condition; no model call | Passed |

## Failures found and changes made

The initial run guessed a date locale. A deterministic source-format gate now returns ambiguous dates to unknown, retains the original proposal and requests owner correction. The blank-image probe also motivated a uniform-image gate: reporter text cannot establish equipment in a blank photograph.

The second run produced `month` instead of the canonical frequency, causing a repair attempt that introduced an invalid citation. Equivalent frequency words are now normalized before verification; the original wording remains recorded. Invalid citations still block acceptance without a human correction.

The next run selected one of two conflicting monthly rents. A conservative English source scan now detects different explicit monthly amounts, retains both citations and returns the monthly rent to unknown. It does not resolve precedence. Legitimate stepped schedules can also need owner review; broader syntax and language coverage are not claimed.

Earlier results are retained so these failures can be inspected. The final set was rerun in full after the fixes.

| Run | Passing cases | Model calls | Estimated cost |
|---|---:|---:|---:|
| `initial` | 11/12 | 12 | $0.0224664 |
| `after_gates` | 11/12 | 13 | $0.0254824 |
| `after_frequency` | 11/12 | 11 | $0.0211652 |
| `final` | 12/12 | 11 | $0.0211972 |

The final run used 19,261 input tokens and 8,433 output tokens. Measured per-call latency ranged from 9.07s to 14.62s (median 11.72s).

## Browser and budget evidence

The refreshed live Chromium walkthrough used the prose lease, both actual AC/coil photographs and a separate four-photo issue, then checked source evidence, seven rules, a photo correction, work-order editing/approval, all 18 field approvals, two signature acknowledgements, occupancy, audit and JSON export. Desktop and 390 × 844 mobile checks passed without JavaScript errors or document-level horizontal overflow. Screenshots and the exported record are in `docs/screenshots/live/`.

The original four recorded scenario runs plus their original browser inference had a combined usage-based estimate of **$0.0949**. Later revision runs are recorded separately below and in REALISTIC_VALIDATION.md. This uses $0.40/million input and $1.60/million output tokens without cached discounts. It is not an invoice and excludes a few small startup/connectivity calls. The scenario runner bounds calls and fixture sizes, but is not an account-wide spend limiter.

## What this establishes

This checks live provider integration and the expected behavior of a small development set: eight fictional English lease texts and two public photographs across four photo scenarios. It is not a statistically meaningful or held-out accuracy benchmark, legal verification, or an inspection diagnosis. Exact quote membership cannot prove correct interpretation, and signature markers cannot authenticate signing. Owner review remains mandatory. The broader pilot evaluation is described in `EVALUATION.md`.

Photo credits and licence links are in `samples/live/ATTRIBUTION.md`. These sample photos are not associated with the supplied property units. Docker was not available for a runtime check; the native Python application was tested.

## Submission revision regression

Replacing the drawn offline image fixtures with real photographs exposed a stated-term regression in live extraction. The first revision run passed 11/12; the source verifier fix restored 12/12. After the public-form prompt fixes I reran the full original set again: **12/12 passed**, 11 model calls, estimated $0.0227796, recorded in `results/live/submission_final/`. The earlier revision receipts are in `real_photo_regression/` and `real_photo_final/`.

The expanded public-PDF, bilingual and four-photo evaluation passed **17/17**; see [REALISTIC_VALIDATION.md](REALISTIC_VALIDATION.md). The current offline and live screenshots were regenerated after these fixes, and both browser flows include the four-photo issue.

The final expanded submission evaluation reran the original suite at 12/12, the public-form suite at 17/17 and 25 new boundary cases at 25/25. See [test_cases.txt](../test_cases.txt) for all 54 scenario results and [REALISTIC_VALIDATION.md](REALISTIC_VALIDATION.md) for the additional fixes.
