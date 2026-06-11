"""
SkySaver AI — iCalendar (.ics) export.

Generates a standards-compliant .ics file from a trip document so the user can
import their itinerary into Google Calendar, Apple Calendar, Outlook, or any
other calendar app — no OAuth dance required.

Each leg becomes a single VEVENT. Hotels become an all-day-ish block from
check-in to check-out. Meetings carry attendees as ATTENDEE properties.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


_PRODID = "-//SkySaver AI//Travel Itinerary//EN"


def _ics_datetime(iso_string: str) -> str:
    """Convert an ISO 8601 UTC timestamp into ICS basic-format UTC: 20260606T100000Z."""
    dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
    return dt.strftime("%Y%m%dT%H%M%SZ")


def _escape(text: str) -> str:
    """Escape ICS reserved characters."""
    if text is None:
        return ""
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def _leg_event(trip_id: str, leg: dict[str, Any]) -> list[str]:
    """Render a single leg as an ICS VEVENT block (list of lines)."""
    ltype = leg.get("type")
    leg_id = leg.get("leg_id", "")
    uid = f"{trip_id}-{leg_id}@skysaver.ai"
    dt_stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    if ltype == "flight":
        summary = f"Flight {leg.get('flight_number','')} {leg.get('origin','')} -> {leg.get('destination','')}".strip()
        description_lines = [
            f"Airline: {leg.get('airline','')}",
            f"Flight: {leg.get('flight_number','')}",
            f"From: {leg.get('origin','')} (Terminal {leg.get('departure_terminal','?')})",
            f"To: {leg.get('destination','')} (Terminal {leg.get('arrival_terminal','?')})",
            f"Price: ${leg.get('price_usd','?')}",
            f"Booking ref: {leg.get('booking_reference','')}",
            f"Notes: {leg.get('notes','')}",
        ]
        location = f"{leg.get('origin','?')} Airport"
    elif ltype == "hotel":
        summary = f"Hotel: {leg.get('name','')}"
        description_lines = [
            f"Hotel: {leg.get('name','')}",
            f"Address: {leg.get('address','')}",
            f"Total: ${leg.get('total_usd','?')}",
            f"Confirmation: {leg.get('confirmation_code','')}",
            f"Notes: {leg.get('notes','')}",
        ]
        location = leg.get("address") or leg.get("city", "")
    elif ltype == "transport":
        summary = f"{leg.get('mode','Transport').title()}: {leg.get('from','')} -> {leg.get('to','')}"
        description_lines = [
            f"Mode: {leg.get('mode','')}",
            f"From: {leg.get('from','')}",
            f"To: {leg.get('to','')}",
            f"Estimated cost: ${leg.get('estimated_cost_usd','?')}",
            f"Notes: {leg.get('notes','')}",
        ]
        location = leg.get("from", "")
    elif ltype == "meeting":
        summary = f"Meeting: {leg.get('title','')}"
        description_lines = [
            f"Title: {leg.get('title','')}",
            f"Importance: {leg.get('importance','')}",
            f"Attendees: {', '.join(leg.get('attendees', []))}",
            f"Notes: {leg.get('notes','')}",
        ]
        location = leg.get("location", "")
    else:
        summary = f"Itinerary item {leg_id}"
        description_lines = []
        location = ""

    description = "\\n".join(_escape(line) for line in description_lines)

    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{dt_stamp}",
        f"DTSTART:{_ics_datetime(leg['start_at'])}",
        f"DTEND:{_ics_datetime(leg['end_at'])}",
        f"SUMMARY:{_escape(summary)}",
        f"LOCATION:{_escape(location)}",
        f"DESCRIPTION:{description}",
    ]

    if ltype == "meeting":
        for email in leg.get("attendees", []):
            lines.append(f"ATTENDEE;CN={_escape(email)};RSVP=FALSE:mailto:{email}")

    lines.append("END:VEVENT")
    return lines


def trip_to_ics(trip: dict[str, Any]) -> str:
    """Render a full trip as an iCalendar string."""
    head = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{_PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(trip.get('title','Trip'))}",
    ]
    body: list[str] = []
    for leg in trip.get("legs", []):
        body.extend(_leg_event(trip["_id"], leg))
    tail = ["END:VCALENDAR"]
    # ICS spec: lines should be CRLF-terminated.
    return "\r\n".join(head + body + tail) + "\r\n"
