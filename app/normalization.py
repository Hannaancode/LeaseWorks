"""Reject date assumptions that source evidence cannot resolve."""

import re
from datetime import date

FREQUENCIES = {
    'month': 'monthly', 'per month': 'monthly', 'monthly': 'monthly',
    'year': 'annual', 'yearly': 'annual', 'annually': 'annual', 'annual': 'annual',
    'quarter': 'quarterly', 'quarterly': 'quarterly', 'week': 'weekly', 'weekly': 'weekly',
}


def normalize_frequency(field):
    if field.name == 'rent_frequency' and isinstance(field.value, str):
        normalized = FREQUENCIES.get(field.value.strip().lower())
        if normalized and field.value != normalized:
            original = field.value
            field.value = normalized
            field.explanation += f' Canonical frequency normalization from {original!r} to {normalized!r}.'
            return original
    return None


def ambiguous_date_reason(field, segments):
    if field.name not in ("commencement_date", "expiry_date") or field.value is None:
        return None
    quoted = " ".join(c.quote for c in field.evidence)
    if isinstance(field.value, str) and field.value in quoted:
        return None
    numeric = re.findall(r"(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](\d{4}|\d{2})(?!\d)", quoted)
    source = "\n".join(s["text"] for s in segments)
    day_first = bool(re.search(r"\bDD\s*[/.-]\s*MM\s*[/.-]\s*YYYY\b|\bday\s*[/ -]\s*month\s*[/ -]\s*year\b", source, re.I))
    month_first = bool(re.search(r"\bMM\s*[/.-]\s*DD\s*[/.-]\s*YYYY\b|\bmonth\s*[/ -]\s*day\s*[/ -]\s*year\b", source, re.I))
    for first, second, year in numeric:
        a, b = int(first), int(second)
        literal = f"{first}/{second}/{year}"
        if len(year) != 4:
            return f"Date {literal} uses a two-digit year. Request a four-digit year from the owner."
        if 1 <= a <= 12 and 1 <= b <= 12 and a != b:
            if day_first == month_first:
                return f"Date {literal} is ambiguous between day/month and month/day. The source does not establish one format."
            try:
                resolved = date(int(year), b if day_first else a, a if day_first else b).isoformat()
            except ValueError:
                return f"Date {literal} cannot be normalized under the stated format."
            if field.value != resolved:
                return f"Date {literal} contradicts the declared format; expected {resolved}. Owner correction is required."
    return None


def conflicting_monthly_rents(segments):
    """Conservative English source check; it never chooses between schedules."""
    from decimal import Decimal
    currency = r'(?:QAR|USD|EUR|GBP|AED|\$)\s*'
    amount = r'(?P<amount>\d[\d,]*(?:\.\d{1,2})?)(?![\d,]|\.\d)'
    patterns = [
        rf'\bmonthly rent\s*(?:(?:is|of|shall be|:)\s*)?(?:{currency})?{amount}',
        rf'{currency}{amount}\s*(?:each month|per month|monthly)\b',
    ]
    found = []
    for segment in segments:
        for pattern in patterns:
            for match in re.finditer(pattern, segment['text'], re.I):
                found.append((Decimal(match.group('amount').replace(',', '')), segment, match.group()))
    if len({item[0] for item in found}) < 2:
        return []
    return found
