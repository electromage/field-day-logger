"""
Field Day domain knowledge: bands, modes, ARRL/RAC sections, classes, scoring.

This module is the single source of truth for the contest rules used by the
logger and the Cabrillo exporter.  ARRL Field Day rules:
  https://www.arrl.org/field-day
"""

# --------------------------------------------------------------------------
# Bands
# --------------------------------------------------------------------------
# Each band maps to the canonical frequency string Cabrillo expects in the
# QSO freq column.  HF bands are expressed in kHz; VHF/UHF bands use the
# special band designators (50, 144, 222, 432, ...) defined by the Cabrillo
# specification.
BANDS = [
    ("160m", "1800"),
    ("80m", "3500"),
    ("40m", "7000"),
    ("20m", "14000"),
    ("15m", "21000"),
    ("10m", "28000"),
    ("6m", "50"),
    ("2m", "144"),
    ("1.25m", "222"),
    ("70cm", "432"),
    ("33cm", "902"),
    ("23cm", "1.2G"),
]
BAND_NAMES = [b[0] for b in BANDS]
BAND_TO_FREQ = dict(BANDS)


# --------------------------------------------------------------------------
# Modes
# --------------------------------------------------------------------------
# Cabrillo mode codes.  Field Day scores CW and digital at 2 points and
# phone at 1 point.  We keep RY/FM as selectable but score them with their
# parent category.
MODES = [
    ("CW", "CW"),
    ("PH", "Phone"),
    ("DG", "Digital"),
]
MODE_NAMES = [m[0] for m in MODES]
MODE_LABELS = dict(MODES)

# Points per QSO by mode (ARRL Field Day rule 7.2).
MODE_POINTS = {
    "CW": 2,
    "DG": 2,
    "PH": 1,
}


# --------------------------------------------------------------------------
# Operating classes (the letter portion of the exchange)
# --------------------------------------------------------------------------
CLASS_LETTERS = {
    "A": "Club / non-club portable group (3+ persons)",
    "B": "1 or 2 person portable",
    "C": "Mobile",
    "D": "Home station (commercial power)",
    "E": "Home station (emergency power)",
    "F": "Emergency Operations Center (EOC)",
}


# --------------------------------------------------------------------------
# ARRL / RAC Sections (the multiplier portion of the exchange)
# --------------------------------------------------------------------------
# Full list of valid section abbreviations accepted in the Field Day
# exchange, plus DX for stations outside the US/Canada.
SECTIONS = [
    # New England
    "CT", "EMA", "ME", "NH", "RI", "VT", "WMA",
    # Hudson / NY
    "ENY", "NLI", "NNY", "WNY",
    # New Jersey
    "NNJ", "SNJ",
    # Atlantic
    "DE", "EPA", "MDC", "WPA",
    # Southeastern
    "AL", "GA", "KY", "NC", "NFL", "SC", "SFL", "TN", "VA", "VI", "WCF", "PR",
    # Delta
    "AR", "LA", "MS", "TN",
    # West Gulf
    "NM", "NTX", "OK", "STX", "WTX",
    # Pacific
    "EB", "PAC", "SCV", "SF", "SJV", "SV",
    # Southwestern
    "LAX", "ORG", "SB", "SDG", "AZ",
    # Northwestern
    "EWA", "ID", "MT", "OR", "UT", "WWA", "WY", "NV",
    # Great Lakes
    "MI", "OH", "WV",
    # Central
    "IL", "IN", "WI",
    # Dakota
    "MN", "ND", "SD",
    # Midwest
    "IA", "KS", "MO", "NE",
    "CO",
    # Alaska
    "AK",
    # RAC (Canada)
    "MAR", "NL", "QC", "ONE", "ONN", "ONS", "GTA", "MB", "SK", "AB", "BC", "TER",
    # Outside US/Canada
    "DX",
]
# De-duplicate while preserving order (TN/some appear under two divisions).
_seen = set()
SECTIONS = [s for s in SECTIONS if not (s in _seen or _seen.add(s))]
SECTION_SET = set(SECTIONS)


# --------------------------------------------------------------------------
# Validation helpers
# --------------------------------------------------------------------------
import re

_CLASS_RE = re.compile(r"^(\d{1,3})([A-F])$", re.IGNORECASE)
_CALL_RE = re.compile(r"^[A-Z0-9]{1,3}[0-9][A-Z0-9]*[A-Z](/[A-Z0-9]+)?$", re.IGNORECASE)


def normalize_class(value):
    """Return canonical class like '3A' or None if invalid."""
    if not value:
        return None
    m = _CLASS_RE.match(value.strip())
    if not m:
        return None
    return f"{int(m.group(1))}{m.group(2).upper()}"


def normalize_section(value):
    """Return canonical section abbreviation or None if not a known section."""
    if not value:
        return None
    v = value.strip().upper()
    return v if v in SECTION_SET else None


def normalize_call(value):
    """Upper-case and strip a callsign.  Returns '' for empty input."""
    return (value or "").strip().upper()


def looks_like_call(value):
    """Loose sanity check for a callsign (does not enforce ITU rules)."""
    return bool(_CALL_RE.match(value or ""))


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------
def qso_points(rows):
    """Sum Field Day QSO points for an iterable of contact rows/dicts."""
    total = 0
    for r in rows:
        mode = r["mode"] if isinstance(r, dict) else r["mode"]
        total += MODE_POINTS.get(mode, 1)
    return total


# Power multiplier options (ARRL Field Day rule 7.3).
POWER_MULTIPLIERS = {
    "1": "1x  - more than 150 W",
    "2": "2x  - 150 W or less",
    "5": "5x  - 5 W or less, non-commercial power (QRP)",
}
