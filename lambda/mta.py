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

# In the MTA's feed, "N" means northbound, which on every Brooklyn line here
# is the Manhattan-bound direction.
DIRECTION_WORDS = {"N": "Manhattan-bound", "S": "Brooklyn-bound"}

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
    """How Alexa should pronounce a line name, as in "<this> in 4 minutes"."""
    return {"FS": "shuttle to Prospect Park"}.get(line, f"{line} train")


def speak(station: Station, arrivals: dict, direction: str | None = None) -> str:
    """Turn arrivals into one spoken sentence."""
    parts = []
    for d in ([direction] if direction else ["N", "S"]):
        trains = arrivals.get(d, [])
        label = DIRECTION_WORDS[d]
        if not trains:
            parts.append(f"No {label} trains are showing at {station.name} right now.")
            continue
        words = []
        for line, mins in trains:
            when = "now" if mins == 0 else f"in {mins} minute{'s' if mins != 1 else ''}"
            words.append(f"{say_line(line)} {when}")
        if len(words) > 1:
            listed = ", ".join(words[:-1]) + f", and {words[-1]}"
        else:
            listed = words[0]
        parts.append(f"{label} at {station.name}: {listed}.")
    return " ".join(parts)
