"""Provider faults are explicit and never disclose credentials or request data."""

import pytest
from app.providers import OpenAIProvider, ModelError
from app.domain import IssueProposal


def response_client(monkeypatch, status, data):
    class Response:
        status_code = status

        def json(self):
            return data

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr("app.providers.httpx.Client", Client)


@pytest.mark.parametrize(
    "status,text", [(400, "request format"), (401, "authentication"), (403, "access"), (429, "quota"), (503, "unavailable")]
)
def test_api_errors_explain_failure_without_secrets(monkeypatch, status, text):
    response_client(monkeypatch, status, {"error": {"message": "upstream content containing a secret"}})
    provider = OpenAIProvider("fake-key-do-not-echo", "gpt-4.1-mini")
    with pytest.raises(ModelError) as caught:
        provider._request("test", [], IssueProposal)
    assert text in str(caught.value)
    assert "No record was created" in str(caught.value)
    assert "fake-key" not in str(caught.value)
    assert "upstream content" not in str(caught.value)


def test_refusal_not_mistaken_for_json(monkeypatch):
    response_client(monkeypatch, 200, {"status": "completed", "output": [{"content": [{"type": "refusal", "refusal": "Declined"}]}]})
    with pytest.raises(ModelError, match="declined"):
        OpenAIProvider("fake", "gpt-4.1-mini")._request("test", [], IssueProposal)


def test_truncated_model_output_creates_no_record(monkeypatch):
    response_client(monkeypatch, 200, {"status": "incomplete", "output": []})
    with pytest.raises(ModelError, match="did not complete"):
        OpenAIProvider("fake", "gpt-4.1-mini")._request("test", [], IssueProposal)


def test_live_lease_decoder_bounds_evidence_without_changing_demo_schema(monkeypatch):
    import json
    from app.domain import LeaseProposal
    captured = {}

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, **kwargs):
            captured.update(kwargs["json"])

            class Response:
                status_code = 200

                def json(self):
                    return {"status": "completed", "output": [{"content": [{"type": "output_text", "text": json.dumps({"fields": [], "concerns": []})}]}]}

            return Response()

    monkeypatch.setattr("app.providers.httpx.Client", Client)
    OpenAIProvider("fake", "gpt-4.1-mini")._request("test", [], LeaseProposal)
    definitions = captured["text"]["format"]["schema"]["$defs"]
    assert definitions["Citation"]["properties"]["quote"]["maxLength"] == 160
    assert definitions["Proposal"]["properties"]["evidence"]["maxItems"] == 2
    assert LeaseProposal.model_json_schema()["$defs"]["Citation"]["properties"]["quote"]["maxLength"] == 5000
