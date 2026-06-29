"""Field Day Logger — a browser-based, multi-station contest logger.

Run with:  python3 app.py  (then open http://<host>:8073 from any station)

Design goals:
  * Zero external services — just Python stdlib + Flask + SQLite.
  * Multiple operators log into the same server from their own browsers and
    write to one shared database.
  * Live dupe checking and a live shared log via Server-Sent Events, so every
    operator sees new QSOs as they happen.
  * One-click export to a Cabrillo file that the ARRL robot will accept.
"""
import json
import queue
import datetime
from flask import (
    Flask,
    Response,
    request,
    jsonify,
    render_template,
    stream_with_context,
)

import db
import fieldday
import exporter

app = Flask(__name__)
db.init()

# --------------------------------------------------------------------------
# Live updates (Server-Sent Events)
# --------------------------------------------------------------------------
# Each connected browser gets a Queue; events are fanned out to all of them.
_subscribers = []
_subscribers_lock = __import__("threading").Lock()


def broadcast(event, payload):
    data = json.dumps({"event": event, "data": payload})
    with _subscribers_lock:
        dead = []
        for q in _subscribers:
            try:
                q.put_nowait(data)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _subscribers.remove(q)


@app.route("/stream")
def stream():
    def gen():
        q = queue.Queue(maxsize=100)
        with _subscribers_lock:
            _subscribers.append(q)
        try:
            yield ": connected\n\n"
            while True:
                try:
                    data = q.get(timeout=20)
                    yield f"data: {data}\n\n"
                except queue.Empty:
                    yield ": keep-alive\n\n"  # comment frame keeps proxies happy
        finally:
            with _subscribers_lock:
                if q in _subscribers:
                    _subscribers.remove(q)

    return Response(
        stream_with_context(gen()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html", config=db.get_config())


@app.route("/setup")
def setup_page():
    return render_template(
        "setup.html",
        config=db.get_config(),
        sections=fieldday.SECTIONS,
        power_multipliers=fieldday.POWER_MULTIPLIERS,
        class_letters=fieldday.CLASS_LETTERS,
    )


@app.route("/log")
def log_page():
    return render_template("log.html", config=db.get_config())


# --------------------------------------------------------------------------
# Reference data for the front-end
# --------------------------------------------------------------------------
@app.route("/api/meta")
def api_meta():
    return jsonify(
        {
            "bands": fieldday.BAND_NAMES,
            "modes": [{"code": c, "label": l} for c, l in fieldday.MODES],
            "sections": fieldday.SECTIONS,
            "class_letters": fieldday.CLASS_LETTERS,
            "config": db.get_config(),
        }
    )


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "POST":
        data = request.get_json(force=True)
        allowed = set(db.DEFAULT_CONFIG.keys())
        db.update_config({k: v for k, v in data.items() if k in allowed})
        broadcast("config", db.get_config())
    return jsonify(db.get_config())


# --------------------------------------------------------------------------
# Dupe check (called as the operator types a callsign)
# --------------------------------------------------------------------------
@app.route("/api/check")
def api_check():
    call = fieldday.normalize_call(request.args.get("call", ""))
    band = request.args.get("band", "")
    mode = request.args.get("mode", "")
    if not call:
        return jsonify({"call": "", "dupe": False, "worked": []})
    dupes = db.find_dupes(call, band, mode) if band and mode else []
    worked = db.worked_bands_modes(call)
    # If we've worked this call before, surface its last-known exchange so the
    # operator can confirm/prefill class + section.
    last = None
    history = db.list_contacts(search=call)
    for h in history:
        if h["call"] == call:
            last = {"class": h["their_class"], "section": h["their_section"]}
            break
    return jsonify(
        {
            "call": call,
            "dupe": len(dupes) > 0,
            "dupe_count": len(dupes),
            "worked": [{"band": b, "mode": m} for b, m in worked],
            "last_exchange": last,
        }
    )


# --------------------------------------------------------------------------
# Contacts
# --------------------------------------------------------------------------
def _utc_now():
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%Y-%m-%d"), now.strftime("%H%M")


def _validate_and_build(data, require_time=True):
    """Validate inbound contact JSON; return (contact_dict, error_string)."""
    call = fieldday.normalize_call(data.get("call", ""))
    if not call:
        return None, "Callsign is required."

    band = data.get("band", "")
    if band not in fieldday.BAND_NAMES:
        return None, f"Unknown band: {band!r}"

    mode = data.get("mode", "")
    if mode not in fieldday.MODE_NAMES:
        return None, f"Unknown mode: {mode!r}"

    their_class = fieldday.normalize_class(data.get("their_class", ""))
    if not their_class:
        return None, "Class must look like '3A' (number 1-99 + letter A-F)."

    their_section = fieldday.normalize_section(data.get("their_section", ""))
    if not their_section:
        return None, f"Unknown ARRL/RAC section: {data.get('their_section', '')!r}"

    # Date/time: use provided UTC values if present, else stamp now.
    qso_date = data.get("qso_date", "").strip()
    qso_time = data.get("qso_time", "").strip().replace(":", "")
    if not qso_date or not qso_time:
        qso_date, qso_time = _utc_now()

    contact = {
        "call": call,
        "band": band,
        "mode": mode,
        "qso_date": qso_date,
        "qso_time": qso_time,
        "their_class": their_class,
        "their_section": their_section,
        "rst_sent": (data.get("rst_sent") or "").strip(),
        "rst_rcvd": (data.get("rst_rcvd") or "").strip(),
        "freq": (data.get("freq") or "").strip(),
        "operator": fieldday.normalize_call(data.get("operator", "")),
        "station": (data.get("station") or "").strip(),
        "notes": (data.get("notes") or "").strip(),
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    return contact, None


@app.route("/api/contacts", methods=["GET", "POST"])
def api_contacts():
    if request.method == "POST":
        data = request.get_json(force=True)
        contact, err = _validate_and_build(data)
        if err:
            return jsonify({"error": err}), 400
        dupes = db.find_dupes(contact["call"], contact["band"], contact["mode"])
        saved = db.add_contact(contact)
        saved["is_dupe"] = len(dupes) > 0
        broadcast("contact", saved)
        broadcast("stats", _score_payload())
        return jsonify(saved), 201

    limit = request.args.get("limit", type=int)
    search = request.args.get("search")
    return jsonify(db.list_contacts(limit=limit, search=search))


@app.route("/api/contacts/<int:contact_id>", methods=["PUT", "DELETE"])
def api_contact(contact_id):
    if request.method == "DELETE":
        db.delete_contact(contact_id)
        broadcast("delete", {"id": contact_id})
        broadcast("stats", _score_payload())
        return jsonify({"ok": True})

    data = request.get_json(force=True)
    contact, err = _validate_and_build(data)
    if err:
        return jsonify({"error": err}), 400
    saved = db.update_contact(contact_id, contact)
    broadcast("update", saved)
    broadcast("stats", _score_payload())
    return jsonify(saved)


# --------------------------------------------------------------------------
# Score / stats
# --------------------------------------------------------------------------
def _score_payload():
    cfg = db.get_config()
    contacts = db.list_contacts()
    s = db.stats()
    pts = fieldday.qso_points(contacts)
    try:
        mult = int(cfg.get("power_multiplier") or "1")
    except ValueError:
        mult = 1
    try:
        bonus = int(cfg.get("bonus_points") or "0")
    except ValueError:
        bonus = 0
    return {
        "total": s["total"],
        "by_mode": s["by_mode"],
        "by_band": s["by_band"],
        "sections": s["sections"],
        "qso_points": pts,
        "power_multiplier": mult,
        "bonus_points": bonus,
        "claimed_score": pts * mult + bonus,
    }


@app.route("/api/score")
def api_score():
    return jsonify(_score_payload())


# --------------------------------------------------------------------------
# Exports
# --------------------------------------------------------------------------
def _chronological():
    contacts = db.list_contacts()
    contacts.sort(key=lambda c: (c["qso_date"], c["qso_time"], c["id"]))
    return contacts


@app.route("/export/cabrillo")
def export_cabrillo():
    cfg = db.get_config()
    text = exporter.to_cabrillo(cfg, _chronological())
    call = (cfg.get("my_call") or "log").upper().replace("/", "_")
    return Response(
        text,
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment; filename={call}_FD.cbr"},
    )


@app.route("/export/adif")
def export_adif():
    cfg = db.get_config()
    text = exporter.to_adif(cfg, _chronological())
    call = (cfg.get("my_call") or "log").upper().replace("/", "_")
    return Response(
        text,
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment; filename={call}_FD.adi"},
    )


if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", "8073"))
    print(f"\n  Field Day Logger running.  Open http://<this-machine-ip>:{port}/\n")
    app.run(host="0.0.0.0", port=port, threaded=True)
