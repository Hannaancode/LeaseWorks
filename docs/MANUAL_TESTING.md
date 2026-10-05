# Manual testing

## Start on Windows

Install Python 3.12, extract the submission and open a PowerShell terminal in the `leaseworks` folder.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 and keep the terminal running. Ctrl+C stops it. Records survive restarts. For a fresh test, stop it, rename `var` to a backup folder and restart.

The default offline demo understands the labelled sample leases and uses scripted results only for the four exact real sample photographs. To evaluate actual language and photos, stop the server and privately configure live mode:

```powershell
$env:MODEL_PROVIDER = "openai"
$env:OPENAI_MODEL = "gpt-4.1-mini"
$env:OPENAI_API_KEY = Read-Host "Enter your API key"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Live calls incur provider charges. Live mode adds Prose lease and uses AI inference for the real sample photographs. An API credential is configured on the server and is never bundled. The Python startup command does not automatically load an `.env` file.

## Try these checks

Use a fresh database for the approval flow, then restart fresh when repeating availability tests.

| Action | Expected result |
|---|---|
| Apartment 1204 → Valid lease | 18 fields and seven passing rules; occupancy stays available |
| Open rent source citation | Exact source quote with location and offsets |
| Attempt approval before reviewing | Error explaining required reviews; unit remains available |
| Open a field review and cancel | No recorded decision |
| Correct deposit to a negative amount | Validation error; draft unchanged |
| Correct deposit to a valid amount | Original retained; revised rule result and audit event |
| With problems | Five failed checks; lease cannot be activated |
| Missing fields | Unknown values and NOT DETERMINABLE checks |
| Occupied unit | Availability fails; existing occupancy remains |
| Use real sample photos | Two real photographs with labelled reference assessments offline or model inference live |
| Use all four photos | Four real photographs, all covered by observations |
| Correct a photo assessment after accepting work | Work returns to pending and the original observation remains recorded |
| Reject the work order | Rejection shown and recorded; no contractor contacted |
| Accept all valid lease fields and review both signature flags, then approve | Unit becomes occupied and approved lease is immutable |
| Attempt another lease for that unit | Availability fails |
| View audit and Export record | Traceable decisions and downloadable unit JSON |
| Stop and restart server | Records, occupancy, originals and photos persist |
| Upload a corrupt PDF or a fake JPG | Explicit validation error; no partial record |
| Resize browser to a narrow phone width | Single-column workspace; unit navigation scrolls horizontally |
| Live mode → Prose lease | Real AI extraction; verify quotes manually before accepting |
| Live mode → Use real sample photos | Real image assessment and work-order draft; public photo credits available |
| Live mode → upload `samples/live/prose_conflict.txt` or `prose_ambiguous_dates.txt` | Conflicting rent or unresolved dates require owner correction |

Review the original lease for signature authenticity and inspect photos before relying on condition assessments. The prototype prepares proposals; your explicit reviews determine approval.

## Public forms and realistic scenarios

Run `python tests/realistic_validation.py --prepare-only` to download the original public PDFs into `test-results/public-leases/` and create a fictional, unsigned completion of the Queensland form. This preparation makes no AI calls. In live mode upload these PDFs or the fictional TXT cases under `samples/realistic/`. Blank forms should leave rent and tenant unknown, weekly rent should not become monthly rent, and the 49-page QSTP template should return the documented 30-page-limit error. For the mixed-currency case, R6 must not pass.

Select **Use all four photos** to inspect AC, corroded coil, heater and faucet photographs together. Every photo must have a linked assessment. A running faucet alone does not prove a leak, and an exterior photograph cannot establish actual equipment age or hidden faults.
