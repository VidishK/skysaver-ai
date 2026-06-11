"""
SkySaver AI — cascade calculator.

Given a trip and a candidate replacement flight, this module figures out how
that change ripples through the rest of the trip. It is the brain behind the
"cascade preview" the agent shows the user when handling a disruption.

The output is a structured impact report that can be:
  - shown to the user as a side-by-side preview
  - logged into MongoDB as `cascade_changes` after a booking
  - read by the agent to compare two candidate flights against each other

Severity legend:
    ok       — no change needed, buffer is healthy
    shifted  — downstream item moves but still works (e.g. hotel check-in)
    tight    — works but with reduced buffer; user should be warned
    broken   — does not work as-is; needs human intervention
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------


def _parse(iso_string: str) -> datetime:
    return datetime.fromisoformat(iso_string.replace("Z", "+00:00"))


def _to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _minutes_between(a: str, b: str) -> int:
    """Minutes from a to b (positive when b is later)."""
    return int((_parse(b) - _parse(a)).total_seconds() // 60)


# ---------------------------------------------------------------------------
# Data classes for the impact report
# ---------------------------------------------------------------------------


@dataclass
class LegImpact:
    leg_id: str
    leg_type: str
    summary: str
    severity: str  # ok | shifted | tight | broken
    proposed_changes: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CascadeReport:
    affected_leg_id: str
    replacement_summary: str
    arrival_delta_minutes: int  # +ve means later than original
    overall_severity: str
    feasible: bool
    impacts: list[LegImpact]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "affected_leg_id": self.affected_leg_id,
            "replacement_summary": self.replacement_summary,
            "arrival_delta_minutes": self.arrival_delta_minutes,
            "overall_severity": self.overall_severity,
            "feasible": self.feasible,
            "impacts": [asdict(i) for i in self.impacts],
            "warnings": self.warnings,
        }


# ---------------------------------------------------------------------------
# Severity rollup
# ---------------------------------------------------------------------------


_SEVERITY_RANK = {"ok": 0, "shifted": 1, "tight": 2, "broken": 3}


def _max_severity(severities: list[str]) -> str:
    if not severities:
        return "ok"
    return max(severities, key=lambda s: _SEVERITY_RANK.get(s, 0))


# ---------------------------------------------------------------------------
# Per-leg impact rules
# ---------------------------------------------------------------------------


def _flight_label(leg: dict) -> str:
    """Return a clean flight label, avoiding 'SQSQ322'-style duplication."""
    flight_number = leg.get("flight_number", "") or ""
    airline = leg.get("airline", "") or ""
    if flight_number.upper().startswith(airline.upper()) and airline:
        return flight_number
    return f"{airline}{flight_number}".strip()


def _impact_for_flight_connection(
    leg: dict, new_arrival_at_origin: str
) -> LegImpact:
    """A connecting flight downstream of the disrupted one."""
    connection_buffer_minutes = _minutes_between(new_arrival_at_origin, leg["start_at"])
    label = _flight_label(leg)

    if connection_buffer_minutes >= 90:
        return LegImpact(
            leg_id=leg["leg_id"],
            leg_type="flight",
            summary=f"Connecting flight {label} still has {connection_buffer_minutes} min buffer.",
            severity="ok",
        )
    if connection_buffer_minutes >= 45:
        return LegImpact(
            leg_id=leg["leg_id"],
            leg_type="flight",
            summary=f"Tight connection: {connection_buffer_minutes} min between arrival and {label} departure.",
            severity="tight",
        )
    return LegImpact(
        leg_id=leg["leg_id"],
        leg_type="flight",
        summary=f"Connection broken: only {connection_buffer_minutes} min between arrival and {label} — needs rebooking.",
        severity="broken",
    )


def _impact_for_hotel(leg: dict, arrival_delta_minutes: int) -> LegImpact:
    """Hotel check-in shifts if you're arriving later. Standard hotels accept late check-in."""
    if arrival_delta_minutes == 0:
        return LegImpact(
            leg_id=leg["leg_id"],
            leg_type="hotel",
            summary=f"No change to {leg.get('name','hotel')} check-in.",
            severity="ok",
        )

    original_start = leg["start_at"]
    new_start = _to_iso(_parse(original_start) + timedelta(minutes=arrival_delta_minutes))

    if arrival_delta_minutes > 0:
        summary = (
            f"{leg.get('name','Hotel')} check-in shifts "
            f"{arrival_delta_minutes // 60}h{arrival_delta_minutes % 60:02d}m later — "
            f"flag late arrival with front desk."
        )
        severity = "shifted"
    else:
        summary = (
            f"{leg.get('name','Hotel')} check-in shifts "
            f"{abs(arrival_delta_minutes) // 60}h{abs(arrival_delta_minutes) % 60:02d}m earlier."
        )
        severity = "shifted"

    return LegImpact(
        leg_id=leg["leg_id"],
        leg_type="hotel",
        summary=summary,
        severity=severity,
        proposed_changes=[{"field": "start_at", "from": original_start, "to": new_start}],
    )


def _impact_for_transport(leg: dict, arrival_delta_minutes: int) -> LegImpact:
    """Ground transport scheduled around arrival just shifts with the new time."""
    if arrival_delta_minutes == 0:
        return LegImpact(
            leg_id=leg["leg_id"],
            leg_type="transport",
            summary="Transport timing unchanged.",
            severity="ok",
        )

    original_start = leg["start_at"]
    original_end = leg["end_at"]
    new_start = _to_iso(_parse(original_start) + timedelta(minutes=arrival_delta_minutes))
    new_end = _to_iso(_parse(original_end) + timedelta(minutes=arrival_delta_minutes))

    return LegImpact(
        leg_id=leg["leg_id"],
        leg_type="transport",
        summary=(
            f"{leg.get('mode','Transport').capitalize()} shifts "
            f"{abs(arrival_delta_minutes)} minutes "
            f"{'later' if arrival_delta_minutes > 0 else 'earlier'}."
        ),
        severity="shifted",
        proposed_changes=[
            {"field": "start_at", "from": original_start, "to": new_start},
            {"field": "end_at", "from": original_end, "to": new_end},
        ],
    )


def _impact_for_meeting(leg: dict, new_arrival_iso: str) -> LegImpact:
    """A meeting can't be moved (typically). Check if the buffer still holds."""
    required_buffer = leg.get("buffer_before_minutes", 60)
    actual_buffer = _minutes_between(new_arrival_iso, leg["start_at"])
    importance = leg.get("importance", "medium")

    if actual_buffer >= required_buffer * 1.5:
        return LegImpact(
            leg_id=leg["leg_id"],
            leg_type="meeting",
            summary=(
                f"On Time. {actual_buffer // 60}h{actual_buffer % 60:02d}m buffer "
                f"before '{leg.get('title','meeting')}'."
            ),
            severity="ok",
        )
    if actual_buffer >= required_buffer:
        return LegImpact(
            leg_id=leg["leg_id"],
            leg_type="meeting",
            summary=(
                f"On Time (Tight). {actual_buffer} min buffer before "
                f"'{leg.get('title','meeting')}' — must head straight there."
            ),
            severity="tight",
        )
    if actual_buffer > 0:
        return LegImpact(
            leg_id=leg["leg_id"],
            leg_type="meeting",
            summary=(
                f"Critical Risk. Only {actual_buffer} min before "
                f"'{leg.get('title','meeting')}' (importance: {importance}). "
                f"Any slip means missing the meeting."
            ),
            severity="broken" if importance == "high" else "tight",
        )
    return LegImpact(
        leg_id=leg["leg_id"],
        leg_type="meeting",
        summary=(
            f"Meeting '{leg.get('title','meeting')}' "
            f"({importance}) cannot be attended — arrival is after the start."
        ),
        severity="broken",
    )


# ---------------------------------------------------------------------------
# Top-level cascade calculation
# ---------------------------------------------------------------------------


def calculate_cascade(
    trip: dict[str, Any],
    affected_leg_id: str,
    replacement_flight: dict[str, Any],
) -> CascadeReport:
    """
    Compute the downstream impact of replacing one flight leg with another.

    Args:
        trip: Full trip document as stored in MongoDB.
        affected_leg_id: The leg being replaced (must be a flight leg).
        replacement_flight: A normalized flight option dict, expected to carry
            at least: airline, flight_number, departure_at_iso, arrival_at_iso,
            destination. (See flight_search.search_flights output, augmented
            with explicit ISO timestamps by the caller.)

    Returns:
        CascadeReport with per-leg impacts and an overall severity.
    """
    affected_leg = next(
        (l for l in trip.get("legs", []) if l.get("leg_id") == affected_leg_id),
        None,
    )
    if affected_leg is None:
        raise ValueError(f"Trip has no leg with id {affected_leg_id!r}")
    if affected_leg.get("type") != "flight":
        raise ValueError(f"Leg {affected_leg_id} is not a flight, cannot cascade")

    new_arrival_iso = replacement_flight["arrival_at_iso"]
    arrival_delta = _minutes_between(affected_leg["end_at"], new_arrival_iso)

    new_destination = replacement_flight.get("destination", affected_leg["destination"])

    impacts: list[LegImpact] = []
    warnings: list[str] = []

    affected_index = next(
        i for i, l in enumerate(trip["legs"]) if l.get("leg_id") == affected_leg_id
    )

    for leg in trip["legs"][affected_index + 1 :]:
        ltype = leg.get("type")
        if ltype == "flight":
            # Only treat it as a connection if origin matches new destination
            if leg.get("origin") == new_destination:
                impacts.append(_impact_for_flight_connection(leg, new_arrival_iso))
            else:
                # Different segment of the trip, shift it
                impacts.append(_impact_for_transport_like_flight(leg, arrival_delta))
        elif ltype == "hotel":
            impacts.append(_impact_for_hotel(leg, arrival_delta))
        elif ltype == "transport":
            impacts.append(_impact_for_transport(leg, arrival_delta))
        elif ltype == "meeting":
            impacts.append(_impact_for_meeting(leg, new_arrival_iso))

    # Special warning if the replacement arrives at a different airport
    if new_destination != affected_leg.get("destination"):
        warnings.append(
            f"Replacement arrives at {new_destination} instead of "
            f"{affected_leg.get('destination')} — ground transport may need to change."
        )

    overall_severity = _max_severity([imp.severity for imp in impacts])
    feasible = overall_severity != "broken"

    summary = (
        f"{replacement_flight.get('airline','')} "
        f"{replacement_flight.get('flight_number','')} "
        f"{replacement_flight.get('origin','')} → {new_destination}"
    ).strip()

    return CascadeReport(
        affected_leg_id=affected_leg_id,
        replacement_summary=summary,
        arrival_delta_minutes=arrival_delta,
        overall_severity=overall_severity,
        feasible=feasible,
        impacts=impacts,
        warnings=warnings,
    )


def _impact_for_transport_like_flight(leg: dict, arrival_delta_minutes: int) -> LegImpact:
    """A later flight in the trip that isn't a direct connection."""
    label = _flight_label(leg)
    if arrival_delta_minutes <= 0:
        return LegImpact(
            leg_id=leg["leg_id"],
            leg_type="flight",
            summary=f"Downstream flight {label} unaffected.",
            severity="ok",
        )
    return LegImpact(
        leg_id=leg["leg_id"],
        leg_type="flight",
        summary=f"Downstream flight {label} may need review — arrival shifted by {arrival_delta_minutes} minutes.",
        severity="tight",
    )


# ---------------------------------------------------------------------------
# Pretty printing for the CLI / agent text output
# ---------------------------------------------------------------------------


def format_report(report: CascadeReport) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append(f"Cascade preview — replacement: {report.replacement_summary}")
    lines.append(
        f"Arrival delta: {report.arrival_delta_minutes:+d} min   |   "
        f"Overall: {report.overall_severity.upper()}   |   "
        f"Feasible: {report.feasible}"
    )
    lines.append("=" * 60)
    for imp in report.impacts:
        lines.append(f"  [{imp.severity.upper():>7}] {imp.leg_type:<9} {imp.leg_id}  ::  {imp.summary}")
    if report.warnings:
        lines.append("")
        lines.append("Warnings:")
        for w in report.warnings:
            lines.append(f"  ! {w}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI quick test
# ---------------------------------------------------------------------------


def _demo_main() -> None:
    """
    Quick CLI test: assumes you've seeded trip_001, then simulates a candidate
    replacement for leg_002 (Dubai → Singapore) arriving 2h later.
    """
    from mongo_helpers import get_trip

    trip = get_trip("trip_001")
    if trip is None:
        print("Run `python seed_trip.py` first.")
        return

    # Candidate: arrives 2h later than the original leg_002 end_at
    original_leg2 = next(l for l in trip["legs"] if l["leg_id"] == "leg_002")
    later_arrival = _to_iso(_parse(original_leg2["end_at"]) + timedelta(hours=2))

    replacement = {
        "airline": "Singapore Airlines",
        "flight_number": "SQ495",
        "origin": "DXB",
        "destination": "SIN",
        "departure_at_iso": _to_iso(_parse(original_leg2["start_at"]) + timedelta(hours=2)),
        "arrival_at_iso": later_arrival,
        "price_usd": 720,
    }

    report = calculate_cascade(trip, "leg_002", replacement)
    print(format_report(report))


if __name__ == "__main__":
    _demo_main()
