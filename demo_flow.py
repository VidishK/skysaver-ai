"""
SkySaver AI — direct demo of the agent's intelligence layer.

This script proves the *whole pipeline* works end-to-end without going through
Gemini's function-calling. It runs the same sequence the agent would: read the
trip, simulate a cancellation, search for alternatives, pick the best one
based on the user's preferences, preview the cascade, apply the booking.

Use it for two things:
  1. As a sanity check that every module (mongo_helpers, flight_search,
     cascade) is wired correctly.
  2. As a fallback demo path if Gemini's tool-calling misbehaves on demo day.

Usage:
    python demo_flow.py
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cascade import _flight_label, calculate_cascade, format_report
from flight_search import search_flights
from mongo_helpers import find_leg, get_trip, log_disruption, update_leg


TRIP_ID = "trip_001"
AFFECTED_LEG_ID = "leg_002"  # Dubai -> Singapore


def _parse(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _heading(text: str) -> None:
    print("\n" + "=" * 70)
    print(text)
    print("=" * 70)


def step_1_read_trip() -> dict:
    _heading("STEP 1 — Read trip from MongoDB")
    trip = get_trip(TRIP_ID)
    assert trip is not None, "Run seed_trip.py first"
    print(f"  Title: {trip['title']}")
    print(f"  Legs:  {len(trip['legs'])}")
    print(f"  User:  {trip['user_id']}")
    return trip


def step_2_inject_cancellation(trip: dict) -> dict:
    _heading("STEP 2 — Inject a cancellation on leg_002 (DXB → SIN)")
    update_leg(TRIP_ID, AFFECTED_LEG_ID, {"status": "cancelled"})
    print(f"  Marked {AFFECTED_LEG_ID} as cancelled in MongoDB.")
    return get_trip(TRIP_ID)


def step_3_find_disrupted(trip: dict) -> dict:
    _heading("STEP 3 — Detect the disruption")
    leg = find_leg(trip, AFFECTED_LEG_ID)
    print(f"  Disrupted leg: {leg['flight_number']}  {leg['origin']} → {leg['destination']}  status={leg['status']}")
    return leg


def step_4_search_alternatives(disrupted_leg: dict) -> list[dict]:
    _heading("STEP 4 — Search for real alternatives via Google Flights")
    origin = disrupted_leg["origin"]
    destination = disrupted_leg["destination"]
    date = disrupted_leg["start_at"][:10]
    print(f"  Querying SerpAPI: {origin} → {destination} on {date} …")
    options = search_flights(origin, destination, date)
    print(f"  Got {len(options)} options. Top 3:")
    for i, opt in enumerate(options[:3], 1):
        stops = "direct" if opt["stops"] == 0 else f"{opt['stops']} stop"
        print(f"    {i}. {opt['airline']:<22} {opt['departure_time']} → {opt['arrival_time']}   {opt['duration_minutes']} min  {stops}  ${opt['price_usd']}")
    return options


def _parse_serpapi_time(value: str, fallback_date: str) -> datetime:
    """SerpAPI Google Flights returns times as either 'YYYY-MM-DD HH:MM' or
    'HH:MM'. Normalise both into a UTC datetime."""
    if not value:
        return datetime.fromisoformat(fallback_date + "T09:00:00+00:00")
    value = value.strip()
    try:
        if " " in value and "-" in value:
            return datetime.fromisoformat(value.replace(" ", "T") + "+00:00")
        # Plain "HH:MM"
        hh, mm = value.split(":", 1)
        base = datetime.fromisoformat(fallback_date + "T00:00:00+00:00")
        return base.replace(hour=int(hh), minute=int(mm[:2]))
    except (ValueError, IndexError):
        return datetime.fromisoformat(fallback_date + "T09:00:00+00:00")


def _augment_with_iso(opt: dict, date: str) -> dict:
    """Attach real ISO departure/arrival timestamps to a SerpAPI option."""
    dep_dt = _parse_serpapi_time(opt.get("departure_time", ""), date)
    arr_dt = _parse_serpapi_time(opt.get("arrival_time", ""), date)
    # If arrival looks earlier than departure on the same day, assume it
    # landed the following calendar day.
    if arr_dt <= dep_dt:
        arr_dt += timedelta(days=1)
    return {
        **opt,
        "origin": opt.get("origin") or "DXB",
        "destination": opt.get("destination") or "SIN",
        "departure_at_iso": _to_iso(dep_dt),
        "arrival_at_iso": _to_iso(arr_dt),
    }


def step_5_rank_and_preview(trip: dict, options: list[dict], disrupted_leg: dict) -> dict:
    _heading("STEP 5 — Rank by preferences and preview cascade impact")

    prefs = trip.get("preferences", {})
    preferred_airlines = prefs.get("preferred_airlines", [])
    prefers_direct = prefs.get("prefers_direct", True)
    budget_sensitivity = prefs.get("budget_sensitivity", "medium")

    def score(opt: dict) -> float:
        s = 0.0
        # Direct preference
        if prefers_direct and opt.get("stops", 0) == 0:
            s += 30
        # Preferred airline
        airline_code = (opt.get("airline_code") or "").upper()
        for i, code in enumerate(preferred_airlines):
            if code.upper() == airline_code:
                s += 20 - i * 5
                break
        # Cheaper = better, scaled by budget sensitivity
        price = opt.get("price_usd") or 9999
        weight = {"low": 0.005, "medium": 0.02, "high": 0.05}[budget_sensitivity]
        s -= price * weight
        # Shorter = better
        s -= (opt.get("duration_minutes") or 0) / 60
        return s

    ranked = sorted(options, key=score, reverse=True)
    date = disrupted_leg["start_at"][:10]
    print("\n  Top 3 ranked alternatives (with cascade preview):")
    top3 = []
    for i, opt in enumerate(ranked[:3], 1):
        augmented = _augment_with_iso(opt, date)
        report = calculate_cascade(trip, AFFECTED_LEG_ID, augmented)
        print(f"\n  --- Option {i} ---")
        print(format_report(report))
        top3.append({"option": augmented, "report": report})
    return top3[0] if top3 else None


def step_6_book_and_apply(trip: dict, chosen: dict) -> None:
    _heading("STEP 6 — Apply chosen option (user confirmed)")
    if chosen is None:
        print("  No options to apply — skipping.")
        return

    option = chosen["option"]
    report = chosen["report"]

    update_leg(
        TRIP_ID,
        AFFECTED_LEG_ID,
        {
            "airline": option.get("airline_code") or option.get("airline", "")[:2].upper(),
            "flight_number": option.get("flight_number", "TBD"),
            "origin": option["origin"],
            "destination": option["destination"],
            "start_at": option["departure_at_iso"],
            "end_at": option["arrival_at_iso"],
            "price_usd": option.get("price_usd"),
            "status": "rebooked",
            "booking_reference": "DEMO-BOOKED",
            "booking_method": "mock",
        },
    )
    for imp in report.impacts:
        if not imp.proposed_changes:
            continue
        change_dict = {c["field"]: c["to"] for c in imp.proposed_changes}
        update_leg(TRIP_ID, imp.leg_id, change_dict)

    log_disruption(
        TRIP_ID,
        {
            "disruption_id": f"rec_{AFFECTED_LEG_ID}",
            "affected_leg_id": AFFECTED_LEG_ID,
            "disruption_type": "recovered",
            "details": f"Replaced with {option.get('airline','?')} {option.get('flight_number','?')}.",
            "chosen_alternative": report.replacement_summary,
            "booking_method": "mock",
            "new_booking_reference": "DEMO-BOOKED",
            "cascade_changes": [c for imp in report.impacts for c in imp.proposed_changes],
        },
    )
    print(f"  Booked {option.get('airline','?')} {option.get('flight_number','?')} and applied {sum(1 for i in report.impacts if i.proposed_changes)} downstream changes.")


def step_7_show_final_trip() -> None:
    _heading("STEP 7 — Final trip state in MongoDB")
    trip = get_trip(TRIP_ID)
    for leg in trip["legs"]:
        if leg["type"] == "flight":
            label = _flight_label(leg)
            print(f"  ✈  {leg['leg_id']}  {label:<10}  {leg['origin']} → {leg['destination']}  status={leg['status']}")
        elif leg["type"] == "hotel":
            print(f"  🏨  {leg['leg_id']}  {leg['name']}  check-in={leg['start_at']}")
        elif leg["type"] == "transport":
            print(f"  🚖  {leg['leg_id']}  {leg['mode']}  start={leg['start_at']}")
        elif leg["type"] == "meeting":
            print(f"  📅  {leg['leg_id']}  {leg['title']}  start={leg['start_at']}")
    print(f"\n  Disruption history events: {len(trip.get('disruption_history', []))}")


def main() -> None:
    trip = step_1_read_trip()
    trip = step_2_inject_cancellation(trip)
    disrupted_leg = step_3_find_disrupted(trip)
    options = step_4_search_alternatives(disrupted_leg)
    if not options:
        print("\n[demo] No alternatives returned from SerpAPI — check your key or quota.")
        return
    chosen = step_5_rank_and_preview(trip, options, disrupted_leg)
    step_6_book_and_apply(trip, chosen)
    step_7_show_final_trip()
    print("\n" + "=" * 70)
    print("Demo flow complete — every module works end-to-end.")
    print("=" * 70)


if __name__ == "__main__":
    main()
