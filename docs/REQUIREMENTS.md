# Requirements checklist

Source: the supplied solution brief, owner rules, units register and shortlisting email.

| Requirement | Status | Where to review |
|---|---|---|
| Small full-stack service | Implemented | FastAPI API plus responsive owner console |
| Upload lease | Implemented | TXT, text-based PDF and DOCX |
| Parties, unit, dates, rent amount/frequency, deposit, escalation, renewal, termination | Implemented | 18 individual lease fields |
| Evidence for extracted fields | Implemented | Exact quotes with source locations and offsets; human overrides retained separately |
| Missing fields, contradictions and unusual values | Implemented | Missing/invalid flags, model concerns, demo contradiction detection and deterministic date/rent checks |
| All supplied owner rules with reasons and three outcomes | Implemented | R1–R7; snapshot of original rules preserved per lease |
| Match supplied units and update occupancy | Implemented | Exact ID; occupancy changes after explicit owner approval and transactional availability check |
| One or more uploaded property photos | Implemented | 1–4 decoded PNG/JPEG/WEBP images |
| Visible condition and equipment | Implemented and live tested | Hash-specific synthetic fixtures offline; real image-byte inference via live adapter |
| Draft work order with title, problem and affected unit | Implemented | Unit-linked issue workflow and editable work order |
| Lease and open issues on one unit screen | Implemented | Owner console and unit detail API |
| Accept/reject each field, flag and work order | Implemented | Reasoned review and optimistic revisions |
| Override incorrect condition calls | Implemented | Observation correction retains original and resets work approval |
| Traceable and bounded agent behavior | Implemented | Model boundary, source/image verification, one lease repair, deterministic policy, suspended approval |
| Use provided core test data | Implemented | Supplied JSON files copied without changes |
| No API key required | Implemented | Clearly labelled default demo |
| Document live API requirements | Implemented | README and `.env.example` |
| README: run, approach, decisions, trade-offs, omissions, scale, enhancements | Complete | README and linked documentation |
| First-30-days note and built-project example | Complete | FIRST_30_DAYS.md and SUBMISSION_NOTE.md |
| Existing public repository of own work | Verified | https://github.com/Hannaancode/RecoverML |
| GitHub solution repository | Published | https://github.com/Hannaancode/LeaseWorks |
| Send both links to contact@truelinks.ai | Draft prepared, not sent | SUBMISSION_NOTE.md; both links included |
| Within four days of original receipt | Requires receipt date | Original receipt date was not supplied |

Live text and vision integration has been evaluated on a small, documented sample set. General model accuracy and production security are not claimed; broader evaluation and the prerequisites listed in the README remain necessary.
