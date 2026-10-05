# Broader reliability validation

Run on 5 October 2026 with Python 3.12 and Chromium 153. This report describes checks actually executed after the live integration evaluation.

**Final result: 150 automated tests passed, including 82 new cases.** One test also exercises 500 reproducible generated rent/deposit/annual-rent combinations. The complete owner browser walkthrough and the new adversarial browser walkthrough both passed with no JavaScript errors.

## What was broadened

| Area | Checks and outcome |
|---|---|
| Monetary inputs | Non-finite values, negatives, fractions of a cent, extremely small exponents, wrong types and long precision; invalid inputs fail validation |
| Review integrity | Whitespace-only reasons and coerced revision types rejected without writes; eight simultaneous reviews yield one successful write and seven conflicts |
| AI failure behavior | Timeouts, connection errors, malformed JSON envelopes, incomplete outputs, refusals and HTTP errors produce explicit safe failures |
| Photo completeness | A proposal omitting any usable photo is rejected instead of silently recording partial coverage |
| Document formats | Valid, failing, missing and occupied-unit samples uploaded as DOCX and PDF produce the same rule statuses as TXT |
| Corrupt documents | Eight reproducible random payloads tested across TXT/PDF/DOCX; malformed files produce validation errors and no lease records |
| Resource limits | Expanded DOCX size, encrypted and excessive-page PDFs, text length, unsupported image formats, truncated/empty images, image pixel count, excessive photo count and report length |
| Request size | Uploads over 32 MiB rejected with and without a Content-Length header; actual received bytes are counted |
| Persistence | New app instance retains occupied status, active lease, source bytes, image bytes, issue record and audit events |
| Transaction failure | Injected audit write failure rolls back activation, leaving the unit available and the lease a draft; simulated provider failure leaves no issue/photo files |
| Owner decisions | Rejected observations invalidate earlier work approval and remove the rejected assessment from its description |
| Saved live evidence | All eight saved live leases meet stricter value checks and source offsets; all three saved real-photo proposals cover their image references |
| Browser failures | Blocked approval, Cancel/Escape, invalid correction followed by a successful correction, failed network request followed by recovery |
| Untrusted text | Uploaded markup remains literal text in fields, source evidence and issue reports; no script executes |
| Responsive layout | Long untrusted text checked at widths 320, 390, 768 and 1440; no document-level horizontal overflow |

## Bugs found and fixed

- Monetary precision checking previously used Decimal normalization, which can round under its precision context. Validation now inspects the original digits and exponent exactly.
- Review reasons were length-checked before trimming. They now require at least three characters after trimming. Revision numbers also require an actual integer JSON type.
- Malformed provider envelopes could raise an unhandled type/attribute error. Envelope, usage, output and content shapes are now checked before interpretation, and invalid output becomes a sanitized provider error.
- A photo proposal could omit an uploaded usable image. Coverage is now required for every usable photo before saving.
- Body size was checked from the declared length. A streaming byte counter now also enforces the cap when that header is absent.
- Long unbroken report text overflowed at a 320-pixel viewport. Workspace/dialog text now wraps, and flex/grid children can shrink safely.

## Reproduce

```bash
python -m pip install -r requirements-dev.txt
python -m ruff check app tests
python -m pytest -q
python -m playwright install chromium
python tests/browser_smoke.py
python tests/browser_adversarial.py
```

Both browser scripts use fresh temporary storage and default to the offline provider. The adversarial script always uses it. CI now includes both scripts.

## Limits of these results

The earlier live evaluation remains 12/12 passing on its final small integration set; see LIVE_VALIDATION.md. This broader pass added deterministic, mocked-provider and browser checks, not new paid model calls. Saved live outputs were checked against the stricter boundaries, which does not replace a new inference benchmark.

No claim is made that every future AI interpretation will be correct. Arabic, scanned-document OCR, authenticated users, organisation isolation and production deployment remain outside scope. Native Python startup was exercised on Linux; a Windows machine and Docker runtime were not available for execution here.

Two non-failing warnings remain: the framework TestClient adapter deprecation and Pillow's expected decompression warning when deliberately submitting an oversized image. The image request is rejected. An injected database outage returns a server error while rolling back safely; this prototype does not implement storage-outage retry/recovery jobs.
