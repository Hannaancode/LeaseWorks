"""Extreme values fail review safely instead of crashing policy evaluation."""

import pytest
from app.domain import validate_value
from app.rules import evaluate


@pytest.mark.parametrize("name,value", [("term_months", 99999999), ("monthly_rent", "1e99999"), ("expiry_date", "20261001")])
def test_extreme_values_are_invalid(name, value):
    with pytest.raises(ValueError):
        validate_value(name, value)


def test_redundant_decimal_zeroes_do_not_invalidate_money():
    validate_value("monthly_rent", "8500.000")


def test_calendar_overflow_is_a_rule_failure():
    fields = {
        name: {"value": value} for name, value in [("commencement_date", "9999-12-01"), ("expiry_date", "9999-12-31"), ("term_months", 12)]
    }
    rules = {"rules": [{"id": "R4", "description": "Date agreement", "severity": "high"}]}
    result = evaluate(fields, {}, rules)
    assert result[0]["status"] == "FAIL"
    assert "supported calendar" in result[0]["reason"]
