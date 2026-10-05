"""Adversarial inputs and persistence checks beyond the happy path."""

import json
import random
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfWriter
from app.agents import issue_agent
from app.domain import FIELD_TYPES, IssueProposal, validate_value
from app.main import create_app
from app.providers import DemoProvider, ModelError, OpenAIProvider
from app.rules import evaluate
from test_workflows import upload, review_all, activate
from test_provider_failures import response_client

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_STORAGE", str(tmp_path / "files"))
    return TestClient(create_app(tmp_path / "db.sqlite3", DemoProvider(ROOT / "samples/vision_fixtures.json")))


@pytest.mark.parametrize(
    "value",
    [
        "0.001",
        "8500.000000000000000000000000001",
        "1e-999999999999999999",
        "sNaN",
        "Infinity",
        "-Infinity",
        "1e999999",
        {},
        [],
        True,
        "",
        "QAR 8500",
    ],
)
def test_money_invalid_values_are_validation_errors(value):
    with pytest.raises(ValueError):
        validate_value("monthly_rent", value)


@pytest.mark.parametrize("reason", ["   ", "\n\t ", " x "])
def test_review_reason_requires_meaningful_text(client, reason):
    lease = upload(client)
    response = client.post(
        f"/api/leases/{lease['id']}/fields/tenant/review", json={"decision": "accepted", "reason": reason, "expected_revision": 1}
    )
    assert response.status_code == 422
    assert client.get("/api/leases/" + lease["id"]).json()["revision"] == 1
    assert len(client.get("/api/audit/" + lease["id"]).json()) == 1


@pytest.mark.parametrize("revision", [True, "1", 1.0])
def test_revision_requires_integer_json_type(client, revision):
    lease = upload(client)
    response = client.post(
        f"/api/leases/{lease['id']}/fields/tenant/review",
        json={"decision": "accepted", "reason": "Verified source", "expected_revision": revision},
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        None,
        [],
        {"status": "completed", "output": None},
        {"status": "completed", "usage": [], "output": [None]},
        {"status": "completed", "output": [{"content": None}]},
    ],
)
def test_malformed_provider_envelopes_are_safe_errors(monkeypatch, body):
    response_client(monkeypatch, 200, body)
    with pytest.raises(ModelError):
        OpenAIProvider("fake-key", "test-model")._request("test", [], IssueProposal)


@pytest.mark.parametrize("failure", [httpx.ConnectError("private upstream data"), httpx.ReadTimeout("private upstream data")])
def test_network_failure_has_sanitized_error(monkeypatch, failure):
    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, *args, **kwargs):
            raise failure

    monkeypatch.setattr("app.providers.httpx.Client", Client)
    with pytest.raises(ModelError) as caught:
        OpenAIProvider("private-key", "test-model")._request("test", [], IssueProposal)
    assert "private" not in str(caught.value)


def test_model_must_cover_every_usable_photo():
    class Partial:
        name = "test"

        def issue(self, images, report):
            return IssueProposal.model_validate(
                {
                    "observations": [
                        {
                            "image_indexes": [0],
                            "equipment": "Sink",
                            "condition": "unknown",
                            "visible_damage": "No claim",
                            "explanation": "Inspect",
                        }
                    ],
                    "title": "Inspect",
                    "description": "Inspect sink",
                    "priority": "unknown",
                    "limitations": [],
                }
            )

    with pytest.raises(ValueError, match="every"):
        issue_agent(Partial(), [{"id": "one"}, {"id": "two"}], "")


@pytest.mark.parametrize(
    "name,raw",
    [
        ("bad.pdf", b"%PDF-1.7 broken"),
        ("bad.docx", b"not a zip"),
        ("empty.txt", b" \n\t"),
        ("bad.txt", b"\xff\xfe"),
        ("long.txt", b"x" * 80001),
    ],
)
def test_bad_documents_do_not_create_records_or_files(client, name, raw):
    response = client.post("/api/leases", files={"file": (name, raw)})
    assert response.status_code == 422
    assert client.get("/api/leases").json() == []


@pytest.mark.parametrize("kind", ["encrypted", "too_many_pages", "expanded_docx"])
def test_document_resource_limits(client, kind):
    stream = BytesIO()
    if kind == "expanded_docx":
        with ZipFile(stream, "w", ZIP_DEFLATED) as z:
            z.writestr("huge.xml", b"x" * (20 * 1024 * 1024 + 1))
        name = "large.docx"
    else:
        pdf = PdfWriter()
        for _ in range(31 if kind == "too_many_pages" else 1):
            pdf.add_blank_page(100, 100)
        if kind == "encrypted":
            pdf.encrypt("password")
        pdf.write(stream)
        name = "lease.pdf"
    assert client.post("/api/leases", files={"file": (name, stream.getvalue())}).status_code == 422


@pytest.mark.parametrize("fmt", ["GIF", "BMP", "TIFF"])
def test_non_supported_image_formats_rejected(client, fmt):
    stream = BytesIO()
    Image.new("RGB", (20, 20), "blue").save(stream, format=fmt)
    assert (
        client.post("/api/units/MC-B-1204/issues", files={"photos": ("disguised.png", stream.getvalue(), "image/png")}).status_code == 422
    )


@pytest.mark.parametrize("case", ["five_photos", "long_report", "empty_photo", "huge_pixels", "truncated_png"])
def test_image_and_report_limits(client, case):
    stream = BytesIO()
    Image.new("RGB", (4001, 4000) if case == "huge_pixels" else (20, 20), "blue").save(stream, format="PNG")
    raw = b"" if case == "empty_photo" else stream.getvalue()[:-12] if case == "truncated_png" else stream.getvalue()
    files = [("photos", ("x.png", raw, "image/png"))] * (5 if case == "five_photos" else 1)
    result = client.post("/api/units/MC-B-1204/issues", files=files, data={"report": "x" * 4001 if case == "long_report" else ""})
    assert result.status_code == 422
    assert client.get("/api/units/MC-B-1204").json()["issues"] == []


def test_restart_preserves_active_lease_source_photos_and_audit(client):
    lease = activate(client, review_all(client, upload(client))).json()
    issue = client.post("/api/units/MC-B-1204/issues", files={"photos": ("ac.jpg", (ROOT / "samples/live/wall_ac.jpg").read_bytes())}).json()
    restarted = TestClient(create_app(client.app.state.store.path, DemoProvider(ROOT / "samples/vision_fixtures.json")))
    unit = restarted.get("/api/units/MC-B-1204").json()
    assert unit["status"] == "occupied" and unit["active_lease_id"] == lease["id"]
    assert unit["issues"][0]["id"] == issue["id"]
    assert restarted.get("/api/leases/" + lease["id"] + "/source").content == (ROOT / "samples/lease_valid.txt").read_bytes()
    photo = issue["photos"][0]
    assert restarted.get(f"/api/issues/{issue['id']}/photos/{photo['id']}").content == (ROOT / "samples/live/wall_ac.jpg").read_bytes()
    assert restarted.get("/api/audit/" + lease["id"]).json()[-1]["action"] == "lease_activated"


def test_eight_concurrent_reviews_have_one_winner(client):
    lease = upload(client)
    path = f"/api/leases/{lease['id']}/fields/tenant/review"
    body = {"decision": "accepted", "reason": "Verified source", "expected_revision": 1}
    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(lambda _: client.post(path, json=body).status_code, range(8)))
    assert statuses.count(200) == 1 and statuses.count(409) == 7
    assert len(client.get("/api/audit/" + lease["id"]).json()) == 2


def test_rejected_observation_cannot_leave_old_work_approved(client):
    issue = client.post("/api/units/MC-B-1204/issues", files={"photos": ("ac.jpg", (ROOT / "samples/live/wall_ac.jpg").read_bytes())}).json()
    approved = client.post(
        f"/api/issues/{issue['id']}/review", json={"decision": "accepted", "reason": "Checked photo", "expected_revision": 1}
    ).json()
    rejected = client.post(
        f"/api/issues/{issue['id']}/observations/0/review",
        json={"decision": "rejected", "reason": "Photo is unrelated", "expected_revision": approved["revision"]},
    ).json()
    assert rejected["work_order"]["decision"] == "pending"
    assert "All visual assessments rejected" in rejected["work_order"]["description"]


@pytest.mark.parametrize(
    "path",
    [
        "/api/leases/missing",
        "/api/leases/missing/source",
        "/api/issues/missing/photos/missing",
        "/api/units/missing/export",
        "/samples/..%2Fdata%2Funits.json",
    ],
)
def test_unknown_ids_and_traversal_return_not_found(client, path):
    assert client.get(path).status_code == 404


def test_random_valid_policy_inputs_never_crash_and_rent_math_is_exact():
    rng = random.Random(721)
    rules = json.loads((ROOT / "data/owner_ruleset.json").read_text())
    for _ in range(500):
        monthly = Decimal(rng.randrange(0, 100000000)) / 100
        deposit = monthly + Decimal(rng.choice([-1, 0, 1]))
        deposit = max(Decimal(0), deposit)
        annual = monthly * 12 + Decimal(rng.choice([-1, 0, 1]))
        annual = max(Decimal(0), annual)
        fields = {name: {"value": None} for name in FIELD_TYPES}
        fields.update(
            {
                name: {"value": value}
                for name, value in [("monthly_rent", str(monthly)), ("deposit_amount", str(deposit)), ("annual_rent", str(annual))]
            }
        )
        results = {r["id"]: r for r in evaluate(fields, {}, rules)}
        assert results["R1"]["status"] == ("PASS" if deposit >= monthly else "FAIL")
        assert results["R6"]["status"] == ("PASS" if annual == monthly * 12 else "FAIL")
        assert all(r["status"] in ("PASS", "FAIL", "NOT_DETERMINABLE") for r in results.values())


def test_activation_transaction_rolls_back_on_audit_failure(client, monkeypatch):
    import sqlite3

    lease = review_all(client, upload(client))

    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("Simulated audit write failure")

    monkeypatch.setattr(client.app.state.store, "audit", fail)
    failed = TestClient(client.app, raise_server_exceptions=False)
    assert activate(failed, lease).status_code == 500
    assert client.get("/api/units/MC-B-1204").json()["status"] == "available"
    assert client.get("/api/leases/" + lease["id"]).json()["status"] == "draft"
    assert not any(e["action"] == "lease_activated" for e in client.get("/api/audit/" + lease["id"]).json())


def test_issue_model_failure_leaves_no_issue_or_photo_files(client):
    class Failing(DemoProvider):
        def issue(self, images, report):
            raise ModelError("Provider unavailable. No record was created.")

    failed = TestClient(create_app(client.app.state.store.path, Failing(ROOT / "samples/vision_fixtures.json")))
    assert (
        failed.post("/api/units/MC-B-1204/issues", files={"photos": ("ac.jpg", (ROOT / "samples/live/wall_ac.jpg").read_bytes())}).status_code
        == 502
    )
    assert failed.get("/api/units/MC-B-1204").json()["issues"] == []
    import os

    assert not list(Path(os.environ["APP_STORAGE"]).glob("*.png"))


@pytest.mark.parametrize("filename", ["lease_valid.txt", "lease_problematic.txt", "lease_missing.txt", "lease_occupied.txt"])
def test_docx_lease_roundtrip_retains_expected_rules(client, filename):
    from docx import Document

    original = upload(client, filename)
    d = Document()
    for line in (ROOT / "samples" / filename).read_text().splitlines():
        d.add_paragraph(line)
    stream = BytesIO()
    d.save(stream)
    docx = client.post("/api/leases", files={"file": ("lease.docx", stream.getvalue())})
    assert docx.status_code == 201
    result = docx.json()
    assert [(r["id"], r["status"]) for r in result["rules"]] == [(r["id"], r["status"]) for r in original["rules"]]
    assert all(e["location"].startswith("Paragraph") for f in result["fields"].values() for e in f["evidence"])


@pytest.mark.parametrize("filename", ["lease_valid.txt", "lease_problematic.txt", "lease_missing.txt", "lease_occupied.txt"])
def test_pdf_lease_roundtrip_retains_expected_rules(client, filename):
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

    original = upload(client, filename)
    writer = PdfWriter()
    page = writer.add_blank_page(612, 792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    commands = ["BT /F1 10 Tf 10 780 Td"]
    for line in (ROOT / "samples" / filename).read_text().splitlines():
        escaped = line.replace("—", "-").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        commands.append(f"({escaped}) Tj 0 -16 Td")
    commands.append("ET")
    content = DecodedStreamObject()
    content.set_data("\n".join(commands).encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(content)
    stream = BytesIO()
    writer.write(stream)
    pdf = client.post("/api/leases", files={"file": ("lease.pdf", stream.getvalue())})
    assert pdf.status_code == 201
    assert [(r["id"], r["status"]) for r in pdf.json()["rules"]] == [(r["id"], r["status"]) for r in original["rules"]]
    assert all(e["location"] == "Page 1" for f in pdf.json()["fields"].values() for e in f["evidence"])


@pytest.mark.parametrize("seed", range(8))
def test_generated_document_garbage_is_rejected_safely(client, seed):
    rng = random.Random(seed)
    raw = bytes(rng.randrange(256) for _ in range(128))
    for suffix in ["pdf", "docx", "txt"]:
        assert client.post("/api/leases", files={"file": ("bad." + suffix, raw)}).status_code == 422
    assert client.get("/api/leases").json() == []


@pytest.mark.parametrize("length_header", [None, str(33 * 1024 * 1024)])
def test_request_body_limit_even_without_content_length(client, length_header):
    boundary = "leaseworks-test"

    def body():
        yield (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="lease.txt"\r\nContent-Type: text/plain\r\n\r\n'
        ).encode()
        for _ in range(33):
            yield b"x" * (1024 * 1024)
        yield f"\r\n--{boundary}--\r\n".encode()

    headers = {"content-type": f"multipart/form-data; boundary={boundary}"}
    if length_header:
        headers["content-length"] = length_header
    response = client.post("/api/leases", content=body(), headers=headers)
    assert response.status_code == 413
    assert client.get("/api/leases").json() == []


@pytest.mark.parametrize("filename", sorted(p.name for p in (ROOT / "results/live/final").glob("prose_*.json")))
def test_saved_live_lease_values_satisfy_stricter_validation(filename):
    record = json.loads((ROOT / "results/live/final" / filename).read_text())
    for name, field in record["fields"].items():
        assert not field["invalid"]
        validate_value(name, field["value"])
    sources = {s["id"]: s["text"] for s in record["segments"]}
    for field in record["fields"].values():
        for e in field["evidence"]:
            assert sources[e["segment_id"]][e["start"] : e["end"]] == e["quote"]


@pytest.mark.parametrize("filename", ["real_wall_ac.json", "real_rusty_coil.json", "real_multi_photo.json"])
def test_saved_live_photo_proposals_cover_all_photos(filename):
    record = json.loads((ROOT / "results/live/final" / filename).read_text())
    indexes = {i for o in record["observations"] for i in o["image_indexes"]}
    assert indexes == set(range(len(record["photos"])))
    assert all(set(o["image_ids"]).issubset({p["id"] for p in record["photos"]}) for o in record["observations"])
