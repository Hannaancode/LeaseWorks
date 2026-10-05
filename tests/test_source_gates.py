"""Regression tests from live evaluation failures, independent of the model."""

from pathlib import Path
import pytest
from app.domain import Proposal
from app.normalization import ambiguous_date_reason
from app.agents import lease_agent, issue_agent
from app.providers import DemoProvider
from app.documents import read_document

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    "literal,value,format_clause,blocked",
    [
        ("01/02/2026", "2026-02-01", "", True),
        ("01/02/2026", "2026-02-01", "Dates are DD/MM/YYYY", False),
        ("01/02/2026", "2026-01-02", "Dates are MM/DD/YYYY", False),
        ("01/02/2026", "2026-01-02", "Dates are DD/MM/YYYY", True),
        ("01/02/26", "2026-02-01", "", True),
        ("01/01/2026", "2026-01-01", "", False),
    ],
)
def test_numeric_dates_require_source_format(literal, value, format_clause, blocked):
    field = Proposal(name="commencement_date", value=value, evidence=[{"segment_id": "s1", "quote": literal}], explanation="test")
    reason = ambiguous_date_reason(field, [{"id": "s1", "text": literal}, {"id": "s2", "text": format_clause}])
    assert bool(reason) is blocked


def test_model_date_guess_becomes_unknown_with_original_retained():
    class Guessing(DemoProvider):
        def lease(self, segments, feedback=None):
            proposal = super().lease(segments)
            field = next(f for f in proposal.fields if f.name == "commencement_date")
            field.value = "2026-02-01"
            return proposal

    text = (ROOT / "samples/lease_valid.txt").read_bytes().replace(b"2026-10-01", b"01/02/2026")
    from json import loads

    lease = lease_agent(
        Guessing(ROOT / "samples/vision_fixtures.json"),
        read_document("lease.txt", text),
        {"MC-B-1204": {"status": "available"}},
        loads((ROOT / "data/owner_ruleset.json").read_text()),
    )
    assert lease["fields"]["commencement_date"]["value"] is None
    assert lease["fields"]["commencement_date"]["original_value"] == "2026-02-01"
    assert any(flag["kind"] == "ambiguous_date" for flag in lease["flags"])
    assert next(r for r in lease["rules"] if r["id"] == "R4")["status"] == "NOT_DETERMINABLE"


def test_blank_photo_never_calls_model():
    class NeverCalled:
        name = "test"

        def issue(self, images, report):
            raise AssertionError("Blank images must not invoke visual inference")

    result = issue_agent(
        NeverCalled(), [{"id": "blank", "quality_warnings": ["No visual detail"]}], "Definitely a broken AC and a gas leak"
    )
    assert result["observations"][0]["equipment"] == "Unidentified"
    assert result["observations"][0]["condition"] == "unknown"
    assert result["model_calls"] == []


def test_mixed_image_quality_keeps_original_reference_indexes():
    from app.domain import IssueProposal

    class Vision:
        name = "test"

        def issue(self, images, report):
            assert len(images) == 1 and images[0]["id"] == "usable"
            return IssueProposal.model_validate(
                {
                    "observations": [
                        {
                            "image_indexes": [0],
                            "equipment": "AC",
                            "condition": "unknown",
                            "visible_damage": "Not confirmed",
                            "explanation": "Inspection required",
                        }
                    ],
                    "title": "Inspect",
                    "description": "Inspect AC",
                    "priority": "unknown",
                    "limitations": [],
                }
            )

    result = issue_agent(Vision(), [{"id": "blank", "quality_warnings": ["Insufficient detail"]}, {"id": "usable"}], "Unverified AC claim")
    assert result["observations"][0]["image_indexes"] == [1]
    assert result["observations"][0]["image_ids"] == ["usable"]
    assert result["observations"][1]["equipment"] == "Unidentified"


@pytest.mark.parametrize('literal,expected', [('month', 'monthly'), ('YEARLY', 'annual')])
def test_frequency_normalization_preserves_original(literal, expected):
    from app.normalization import normalize_frequency
    field = Proposal(name='rent_frequency', value=literal, evidence=[], explanation='Source wording')
    assert normalize_frequency(field) == literal
    assert field.value == expected
    assert literal in field.explanation


@pytest.mark.parametrize('second,conflict', [('9,000', True), ('8,500', False)])
def test_conflicting_monthly_rent_source_gate(second, conflict):
    from app.normalization import conflicting_monthly_rents
    segments = [{'id': 's1', 'text': 'The tenant shall pay QAR 8,500 each month.'},
                {'id': 's2', 'text': f'The monthly rent is QAR {second}.'}]
    assert bool(conflicting_monthly_rents(segments)) is conflict


def test_model_cannot_choose_one_of_conflicting_rents():
    import json
    class ChoosesFirst(DemoProvider):
        def lease(self, segments, feedback=None):
            clean = read_document('clean.txt', (ROOT / 'samples/lease_valid.txt').read_bytes())
            proposal = super().lease(clean)
            # Use valid source citations so this test isolates conflicting amounts.
            for field in proposal.fields:
                field.value = None
                field.evidence = []
            monthly = next(f for f in proposal.fields if f.name == 'monthly_rent')
            monthly.value = '8500'
            monthly.evidence = [{'segment_id': 's1', 'quote': 'QAR 8,500 each month'}]
            from app.domain import Citation
            monthly.evidence = [Citation.model_validate(c) for c in monthly.evidence]
            return proposal
    segments = [{'id': 's1', 'text': 'QAR 8,500 each month', 'location': 'line 1'},
                {'id': 's2', 'text': 'monthly rent is QAR 9,000', 'location': 'line 2'}]
    lease = lease_agent(ChoosesFirst(ROOT / 'samples/vision_fixtures.json'), segments, {}, json.loads((ROOT / 'data/owner_ruleset.json').read_text()))
    assert lease['fields']['monthly_rent']['value'] is None
    assert lease['fields']['monthly_rent']['original_value'] == '8500'
    assert {e['segment_id'] for e in lease['fields']['monthly_rent']['evidence']} == {'s1', 's2'}
    assert next(r for r in lease['rules'] if r['id'] == 'R1')['status'] == 'NOT_DETERMINABLE'
