"""Cabrillo 3.0 and ADIF exporters for ARRL Field Day.

The Cabrillo output conforms to the Cabrillo specification used by the ARRL
log-checking robot for the ARRL-FD contest.  Field exchange is the station
class and ARRL/RAC section.
"""
import fieldday


def _qso_line(c, my_call, my_class, my_section):
    """Format one Cabrillo QSO line.

    Layout:  QSO: freq mo date time mycall mycls mysec call cls sec
             sent exchange (mine) ----^         received exchange ^
    """
    freq = c.get("freq") or fieldday.BAND_TO_FREQ.get(c["band"], "")
    return (
        "QSO: "
        f"{freq:>6} "
        f"{c['mode']:>2} "
        f"{c['qso_date']} "
        f"{c['qso_time']:>4} "
        f"{my_call:<10} "
        f"{my_class:>3} "
        f"{my_section:<5} "
        f"{c['call']:<10} "
        f"{c['their_class']:>3} "
        f"{c['their_section']:<5}"
    ).rstrip()


def to_cabrillo(config, contacts):
    """Return a Cabrillo 3.0 log as a string.

    `contacts` should be in chronological order (oldest first), as the robot
    expects.
    """
    my_call = (config.get("my_call") or "").upper()
    my_class = config.get("my_class") or ""
    my_section = config.get("my_section") or ""

    # Claimed score = QSO points * power multiplier + bonus points.
    pts = fieldday.qso_points(contacts)
    try:
        mult = int(config.get("power_multiplier") or "1")
    except ValueError:
        mult = 1
    try:
        bonus = int(config.get("bonus_points") or "0")
    except ValueError:
        bonus = 0
    claimed = pts * mult + bonus

    lines = []
    lines.append("START-OF-LOG: 3.0")
    lines.append("CONTEST: ARRL-FD")
    lines.append(f"CALLSIGN: {my_call}")
    lines.append(f"LOCATION: {my_section}")
    lines.append(f"CATEGORY-OPERATOR: {config.get('category_operator', '')}")
    lines.append(f"CATEGORY-STATION: {config.get('category_station', '')}")
    if config.get("category_transmitter"):
        lines.append(f"CATEGORY-TRANSMITTER: {config['category_transmitter']}")
    lines.append(f"CATEGORY-POWER: {config.get('category_power', '')}")
    lines.append(f"CATEGORY-ASSISTED: {config.get('category_assisted', '')}")
    lines.append(f"CLAIMED-SCORE: {claimed}")
    if config.get("club_name"):
        lines.append(f"CLUB: {config['club_name']}")
    if config.get("operators"):
        lines.append(f"OPERATORS: {config['operators'].upper()}")
    if config.get("contact_name"):
        lines.append(f"NAME: {config['contact_name']}")
    if config.get("address"):
        lines.append(f"ADDRESS: {config['address']}")
    if config.get("address_city"):
        lines.append(f"ADDRESS-CITY: {config['address_city']}")
    if config.get("email"):
        lines.append(f"EMAIL: {config['email']}")
    lines.append("CREATED-BY: Field Day Logger")
    if config.get("soapbox"):
        for chunk in config["soapbox"].splitlines():
            lines.append(f"SOAPBOX: {chunk}")

    for c in contacts:
        lines.append(_qso_line(c, my_call, my_class, my_section))

    lines.append("END-OF-LOG:")
    return "\r\n".join(lines) + "\r\n"


def _adif_field(name, value):
    value = "" if value is None else str(value)
    return f"<{name}:{len(value)}>{value} "


def to_adif(config, contacts):
    """Return an ADIF 3.x log as a string (useful for importing to LoTW etc.)."""
    out = ["ADIF export from Field Day Logger", "<ADIF_VER:5>3.1.4", "<PROGRAMID:17>Field Day Logger", "<EOH>", ""]
    my_call = (config.get("my_call") or "").upper()
    for c in contacts:
        parts = []
        parts.append(_adif_field("CALL", c["call"]))
        parts.append(_adif_field("QSO_DATE", c["qso_date"].replace("-", "")))
        parts.append(_adif_field("TIME_ON", c["qso_time"] + "00" if len(c["qso_time"]) == 4 else c["qso_time"]))
        parts.append(_adif_field("BAND", c["band"]))
        parts.append(_adif_field("MODE", _adif_mode(c["mode"])))
        if c.get("freq"):
            parts.append(_adif_field("FREQ", _khz_to_mhz(c["freq"])))
        parts.append(_adif_field("STATION_CALLSIGN", my_call))
        if c.get("operator"):
            parts.append(_adif_field("OPERATOR", c["operator"].upper()))
        # Field Day exchange -> ADIF contest fields.
        parts.append(_adif_field("CONTEST_ID", "ARRL-FIELD-DAY"))
        parts.append(_adif_field("CLASS", c["their_class"]))
        parts.append(_adif_field("ARRL_SECT", c["their_section"]))
        if c.get("rst_sent"):
            parts.append(_adif_field("RST_SENT", c["rst_sent"]))
        if c.get("rst_rcvd"):
            parts.append(_adif_field("RST_RCVD", c["rst_rcvd"]))
        parts.append("<EOR>")
        out.append("".join(parts))
    return "\n".join(out) + "\n"


def _adif_mode(mode):
    return {"PH": "SSB", "DG": "DIGITAL", "CW": "CW"}.get(mode, mode)


def _khz_to_mhz(freq):
    try:
        return f"{int(freq) / 1000:.4f}"
    except (ValueError, TypeError):
        return str(freq)
