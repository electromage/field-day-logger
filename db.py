"""SQLite persistence for the Field Day logger.

A single SQLite database holds all station configuration and every logged
contact.  SQLite serializes writers, which is plenty for the handful of
concurrent operators at a typical Field Day site.
"""
import os
import sqlite3
import threading

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "fieldday.db")

# One lock to serialize writes from multiple request threads.  Reads are fine
# concurrently; this just keeps write transactions from interleaving badly.
_write_lock = threading.Lock()

DEFAULT_CONFIG = {
    "my_call": "",
    "my_class": "",
    "my_section": "",
    "club_name": "",
    "operators": "",
    "category_operator": "MULTI-OP",
    "category_station": "FIELD",
    "category_transmitter": "",
    "category_power": "LOW",
    "category_assisted": "NON-ASSISTED",
    "power_multiplier": "2",
    "bonus_points": "0",
    "contact_name": "",
    "address": "",
    "address_city": "",
    "email": "",
    "soapbox": "",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contacts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    call          TEXT NOT NULL,
    band          TEXT NOT NULL,
    mode          TEXT NOT NULL,
    qso_date      TEXT NOT NULL,   -- UTC YYYY-MM-DD
    qso_time      TEXT NOT NULL,   -- UTC HHMM
    their_class   TEXT NOT NULL,
    their_section TEXT NOT NULL,
    rst_sent      TEXT DEFAULT '',
    rst_rcvd      TEXT DEFAULT '',
    freq          TEXT DEFAULT '',
    operator      TEXT DEFAULT '',
    station       TEXT DEFAULT '',
    notes         TEXT DEFAULT '',
    created_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_contacts_dupe ON contacts(call, band, mode);
CREATE INDEX IF NOT EXISTS idx_contacts_time ON contacts(qso_date, qso_time);
"""


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)
        # Seed any missing default config keys.
        existing = {r["key"] for r in conn.execute("SELECT key FROM config")}
        for k, v in DEFAULT_CONFIG.items():
            if k not in existing:
                conn.execute("INSERT INTO config(key, value) VALUES(?, ?)", (k, v))
        conn.commit()


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
def get_config():
    with connect() as conn:
        rows = conn.execute("SELECT key, value FROM config").fetchall()
    cfg = dict(DEFAULT_CONFIG)
    cfg.update({r["key"]: r["value"] for r in rows})
    return cfg


def update_config(values):
    with _write_lock, connect() as conn:
        for k, v in values.items():
            conn.execute(
                "INSERT INTO config(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (k, "" if v is None else str(v)),
            )
        conn.commit()


# --------------------------------------------------------------------------
# Contacts
# --------------------------------------------------------------------------
def add_contact(c):
    with _write_lock, connect() as conn:
        cur = conn.execute(
            """INSERT INTO contacts
               (call, band, mode, qso_date, qso_time, their_class, their_section,
                rst_sent, rst_rcvd, freq, operator, station, notes, created_at)
               VALUES (:call, :band, :mode, :qso_date, :qso_time, :their_class,
                       :their_section, :rst_sent, :rst_rcvd, :freq, :operator,
                       :station, :notes, :created_at)""",
            c,
        )
        conn.commit()
        new_id = cur.lastrowid
    return get_contact(new_id)


def update_contact(contact_id, c):
    with _write_lock, connect() as conn:
        conn.execute(
            """UPDATE contacts SET
                 call=:call, band=:band, mode=:mode, qso_date=:qso_date,
                 qso_time=:qso_time, their_class=:their_class,
                 their_section=:their_section, rst_sent=:rst_sent,
                 rst_rcvd=:rst_rcvd, freq=:freq, operator=:operator,
                 station=:station, notes=:notes
               WHERE id=:id""",
            {**c, "id": contact_id},
        )
        conn.commit()
    return get_contact(contact_id)


def delete_contact(contact_id):
    with _write_lock, connect() as conn:
        conn.execute("DELETE FROM contacts WHERE id=?", (contact_id,))
        conn.commit()


def get_contact(contact_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM contacts WHERE id=?", (contact_id,)).fetchone()
    return dict(row) if row else None


def list_contacts(limit=None, search=None):
    q = "SELECT * FROM contacts"
    params = []
    if search:
        q += " WHERE call LIKE ?"
        params.append(f"%{search.upper()}%")
    q += " ORDER BY qso_date DESC, qso_time DESC, id DESC"
    if limit:
        q += " LIMIT ?"
        params.append(limit)
    with connect() as conn:
        rows = conn.execute(q, params).fetchall()
    return [dict(r) for r in rows]


def find_dupes(call, band, mode):
    """Return prior contacts with the same call on the same band+mode.

    Field Day dupes are counted per band per mode, so the same station may be
    worked once on each band/mode combination.
    """
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM contacts WHERE call=? AND band=? AND mode=? "
            "ORDER BY qso_date, qso_time",
            (call.upper(), band, mode),
        ).fetchall()
    return [dict(r) for r in rows]


def worked_bands_modes(call):
    """All band/mode pairs a call has already been worked on (any time)."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT band, mode FROM contacts WHERE call=?",
            (call.upper(),),
        ).fetchall()
    return [(r["band"], r["mode"]) for r in rows]


def stats():
    with connect() as conn:
        rows = conn.execute("SELECT mode, COUNT(*) n FROM contacts GROUP BY mode").fetchall()
        by_band = conn.execute(
            "SELECT band, COUNT(*) n FROM contacts GROUP BY band"
        ).fetchall()
        sections = conn.execute(
            "SELECT COUNT(DISTINCT their_section) n FROM contacts"
        ).fetchone()
    by_mode = {r["mode"]: r["n"] for r in rows}
    return {
        "by_mode": by_mode,
        "by_band": {r["band"]: r["n"] for r in by_band},
        "total": sum(by_mode.values()),
        "sections": sections["n"] if sections else 0,
    }
