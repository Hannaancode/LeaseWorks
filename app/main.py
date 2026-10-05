"""HTTP API and static owner console. Run: python -m uvicorn app.main:app."""

import hashlib
import json
import os
import uuid
from io import BytesIO
from pathlib import Path
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from .agents import lease_agent, issue_agent
from .documents import read_document, MAX_DOCUMENT_BYTES
from .domain import Review, Activation, WorkReview, ObservationReview, validate_value
from .providers import DemoProvider, OpenAIProvider, ModelError
from .rules import evaluate
from .store import Store, now
from .boundaries import RequestBodyLimit

ROOT = Path(__file__).resolve().parent.parent
MAX_IMAGE_BYTES = 6 * 1024 * 1024


def create_app(db_path=None, provider=None):
    storage = Path(os.environ.get("APP_STORAGE", ROOT / "var"))
    storage.mkdir(parents=True, exist_ok=True)
    store = Store(Path(db_path) if db_path else storage / "leaseworks.sqlite3", ROOT / "data/units.json")
    mode = os.environ.get("MODEL_PROVIDER", "demo")
    model = provider or (
        OpenAIProvider(os.environ.get("OPENAI_API_KEY"), os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"))
        if mode == "openai"
        else DemoProvider(ROOT / "samples/vision_fixtures.json")
        if mode == "demo"
        else None
    )
    if model is None:
        raise ValueError("MODEL_PROVIDER must be demo or openai")
    ruleset = json.loads((ROOT / "data/owner_ruleset.json").read_text())
    api = FastAPI(
        title="LeaseWorks",
        version="1.0.0",
        description="Traceable lease and property issue review. Local sample-data prototype.",
        docs_url=None,
        redoc_url=None,
    )
    api.state.store, api.state.provider = store, model
    api.add_middleware(RequestBodyLimit)

    @api.middleware("http")
    async def local_boundary(request, call_next):
        # Not authentication. Block browser cross-origin writes to this local app.
        origin = request.headers.get("origin")
        if request.method not in ("GET", "HEAD", "OPTIONS") and origin and origin != str(request.base_url).rstrip("/"):
            return JSONResponse({"detail": "Cross-origin writes are disabled"}, status_code=403)
        try:
            too_large = int(request.headers.get("content-length", "0")) > 32 * 1024 * 1024
        except ValueError:
            too_large = True
        if too_large:
            return JSONResponse({"detail": "Request exceeds 32 MiB"}, status_code=413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @api.exception_handler(ModelError)
    async def model_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=502)

    def required(db, table, entity_id):
        entity = store.get(db, table, entity_id)
        if entity is None:
            raise HTTPException(404, "Record not found")
        return entity

    def revision(entity, requested):
        if entity["revision"] != requested:
            raise HTTPException(409, "Record changed. Refresh and review the latest version.")

    def refresh_lease(lease, units):
        f = lease["fields"]["unit_id"]
        uid = f["value"] if f["decision"] != "rejected" and not f["invalid"] else None
        lease["unit_id"] = uid if uid in units else None
        lease["rules"] = evaluate(lease["fields"], units, lease["ruleset"], lease["availability_snapshot"])

    @api.get("/api/health")
    def health():
        return {"status": "ok", "provider": model.name, "sample_data_only": True}

    @api.get("/api/units")
    def list_units():
        with store.transaction() as db:
            return list(store.units(db).values())

    @api.get("/api/leases")
    def list_leases():
        with store.transaction() as db:
            return [json.loads(r["data"]) for r in db.execute("SELECT data FROM leases ORDER BY rowid DESC")]

    @api.get("/api/units/{unit_id}")
    def unit_detail(unit_id: str):
        with store.transaction() as db:
            unit = required(db, "units", unit_id)
            unit["leases"] = [
                json.loads(r["data"]) for r in db.execute("SELECT data FROM leases WHERE unit_id=? ORDER BY rowid DESC", (unit_id,))
            ]
            unit["issues"] = [
                json.loads(r["data"]) for r in db.execute("SELECT data FROM issues WHERE unit_id=? ORDER BY rowid DESC", (unit_id,))
            ]
            return unit

    @api.post("/api/leases", status_code=201)
    def upload_lease(file: UploadFile = File(...)):
        raw = file.file.read(MAX_DOCUMENT_BYTES + 1)
        try:
            segments = read_document(file.filename or "", raw)
        except Exception as exc:
            raise HTTPException(422, str(exc) if isinstance(exc, ValueError) else "Unable to read document") from exc
        with store.transaction() as db:
            units = store.units(db)
        # Slow model calls never hold the database write lock.
        try:
            draft = lease_agent(model, segments, units, ruleset)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        lease_id = uuid.uuid4().hex
        suffix = Path(file.filename or "").suffix.lower()
        filename = lease_id + suffix
        (storage / filename).write_bytes(raw)
        lease = {
            **draft,
            "id": lease_id,
            "filename": Path(file.filename or "lease").name,
            "stored_file": filename,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "segments": segments,
            "status": "draft",
            "revision": 1,
            "created_at": now(),
            "provider": model.name,
        }
        with store.transaction() as db:
            store.save(db, "leases", lease)
            store.audit(
                db, lease_id, "lease_proposed", {"provider": model.name, "sha256": lease["sha256"], "ruleset_version": ruleset["version"]}
            )
        return lease

    @api.get("/api/leases/{lease_id}")
    def get_lease(lease_id: str):
        with store.transaction() as db:
            return required(db, "leases", lease_id)

    @api.get("/api/leases/{lease_id}/source")
    def source_document(lease_id: str):
        with store.transaction() as db:
            lease = required(db, "leases", lease_id)
        return FileResponse(storage / lease["stored_file"], filename=lease["filename"])

    @api.post("/api/leases/{lease_id}/fields/{field_name}/review")
    def review_field(lease_id: str, field_name: str, review: Review):
        with store.transaction() as db:
            lease = required(db, "leases", lease_id)
            revision(lease, review.expected_revision)
            if lease["status"] == "active":
                raise HTTPException(409, "Active lease is immutable. Amendments need a new review workflow.")
            if field_name not in lease["fields"]:
                raise HTTPException(404, "Field not found")
            field = lease["fields"][field_name]
            before = dict(field)
            if review.replace_value:
                try:
                    validate_value(field_name, review.value)
                except ValueError as exc:
                    raise HTTPException(422, str(exc)) from exc
                field.update(value=review.value, invalid=False, origin="human")
            elif review.decision == "accepted" and field["invalid"]:
                raise HTTPException(422, "Correct the unverified field before accepting it")
            field.update(decision=review.decision, review_reason=review.reason)
            lease["revision"] += 1
            refresh_lease(lease, store.units(db))
            store.save(db, "leases", lease)
            store.audit(
                db, lease_id, "field_reviewed", {"field": field_name, "before": before, "after": field, "revision": lease["revision"]}
            )
            return lease

    @api.post("/api/leases/{lease_id}/flags/{flag_id}/review")
    def review_flag(lease_id: str, flag_id: str, review: Review):
        with store.transaction() as db:
            lease = required(db, "leases", lease_id)
            revision(lease, review.expected_revision)
            if lease["status"] == "active":
                raise HTTPException(409, "Active lease is immutable")
            flag = next((f for f in lease["flags"] if f["id"] == flag_id), None)
            if flag is None:
                raise HTTPException(404, "Flag not found")
            flag.update(decision=review.decision, review_reason=review.reason)
            lease["revision"] += 1
            store.save(db, "leases", lease)
            store.audit(
                db,
                lease_id,
                "flag_reviewed",
                {"flag_id": flag_id, "decision": review.decision, "reason": review.reason, "revision": lease["revision"]},
            )
            return lease

    @api.post("/api/leases/{lease_id}/activate")
    def activate(lease_id: str, request: Activation):
        with store.transaction() as db:
            lease = required(db, "leases", lease_id)
            if lease["status"] == "active":
                return lease  # Idempotent activation cannot occupy another unit.
            revision(lease, request.expected_revision)
            units = store.units(db)
            refresh_lease(lease, units)
            blocking = [r["id"] for r in lease["rules"] if r["status"] != "PASS"]
            undecided = [k for k, f in lease["fields"].items() if f["decision"] != "accepted" or f["value"] is None or f["invalid"]]
            flags = [f["id"] for f in lease["flags"] if f["decision"] == "pending"]
            if blocking or undecided or flags:
                raise HTTPException(
                    409,
                    {
                        "message": "Review required. All fields must be accepted with values, all rules must pass and all flags must be reviewed.",
                        "rules": blocking,
                        "fields": undecided,
                        "flags": flags,
                    },
                )
            unit = units.get(lease["unit_id"])
            if not unit or unit["status"] != "available":
                raise HTTPException(409, "Unit is no longer available. Occupancy was not changed.")
            unit["status"] = "occupied"
            unit["active_lease_id"] = lease_id
            lease.update(status="active", activated_at=now(), revision=lease["revision"] + 1)
            store.save(db, "units", unit)
            store.save(db, "leases", lease)
            store.audit(
                db,
                lease_id,
                "lease_activated",
                {
                    "unit_id": lease["unit_id"],
                    "prior_unit_status": "available",
                    "new_unit_status": "occupied",
                    "revision": lease["revision"],
                },
            )
            return lease

    @api.post("/api/units/{unit_id}/issues", status_code=201)
    def upload_issue(unit_id: str, photos: list[UploadFile] = File(...), report: str = Form("")):
        with store.transaction() as db:
            required(db, "units", unit_id)
        if len(photos) < 1 or len(photos) > 4 or len(report) > 4000:
            raise HTTPException(422, "Use 1–4 photos and a report under 4,000 characters")
        images = []
        Image.MAX_IMAGE_PIXELS = 16000000
        for photo in photos:
            raw = photo.file.read(MAX_IMAGE_BYTES + 1)
            if not raw or len(raw) > MAX_IMAGE_BYTES:
                raise HTTPException(422, "Each photo must be between 1 byte and 6 MiB")
            try:
                with Image.open(BytesIO(raw)) as img:
                    if img.format not in ("PNG", "JPEG", "WEBP") or img.width * img.height > 16000000:
                        raise ValueError("Use PNG, JPEG or WEBP under 16 megapixels")
                    fmt = img.format
                    img.verify()
                with Image.open(BytesIO(raw)) as decoded:
                    uniform = all(high - low <= 2 for low, high in decoded.convert("RGB").getextrema())
            except (UnidentifiedImageError, ValueError, OSError, Image.DecompressionBombError) as exc:
                raise HTTPException(422, "Invalid or oversized image. Use PNG, JPEG or WEBP under 16 megapixels.") from exc
            image_id = uuid.uuid4().hex
            images.append(
                {
                    "id": image_id,
                    "filename": Path(photo.filename or "image").name,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "bytes": raw,
                    "mime": {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}[fmt],
                    "stored_file": image_id + "." + fmt.lower(),
                    "quality_warnings": ["This image has almost no visual variation. Request a clearer photo or an in-person inspection."]
                    if uniform
                    else [],
                }
            )
        try:
            draft = issue_agent(model, images, report)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        issue_id = uuid.uuid4().hex
        for img in images:
            (storage / img["stored_file"]).write_bytes(img["bytes"])
        issue = {
            **draft,
            "id": issue_id,
            "unit_id": unit_id,
            "report": report,
            "photos": [{k: v for k, v in img.items() if k != "bytes"} for img in images],
            "created_at": now(),
            "revision": 1,
            "provider": model.name,
        }
        with store.transaction() as db:
            store.save(db, "issues", issue)
            store.audit(
                db,
                issue_id,
                "issue_proposed",
                {"unit_id": unit_id, "photos": [p["sha256"] for p in issue["photos"]], "provider": model.name},
            )
        return issue

    @api.get("/api/issues/{issue_id}/photos/{image_id}")
    def get_photo(issue_id: str, image_id: str):
        with store.transaction() as db:
            issue = required(db, "issues", issue_id)
        photo = next((p for p in issue["photos"] if p["id"] == image_id), None)
        if photo is None:
            raise HTTPException(404, "Photo not found")
        return FileResponse(storage / photo["stored_file"], media_type=photo["mime"])

    @api.post("/api/issues/{issue_id}/review")
    def review_work_order(issue_id: str, review: WorkReview):
        with store.transaction() as db:
            issue = required(db, "issues", issue_id)
            revision(issue, review.expected_revision)
            before = dict(issue["work_order"])
            if review.title is not None:
                if not review.title.strip():
                    raise HTTPException(422, "Title cannot be blank")
                issue["work_order"]["title"] = review.title
            if review.description is not None:
                if not review.description.strip():
                    raise HTTPException(422, "Description cannot be blank")
                issue["work_order"]["description"] = review.description
            issue["work_order"].update(decision=review.decision, review_reason=review.reason)
            issue["revision"] += 1
            store.save(db, "issues", issue)
            store.audit(
                db,
                issue_id,
                "work_order_reviewed",
                {"before": before, "after": issue["work_order"], "reason": review.reason, "revision": issue["revision"]},
            )
            return issue

    @api.post("/api/issues/{issue_id}/observations/{index}/review")
    def review_observation(issue_id: str, index: int, review: ObservationReview):
        with store.transaction() as db:
            issue = required(db, "issues", issue_id)
            revision(issue, review.expected_revision)
            if index < 0 or index >= len(issue["observations"]):
                raise HTTPException(404, "Observation not found")
            observation = issue["observations"][index]
            before = dict(observation)
            observation.setdefault("original", {k: v for k, v in observation.items() if k != "original"})
            for name in ("equipment", "condition", "visible_damage"):
                value = getattr(review, name)
                if value is not None:
                    if not value.strip():
                        raise HTTPException(422, "Correction cannot be blank")
                    observation[name] = value
            observation.update(decision=review.decision, origin="human", review_reason=review.reason)
            if any(getattr(review, name) is not None for name in ("equipment", "condition", "visible_damage")):
                observation["explanation"] = "Owner correction: " + review.reason
            # A changed/rejected assessment invalidates earlier work approval.
            if review.decision == "rejected" or any(
                getattr(review, name) is not None for name in ("equipment", "condition", "visible_damage")
            ):
                issue["work_order"]["decision"] = "pending"
                issue["work_order"].pop("review_reason", None)
                current = [item for item in issue["observations"] if item.get("decision") != "rejected"]
                issue["work_order"]["description"] = (
                    "\n".join(f"{item['equipment']} ({item['condition']}): {item['visible_damage']}" for item in current)
                    or "All visual assessments rejected. Inspect in person before specifying repairs."
                )
                if issue["report"]:
                    issue["work_order"]["description"] += "\nReporter states (unverified): " + issue["report"]
                issue["work_order"]["description"] += "\nOwner review: " + review.reason
            issue["revision"] += 1
            store.save(db, "issues", issue)
            store.audit(
                db,
                issue_id,
                "observation_reviewed",
                {"index": index, "before": before, "after": observation, "reason": review.reason, "revision": issue["revision"]},
            )
            return issue

    @api.get("/api/audit/{entity_id}")
    def audit(entity_id: str):
        with store.transaction() as db:
            rows = db.execute("SELECT * FROM events WHERE entity_id=? ORDER BY seq", (entity_id,))
            return [{**dict(row), "data": json.loads(row["data"])} for row in rows]

    @api.get("/api/units/{unit_id}/export")
    def export(unit_id: str):
        return unit_detail(unit_id)

    @api.get("/samples/{name}")
    def sample(name: str):
        live_samples = {
            "prose_lease.txt": "prose_valid.txt",
            "photo_wall_ac.jpg": "wall_ac.jpg",
            "photo_corrosion.jpg": "rusty_ac.jpg",
            "photo_water_heater.jpg": "water_heater.jpg",
            "photo_faucet.jpg": "faucet.jpg",
            "photo_attribution.md": "ATTRIBUTION.md",
        }
        if name in live_samples:
            return FileResponse(ROOT / "samples/live" / live_samples[name], filename=name)
        allowed = {
            "lease_valid.txt",
            "lease_problematic.txt",
            "lease_occupied.txt",
            "lease_missing.txt",
        }
        if name not in allowed:
            raise HTTPException(404, "Sample not found")
        return FileResponse(ROOT / "samples" / name, filename=name)

    api.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

    @api.get("/")
    def index():
        return FileResponse(ROOT / "static/index.html")

    return api


app = create_app()
