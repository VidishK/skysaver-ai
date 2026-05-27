"""
SkySaver AI — read the demo trip back from MongoDB and print a summary.

Usage:
    python read_trip.py [trip_id]

If no trip_id is passed, defaults to trip_001 (the seeded demo trip).
Verifies the write -> read round trip works and gives a quick visual sanity
check on what the agent will see when it queries MongoDB.
"""

from __future__ import annotations

import sys

from mongo_helpers import get_trip


LEG_ICON = {
    "flight":    "✈ ",
    "hotel":     "🏨 ",
    "transport": "🚖 ",
    "meeting":   "📅 ",
}


def format_leg(leg: dict) -> str:
    """Return a one-line summary of a leg."""
    icon = LEG_ICON.get(leg["type"], "•  ")
    start = leg["start_at"]
    end = leg["end_at"]
    leg_type = leg["type"]
    status = leg["status"]

    if leg_type == "flight":
        body = (
            f"{leg['airline']}{leg['flight_number']} "
            f"{leg['origin']} → {leg['destination']} "
            f"(${leg['price_usd']})"
        )
    elif leg_type == "hotel":
        body = f"{leg['name']}, {leg['city']} (${leg['total_usd']} total)"
    elif leg_type == "transport":
        body = f"{leg['mode']}: {leg['from']} → {leg['to']}"
    elif leg_type == "meeting":
        body = f"{leg['title']} [{leg['importance']} importance]"
    else:
        body = "(unknown leg type)"

    return f"  {icon}{body}\n      {start} → {end}   status={status}"


def main() -> None:
    trip_id = sys.argv[1] if len(sys.argv) > 1 else "trip_001"

    trip = get_trip(trip_id)
    if trip is None:
        print(f"No trip found with _id={trip_id!r}")
        print("Did you run `python seed_trip.py` first?")
        sys.exit(1)

    print("=" * 60)
    print(f"Trip: {trip['title']}")
    print(f"ID: {trip['_id']}  |  User: {trip['user_id']}  |  Status: {trip['status']}")
    print("=" * 60)

    prefs = trip.get("preferences", {})
    print("\nPreferences:")
    print(f"  direct flights: {prefs.get('prefers_direct')}")
    print(f"  preferred airlines: {', '.join(prefs.get('preferred_airlines', []))}")
    print(f"  budget sensitivity: {prefs.get('budget_sensitivity')}")
    print(f"  seat class: {prefs.get('seat_class')}")

    print(f"\nLegs ({len(trip.get('legs', []))}):")
    for leg in trip.get("legs", []):
        print(format_leg(leg))

    history = trip.get("disruption_history", [])
    print(f"\nDisruption history: {len(history)} event(s)")
    for event in history:
        print(f"  - {event.get('detected_at')}: {event.get('disruption_type')} on {event.get('affected_leg_id')}")

    print("\n" + "=" * 60)
    print("Round-trip OK — MongoDB read path works.")
    print("=" * 60)


if __name__ == "__main__":
    main()
