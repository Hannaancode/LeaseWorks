"""Bounded agent workflows: observe, verify, check policy, propose, await review."""

import hashlib
import json
from .domain import FIELD_TYPES, validate_value, IssueProposal
from .normalization import ambiguous_date_reason, normalize_frequency, normalize_stated_term, conflicting_monthly_rents, explicit_money_currencies
from .rules import evaluate


def lease_agent(provider, segments, units, ruleset):
    source = {s["id"]: s for s in segments}
    citation_corrections = []

    def locate_citations(candidate):
        proposed = {field.name: [citation.model_dump() for citation in field.evidence] for field in candidate.fields}
        for field in candidate.fields:
            for citation in field.evidence:
                segment = source.get(citation.segment_id)
                if not citation.quote or (segment and citation.quote in segment["text"]):
                    continue
                matches = [segment for segment in segments if citation.quote in segment["text"]]
                if len(matches) == 1:
                    citation_corrections.append({"field": field.name, "proposed_segment_id": citation.segment_id, "resolved_segment_id": matches[0]["id"], "quote": citation.quote})
                    citation.segment_id = matches[0]["id"]
        return proposed

    def verifier_feedback(candidate):
        errors = []
        seen = set()
        for field in candidate.fields:
            if field.name not in FIELD_TYPES or field.name in seen:
                errors.append(f"{field.name}: unknown or duplicate field")
                continue
            seen.add(field.name)
            try:
                validate_value(field.name, field.value)
            except ValueError as exc:
                errors.append(f"{field.name}: {exc}")
            if field.value is not None and not field.evidence:
                errors.append(f"{field.name}: a non-null value requires source evidence")
            for citation in field.evidence:
                segment = source.get(citation.segment_id)
                if not segment or not citation.quote or citation.quote not in segment["text"]:
                    errors.append(f"{field.name}: quote is not present in cited source segment {citation.segment_id}; rejected quote: {citation.quote!r}")
        return errors

    proposal = provider.lease(segments)
    proposed_evidence = locate_citations(proposal)
    normalized_originals = {}
    for field in proposal.fields:
        original = normalize_frequency(field)
        if original is None:
            original = normalize_stated_term(field, segments)
        if original is not None:
            normalized_originals[field.name] = original
    model_calls = [provider.last_call] if getattr(provider, "last_call", None) else []
    feedback = verifier_feedback(proposal)
    # One evidence-driven repair, never an unbounded autonomous loop.
    if feedback:
        # Requests are stateless: include the rejected proposal, not just errors,
        # so the model can actually repair the precise prior citations.
        repair_feedback = feedback + ["Previous proposal to repair: " + json.dumps(proposal.model_dump(), ensure_ascii=False)]
        proposal = provider.lease(segments, feedback=repair_feedback)
        proposed_evidence = locate_citations(proposal)
        for field in proposal.fields:
            original = normalize_frequency(field)
            if original is None:
                original = normalize_stated_term(field, segments)
            if original is not None:
                normalized_originals[field.name] = original
        if getattr(provider, "last_call", None):
            model_calls.append(provider.last_call)
    names = [f.name for f in proposal.fields]
    date_ambiguities, original_dates = {}, {}
    for field in proposal.fields:
        ambiguity = ambiguous_date_reason(field, segments)
        if ambiguity:
            original_dates[field.name] = field.value
            date_ambiguities[field.name] = ambiguity
            field.value = None
            field.explanation += " Application normalization gate: " + ambiguity
    if len(names) != len(set(names)) or any(n not in FIELD_TYPES for n in names):
        raise ValueError("Model returned duplicate or unknown lease fields")
    fields, flags = {}, []

    def flag(kind, message, related=None):
        fid = hashlib.sha256((kind + message).encode()).hexdigest()[:16]
        flags.append({"id": fid, "kind": kind, "message": message, "field": related, "decision": "pending"})

    for f in proposal.fields:
        evidence = []
        invalid = False
        for citation in f.evidence:
            seg = source.get(citation.segment_id)
            if not seg or not citation.quote or citation.quote not in seg["text"]:
                invalid = True
            else:
                offset = seg["text"].index(citation.quote)
                evidence.append(
                    {**citation.model_dump(), "location": seg["location"], "start": offset, "end": offset + len(citation.quote)}
                )
        if f.value is not None and not evidence:
            invalid = True
        try:
            validate_value(f.name, f.value)
        except ValueError:
            invalid = True
        fields[f.name] = {
            "value": f.value,
            "original_value": original_dates.get(f.name, normalized_originals.get(f.name, f.value)),
            "evidence": evidence,
            "proposed_evidence": proposed_evidence.get(f.name, []),
            "explanation": f.explanation,
            "invalid": invalid,
            "decision": "pending",
            "origin": "model",
        }
    for name in FIELD_TYPES:
        fields.setdefault(
            name,
            {
                "value": None,
                "original_value": None,
                "evidence": [],
                "explanation": "Not returned by model",
                "invalid": False,
                "decision": "pending",
                "origin": "model",
            },
        )
        f = fields[name]
        if f["invalid"]:
            flag("unverified", f"{name}: invalid type or citation. Human correction is required.", name)
        elif f["value"] is None:
            flag("missing", f"{name}: no determinate source value.", name)
    for concern in proposal.concerns:
        flag("model_concern", concern)
    rent_conflicts = conflicting_monthly_rents(segments)
    if rent_conflicts:
        field = fields["monthly_rent"]
        field["value"] = None
        field["explanation"] += " Source gate found different stated monthly rents. Owner must resolve the schedules."
        for _, segment, quote in rent_conflicts:
            start = segment["text"].index(quote)
            citation = {
                "segment_id": segment["id"],
                "quote": quote,
                "location": segment["location"],
                "start": start,
                "end": start + len(quote),
            }
            if citation not in field["evidence"]:
                field["evidence"].append(citation)
        flag("contradiction", "Different source clauses state different monthly rents; owner correction is required.", "monthly_rent")
    for name, reason in date_ambiguities.items():
        flag("ambiguous_date", reason, name)
    mixed_currencies = explicit_money_currencies(segments)
    if mixed_currencies:
        message = "Different explicit monetary currencies occur in the source: " + ", ".join(sorted(mixed_currencies)) + ". Resolve currencies before comparing amounts."
        for name in ("currency", "rent_amount", "monthly_rent", "annual_rent", "deposit_amount"):
            fields[name]["value"] = None
            fields[name]["explanation"] += " " + message
        flag("currency_conflict", message, "currency")
    for name in ("landlord_signed", "tenant_signed"):
        if fields[name]["value"] is True:
            flag("signature", f"{name}: documentary marker only; manually inspect the signed original.", name)
    monthly = fields["monthly_rent"]["value"]
    if monthly is not None and not fields["monthly_rent"]["invalid"] and float(monthly) == 0:
        flag("unusual", "Monthly rent is zero. Confirm this is intentional.", "monthly_rent")
    availability = {uid: u["status"] for uid, u in units.items()}
    rules = evaluate(fields, units, ruleset, availability)
    for r in rules:
        if r["status"] != "PASS":
            flag("rule", f"{r['id']} {r['status']}: {r['reason']}")
    uid = fields["unit_id"]["value"] if not fields["unit_id"]["invalid"] else None
    return {
        "fields": fields,
        "flags": flags,
        "rules": rules,
        "ruleset": ruleset,
        "availability_snapshot": availability,
        "unit_id": uid if uid in units else None,
        "model_calls": model_calls,
        "citation_corrections": citation_corrections,
        "trace": [
            {"step": "read", "detail": f"{len(segments)} source segments"},
            {"step": "extract", "detail": provider.name},
            {"step": "verify", "detail": f"Check schema, exact quote membership and locations; {len(citation_corrections)} uniquely located exact quotes corrected"},
            {"step": "repair", "detail": "One verifier-feedback retry: " + "; ".join(feedback) if feedback else "No repair needed"},
            {"step": "validate", "detail": f"{len(rules)} deterministic policy checks using ruleset {ruleset['version']}"},
            {"step": "await_review", "detail": "No occupancy write until explicit approval"},
        ],
    }


def issue_agent(provider, images, report):
    valid_indexes = [i for i, image in enumerate(images) if not image.get("quality_warnings")]
    usable_images = [images[i] for i in valid_indexes]
    if usable_images:
        proposal = provider.issue(usable_images, report)
    else:
        proposal = IssueProposal.model_validate(
            {
                "observations": [],
                "title": "Request clearer photographs before specifying repairs",
                "description": "The images contain insufficient visual detail. Request clearer photographs or an in-person inspection."
                + ("\nReporter states (unverified): " + report if report else ""),
                "priority": "unknown",
                "limitations": [
                    "The image-quality gate blocked visual inference.",
                    "Reporter equipment, damage and safety claims are unverified.",
                ],
            }
        )
    if usable_images and not proposal.observations:
        raise ValueError("Model returned no image observations")
    observations = []
    cited_indexes = set()
    for o in proposal.observations:
        if not o.image_indexes or any(type(i) is not int or i < 0 or i >= len(usable_images) for i in o.image_indexes):
            raise ValueError("Model returned an invalid image citation")
        original_indexes = [valid_indexes[i] for i in o.image_indexes]
        cited_indexes.update(o.image_indexes)
        observations.append({**o.model_dump(), "image_indexes": original_indexes, "image_ids": [images[i]["id"] for i in original_indexes]})
    if cited_indexes != set(range(len(usable_images))):
        raise ValueError("Model must assess every usable photo. No issue record was created; retry or inspect manually.")
    for i, image in enumerate(images):
        if image.get("quality_warnings"):
            observations.append(
                {
                    "image_indexes": [i],
                    "image_ids": [image["id"]],
                    "equipment": "Unidentified",
                    "condition": "unknown",
                    "visible_damage": "No visual damage can be established from this image.",
                    "explanation": " ".join(image["quality_warnings"]),
                }
            )
    if not proposal.title.strip() or not proposal.description.strip():
        raise ValueError("Model returned an empty work order")
    return {
        "model_calls": [provider.last_call] if usable_images and getattr(provider, "last_call", None) else [],
        "observations": observations,
        "work_order": {"title": proposal.title, "description": proposal.description, "priority": proposal.priority, "decision": "pending"},
        "limitations": proposal.limitations,
        "trace": [
            {"step": "inspect", "detail": provider.name if usable_images else "Image-quality gate; no model call"},
            {"step": "verify", "detail": "Validate image references and typed condition labels"},
            {"step": "draft", "detail": "No vendor dispatch or financial commitment"},
            {"step": "await_review", "detail": "Owner can correct, accept or reject draft"},
        ],
    }
