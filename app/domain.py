"""Typed model boundaries. AI proposes evidence; application code owns decisions."""

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal, Annotated
import re
from pydantic import BaseModel, ConfigDict, Field, JsonValue, StringConstraints

ReviewReason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=2000)]

FIELD_TYPES = {
    "landlord": "text",
    "tenant": "text",
    "unit_id": "text",
    "commencement_date": "date",
    "expiry_date": "date",
    "term_months": "integer",
    "rent_amount": "money",
    "rent_frequency": "frequency",
    "currency": "text",
    "monthly_rent": "money",
    "annual_rent": "money",
    "deposit_amount": "money",
    "escalation_clause": "text",
    "escalation_defined": "boolean",
    "renewal_terms": "text",
    "termination_terms": "text",
    "landlord_signed": "boolean",
    "tenant_signed": "boolean",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Citation(StrictModel):
    segment_id: str
    quote: str = Field(max_length=5000)


class Proposal(StrictModel):
    name: str
    value: str | bool | int | float | None
    evidence: list[Citation]
    explanation: str


class LeaseProposal(StrictModel):
    fields: list[Proposal]
    concerns: list[str]


class Observation(StrictModel):
    image_indexes: list[int]
    equipment: str
    condition: Literal["appears_new", "worn", "damaged", "unknown"]
    visible_damage: str
    explanation: str


class IssueProposal(StrictModel):
    observations: list[Observation]
    title: str
    description: str
    priority: Literal["routine", "urgent", "unknown"]
    limitations: list[str]


class Review(StrictModel):
    decision: Literal["accepted", "rejected"]
    reason: ReviewReason
    value: JsonValue = None
    replace_value: bool = False
    expected_revision: int = Field(ge=1, strict=True)


class Activation(StrictModel):
    expected_revision: int = Field(ge=1, strict=True)


class WorkReview(Review):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=4000)


class ObservationReview(StrictModel):
    decision: Literal["accepted", "rejected"]
    reason: ReviewReason
    expected_revision: int = Field(ge=1, strict=True)
    equipment: str | None = Field(default=None, min_length=1, max_length=300)
    condition: Literal["appears_new", "worn", "damaged", "unknown"] | None = None
    visible_damage: str | None = Field(default=None, min_length=1, max_length=2000)


def validate_value(name, value):
    if name not in FIELD_TYPES:
        raise ValueError("Unknown lease field")
    if value is None:
        return
    kind = FIELD_TYPES[name]
    if kind == "boolean" and type(value) is not bool:
        raise ValueError("Expected true or false")
    if kind == "integer" and (type(value) is not int or value <= 0 or value > 1200):
        raise ValueError("Expected a whole number from 1 to 1200 months")
    if kind == "money":
        if type(value) not in (str, int, float):
            raise ValueError("Expected a monetary amount")
        if len(str(value)) > 128:
            raise ValueError("Monetary representation is too long")
        try:
            amount = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError("Invalid monetary amount") from exc
        if not amount.is_finite() or amount < 0 or amount > Decimal("1000000000000"):
            raise ValueError("Amount must be nonnegative, no more than 1 trillion, and representable to two decimal places")
        # Inspect digits exactly: normalize() rounds under the Decimal context.
        digits = amount.as_tuple().digits
        trailing_zeroes = len(digits) - len("".join(map(str, digits)).rstrip("0"))
        if amount != 0 and amount.as_tuple().exponent + trailing_zeroes < -2:
            raise ValueError("Amount must be representable to two decimal places")
    if kind == "date":
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("Expected ISO date YYYY-MM-DD")
        date.fromisoformat(value)
    if kind == "text" and (not isinstance(value, str) or not value.strip() or len(value) > 5000):
        raise ValueError("Expected nonempty text")
    if kind == "frequency" and value not in ("monthly", "annual", "quarterly", "weekly"):
        raise ValueError("Frequency must be monthly, annual, quarterly or weekly")
