"""Every timestamp the tool writes comes from here, never from an argument."""

import re
from datetime import datetime

# What a heading's zone may look like: a letter abbreviation (PDT, UTC, IST) or a numeric offset (+04, -0330).
# Zones with no abbreviation print as "+04" from both strftime("%Z") and `date +%Z`.
ZONE_PATTERN = r"(?:[A-Z]{2,5}|[+-]\d{2}(?:\d{2})?)"
_ZONE_RE = re.compile(ZONE_PATTERN)


def now() -> datetime:
    return datetime.now().astimezone()


def stamp() -> str:
    """The heading form: 2026-09-25 10:12 PDT (or 2026-09-25 21:12 +04 where the zone has no abbreviation)."""
    moment = now()
    zone = moment.strftime("%Z")
    if not _ZONE_RE.fullmatch(zone):
        # Fixed offsets print "UTC+04:00" and Windows prints "Pacific Daylight Time"; neither parses back.
        zone = moment.strftime("%z")
    return f"{moment:%Y-%m-%d %H:%M} {zone}"


def iso() -> str:
    """The event form, second resolution with offset."""
    return now().isoformat(timespec="seconds")
