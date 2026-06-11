"""
SkySaver AI — flight search tool.

Wraps SerpAPI's Google Flights endpoint so the agent can fetch real flight
options when handling a disruption.

Key design choices:

1. **Single function, normalised output.** `search_flights()` returns a list of
   plain dicts with the fields the agent and ranker actually care about
   (airline, times, duration, stops, price). The raw API response is kept on
   each item under "raw" for debugging.

2. **File-based cache.** SerpAPI's free tier is 100 searches total. During
   development you'll re-run the same query many times. Each (origin,
   destination, date) tuple is cached to `.flight_cache/` for 6 hours, which
   keeps testing cheap. Set `use_cache=False` to bypass.

3. **Graceful failure.** If SerpAPI returns no flights or the request fails,
   we return an empty list instead of crashing. The agent's prompt should
   handle "no alternatives found" already.

Usage from Python:
    from flight_search import search_flights
    options = search_flights("DXB", "SIN", "2026-05-28")

Usage from the command line:
    python flight_search.py DXB SIN 2026-05-28
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()


SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
CACHE_DIR = Path(__file__).parent / ".flight_cache"
CACHE_TTL_SECONDS = 6 * 60 * 60  # 6 hours


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _cache_key(origin: str, destination: str, date: str) -> str:
    raw = f"{origin.upper()}|{destination.upper()}|{date}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _cache_path(key: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / f"{key}.json"


def _read_cache(origin: str, destination: str, date: str) -> dict | None:
    path = _cache_path(_cache_key(origin, destination, date))
    if not path.exists():
        return None
    if time.time() - path.stat().st_mtime > CACHE_TTL_SECONDS:
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _write_cache(origin: str, destination: str, date: str, payload: dict) -> None:
    path = _cache_path(_cache_key(origin, destination, date))
    try:
        with open(path, "w") as f:
            json.dump(payload, f)
    except OSError:
        # Cache failure should never block a real query
        pass


# ---------------------------------------------------------------------------
# SerpAPI call + normalisation
# ---------------------------------------------------------------------------


def _fetch_from_serpapi(origin: str, destination: str, date: str) -> dict:
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        raise RuntimeError("SERPAPI_KEY is not set in the environment / .env file")

    params = {
        "engine": "google_flights",
        "api_key": api_key,
        "departure_id": origin.upper(),
        "arrival_id": destination.upper(),
        "outbound_date": date,
        "currency": "USD",
        "type": "2",  # 2 = one-way (we rebook a single segment at a time)
        "hl": "en",
    }
    response = requests.get(SERPAPI_ENDPOINT, params=params, timeout=20)
    response.raise_for_status()
    return response.json()


def _normalise(raw: dict) -> list[dict[str, Any]]:
    """Convert SerpAPI's response into the agent's preferred flat shape."""
    options: list[dict[str, Any]] = []
    groups = (raw.get("best_flights") or []) + (raw.get("other_flights") or [])

    for group in groups:
        flights = group.get("flights") or []
        if not flights:
            continue

        first = flights[0]
        last = flights[-1]
        airline = first.get("airline") or ""
        airline_code = first.get("airline_logo", "").split("/")[-1].split(".")[0].upper()[:2] if first.get("airline_logo") else ""
        flight_number = first.get("flight_number", "")

        options.append({
            "airline": airline,
            "airline_code": airline_code,
            "flight_number": flight_number,
            "origin": first.get("departure_airport", {}).get("id", ""),
            "destination": last.get("arrival_airport", {}).get("id", ""),
            "departure_time": first.get("departure_airport", {}).get("time", ""),
            "arrival_time": last.get("arrival_airport", {}).get("time", ""),
            "duration_minutes": group.get("total_duration", 0),
            "stops": max(len(flights) - 1, 0),
            "price_usd": group.get("price"),
            "carbon_emissions_g": group.get("carbon_emissions", {}).get("this_flight"),
            "raw": group,
        })

    return options


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def search_flights(
    origin: str,
    destination: str,
    date: str,
    use_cache: bool = True,
) -> list[dict[str, Any]]:
    """
    Search for one-way flights from `origin` to `destination` on `date`.

    Args:
        origin:      IATA code (e.g., "LHR", "DXB")
        destination: IATA code (e.g., "SIN")
        date:        YYYY-MM-DD outbound date
        use_cache:   When True (default), returns cached results within 6h.

    Returns:
        List of normalised flight option dicts. Empty list on no results.
    """
    if use_cache:
        cached = _read_cache(origin, destination, date)
        if cached is not None:
            return _normalise(cached)

    try:
        payload = _fetch_from_serpapi(origin, destination, date)
    except requests.RequestException as exc:
        print(f"[flight_search] SerpAPI request failed: {exc}", file=sys.stderr)
        return []

    _write_cache(origin, destination, date, payload)
    return _normalise(payload)


# ---------------------------------------------------------------------------
# CLI for quick manual checks
# ---------------------------------------------------------------------------


def main() -> None:
    if len(sys.argv) < 4:
        print("Usage: python flight_search.py ORIGIN DESTINATION DATE")
        print("Example: python flight_search.py DXB SIN 2026-05-28")
        sys.exit(1)

    origin, destination, date = sys.argv[1], sys.argv[2], sys.argv[3]
    options = search_flights(origin, destination, date)

    if not options:
        print(f"No flights found for {origin} → {destination} on {date}.")
        return

    print(f"\n{len(options)} flight option(s) for {origin} → {destination} on {date}:\n")
    for i, opt in enumerate(options[:10], start=1):
        stops_label = "direct" if opt["stops"] == 0 else f"{opt['stops']} stop"
        price = opt["price_usd"] if opt["price_usd"] is not None else "—"
        print(
            f"  {i:>2}. {opt['airline']:<22} "
            f"{opt['departure_time']:>5} → {opt['arrival_time']:>5}   "
            f"{opt['duration_minutes']:>4} min   "
            f"{stops_label:<8}   "
            f"${price}"
        )
    if len(options) > 10:
        print(f"  ... ({len(options) - 10} more)")


if __name__ == "__main__":
    main()
