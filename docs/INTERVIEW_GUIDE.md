# Walkthrough preparation

Start with the owner problem: a wrong lease value or a misleading condition assessment has a practical cost. The design keeps every proposal beside its source and holds consequential writes behind review.

## Explain the implementation

`providers.py` is the replaceable AI boundary. `agents.py` controls the read/interpret/verify/review sequence and the single repair attempt. `rules.py` contains deterministic checks rather than executing model output or JSON expressions. `store.py` controls transactions and the active-lease constraint. `main.py` exposes the API. The frontend joins both flows by unit ID.

Show the valid sample, a rent source citation, the two-photo report and one owner correction. Show a problematic lease and explain PASS/FAIL/NOT_DETERMINABLE. Demonstrate that a lease upload does not occupy a unit and that dismissing a flag cannot override a rule failure.

## Questions to be ready for

- Why use a bounded workflow? The agents interpret and prepare proposals but policy, money-related fields and occupancy need explicit controls. The model has no direct database or dispatch tools.
- Is offline extraction real AI? No. It is a disclosed stub allowed by the brief. Live mode uses structured text and image inference, and still needs an accuracy evaluation with an API key.
- What does a citation prove? The passage exists at the recorded location. It does not guarantee the interpretation is right. That is why the original source and correction workflow matter.
- Why SQLite? It makes the exercise easy to run and transactions easy to inspect. PostgreSQL, a job queue and tenant-scoped object storage come before multiple app instances.
- What prevents two leases claiming one unit? A transactional availability recheck, serialized write transaction and unique index on active lease per unit.
- Why preserve the original availability? R7 is about availability before linking. A correctly approved lease should not turn into a historical failure after it occupies the unit.
- Why Decimal and calendar months? Financial amounts need exact arithmetic and contract terms do not fit fixed 30-day approximations.
- What is missing for production? Authenticated roles, organisation isolation, OCR, legal/owner rule conventions, upload scanning, asynchronous jobs, retention controls, observability and live quality measurement.
- Why not assign contractors automatically? The exercise asks for drafts. Dispatch and financial commitments need additional approval, scope and vendor controls.
- What would you improve first? Reduce review effort with an exception-first queue and better intake, then measure review time and correction rate with users.

Read the code and run the demo before the interview. Be able to explain and change the parts above rather than relying on the README alone.
