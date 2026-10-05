# My first 30 days at TrueLinks AI

I would start with one lease-to-maintenance workflow and make it easier for an owner to trust and approve the work. The official product overview already emphasises grounded answers and approvals, so I would build on that direction after learning the current implementation and roadmap.

**Days 1–7:** I would walk through the workflow with owners, facility teams and engineers and observe where they repeat work or wait for missing information. I would review the data model, access controls and existing agent boundaries and establish a baseline for review time, correction rate and work-order completion.

**Days 8–15:** I would choose one improvement with the team and ship a small pilot. My starting candidate is an exception-first review screen that shows the source clause or photo beside the decision and asks for missing information before the work reaches an approver. I would pair with teammates on the implementation and document the conventions for evidence, failure states and review decisions.

**Days 16–23:** I would test the pilot with a small user group and fix the biggest sources of wrong or incomplete records. I would add regression cases from reviewed corrections and check that access permissions and audit records work throughout the flow. If intake language is the main obstacle, I would prioritise Arabic/English and RTL at that stage rather than adding more AI features.

**Days 24–30:** I would compare the pilot with the baseline and share a demo, results and a short decision note. I would propose the next step based on what users needed most, such as renewal reminders or work-order completion photos, and agree the rollout and ownership with the team. I would not promise a numerical improvement before measuring the starting point.

## An existing project I built

[RecoverML](https://github.com/Hannaancode/RecoverML) is my public prototype for saving and restoring earlier states of machine learning pipelines. It records artifact dependencies and hashes and chooses what to keep under a storage budget. The repository includes the implementation, tests, a captured replay example, benchmark results, plots and reproduction instructions.

For this exercise I built LeaseWorks to connect document extraction, owner policy checks and photo-based issue drafts around a single unit. The working sample-data flow includes source evidence, owner corrections, audit history and a controlled occupancy update. Its live text/vision adapter is included, while the default demo runs without an API key.
