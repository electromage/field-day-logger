# Field Day Logger

A browser-based, multi-station logger for **ARRL Field Day** — the same job as
N3FJP's Field Day Contest Log, but served over the network so every operator
logs from their own browser into one shared database. Output is a fully
**Cabrillo 3.0** file accepted by the ARRL log-checking robot.

Built to run off a single laptop in a field with no internet: Python standard
library + Flask + SQLite, nothing else.

## Features

- **Clean, fast entry** — big callsign field, sticky band/mode per position,
  UTC timestamp stamped automatically, log with the Enter key.
- **Live dupe checking** — as you type a callsign, it tells you whether that
  station is already worked on the current band/mode (Field Day dupes are per
  band per mode) and shows where it has been worked before.
- **Exchange prefill** — if a station was already worked, its class/section is
  offered to speed up entry.
- **Multi-operator, live** — every browser sees new QSOs, the running score,
  and dupes update in real time via Server-Sent Events.
- **Scoring** — QSO points (CW/digital = 2, phone = 1) × power multiplier +
  manual bonus points = claimed score.
- **Full log view** — search, edit, and delete contacts.
- **Exports** — one-click **Cabrillo** (`.cbr`) for ARRL submission and
  **ADIF** (`.adi`) for LoTW / other logbooks.
- **Setup page** — station callsign, class, section, categories, club,
  operators, and address that populate the Cabrillo header.

## Requirements

- Python 3.9+
- Flask (`pip install Flask`)

## Running

```bash
# optional but recommended
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

./run.sh            # or:  python3 app.py
```

The server listens on `0.0.0.0:8073`. `run.sh` prints the LAN URL operators
should open (e.g. `http://192.168.1.50:8073/`). Set `PORT` to change the port.

The database lives at `data/fieldday.db` (created on first run). Back it up by
copying that file.

## First-time setup

1. Open **Setup** and enter your station callsign, your **class** (e.g. `3A`)
   and **section** (e.g. `NTX`), power category, and the power multiplier.
2. Go to **Log** and start entering contacts. Each operator can set their own
   operator callsign and station/position label at the bottom of the page;
   those are remembered per browser.

## Exporting for submission

On the **Full Log** page, click **Cabrillo (.cbr)**. The file contains a
Cabrillo 3.0 header (`CONTEST: ARRL-FD`) followed by one `QSO:` line per
contact, with your sent exchange (call / class / section) and each station's
received exchange. Submit it per the current ARRL Field Day instructions.

## Project layout

| File | Purpose |
|------|---------|
| `app.py` | Flask routes, live SSE broadcast, validation |
| `db.py` | SQLite schema and queries |
| `fieldday.py` | Bands, modes, ARRL/RAC sections, classes, scoring |
| `exporter.py` | Cabrillo 3.0 and ADIF generators |
| `templates/` | `index` (logging), `log` (full log), `setup` |
| `static/` | `app.js`, `style.css` |

## Notes & limitations

- Dupe checking is informational — it never blocks logging a contact (work it
  and move on; remove dupes later if needed).
- Bonus points are entered manually on the Setup page; the logger does not try
  to detect which bonuses you qualify for.
- There is no authentication. Run it on a trusted local network, as you would
  at a Field Day site.
