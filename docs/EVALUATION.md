# Live model evaluation before a real pilot

The current correctness tests validate the application workflow. They do not measure a model's lease or vision accuracy. I would create a small consented or synthetic evaluation set and separate development examples from a held-out set.

## Lease cases

Include clean leases, missing signatures, ambiguous signatures, different date formats, bilingual clauses, handwritten/scanned pages, duplicate rent statements, quarterly payments, unknown units, occupied units, vague escalation and longer terms. Include embedded instructions asking the system to ignore policy.

Have two reviewers annotate the critical fields and their source clauses and resolve disagreements. Measure exact or normalized accuracy for rent, deposit, dates and unit ID; source citation validity; contradiction recall; missing-field recall; and the rate at which a bad lease is wrongly presented as fully passing. Report unknowns separately from errors. Test each rule against the owner's intended interpretation rather than treating the prototype's conventions as legal authority.

## Photo cases

Use a held-out set with clear and blurred photos, multiple equipment types, no visible damage, worn fixtures, apparent damage, unrelated images and multi-photo reports. Compare equipment labels and visible-condition descriptions with inspection annotations. Count unsupported claims about age, cause, cost or safety. Evaluate whether a proposed work order gives a technician useful scope without presenting uncertain guesses as fact.

## Workflow cases

Observe owners and inspectors completing the task. Measure time to review, number of follow-up questions, correction rate, reopened work orders and time from report to approval. Record the denominator and sample size. Keep operational timing distinct from model latency and inference cost.

Version the model, prompts, rules, documents and reviewer annotations. Re-run the held-out set when changing any of them. Do not set automatic acceptance thresholds from model self-confidence alone. Begin with explicit approval and use the evidence from the pilot to decide whether any lower-risk grouping is justified.
