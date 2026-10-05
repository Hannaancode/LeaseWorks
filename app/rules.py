"""Versioned deterministic policy evaluation. Never execute the rules' check strings."""

import calendar
from datetime import date, timedelta
from decimal import Decimal

RULE_FIELDS = {
    "R1": ["deposit_amount", "monthly_rent"],
    "R2": ["escalation_clause", "escalation_defined"],
    "R3": ["term_months"],
    "R4": ["commencement_date", "expiry_date", "term_months"],
    "R5": ["landlord", "tenant", "landlord_signed", "tenant_signed"],
    "R6": ["annual_rent", "monthly_rent"],
    "R7": ["unit_id"],
}


def add_months(day, months):
    year, month = divmod(day.year * 12 + day.month - 1 + months, 12)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def evaluate(fields: dict, units: dict, ruleset: dict, availability: dict | None = None):
    def val(name):
        f = fields.get(name, {})
        if f.get("decision") == "rejected" or f.get("invalid"):
            return None
        return f.get("value")

    values = {k: val(k) for k in fields}
    results = []
    for spec in ruleset["rules"]:
        rid = spec["id"]
        needed = RULE_FIELDS.get(rid)
        result = {**spec, "status": "NOT_DETERMINABLE", "reason": "", "evidence": []}
        if not needed:
            result["reason"] = "No evaluator registered for this rule version."
            results.append(result)
            continue
        result["evidence"] = [e for k in needed for e in fields.get(k, {}).get("evidence", [])]
        missing = [k for k in needed if values.get(k) is None]
        if missing:
            result["reason"] = "Missing, rejected, or invalid: " + ", ".join(missing)
            results.append(result)
            continue
        v = values
        passed = False
        if rid == "R1":
            deposit, monthly = Decimal(str(v["deposit_amount"])), Decimal(str(v["monthly_rent"]))
            passed = deposit >= monthly
            reason = f"Deposit {deposit} compared with monthly rent {monthly}."
        elif rid == "R2":
            # The model identifies the mechanism; its exact clause remains reviewable.
            vague = v["escalation_clause"].strip().lower() in ("as mutually agreed", "mutually agreed", "none")
            passed = v["escalation_defined"] is True and not vague
            reason = "Defined escalation mechanism proposed with cited clause." if passed else "No defined escalation mechanism."
        elif rid == "R3":
            passed = v["term_months"] <= 36
            reason = f"Stated term is {v['term_months']} months; limit is 36. Longer terms need owner approval outside this prototype."
        elif rid == "R4":
            start, end = date.fromisoformat(v["commencement_date"]), date.fromisoformat(v["expiry_date"])
            try:
                anniversary = add_months(start, v["term_months"])
            except (ValueError, OverflowError):
                result.update(
                    status="FAIL", reason="The stated term produces a date outside the supported calendar. Correct the dates or term."
                )
                results.append(result)
                continue
            # Explicit convention: inclusive last day OR exclusive anniversary.
            passed = end > start and end in (anniversary, anniversary - timedelta(days=1))
            reason = f"Expected expiry {anniversary - timedelta(days=1)} (inclusive) or {anniversary} (exclusive); stated {end}."
        elif rid == "R5":
            passed = v["landlord_signed"] is True and v["tenant_signed"] is True
            reason = (
                "Both parties identified and signature markers reported; authenticity is not verified."
                if passed
                else "One or both signature markers are absent."
            )
        elif rid == "R6":
            annual, monthly = Decimal(str(v["annual_rent"])), Decimal(str(v["monthly_rent"]))
            passed = annual == monthly * 12
            reason = f"Annual rent {annual}; monthly × 12 = {monthly * 12}."
        elif rid == "R7":
            unit = units.get(v["unit_id"])
            status = (availability or {}).get(v["unit_id"], unit["status"] if unit else None)
            passed = unit is not None and status == "available"
            reason = f"Unit {v['unit_id']} {'exists and was ' + str(status) + ' before linking' if unit else 'does not exist in supplied register'}."
        result.update(status="PASS" if passed else "FAIL", reason=reason)
        results.append(result)
    return results
