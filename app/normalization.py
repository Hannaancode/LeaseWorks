"""Reject date assumptions that source evidence cannot resolve."""

import re
from datetime import date

FREQUENCIES = {
    'month': 'monthly', 'per month': 'monthly', 'monthly': 'monthly',
    'year': 'annual', 'yearly': 'annual', 'annually': 'annual', 'annual': 'annual',
    'quarter': 'quarterly', 'quarterly': 'quarterly', 'week': 'weekly', 'weekly': 'weekly',
}


def normalize_stated_term(field, segments):
    """Keep an explicit English fixed term, never a term inferred from dates."""
    if field.name != "term_months" or field.value is None:
        return None
    source = {segment["id"]: segment["text"] for segment in segments}
    words = {word: number for number, word in enumerate(
        "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
    )}
    words.update({"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90})
    values = set()
    patterns = [
        r"\bfixed\s+term\s*(?:is|of|shall be|shall last|:)\s*(\d{1,3}|[a-z]+(?:[- ][a-z]+)?)\s+months?\b",
        r"\bfixed\s+term\s+months\s*:\s*(\d{1,3})\b",
    ]
    for citation in field.evidence:
        if citation.quote not in source.get(citation.segment_id, ""):
            continue
        for pattern in patterns:
            for match in re.finditer(pattern, citation.quote, re.I):
                token = match.group(1).lower()
                parts = token.replace("-", " ").split()
                if token.isdigit():
                    values.add(int(token))
                elif len(parts) == 1 and parts[0] in words:
                    values.add(words[parts[0]])
                elif len(parts) == 2 and words.get(parts[0], 0) >= 20 and 0 < words.get(parts[1], 0) < 10:
                    values.add(words[parts[0]] + words[parts[1]])
    if len(values) == 1 and field.value != next(iter(values)):
        original = field.value
        field.value = next(iter(values))
        field.explanation += " Source verifier retained the explicitly stated fixed term instead of an inferred date duration."
        return original
    return None


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


def explicit_money_currencies(segments):
    """A single-currency record cannot reconcile explicit mixed-currency amounts."""
    found = {}
    for segment in segments:
        for match in re.finditer(r"\b(QAR|QR|USD|AED|EUR|GBP|AUD|CAD)\s+\d[\d,]*(?:\.\d{1,2})?\b", segment["text"], re.I):
            currency = match.group(1).upper()
            found.setdefault("QAR" if currency == "QR" else currency, []).append((segment, match.group()))
    return found if len(found) > 1 else {}
