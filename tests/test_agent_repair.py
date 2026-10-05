"""An agent uses verifier feedback once, then suspends unsafe proposals."""

from pathlib import Path
import json
from app.agents import lease_agent
from app.documents import read_document
from app.providers import DemoProvider

ROOT = Path(__file__).resolve().parent.parent


def test_agent_repairs_fabricated_source_quote_once():
    class Repairing(DemoProvider):
        calls = 0
        feedback_received = None

        def lease(self, segments, feedback=None):
            self.calls += 1
            proposal = super().lease(segments)
            if feedback is None:
                proposal.fields[0].evidence[0].quote = "Fabricated source"
            else:
                self.feedback_received = feedback
            return proposal

    model = Repairing(ROOT / "samples/vision_fixtures.json")
    source = read_document("lease.txt", (ROOT / "samples/lease_valid.txt").read_bytes())
    units = {"MC-B-1204": {"status": "available"}}
    result = lease_agent(model, source, units, json.loads((ROOT / "data/owner_ruleset.json").read_text()))
    assert model.calls == 2
    assert any("quote is not present" in error for error in model.feedback_received)
    assert any("Previous proposal to repair:" in error and "Fabricated source" in error for error in model.feedback_received)
    assert result["fields"]["landlord"]["invalid"] is False
    assert "retry" in next(s for s in result["trace"] if s["step"] == "repair")["detail"]


def test_explicit_term_is_preserved_when_model_reconciles_wrong_dates():
    class ComputedTerm(DemoProvider):
        def lease(self, segments, feedback=None):
            proposal = super().lease(segments, feedback)
            term = next(field for field in proposal.fields if field.name == "term_months")
            term.value = 11
            return proposal

    source = read_document("lease.txt", (ROOT / "samples/lease_problematic.txt").read_bytes())
    result = lease_agent(ComputedTerm(ROOT / "samples/vision_fixtures.json"), source, {"MC-B-1204": {"status": "available"}}, json.loads((ROOT / "data/owner_ruleset.json").read_text()))
    assert result["fields"]["term_months"]["value"] == 12
    assert result["fields"]["term_months"]["original_value"] == 11
    assert next(rule for rule in result["rules"] if rule["id"] == "R4")["status"] == "FAIL"


def test_stated_term_verifier_does_not_trust_a_fabricated_quote():
    from app.domain import LeaseProposal
    from app.normalization import normalize_stated_term

    field = LeaseProposal.model_validate({"fields": [{"name": "term_months", "value": 11, "evidence": [{"segment_id": "s1", "quote": "The fixed term is twelve months"}], "explanation": "test"}], "concerns": []}).fields[0]
    assert normalize_stated_term(field, [{"id": "s1", "text": "The fixed term is twenty-four months"}]) is None
    assert field.value == 11


def test_unique_exact_quote_is_relocated_with_an_audit_record():
    class WrongLocation(DemoProvider):
        calls = 0

        def lease(self, segments, feedback=None):
            self.calls += 1
            proposal = super().lease(segments, feedback)
            proposal.fields[0].evidence[0].segment_id = "nonexistent"
            return proposal

    model = WrongLocation(ROOT / "samples/vision_fixtures.json")
    source = read_document("lease.txt", (ROOT / "samples/lease_valid.txt").read_bytes())
    result = lease_agent(model, source, {"MC-B-1204": {"status": "available"}}, json.loads((ROOT / "data/owner_ruleset.json").read_text()))
    assert model.calls == 1
    assert not result["fields"]["landlord"]["invalid"]
    assert result["citation_corrections"][0]["proposed_segment_id"] == "nonexistent"
    assert result["fields"]["landlord"]["proposed_evidence"][0]["segment_id"] == "nonexistent"


def test_ambiguous_exact_quote_is_not_relocated_by_guessing():
    class AmbiguousLocation(DemoProvider):
        def lease(self, segments, feedback=None):
            proposal = super().lease(segments, feedback)
            proposal.fields[0].evidence[0].segment_id = "nonexistent"
            return proposal

    source = read_document("lease.txt", (ROOT / "samples/lease_valid.txt").read_bytes())
    landlord = next(segment for segment in source if segment["text"].startswith("Landlord:"))
    source.append({**landlord, "id": "duplicate"})
    result = lease_agent(AmbiguousLocation(ROOT / "samples/vision_fixtures.json"), source, {"MC-B-1204": {"status": "available"}}, json.loads((ROOT / "data/owner_ruleset.json").read_text()))
    assert result["fields"]["landlord"]["invalid"]
    assert not result["citation_corrections"]


def test_equal_numbers_in_different_currencies_do_not_reconcile():
    source = read_document("lease.txt", (ROOT / "samples/lease_valid.txt").read_bytes())
    source.append({"id": "mixed", "text": "Monthly rent is QAR 8500; annual rent is USD 102000", "location": "Line 30"})
    result = lease_agent(DemoProvider(ROOT / "samples/vision_fixtures.json"), source, {"MC-B-1204": {"status": "available"}}, json.loads((ROOT / "data/owner_ruleset.json").read_text()))
    assert result["fields"]["monthly_rent"]["value"] is None
    assert result["fields"]["monthly_rent"]["original_value"] == "8500"
    assert any(flag["kind"] == "currency_conflict" for flag in result["flags"])
    assert next(rule for rule in result["rules"] if rule["id"] == "R6")["status"] == "NOT_DETERMINABLE"
