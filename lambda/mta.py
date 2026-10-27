"""Read the MTA's live subway feed and answer: when are the next trains at my station?

No API key is needed. The MTA publishes one feed per group of lines, refreshed
every 30 seconds, in Google's GTFS-Realtime format (a compact binary that the
gtfs-realtime-bindings library decodes).
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import requests
from google.transit import gtfs_realtime_pb2

FEED_BASE = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2F"

# Which feed carries which lines. Oddly, the Franklin Av shuttle ("FS") rides in
# the B/D/F/M feed, and the 42 St shuttle ("GS") in the 1-7 feed. (Checked live
# 2026-10-26 by searching every feed for stop S01.)
FEED_FOR_LINE = {
    **{l: "gtfs-ace" for l in "ACE"},
    **{l: "gtfs" for l in "1234567"},
    "GS": "gtfs",
    **{l: "gtfs-bdfm" for l in "BDFM"}, "FS": "gtfs-bdfm",
    **{l: "gtfs-nqrw" for l in "NQRW"},
    **{l: "gtfs-jz" for l in "JZ"},
    "G": "gtfs-g", "L": "gtfs-l", "SI": "gtfs-si",
}


@dataclass
class Station:
    name: str          # how Alexa says it
    stop_ids: list     # MTA stop ids, without the N/S suffix
    lines: list        # which lines to report (feed is derived from these)
    pair: str = ""     # which station pair this belongs to (set below)


# The two Brooklyn station pairs that share these names.
STATIONS = {
    "franklin_c_nostrand_a": {
        "franklin": Station("Franklin Avenue", ["A45", "S01"], ["C", "FS"]),
        "nostrand": Station("Nostrand Avenue", ["A46"], ["A", "C"]),
    },
    "eastern_parkway": {
        "franklin": Station("Franklin Avenue", ["239"], ["2", "3", "4", "5"]),
        "nostrand": Station("Nostrand Avenue", ["248"], ["3"]),
    },
}

for _pair, _stations in STATIONS.items():
    for _st in _stations.values():
        _st.pair = _pair

# In the MTA's feed, "N" means northbound, which on every Brooklyn line here
# is the direction toward Manhattan. How Alexa names each direction, per pair:
DIRECTION_WORDS = {
    "franklin_c_nostrand_a": {"N": "Toward Manhattan", "S": "Toward Euclid Avenue"},
    "eastern_parkway": {"N": "Toward Manhattan", "S": "Toward Flatbush and New Lots"},
}

_cache = {}  # feed name -> (fetched_at, decoded feed)


def _fetch_feed(feed_name: str, max_age: int = 25):
    """Download and decode one feed; reuse it if fetched in the last 25 s."""
    cached = _cache.get(feed_name)
    if cached and time.time() - cached[0] < max_age:
        return cached[1]
    resp = requests.get(FEED_BASE + feed_name, timeout=8)
    resp.raise_for_status()
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(resp.content)
    _cache[feed_name] = (time.time(), feed)
    return feed


# ── Only trust trains that are really there ─────────────────────────────────
# The MTA feed also lists trips that are only PLANNED: not yet assigned to a train,
# not yet started, or with a position that is a projection rather than a sighting
# (seen live 2026-10-26: a Far Rockaway A listed 11 minutes out whose "position"
# was stamped 8 minutes in the future; Google Maps and the platform clock ignored
# it). A train counts only if the MTA has a CURRENT position report for it.
POSITION_MAX_AGE_S = 5 * 60   # older than this = the train has gone quiet
POSITION_MAX_AHEAD_S = 60     # stamped further ahead than this = a projection

try:
    from google.protobuf.unknown_fields import UnknownFieldSet
except ImportError:  # older protobuf: skip the assigned flag, keep the position test
    UnknownFieldSet = None


def _nyct_assigned(trip_descriptor):
    """The MTA's own 'is this trip assigned to a real train' flag (extension 1001,
    field 2). Returns True/False, or None when it can't be read."""
    if UnknownFieldSet is None:
        return None
    try:
        for f in UnknownFieldSet(trip_descriptor):
            if f.field_number != 1001:
                continue
            data, i = f.data, 0
            while i < len(data):
                key = data[i]; i += 1
                num, wire = key >> 3, key & 7
                if wire == 0:
                    val, shift = 0, 0
                    while True:
                        b = data[i]; i += 1
                        val |= (b & 0x7F) << shift; shift += 7
                        if not b & 0x80:
                            break
                    if num == 2:
                        return bool(val)
                elif wire == 2:
                    ln = data[i]; i += 1 + ln
                else:
                    return None
            return False   # extension present, no assigned flag = not assigned
    except Exception:
        return None
    return None


def live_trip_ids(feed, now: float) -> set:
    """Trip ids the MTA is tracking right now: assigned, with a current position."""
    live = set()
    for entity in feed.entity:
        if not entity.HasField("vehicle"):
            continue
        v = entity.vehicle
        if not v.timestamp:
            continue
        age = now - v.timestamp
        if age > POSITION_MAX_AGE_S or age < -POSITION_MAX_AHEAD_S:
            continue
        if _nyct_assigned(v.trip) is False:
            continue
        live.add(v.trip.trip_id)
    return live


def _min_minutes(station: Station) -> float:
    """The catchable-train cutoff for this station, from config (default 1 minute)."""
    try:
        import config
        table = getattr(config, "HIDE_TRAINS_UNDER_MINUTES", {})
    except ImportError:
        table = {}
    key = "franklin" if "Franklin" in station.name else "nostrand" if "Nostrand" in station.name else ""
    return float(table.get(key, 1))


def next_arrivals(station: Station, now: float | None = None, limit: int = 3) -> dict:
    """Return {"N": [(line, minutes), ...], "S": [...]} sorted soonest first."""
    now = now or time.time()
    min_minutes = _min_minutes(station)
    feeds = {FEED_FOR_LINE[l] for l in station.lines}
    arrivals = {"N": [], "S": []}
    for feed_name in feeds:
        feed = _fetch_feed(feed_name)
        live = live_trip_ids(feed, now)
        for entity in feed.entity:
            if not entity.HasField("trip_update"):
                continue
            trip = entity.trip_update
            if trip.trip.trip_id not in live:
                continue  # planned or untracked, not a train you can see coming
            line = trip.trip.route_id
            # Report ANY line the feed says stops here, not just the usual ones:
            # at night and during service changes the A runs local and covers the
            # C's stops (seen live 2026-10-26: A trains at Franklin, no C).
            for stu in trip.stop_time_update:
                base, direction = stu.stop_id[:-1], stu.stop_id[-1]
                if base not in station.stop_ids or direction not in arrivals:
                    continue
                if line == "FS" and direction == "N":
                    continue  # the shuttle ends at Franklin Av; only departures matter
                t = stu.arrival.time or stu.departure.time
                if not t:
                    continue
                minutes = (t - now) / 60
                if minutes < min_minutes:
                    continue  # already left, or too close to catch
                arrivals[direction].append((line, round(minutes)))
    for d in arrivals:
        arrivals[d] = sorted(arrivals[d], key=lambda x: x[1])[:limit]
    return arrivals


def say_line(line: str) -> str:
    """How Alexa names a line, as in "<this> in 4 minutes"."""
    return {"FS": "shuttle to Prospect Park"}.get(line, f"{line} train")


def _when(mins: int) -> str:
    return "now" if mins == 0 else f"in {mins} minute{'s' if mins != 1 else ''}"


def _times(trains) -> str:
    """"A train in 3 minutes, then C train in 11 minutes": every train names its line."""
    return ", then ".join(f"{say_line(line)} {_when(mins)}" for line, mins in trains)


def speak(station: Station, arrivals: dict, direction: str | None = None,
          line: str | None = None, mention_direction: bool = True, limit: int = 2) -> str:
    """Turn arrivals into speech.

    direction: "N", "S" or None for both.
    line: answer about one line only ("C"), in the short form.
    mention_direction: say "toward Manhattan"; off when it's the default anyway.
    """
    stopping_now = {l for trains in arrivals.values() for l, _ in trains}
    if line and line not in station.lines and line not in stopping_now:
        return f"The {say_line(line)} doesn't stop at {station.name}."
    parts = []
    for d in ([direction] if direction else ["N", "S"]):
        label = DIRECTION_WORDS[station.pair][d]
        toward = f" {label.lower()}" if mention_direction else ""
        trains = [t for t in arrivals.get(d, []) if not line or t[0] == line][:limit]
        if not trains:
            what = f"{say_line(line)}s" if line else "trains"
            parts.append(f"No {what}{toward} are showing at {station.name} right now.")
        elif line:
            first, rest = trains[0], trains[1:]
            more = "".join(f", then another {_when(m)}" for _, m in rest)
            first_when = "arriving now" if first[1] == 0 else _when(first[1])
            parts.append(f"The next {say_line(line)}{toward} at {station.name} is {first_when}{more}.")
        else:
            where = f"{label} at {station.name}" if mention_direction else station.name
            parts.append(f"{where}: {_times(trains)}.")
    return " ".join(parts)
