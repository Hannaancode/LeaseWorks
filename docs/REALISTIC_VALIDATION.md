# Public-form and real-photo validation

I expanded validation on 5 October 2026 beyond the labelled demonstration fixtures. I used original public PDF formats, fictional contract details and four attributed photographs. I retained unsuccessful runs and added checks for the problems they exposed.

## Documents and expected outcomes

| Input | What I checked |
|---|---|
| Qatar Manateq commercial plot lease template | Blank tenant, rent, deposit and unit remain unknown; printed signature labels do not establish signing |
| Dubai Land Department unified tenancy form | Unfilled party and rent fields remain unknown; bilingual layout must not produce invented values |
| Queensland RTA Form 18a | Blank fields remain unknown; actual interactive PDF fields can be read |
| Fictional completion of the original Form 18a | AUD 1,000 weekly rent, AUD 4,000 bond, stated 12-month term and exact test unit; no invented monthly or annual rent; no signatures |
| Fictional Qatar residential and bilingual residential text | QAR 8,500 monthly, QAR 102,000 annual and stated dates; unsigned clauses must not pass R5 |
| Fictional quarterly tenancy | Preserve quarterly frequency; missing monthly and annual figures remain unknown |
| Fictional external Qatar unit | R7 fails; no inferred match to the supplied register |
| Fictional US periodic tenancy | No invented fixed term, expiry date or annual rent; apply the supplied policy without adapting it to another jurisdiction |
| Fictional QAR/USD conflict | Numerically matching amounts cannot pass R6 across different currencies |
| Qatar QSTP 49-page commercial template | Reject with the documented 30-page limit, without making a paid inference call |

The original publishers, URLs and SHA-256 fingerprints are in [public_sources.json](../samples/realistic/public_sources.json). Originals download into ignored `test-results/public-leases/`; they are not redistributed as my own documents. The completion and narrative details are explicitly fictional, not executed leases. The two Qatar public documents are commercial templates, not residential standard forms. This tests ingestion and application behavior, not jurisdictional legal compliance.

## Real photographs

I replaced the drawn demonstration images with four original public photographs: a wall AC unit, corroded coil/housing, storage water heater and running kitchen faucet. Credits and licences are in [ATTRIBUTION.md](../samples/live/ATTRIBUTION.md).

The live evaluation checks individual identification, visible corrosion despite a contradictory reporter claim, paired photographs and coverage of all four photos. Actual file bytes are sent to the model. Offline mode deliberately uses disclosed hash-specific reference assessments for those same files. It is not live vision inference.

Condition labels vary between calls, including `appears_new`, `worn` and `damaged`. These labels describe appearance, not actual age. The corroded object may remain unidentified while its corrosion is reported. Running tap water does not prove a leak. Owner correction and an in-person inspection remain necessary for an uncertain diagnosis.

## Problems found and fixes

- Long PDF line fragments made citations brittle. I now use whitespace-normalized page passages, retain exact source offsets within that canonical text and read populated interactive form widgets separately. Those offsets are not raw PDF byte offsets.
- A stateless repair request initially contained errors without the rejected proposal. It now includes both so the model can repair the actual rejected fields within the one-retry limit.
- The model sometimes changed a source's stated 12-month term to 11 months to reconcile contradictory dates. A source verifier preserves a uniquely cited explicit English term; the disagreement remains an R4 failure.
- Equal numbers in QAR and USD could incorrectly pass annual reconciliation. A conservative source gate returns the monetary fields to unknown and adds a currency-conflict flag. It does not perform exchange conversion; legitimate contracts mentioning alternative currencies may also need owner review.
- Some exact quotes were assigned to the wrong source segment. They are relocated only when they occur in precisely one segment. Proposed and resolved locations are retained. Fabricated or ambiguous quotes remain blocked.
- The model joined distant clauses and PDF symbols into nonexistent quotes. Renewal, termination and escalation text now use short verbatim excerpts with interpretation in the explanation. Blank signature forms return unknown, and repair instructions favor abstaining over unsupported evidence.

Exact quote membership does not establish correct semantic interpretation. No fuzzy matching or automatic acceptance was added to force a passing result. Invalid fields still require owner correction and review before approval.

## Recorded results

**Final public-form/photo run: 17/17 passed. Original live regression: 12/12 passed. Automated application tests: 159 passed.** Offline, live and adversarial Chromium walkthroughs all passed after the fixes.

| Run | Passing cases | Model calls | Usage-based estimated cost |
|---|---:|---:|---:|
| `initial` | 12/17 | 23 | $0.1805256 |
| `after_document_fixes` | 13/17 | 20 | $0.0693532 |
| `after_source_gates` | 14/17 | 19 | $0.0707892 |
| `final` | 17/17 | 18 | $0.0668388 |

Compact receipts are under [results/realistic](../results/realistic/). The original regression receipt is [results/live/submission_final/summary.json](../results/live/submission_final/summary.json). Earlier failures are retained; the expected checks were not relaxed to obtain a pass. Costs use uncached input/output rates, are not account invoices and exclude separate browser/connectivity calls.

## Reproduce

Prepare the original forms and fictional completion without a key or model calls:

```bash
python tests/realistic_validation.py --prepare-only
```

After privately setting `OPENAI_API_KEY`, run the opt-in paid evaluation:

```bash
python tests/realistic_validation.py
```

This runner uses `gpt-4.1-mini`, isolated temporary database/storage, a call limit and a conservative local cost reservation. It does not enforce the account's spending cap. Full generated proposals stay in ignored test output. Compact checked-in summaries omit publishers' clause text.

Every lease case also checks that activation without human review is rejected and the supplied unit remains available. Photo evaluation checks all uploaded image references before any issue record is saved. The final local and live browser walkthroughs exercise owner correction, work approval, 18 lease-field reviews, signature flags, transactional activation, audit and export, followed by a four-photo issue.

This is a development integration set, not held-out accuracy measurement or proof that every future document succeeds. OCR, signature authentication, general Arabic accuracy, complete translated RTL workflows, production authentication and legal policy interpretation remain outside this prototype. Native Python startup was tested on Linux; Docker and Windows runtime execution were unavailable.

## Expanded submission evaluation

I reran the original 12 cases and the 17 public-form/photo cases, then added 25 boundary scenarios: 20 fictional lease variations including two actual DOCX files and five real-photo combinations/report contradictions. The final runs passed **54/54**, and the automated suite passed **160 tests**. The numbered results are in [test_cases.txt](../test_cases.txt).

The first added-boundary run passed 24/25: the model omitted explicit dates when chronology was invalid. I instructed it to retain readable contradictory dates so R4 can fail rather than becoming unknown. The repeated public-form run passed 15/17 with intermittent citation errors. I enforced a 160-character quote limit and at most two citations per field in the live JSON schema; prompt wording alone was insufficient. A test-harness money comparison also treated `1000.00` and `1000` as different, which I corrected using Decimal. Invalid-citation requirements remain unchanged. Earlier failures are retained in `results/expanded/initial-summary.json` and `results/realistic/fifty-case-initial-summary.json`.
