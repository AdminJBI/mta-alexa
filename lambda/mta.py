"""Read the MTA's live subway feed and answer: when are the next trains at my station?

No API key is needed. The MTA publishes one feed per group of lines, refreshed
every 30 seconds, in Google's GTFS-Realtime format (a compact binary that the
gtfs-realtime-bindings library decodes).
"""
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


def next_arrivals(station: Station, now: float | None = None, limit: int = 3) -> dict:
    """Return {"N": [(line, minutes), ...], "S": [...]} sorted soonest first."""
    now = now or time.time()
    wanted = set(station.lines)
    feeds = {FEED_FOR_LINE[l] for l in wanted}
    arrivals = {"N": [], "S": []}
    for feed_name in feeds:
        feed = _fetch_feed(feed_name)
        for entity in feed.entity:
            if not entity.HasField("trip_update"):
                continue
            trip = entity.trip_update
            line = trip.trip.route_id
            if line not in wanted:
                continue
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
                if minutes < -0.5:
                    continue  # already left
                arrivals[direction].append((line, max(0, round(minutes))))
    for d in arrivals:
        arrivals[d] = sorted(arrivals[d], key=lambda x: x[1])[:limit]
    return arrivals


def say_line(line: str) -> str:
    """How Alexa names a line, as in "<this> in 4 minutes"."""
    return {"FS": "shuttle to Prospect Park"}.get(line, f"{line} train")


def _when(mins: int) -> str:
    return "now" if mins == 0 else f"in {mins} minute{'s' if mins != 1 else ''}"


def _times(trains) -> str:
    """"C train in 3 minutes, then 11 minutes" / "A train in 2 minutes, then C train in 5 minutes"."""
    same_line = len({l for l, _ in trains}) == 1
    pieces = []
    for i, (line, mins) in enumerate(trains):
        if i == 0 or not same_line:
            pieces.append(f"{say_line(line)} {_when(mins)}")
        else:
            pieces.append(_when(mins) if mins == 0 else f"{mins} minute{'s' if mins != 1 else ''}")
    return ", then ".join(pieces)


def speak(station: Station, arrivals: dict, direction: str | None = None,
          line: str | None = None, mention_direction: bool = True, limit: int = 2) -> str:
    """Turn arrivals into speech.

    direction: "N", "S" or None for both.
    line: answer about one line only ("C"), in the short form.
    mention_direction: say "toward Manhattan"; off when it's the default anyway.
    """
    if line and line not in station.lines:
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
            more = (", then " + ", then ".join(
                _when(m).replace("in ", "", 1) if m else "now" for _, m in rest)) if rest else ""
            first_when = "arriving now" if first[1] == 0 else _when(first[1])
            parts.append(f"The next {say_line(line)}{toward} at {station.name} is {first_when}{more}.")
        else:
            where = f"{label} at {station.name}" if mention_direction else station.name
            parts.append(f"{where}: {_times(trains)}.")
    return " ".join(parts)
