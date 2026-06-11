"""
SkySaver AI — the agent orchestrator.

Wires Gemini (via Vertex AI) to the three core capability modules we've already
built — MongoDB helpers, flight search, and cascade calculation — exposes them
as tools, and lets the model plan and execute multi-step travel-recovery flows.

This file purposefully keeps the tools as plain Python functions because the
`google-genai` SDK can introspect them and auto-execute them when Gemini
decides to call a tool. That keeps the orchestration code small.

Usage:
    python agent.py

Then chat naturally:
    > What does my trip look like?
    > Are there any disruptions on trip_001?
    > Find me alternatives for the cancelled flight.
    > Show me the cascade impact of option 1.
    > Book option 1.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

from cascade import calculate_cascade, format_report
from flight_search import search_flights
from mongo_helpers import (
    find_leg,
    get_trip,
    list_trips,
    log_disruption,
    update_leg,
)


load_dotenv()


MODEL_NAME = "gemini-2.5-flash"

# Set to True for verbose tool logging.
DEBUG_TOOLS = True


def _log_tool(name: str, args: dict, result: Any | None = None, exc: Exception | None = None) -> None:
    """Print a tool call/result/error line to stderr so it isn't buffered or
    swallowed by the Gemini SDK's auto-function-calling loop."""
    if not DEBUG_TOOLS:
        return
    print(f"\n[tool] {name}  args={args}", file=sys.stderr, flush=True)
    if exc is not None:
        print(f"[tool:{name}:ERROR] {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        return
    if result is not None:
        preview = json.dumps(result, default=str)[:300]
        print(f"[tool:{name}:ok] {preview}{'…' if len(preview) == 300 else ''}", file=sys.stderr, flush=True)


SYSTEM_INSTRUCTION = """\
You are SkySaver AI — an autonomous travel recovery agent. Your job is to
manage trips end-to-end and intelligently handle disruptions like cancelled
flights, delays, gate changes, and missed connections.

Tools available to you:
  - tool_list_trips() : list all trips
  - tool_get_trip(trip_id) : fetch a trip from MongoDB
  - tool_check_disruptions(trip_id) : return any disrupted/cancelled legs
  - tool_search_alternatives(origin, destination, date) : real flight options
  - tool_preview_cascade(trip_id, affected_leg_id, replacement) : show how a
    candidate flight ripples through the rest of the trip
  - tool_apply_cascade(trip_id, affected_leg_id, replacement) : update the trip
    in MongoDB with the new flight and downstream changes (use after user
    confirms)

Behavior rules:
  1. Always read the latest trip from MongoDB before answering about it.
  2. When a disruption is detected, immediately search alternatives.
  3. Present the top 3 options ranked by the user's stored preferences
     (budget_sensitivity, prefers_direct, preferred_airlines,
     preferred_arrival_window, max_layover_hours). Show the cascade impact
     for each.
  4. NEVER book, send messages, or commit changes without explicit user
     confirmation. State the action you are about to take, then wait for
     a clear yes.
  5. Be concise. Lead with the recommendation, then the reasoning. No filler.
  6. If a tool returns no results or fails, say so and propose a next step.

Tone: calm, efficient, decisive. You're a senior travel operations manager who
happens to be an AI — not a chatbot.
"""


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------


def _parse(iso_string: str) -> datetime:
    return datetime.fromisoformat(iso_string.replace("Z", "+00:00"))


def _to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Tools exposed to Gemini
#
# Each tool is a plain Python function with type hints and a short docstring.
# The SDK passes the docstring + signature to Gemini so it knows when to call.
# ---------------------------------------------------------------------------


def _clean(obj: Any) -> Any:
    """Recursively coerce a MongoDB document into JSON-safe primitives.

    Gemini's tool-call serialization is strict — datetimes, Decimal128 values,
    and BSON types all need to become plain strings or numbers.
    """
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


def tool_list_trips() -> dict:
    """List all trips currently stored in MongoDB."""
    try:
        trips = list_trips()
        result = _clean({
            "count": len(trips),
            "trips": [
                {"_id": t["_id"], "title": t.get("title"), "status": t.get("status")}
                for t in trips
            ],
        })
        _log_tool("tool_list_trips", {}, result=result)
        return result
    except Exception as exc:  # noqa: BLE001
        _log_tool("tool_list_trips", {}, exc=exc)
        return {"error": f"{type(exc).__name__}: {exc}"}


def tool_get_trip(trip_id: str) -> dict:
    """Fetch a full trip document from MongoDB.

    Args:
      trip_id: The string ID of the trip (e.g., 'trip_001').
    """
    try:
        trip = get_trip(trip_id)
        if trip is None:
            result = {"error": f"No trip with id {trip_id!r}"}
        else:
            result = _clean(trip)
        _log_tool("tool_get_trip", {"trip_id": trip_id}, result=result)
        return result
    except Exception as exc:  # noqa: BLE001
        _log_tool("tool_get_trip", {"trip_id": trip_id}, exc=exc)
        return {"error": f"{type(exc).__name__}: {exc}"}


def tool_check_disruptions(trip_id: str) -> dict:
    """Check a trip for any legs whose status indicates a disruption.

    Returns the disrupted legs and the trip's disruption history.

    Args:
      trip_id: The string ID of the trip.
    """
    try:
        trip = get_trip(trip_id)
        if trip is None:
            result = {"error": f"No trip with id {trip_id!r}"}
        else:
            disrupted = [
                l for l in trip.get("legs", [])
                if l.get("status") in {"disrupted", "cancelled"}
            ]
            result = _clean({
                "trip_id": trip_id,
                "disrupted_count": len(disrupted),
                "disrupted_legs": disrupted,
                "disruption_history": trip.get("disruption_history", []),
            })
        _log_tool("tool_check_disruptions", {"trip_id": trip_id}, result=result)
        return result
    except Exception as exc:  # noqa: BLE001
        _log_tool("tool_check_disruptions", {"trip_id": trip_id}, exc=exc)
        return {"error": f"{type(exc).__name__}: {exc}"}


def tool_search_alternatives(origin: str, destination: str, date: str) -> dict:
    """Search for real flight alternatives via Google Flights (SerpAPI).

    Args:
      origin: IATA airport code, e.g., 'DXB'.
      destination: IATA airport code, e.g., 'SIN'.
      date: Outbound date in YYYY-MM-DD format.

    Returns the top 8 normalized options as a list of dicts.
    """
    args = {"origin": origin, "destination": destination, "date": date}
    try:
        options = search_flights(origin, destination, date)
        # Strip the verbose 'raw' SerpAPI payload before returning to the model.
        slim = [{k: v for k, v in opt.items() if k != "raw"} for opt in options[:8]]
        result = _clean({
            "origin": origin,
            "destination": destination,
            "date": date,
            "count": len(options),
            "options": slim,
        })
        _log_tool("tool_search_alternatives", args, result=result)
        return result
    except Exception as exc:  # noqa: BLE001
        _log_tool("tool_search_alternatives", args, exc=exc)
        return {"error": f"{type(exc).__name__}: {exc}"}


def tool_preview_cascade(
    trip_id: str,
    affected_leg_id: str,
    replacement_airline: str,
    replacement_flight_number: str,
    replacement_origin: str,
    replacement_destination: str,
    replacement_departure_iso: str,
    replacement_arrival_iso: str,
    replacement_price_usd: float,
) -> dict:
    """Compute how a candidate replacement flight cascades through the trip.

    Args:
      trip_id: The trip being recovered.
      affected_leg_id: The leg being replaced.
      replacement_*: The candidate flight's details. ISO timestamps must be in
        UTC and end with 'Z'.

    Returns a structured cascade report (per-leg impact + overall severity).
    """
    trip = get_trip(trip_id)
    if trip is None:
        return {"error": f"No trip with id {trip_id!r}"}

    replacement = {
        "airline": replacement_airline,
        "flight_number": replacement_flight_number,
        "origin": replacement_origin,
        "destination": replacement_destination,
        "departure_at_iso": replacement_departure_iso,
        "arrival_at_iso": replacement_arrival_iso,
        "price_usd": replacement_price_usd,
    }
    args = {"trip_id": trip_id, "affected_leg_id": affected_leg_id, **replacement}
    try:
        report = calculate_cascade(trip, affected_leg_id, replacement)
        result = _clean(report.to_dict())
        _log_tool("tool_preview_cascade", args, result=result)
        return result
    except Exception as exc:  # noqa: BLE001
        _log_tool("tool_preview_cascade", args, exc=exc)
        return {"error": f"{type(exc).__name__}: {exc}"}


def tool_apply_cascade(
    trip_id: str,
    affected_leg_id: str,
    replacement_airline: str,
    replacement_flight_number: str,
    replacement_origin: str,
    replacement_destination: str,
    replacement_departure_iso: str,
    replacement_arrival_iso: str,
    replacement_price_usd: float,
    booking_reference: str = "MOCK-BOOKED",
    booking_method: str = "mock",
) -> dict:
    """Apply a chosen replacement flight: update the affected leg, shift
    downstream legs per the cascade report, and log the disruption recovery.

    Only call this AFTER the user has explicitly confirmed.

    Args:
      trip_id: The trip being recovered.
      affected_leg_id: The flight leg being replaced.
      replacement_*: Replacement flight details (same as preview_cascade).
      booking_reference: External booking ref (mock string for now).
      booking_method: 'duffel_sandbox' | 'deep_link' | 'mock'.

    Returns a dict describing the changes that were applied.
    """
    args = {
        "trip_id": trip_id,
        "affected_leg_id": affected_leg_id,
        "replacement_flight_number": replacement_flight_number,
    }
    try:
        trip = get_trip(trip_id)
        if trip is None:
            return {"error": f"No trip with id {trip_id!r}"}

        replacement = {
            "airline": replacement_airline,
            "flight_number": replacement_flight_number,
            "origin": replacement_origin,
            "destination": replacement_destination,
            "departure_at_iso": replacement_departure_iso,
            "arrival_at_iso": replacement_arrival_iso,
            "price_usd": replacement_price_usd,
        }
        report = calculate_cascade(trip, affected_leg_id, replacement)

        # Replace the affected leg's flight details
        update_leg(
            trip_id,
            affected_leg_id,
            {
                "airline": replacement_airline,
                "flight_number": replacement_flight_number,
                "origin": replacement_origin,
                "destination": replacement_destination,
                "start_at": replacement_departure_iso,
                "end_at": replacement_arrival_iso,
                "price_usd": replacement_price_usd,
                "status": "rebooked",
                "booking_reference": booking_reference,
                "booking_method": booking_method,
            },
        )

        # Apply each downstream proposed change
        applied_changes: list[dict[str, Any]] = []
        for imp in report.impacts:
            if not imp.proposed_changes:
                continue
            change_dict = {c["field"]: c["to"] for c in imp.proposed_changes}
            if update_leg(trip_id, imp.leg_id, change_dict):
                applied_changes.append({
                    "leg_id": imp.leg_id,
                    "changes": imp.proposed_changes,
                })

        # Log a recovery record
        log_disruption(
            trip_id,
            {
                "disruption_id": f"rec_{affected_leg_id}",
                "affected_leg_id": affected_leg_id,
                "disruption_type": "recovered",
                "details": (
                    f"Replaced with {replacement_airline}{replacement_flight_number} "
                    f"{replacement_origin} → {replacement_destination}."
                ),
                "chosen_alternative": report.replacement_summary,
                "user_confirmed_at": _to_iso(datetime.now(timezone.utc)),
                "booking_method": booking_method,
                "new_booking_reference": booking_reference,
                "cascade_changes": [
                    c for imp in report.impacts for c in imp.proposed_changes
                ],
            },
        )

        result = _clean({
            "status": "applied",
            "trip_id": trip_id,
            "replaced_leg": affected_leg_id,
            "new_flight": f"{replacement_airline}{replacement_flight_number}",
            "downstream_changes_applied": applied_changes,
            "booking_reference": booking_reference,
            "booking_method": booking_method,
        })
        _log_tool("tool_apply_cascade", args, result=result)
        return result
    except Exception as exc:  # noqa: BLE001
        _log_tool("tool_apply_cascade", args, exc=exc)
        return {"error": f"{type(exc).__name__}: {exc}"}


ALL_TOOLS = [
    tool_list_trips,
    tool_get_trip,
    tool_check_disruptions,
    tool_search_alternatives,
    tool_preview_cascade,
    tool_apply_cascade,
]


# ---------------------------------------------------------------------------
# Agent runtime
# ---------------------------------------------------------------------------


def build_client() -> genai.Client:
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    if not project:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT not set in .env")
    return genai.Client(vertexai=True, project=project, location=location)


def run_chat() -> None:
    """Interactive CLI loop. Type messages, get agent responses."""
    client = build_client()

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        tools=ALL_TOOLS,
        temperature=0.3,
    )

    chat = client.chats.create(model=MODEL_NAME, config=config)

    print("=" * 60)
    print("SkySaver AI — agent ready. Type a message, Ctrl-C to exit.")
    print("Tip: start with 'show me my trip' or 'check trip_001 for disruptions'")
    print("=" * 60)

    while True:
        try:
            user_input = input("\nyou > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[exiting]")
            break
        if not user_input:
            continue

        try:
            response = chat.send_message(user_input)
        except Exception as exc:  # noqa: BLE001 — we want to keep the loop alive
            print(f"\n[error] {exc}")
            continue

        # Dump the raw response so we can see if the model tried to call tools
        if DEBUG_TOOLS:
            try:
                cand = response.candidates[0] if response.candidates else None
                if cand and cand.content and cand.content.parts:
                    for i, part in enumerate(cand.content.parts):
                        if getattr(part, "function_call", None):
                            fc = part.function_call
                            print(
                                f"[gemini:function_call] name={fc.name}  args={dict(fc.args) if fc.args else {}}",
                                file=sys.stderr,
                                flush=True,
                            )
                        if getattr(part, "function_response", None):
                            print(
                                f"[gemini:function_response] {str(part.function_response)[:200]}",
                                file=sys.stderr,
                                flush=True,
                            )
            except Exception:
                pass

        text = (response.text or "").strip()
        if text:
            print(f"\nSkySaver > {text}")
        else:
            print("\nSkySaver > [no text response — likely a tool was called silently]")


if __name__ == "__main__":
    run_chat()
