"""
SkySaver AI — seed the demo trip into MongoDB.

Usage:
    python seed_trip.py
    python seed_trip.py --days-out 14   # start the trip 14 days from today

Each run wipes the existing demo trip (trip_001) and inserts a fresh copy
with dates relative to *today*. That way SerpAPI always sees future dates
(it returns 400 for past ones).
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from mongo_helpers import save_trip


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_demo_trip(days_out: int = 7) -> dict:
    """Build the trip document with all dates relative to today.

    Layout (Day = days_out from today):
        Day 0  10:00 UTC : LHR → DXB (EK8)
        Day 0  17:30 UTC : land in DXB
        Day 0  22:00 UTC : DXB → SIN (EK314)
        Day 1  09:30 UTC : land in SIN
        Day 1  10:00 UTC : taxi to hotel
        Day 1  15:00 UTC : hotel check-in
        Day 2  10:00 UTC : Q3 review meeting
        Day 3  23:55 UTC : SIN → LHR (SQ322)
        Day 4  06:30 UTC : land in LHR
    """
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    day_0 = today + timedelta(days=days_out)
    day_1 = day_0 + timedelta(days=1)
    day_2 = day_0 + timedelta(days=2)
    day_3 = day_0 + timedelta(days=3)
    day_4 = day_0 + timedelta(days=4)

    return {
        "_id": "trip_001",
        "user_id": "user_vidish",
        "title": "Singapore Q3 Review Trip",
        "status": "active",

        "preferences": {
            "budget_sensitivity": "medium",
            "prefers_direct": True,
            "preferred_airlines": ["SQ", "EK", "BA"],
            "avoid_airlines": [],
            "max_layover_hours": 4,
            "preferred_arrival_window": "morning",
            "seat_class": "economy",
            "checked_baggage": True,
            "loyalty_programs": {"SQ": "KrisFlyer-1234567"},
        },

        "legs": [
            # ---- Outbound flight 1: London → Dubai ----
            {
                "leg_id": "leg_001",
                "type": "flight",
                "status": "scheduled",
                "start_at": _iso(day_0.replace(hour=10)),
                "end_at":   _iso(day_0.replace(hour=17, minute=30)),
                "airline": "EK",
                "flight_number": "EK8",
                "origin": "LHR",
                "destination": "DXB",
                "departure_terminal": "3",
                "arrival_terminal": "3",
                "stops": 0,
                "duration_minutes": 450,
                "price_usd": 410,
                "currency": "USD",
                "booking_reference": "EK-AB12CD",
                "booking_method": "mock",
                "ticket_class": "economy",
                "notes": "Window seat requested.",
            },

            # ---- Outbound flight 2: Dubai → Singapore ----
            {
                "leg_id": "leg_002",
                "type": "flight",
                "status": "scheduled",
                "start_at": _iso(day_0.replace(hour=22)),
                "end_at":   _iso(day_1.replace(hour=9, minute=30)),
                "airline": "EK",
                "flight_number": "EK314",
                "origin": "DXB",
                "destination": "SIN",
                "departure_terminal": "3",
                "arrival_terminal": "1",
                "stops": 0,
                "duration_minutes": 450,
                "price_usd": 510,
                "currency": "USD",
                "booking_reference": "EK-AB12CD",
                "booking_method": "mock",
                "ticket_class": "economy",
                "notes": "",
            },

            # ---- Ground transport: Changi → hotel ----
            {
                "leg_id": "leg_003",
                "type": "transport",
                "status": "scheduled",
                "start_at": _iso(day_1.replace(hour=10)),
                "end_at":   _iso(day_1.replace(hour=10, minute=45)),
                "mode": "taxi",
                "from": "Changi Airport T1",
                "to":   "Marina Bay Sands",
                "estimated_cost_usd": 35,
                "notes": "Pre-paid via hotel concierge service.",
            },

            # ---- Hotel: Marina Bay Sands, two nights ----
            {
                "leg_id": "leg_004",
                "type": "hotel",
                "status": "scheduled",
                "start_at": _iso(day_1.replace(hour=15)),
                "end_at":   _iso(day_3.replace(hour=11)),
                "name": "Marina Bay Sands",
                "city": "Singapore",
                "address": "10 Bayfront Avenue, Singapore 018956",
                "confirmation_code": "MBS-99281",
                "nightly_rate_usd": 420,
                "total_usd": 840,
                "notes": "Late check-in flagged with the front desk.",
            },

            # ---- High-importance meeting: Q3 review ----
            {
                "leg_id": "leg_005",
                "type": "meeting",
                "status": "scheduled",
                "start_at": _iso(day_2.replace(hour=10)),
                "end_at":   _iso(day_2.replace(hour=11, minute=30)),
                "title": "Q3 review with Acme APAC",
                "location": "Acme Singapore HQ, 1 Raffles Place, Singapore 048616",
                "attendees": ["alice@acme.com", "bob@acme.com"],
                "importance": "high",
                "buffer_before_minutes": 90,
                "notes": "Cannot be rescheduled — quarter-end review.",
            },

            # ---- Return flight: Singapore → London (direct) ----
            {
                "leg_id": "leg_006",
                "type": "flight",
                "status": "scheduled",
                "start_at": _iso(day_3.replace(hour=23, minute=55)),
                "end_at":   _iso(day_4.replace(hour=6, minute=30)),
                "airline": "SQ",
                "flight_number": "SQ322",
                "origin": "SIN",
                "destination": "LHR",
                "departure_terminal": "3",
                "arrival_terminal": "2",
                "stops": 0,
                "duration_minutes": 815,
                "price_usd": 980,
                "currency": "USD",
                "booking_reference": "SQ-ZZ44YX",
                "booking_method": "mock",
                "ticket_class": "economy",
                "notes": "Aisle seat requested.",
            },
        ],

        "disruption_history": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the SkySaver demo trip.")
    parser.add_argument(
        "--days-out",
        type=int,
        default=7,
        help="How many days from today the trip starts (default 7).",
    )
    args = parser.parse_args()

    trip = build_demo_trip(days_out=args.days_out)
    trip_id = save_trip(trip)
    first_flight_date = trip["legs"][0]["start_at"][:10]
    print(f"Seeded demo trip: {trip_id}")
    print(f"Legs: {len(trip['legs'])}")
    print(f"User: {trip['user_id']}")
    print(f"Title: {trip['title']}")
    print(f"First flight departs: {first_flight_date}")


if __name__ == "__main__":
    main()
