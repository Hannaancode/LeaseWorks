# API guide

All routes return JSON except original documents, photos, samples and the owner console. The machine-readable schema is at `/openapi.json`. Interactive API documentation is disabled to keep the application free of browser CDN dependencies.

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/health` | Active model mode and health |
| GET | `/api/units` | Supplied unit register with current occupancy |
| GET | `/api/units/{unit_id}` | Unit, leases and issues |
| GET | `/api/leases` | All drafts including unmatched leases |
| POST | `/api/leases` | Multipart upload in `file` |
| GET | `/api/leases/{lease_id}` | Structured lease and verification results |
| GET | `/api/leases/{lease_id}/source` | Original document download |
| POST | `/api/leases/{lease_id}/fields/{name}/review` | Accept, reject or correct a field |
| POST | `/api/leases/{lease_id}/flags/{flag_id}/review` | Acknowledge or dismiss flag |
| POST | `/api/leases/{lease_id}/activate` | Approve and occupy unit atomically |
| POST | `/api/units/{unit_id}/issues` | Multipart `photos` and optional `report` |
| GET | `/api/issues/{issue_id}/photos/{image_id}` | Verified uploaded image |
| POST | `/api/issues/{issue_id}/observations/{index}/review` | Review/correct condition or equipment |
| POST | `/api/issues/{issue_id}/review` | Accept/reject/edit work order |
| GET | `/api/audit/{entity_id}` | Ordered audit events |
| GET | `/api/units/{unit_id}/export` | Export unit record |

For a field review:

```json
{
  "decision": "accepted",
  "reason": "Checked the amount against the signed addendum",
  "expected_revision": 3,
  "replace_value": true,
  "value": "8500"
}
```

`expected_revision` must match the current record. A stale edit returns HTTP 409. Invalid upload or correction returns 422. Model failure returns 502 without a partial record. Unknown record IDs return 404. Lease activation also returns 409 if review, policy or availability requirements are not met.

For observation corrections, use `decision`, `reason`, `expected_revision` and any of `equipment`, `condition`, `visible_damage`. Conditions are `appears_new`, `worn`, `damaged` and `unknown`. Photo references cannot be replaced by an owner correction. Correcting an observation resets work-order acceptance and rebuilds the draft description from the current assessments.
