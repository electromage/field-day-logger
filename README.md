# Field Day Logger

A simple, browser-based, multi-station logger for **ARRL Field Day**. Run it on
one computer and every operator logs from their own browser into a single shared
database. Output is a fully **Cabrillo 3.0** file accepted by the ARRL
log-checking robot.

The goal is something deliberately small and unfussy that runs **anywhere** —
Linux, macOS, Windows, or a Raspberry Pi — with no operating system lock-in and
nothing to buy. If a device has a web browser, it can log; the server is just
Python standard library + Flask + SQLite, so it happily runs off a single
laptop in a field with no internet and nothing else to install or configure.

---

## Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Running the server](#running-the-server)
- [Connecting operator stations](#connecting-operator-stations)
- [Quick start](#quick-start)
- [Using the logger](#using-the-logger)
  - [Setup page](#1-setup-page-do-this-first)
  - [Logging contacts](#2-logging-contacts)
  - [Dupe checking](#3-dupe-checking)
  - [Per-operator identity](#4-per-operator-identity)
  - [Full Log: search, edit, delete](#5-full-log-search-edit-delete)
  - [Scoring](#6-scoring)
  - [Exporting for submission](#7-exporting-for-submission)
- [The exchange explained](#the-exchange-explained)
- [Backing up the log](#backing-up-the-log)
- [Configuration reference](#configuration-reference)
- [Project layout](#project-layout)
- [Troubleshooting](#troubleshooting)
- [Notes & limitations](#notes--limitations)
- [License](#license)

---

## Features

- **Clean, fast entry** — big callsign field, sticky band/mode per position,
  UTC timestamp stamped automatically, log with the Enter key.
- **Live dupe checking** — as you type a callsign it tells you whether that
  station is already worked on the current band/mode (Field Day dupes are per
  band per mode) and shows where else it has been worked.
- **Exchange prefill** — if a station was already worked, its class/section is
  offered to speed up entry.
- **Multi-operator, live** — every browser sees new QSOs, the running score,
  and dupes update in real time via Server-Sent Events.
- **Field Day scoring** — QSO points (CW/digital = 2, phone = 1) × power
  multiplier + manual bonus points = claimed score, updated live.
- **Full log view** — search, edit, and delete contacts.
- **One-click exports** — **Cabrillo** (`.cbr`) for ARRL submission and
  **ADIF** (`.adi`) for LoTW / other logbooks.
- **Section & class validation** — all 84 ARRL/RAC sections plus DX; classes
  validated as number + category letter (e.g. `3A`).
- **No internet required** — pure Python + Flask + SQLite, runs on one laptop.

---

## Requirements

- **Python 3.9 or newer** (developed on 3.14)
- **Flask 3.x** (the only third-party dependency)

Everything else — the web server, database, and UI — uses the Python standard
library and a few static files. No Node, no build step, no external services.

---

## Installation

Clone the repository:

```bash
git clone git@github.com:electromage/field-day-logger.git
cd field-day-logger
```

Install Flask. A virtual environment is recommended but optional:

```bash
# recommended: isolated environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

Or install Flask system-wide / for your user:

```bash
pip install --user Flask
```

That's the whole install. The SQLite database is created automatically the
first time the server starts.

---

## Running the server

```bash
./run.sh
```

`run.sh` starts the server and prints the addresses operators should open, e.g.:

```
============================================================
  Field Day Logger starting on port 8073
  Operators connect to:  http://192.168.1.50:8073/
  This machine:          http://localhost:8073/
============================================================
```

You can also run it directly:

```bash
python3 app.py
```

The server listens on `0.0.0.0:8073` (all network interfaces). To use a
different port:

```bash
PORT=8080 ./run.sh
```

Leave this process running for the duration of Field Day. Stop it with
`Ctrl-C`.

---

## Connecting operator stations

The logger is meant to be run on **one "server" laptop** that every operating
position connects to over the local network (Wi-Fi or Ethernet).

1. Put all the logging devices on the **same network** as the server laptop —
   a cheap travel router or a phone hotspot is plenty; no internet needed.
2. Find the server laptop's LAN IP (printed by `run.sh`, or run
   `hostname -I` on Linux / `ipconfig` on Windows).
3. On each operator's laptop, tablet, or phone, open a browser to
   **`http://<server-ip>:8073/`**.

That's it — every browser is now logging into the same shared database and
sees the same live log and score.

> **Firewall:** if other devices can't reach the server, allow inbound TCP on
> port `8073`. On Linux with ufw: `sudo ufw allow 8073/tcp`. On Windows, allow
> Python through the firewall on Private networks when prompted.

---

## Quick start

1. `./run.sh` on the server laptop.
2. Open `http://<server-ip>:8073/` and click **Setup**. Enter your station
   callsign, class (e.g. `3A`), section (e.g. `NTX`), and power category. Save.
3. Click **Log**. Type a callsign, set band/mode, enter the other station's
   class and section, press **Enter**. Repeat.
4. When the event ends, go to **Full Log → Cabrillo (.cbr)** and submit the
   downloaded file to the ARRL.

---

## Using the logger

The app has three pages, linked in the top bar: **Log**, **Full Log**, and
**Setup**.

### 1. Setup page (do this first)

Enter the information that identifies your station and fills the Cabrillo
header you'll submit to the ARRL:

- **Station callsign** — the call your group operates under.
- **Your class** — your sent exchange, e.g. `3A` (number of transmitters +
  category letter). See the [exchange section](#the-exchange-explained).
- **Your ARRL/RAC section** — e.g. `NTX`.
- **Power multiplier** — `1×` (>150 W), `2×` (≤150 W), or `5×` (≤5 W QRP on
  non-commercial power). This multiplies your QSO points.
- **Categories** (power / operator / station / transmitters), **club name**,
  **operators**, **bonus points**, and contact **address/email**.

Click **Save setup**. Settings are stored in the database and shared by all
stations. A class-letter reference table is shown at the bottom of the page.

### 2. Logging contacts

On the **Log** page:

1. Type the **callsign**. As you type, the dupe checker runs (see below).
2. Pick **band** and **mode** — these "stick" for your browser, so you only
   change them when you change bands.
3. Enter the other station's **class** (e.g. `2A`) and **section** (e.g. `IL`).
   The section field autocompletes from the list of valid sections.
4. Press **Enter** (or click **Log Contact**).

The **UTC date and time are stamped automatically** at the moment you log, so
you never type a timestamp. The callsign field clears and refocuses for the
next QSO; band, mode, and your operator info stay put. Optional RST, frequency,
and notes fields are tucked under "More fields…".

The contact appears instantly in the **Live log** on the right — and on every
other operator's screen.

### 3. Dupe checking

Field Day allows working each station **once per band per mode**, so the same
call on a different band or mode is *not* a dupe. As you type a callsign:

- **Green "new"** — not worked on the current band/mode. If you've worked them
  on *other* band/mode combos, those are listed as chips, and their previously
  logged class/section is prefilled to save typing.
- **Red "DUPE"** — already in the log on this band *and* mode.

Dupe checking is **informational only** — it never blocks you. If you're not
sure, just log it; you can remove dupes later from the Full Log.

### 4. Per-operator identity

At the bottom of the Log page, each operator can set:

- **Operator call** — the individual operator logging at this position.
- **Station / position label** — e.g. `CW-1`, `GOTA`.

These are remembered in that browser and attached to each contact that
position logs, so multi-op stations can track who worked what.

### 5. Full Log: search, edit, delete

The **Full Log** page lists every contact with date, time, exchange, operator,
and station. You can:

- **Filter** by callsign with the search box.
- **Edit** any contact (fix a busted call, correct an exchange, adjust the
  time) — click **edit**, change fields, **Save**.
- **Delete** a contact (e.g. an accidental dupe) — click **✕**.

Edits and deletes broadcast live to all stations and update the score.

### 6. Scoring

Field Day QSO points:

| Mode | Points per QSO |
|------|----------------|
| Phone (PH) | 1 |
| CW | 2 |
| Digital (DG) | 2 |

The score strip across the top shows live counts (total, CW, phone, digital,
sections worked), total **QSO points**, and the **claimed score**:

```
claimed score = QSO points × power multiplier + bonus points
```

Set the power multiplier and bonus points on the **Setup** page. Bonus points
(emergency power, public location, alternate power, etc.) are entered manually
— the logger doesn't try to guess which bonuses you qualify for.

### 7. Exporting for submission

On the **Full Log** page:

- **Cabrillo (.cbr)** — a Cabrillo 3.0 file with a `CONTEST: ARRL-FD` header
  (built from your Setup values) followed by one `QSO:` line per contact, each
  carrying your sent exchange (call / class / section) and the received
  exchange. This is the file you submit to the ARRL.
- **ADIF (.adi)** — a standard ADIF log for importing into LoTW, eQSL, or
  another logbook program.

Example Cabrillo output:

```
START-OF-LOG: 3.0
CONTEST: ARRL-FD
CALLSIGN: K1ABC
LOCATION: WCF
CATEGORY-OPERATOR: MULTI-OP
CATEGORY-STATION: FIELD
CATEGORY-POWER: LOW
CLAIMED-SCORE: 110
CLUB: Example Amateur Radio Club
QSO:  14000 PH 2026-06-27 1801 K1ABC       3A WCF   W9XYZ       2A IL
QSO:   7000 CW 2026-06-27 1815 K1ABC       3A WCF   N0CALL      1D CO
END-OF-LOG:
```

Submit the file per the current
[ARRL Field Day](https://www.arrl.org/field-day) instructions.

---

## The exchange explained

The Field Day exchange is your **class** and **ARRL/RAC section**.

**Class** = number of transmitters + a category letter:

| Letter | Meaning |
|--------|---------|
| A | Club / non-club portable group (3+ persons) |
| B | 1 or 2 person portable |
| C | Mobile |
| D | Home station (commercial power) |
| E | Home station (emergency power) |
| F | Emergency Operations Center (EOC) |

So `3A` means "three transmitters, club/group portable." `1D` means "one
transmitter, home station on commercial power."

**Section** is your ARRL or RAC section abbreviation (e.g. `NTX`, `WCF`, `ONS`),
or `DX` for stations outside the US and Canada. All 84 sections are validated
and autocompleted.

---

## Backing up the log

The entire log and configuration live in a single SQLite file:

```
data/fieldday.db
```

To back it up mid-event, just copy that file (the `.db-wal` and `.db-shm`
companions can be copied too, or copied after stopping the server for a clean
snapshot):

```bash
cp data/fieldday.db ~/fieldday-backup-$(date +%H%M).db
```

The `data/` database files are gitignored and never committed.

---

## Configuration reference

All settings are editable on the **Setup** page and stored in the database.
Defaults are defined in `db.py` (`DEFAULT_CONFIG`).

| Setting | Cabrillo field | Notes |
|---------|----------------|-------|
| Station callsign | `CALLSIGN` | Your group's call |
| Class | (per-QSO sent exchange) | e.g. `3A` |
| Section | `LOCATION` | e.g. `NTX` |
| Power multiplier | — | 1 / 2 / 5, used for scoring |
| Bonus points | — | Manual, added to claimed score |
| Category — power | `CATEGORY-POWER` | QRP / LOW / HIGH |
| Category — operator | `CATEGORY-OPERATOR` | SINGLE-OP / MULTI-OP / CHECKLOG |
| Category — station | `CATEGORY-STATION` | FIXED / FIELD / MOBILE / PORTABLE |
| Transmitters | `CATEGORY-TRANSMITTER` | |
| Club name | `CLUB` | |
| Operators | `OPERATORS` | Space/comma list of calls |
| Contact name | `NAME` | |
| Address / city | `ADDRESS` / `ADDRESS-CITY` | |
| Email | `EMAIL` | |
| Soapbox | `SOAPBOX` | One line per comment |

Environment variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `PORT` | `8073` | TCP port the server listens on |

---

## Project layout

| Path | Purpose |
|------|---------|
| `app.py` | Flask routes, live SSE broadcast, request validation |
| `db.py` | SQLite schema, queries, and default config |
| `fieldday.py` | Bands, modes, ARRL/RAC sections, classes, scoring rules |
| `exporter.py` | Cabrillo 3.0 and ADIF generators |
| `templates/` | `index.html` (logging), `log.html` (full log), `setup.html`, `base.html` |
| `static/` | `app.js` (front-end logic), `style.css` |
| `data/` | SQLite database (created at runtime, gitignored) |
| `run.sh` | Convenience launcher that prints the LAN URL |

---

## Troubleshooting

**Other devices can't connect.** Confirm they're on the same network and that
the server laptop's firewall allows inbound TCP `8073`. Test from the server
itself first at `http://localhost:8073/`.

**`flask` not found / `ModuleNotFoundError: No module named 'flask'`.** Activate
your virtual environment, or `pip install -r requirements.txt`.

**Port already in use.** Start with a different port: `PORT=8080 ./run.sh`.

**The live log/score isn't updating on a station.** That browser's Server-Sent
Events connection dropped; the indicator in the top bar shows `reconnecting…`.
It reconnects automatically — or just reload the page.

**A contact has the wrong time or call.** Edit it on the **Full Log** page; the
correction propagates to all stations and the score.

---

## Notes & limitations

- Dupe checking is informational — it never blocks logging a contact.
- Bonus points are entered manually on the Setup page; the logger does not
  detect which bonuses you qualify for.
- There is **no authentication**. Run it on a trusted local network, as you
  would at a Field Day site — not on the public internet.
- The built-in Flask server is fine for a Field Day's worth of stations. It is
  not hardened for public deployment.

---

## License

Dedicated to the public domain under [CC0 1.0 Universal](LICENSE).

To the extent possible under law, Matt Blank (KE7NOR) has waived all copyright
and related or neighboring rights to Field Day Logger. You can copy, modify,
distribute, and use the software, including for commercial purposes, all
without asking permission or providing attribution.
