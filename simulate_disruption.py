"""
SkySaver AI — disruption simulator.

In the real world, the agent would detect disruptions by polling airline APIs,
parsing email confirmations, or reading from a flight-status feed. For the
hackathon we control the disruption directly so we can trigger the recovery
flow on demand, including during a live demo.

Usage:
    # Cancel a leg (the most dramatic disruption)
    python simulate_disruption.py trip_001 leg_002 cancelled

    # Delay a leg by a number of minutes
    python simulate_disruption.py trip_001 leg_002 delayed --delay 240

    # Gate change (cosmetic — just for variety)
    python simulate_disruption.py trip_001 leg_002 gate_change --gate B27

Effects:
    - Marks the leg's status as "disrupted" (or "cancelled" if the type is
      cancelled).
    - For delays, pushes the leg's start_at and end_at forward by --delay
      minutes so the rest of the system sees the new timing.
    - Appends a record to disruption_history so the agent (and demo viewers)
      can see what happened.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone

from mongo_helpers import (
    find_leg,
    get_trip,
    log_disruption,
    update_leg,
)


DISRUPTION_TYPES = {"cancelled", "delayed", "gate_change"}


def _shift_iso(iso_string: str, minutes: int) -> str:
    """Shift an ISO 8601 UTC timestamp forward by N minutes."""
    dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
    shifted = dt + timedelta(minutes=minutes)
    return shifted.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def simulate_cancellation(trip_id: str, leg_id: str, leg: dict) -> None:
    update_leg(trip_id, leg_id, {"status": "cancelled"})

    details = (
        f"{leg.get('airline', '')}{leg.get('flight_number', '')} "
        f"{leg.get('origin', '')} → {leg.get('destination', '')} cancelled."
    ).strip()

    log_disruption(
        trip_id,
        {
            "disruption_id": f"dis_{leg_id}_cancelled",
            "affected_leg_id": leg_id,
            "disruption_type": "cancelled",
            "details": details,
            "alternatives_considered": [],
            "chosen_alternative": None,
            "user_confirmed_at": None,
            "booking_method": None,
            "new_booking_reference": None,
            "cascade_changes": [],
        },
    )


def simulate_delay(trip_id: str, leg_id: str, leg: dict, delay_minutes: int) -> None:
    new_start = _shift_iso(leg["start_at"], delay_minutes)
    new_end = _shift_iso(leg["end_at"], delay_minutes)
    update_leg(
        trip_id,
        leg_id,
        {
            "status": "disrupted",
            "start_at": new_start,
            "end_at": new_end,
        },
    )

    details = (
        f"{leg.get('airline', '')}{leg.get('flight_number', '')} "
        f"delayed by {delay_minutes} minutes — new departure {new_start}."
    ).strip()

    log_disruption(
        trip_id,
        {
            "disruption_id": f"dis_{leg_id}_delayed",
            "affected_leg_id": leg_id,
            "disruption_type": "delayed",
            "delay_minutes": delay_minutes,
            "details": details,
            "alternatives_considered": [],
            "chosen_alternative": None,
            "user_confirmed_at": None,
            "booking_method": None,
            "new_booking_reference": None,
            "cascade_changes": [],
        },
    )


def simulate_gate_change(trip_id: str, leg_id: str, leg: dict, new_gate: str) -> None:
    update_leg(trip_id, leg_id, {"status": "disrupted", "departure_gate": new_gate})

    details = (
        f"{leg.get('airline', '')}{leg.get('flight_number', '')} "
        f"gate changed to {new_gate}."
    ).strip()

    log_disruption(
        trip_id,
        {
            "disruption_id": f"dis_{leg_id}_gate_change",
            "affected_leg_id": leg_id,
            "disruption_type": "gate_change",
            "new_gate": new_gate,
            "details": details,
            "alternatives_considered": [],
            "chosen_alternative": None,
            "user_confirmed_at": None,
            "booking_method": None,
            "new_booking_reference": None,
            "cascade_changes": [],
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate a travel disruption.")
    parser.add_argument("trip_id", help="Trip _id (e.g., trip_001)")
    parser.add_argument("leg_id", help="Leg _id within the trip (e.g., leg_002)")
    parser.add_argument(
        "disruption_type",
        choices=sorted(DISRUPTION_TYPES),
        help="Kind of disruption to simulate",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=120,
        help="Minutes of delay (only used for disruption_type=delayed)",
    )
    parser.add_argument(
        "--gate",
        type=str,
        default="B27",
        help="New gate (only used for disruption_type=gate_change)",
    )
    args = parser.parse_args()

    trip = get_trip(args.trip_id)
    if trip is None:
        print(f"No trip found with _id={args.trip_id!r}. Run seed_trip.py first.")
        sys.exit(1)

    leg = find_leg(trip, args.leg_id)
    if leg is None:
        print(f"No leg with _id={args.leg_id!r} in trip {args.trip_id!r}.")
        sys.exit(1)

    if leg.get("type") != "flight":
        print(
            f"Disruptions only apply to flight legs, but leg {args.leg_id} is "
            f"type={leg.get('type')!r}."
        )
        sys.exit(1)

    if args.disruption_type == "cancelled":
        simulate_cancellation(args.trip_id, args.leg_id, leg)
    elif args.disruption_type == "delayed":
        simulate_delay(args.trip_id, args.leg_id, leg, args.delay)
    elif args.disruption_type == "gate_change":
        simulate_gate_change(args.trip_id, args.leg_id, leg, args.gate)

    print(
        f"Injected {args.disruption_type} on {args.trip_id}/{args.leg_id} "
        f"({leg.get('airline', '')}{leg.get('flight_number', '')})."
    )
    print("Run `python read_trip.py` to see the updated trip.")


if __name__ == "__main__":
    main()
