"""
SkySaver AI — seed the demo trip into MongoDB.

Usage:
    python seed_trip.py

This wipes any existing demo trip (trip_001) and inserts a fresh copy. Run it
any time you want to reset the demo state before recording or testing.

The demo scenario: London → Dubai → Singapore with two flights, two hotels,
ground transport in Singapore, and a high-importance Q3 review meeting on
arrival morning. This trip is the canvas the agent operates on during the demo.
"""

from __future__ import annotations

from mongo_helpers import save_trip


DEMO_TRIP = {
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
        "loyalty_programs": {
            "SQ": "KrisFlyer-1234567",
        },
    },

    "legs": [
        # ---- Outbound flight 1: London → Dubai ----
        {
            "leg_id": "leg_001",
            "type": "flight",
            "status": "scheduled",
            "start_at": "2026-05-27T10:00:00Z",
            "end_at":   "2026-05-27T19:30:00Z",
            "airline": "EK",
            "flight_number": "EK8",
            "origin": "LHR",
            "destination": "DXB",
            "departure_terminal": "3",
            "arrival_terminal": "3",
            "stops": 0,
            "duration_minutes": 420,
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
            "start_at": "2026-05-27T22:00:00Z",
            "end_at":   "2026-05-28T09:30:00Z",
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
            "booking_reference": "EK-AB12CD",  # same PNR as leg_001
            "booking_method": "mock",
            "ticket_class": "economy",
            "notes": "",
        },

        # ---- Ground transport: Changi → hotel ----
        {
            "leg_id": "leg_003",
            "type": "transport",
            "status": "scheduled",
            "start_at": "2026-05-28T10:00:00Z",
            "end_at":   "2026-05-28T10:45:00Z",
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
            "start_at": "2026-05-28T15:00:00Z",
            "end_at":   "2026-05-30T11:00:00Z",
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
            "start_at": "2026-05-29T10:00:00Z",
            "end_at":   "2026-05-29T11:30:00Z",
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
            "start_at": "2026-05-30T23:55:00Z",
            "end_at":   "2026-05-31T06:30:00Z",
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
    trip_id = save_trip(DEMO_TRIP)
    print(f"Seeded demo trip: {trip_id}")
    print(f"Legs: {len(DEMO_TRIP['legs'])}")
    print(f"User: {DEMO_TRIP['user_id']}")
    print(f"Title: {DEMO_TRIP['title']}")


if __name__ == "__main__":
    main()
