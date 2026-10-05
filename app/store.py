"""SQLite transactions keep review revisions, occupancy and audit events together."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: Path, units_file: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as db:
            db.executescript("""
              CREATE TABLE IF NOT EXISTS units (id TEXT PRIMARY KEY, data TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS leases (id TEXT PRIMARY KEY, unit_id TEXT, status TEXT NOT NULL, data TEXT NOT NULL);
              CREATE UNIQUE INDEX IF NOT EXISTS one_active_lease ON leases(unit_id) WHERE status='active';
              CREATE INDEX IF NOT EXISTS leases_by_unit ON leases(unit_id);
              CREATE TABLE IF NOT EXISTS issues (id TEXT PRIMARY KEY, unit_id TEXT NOT NULL REFERENCES units(id), data TEXT NOT NULL);
              CREATE INDEX IF NOT EXISTS issues_by_unit ON issues(unit_id);
              CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, entity_id TEXT NOT NULL, at TEXT NOT NULL, action TEXT NOT NULL, data TEXT NOT NULL);
              CREATE INDEX IF NOT EXISTS events_by_entity ON events(entity_id);
            """)
            supplied = json.loads(units_file.read_text())
            for prop in supplied["properties"]:
                for building in prop["buildings"]:
                    for unit in building["units"]:
                        item = {
                            **unit,
                            "property_id": prop["property_id"],
                            "property": prop["name"],
                            "building": building["name"],
                            "building_id": building["building_id"],
                            "location": prop["location"],
                        }
                        db.execute("INSERT OR IGNORE INTO units VALUES (?, ?)", (unit["unit_id"], json.dumps(item)))

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("BEGIN IMMEDIATE")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def get(db, table, entity_id):
        if table not in ("units", "leases", "issues"):
            raise ValueError("Invalid table")
        row = db.execute(f"SELECT data FROM {table} WHERE id=?", (entity_id,)).fetchone()
        return json.loads(row["data"]) if row else None

    @staticmethod
    def units(db):
        return {row["id"]: json.loads(row["data"]) for row in db.execute("SELECT * FROM units ORDER BY id")}

    @staticmethod
    def save(db, table, entity):
        if table == "leases":
            db.execute(
                "INSERT INTO leases VALUES (?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET unit_id=excluded.unit_id,status=excluded.status,data=excluded.data",
                (entity["id"], entity.get("unit_id"), entity["status"], json.dumps(entity)),
            )
        elif table == "issues":
            db.execute(
                "INSERT INTO issues VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                (entity["id"], entity["unit_id"], json.dumps(entity)),
            )
        elif table == "units":
            db.execute("UPDATE units SET data=? WHERE id=?", (json.dumps(entity), entity["unit_id"]))
        else:
            raise ValueError("Invalid table")

    @staticmethod
    def audit(db, entity_id, action, data):
        db.execute("INSERT INTO events(entity_id,at,action,data) VALUES (?, ?, ?, ?)", (entity_id, now(), action, json.dumps(data)))
