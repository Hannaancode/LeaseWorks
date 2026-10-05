# Design walkthrough

I designed LeaseWorks around the cost of an incorrect lease value or misleading condition assessment. I keep each proposal beside its source and require explicit review before occupancy or work approval.

## Agent boundaries

I use two bounded agent workflows. The lease agent reads source segments, extracts a typed proposal, verifies citations and types, and can request one repair using verifier feedback. It then runs the owner policy checks and waits for review. The issue agent interprets image bytes, verifies image coverage and proposes a unit-linked work order for review.

`providers.py` is the replaceable model interface; `agents.py` controls these workflows. `rules.py` evaluates policy without executing source expressions or model output. `store.py` owns transactions and the active-lease constraint. `main.py` exposes the API. The frontend joins both flows around the selected unit.

I deliberately keep database writes and contractor dispatch outside the model's authority. The default offline provider is a disclosed testing adapter; the live adapter performs document and image inference through the Responses API.

## Decisions and trade-offs

- I use exact source quotes and offsets to make the proposal inspectable. Citation membership proves that text exists, not that its interpretation is correct. Owner corrections preserve original values.
- I use SQLite for reproducible local startup and transactional approval. A job queue, PostgreSQL and tenant-scoped object storage are the next infrastructure steps.
- I recheck availability inside the activation transaction and enforce one active lease per unit. Historical R7 results retain the availability snapshot from ingestion.
- I use Decimal for money and calendar-month arithmetic for stated fixed terms. I do not derive missing monthly or annual amounts merely to make rules pass.
- I treat signature markers as documentary evidence requiring manual inspection, not proof of authenticity.
- I distinguish reporter claims from visible photo evidence. Appearance cannot establish equipment age, internal faults or repair cost.
- I leave authentication, organisation isolation, OCR, legally reviewed policy conventions and vendor dispatch for a production pilot.

## Product direction

I would first reduce review effort with an exception-focused queue and better intake prompts. I would establish review-time and correction-rate baselines with users before setting numerical improvement targets. My first-30-days plan explains how I would run that pilot with the team.
