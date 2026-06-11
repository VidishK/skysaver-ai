"""
SkySaver AI — chat assistant.

A lightweight Gemini wrapper that answers user questions about their trip
and can generate deep links to booking pages (airline, Uber, hotels) so the
user can complete actions in one click.

This is intentionally separate from `agent.py`. The agent file is the
full tool-calling agent; this is the lighter "chat side panel" that
sits next to the dashboard.
"""

from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()


MODEL_NAME = "gemini-2.5-flash"


SYSTEM_PROMPT = """\
You are SkySaver's chat assistant — a calm, decisive travel concierge.

The user has an active trip and you can see the full itinerary, preferences,
and any recent disruptions. Your job is to:

  1. Answer questions about the trip clearly and concisely.
  2. Suggest concrete next actions when relevant.
  3. When the user asks to book, pay, or change something, give them a
     working external link using a markdown link like:
         [Open Emirates check-in](https://www.emirates.com/manage-booking)
         [Order an Uber to Marina Bay Sands](https://m.uber.com/ul/?action=setPickup)
         [Open Google Flights for DXB → SIN](https://www.google.com/flights?hl=en#flt=DXB.SIN)
  4. Don't pretend to perform irreversible actions. If they say "book it",
     respond with the booking link and confirm they need to complete payment
     on the airline's site.

Formatting rules (strict):
  - Keep replies under 3 short sentences unless the user explicitly asks for
    more detail.
  - Use bullet points sparingly. Never more than 4 bullets.
  - You may use **bold** for emphasis, but never use headings, horizontal
    rules, or markdown tables.
  - Do not start responses with "Sure" / "Of course" / "Certainly".
  - Do not repeat the user's question back to them.

Tone: warm, brisk, like a smart hotel concierge.
"""


def _build_client() -> genai.Client:
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    if not project:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT not set in .env")
    return genai.Client(vertexai=True, project=project, location=location)


def fetch_trip_via_mcp(trip_id: str) -> dict[str, Any] | None:
    """Fetch a trip through the MongoDB MCP server (hackathon partner integration).

    This is the official path the agent uses to read trip data: it does not
    speak pymongo directly — it speaks the Model Context Protocol to the
    MongoDB MCP server, which then queries Atlas. If the MCP bridge is
    unavailable (Node.js missing, server crashed, etc.) we fall back to pymongo
    so the UI keeps working during development.
    """
    try:
        from mcp_bridge import mcp_find_one  # type: ignore[import-not-found]
        result = mcp_find_one("trips", {"_id": trip_id})
        if isinstance(result, dict):
            return result
        return None
    except Exception:
        # Fallback for local dev when MCP isn't running
        from mongo_helpers import get_trip
        return get_trip(trip_id)


def summarize_trip(trip: dict[str, Any] | None) -> str:
    """Compact text summary of the trip for the chatbot's context."""
    if trip is None:
        return "No active trip."
    lines = [f"Trip: {trip.get('title','')} (id {trip.get('_id','')})"]
    prefs = trip.get("preferences", {})
    if prefs:
        lines.append(
            "Preferences — direct: {direct}, airlines: {airlines}, "
            "budget: {budget}, arrival: {arrival}".format(
                direct=prefs.get("prefers_direct"),
                airlines=", ".join(prefs.get("preferred_airlines", [])),
                budget=prefs.get("budget_sensitivity"),
                arrival=prefs.get("preferred_arrival_window"),
            )
        )
    lines.append("Legs:")
    for leg in trip.get("legs", []):
        if leg["type"] == "flight":
            lines.append(
                f"  - FLIGHT {leg.get('airline','')}{leg.get('flight_number','')} "
                f"{leg.get('origin','')} → {leg.get('destination','')} "
                f"({leg.get('start_at','')} → {leg.get('end_at','')}) "
                f"status={leg.get('status','')}  ${leg.get('price_usd','')}"
            )
        elif leg["type"] == "hotel":
            lines.append(
                f"  - HOTEL {leg.get('name','')}, {leg.get('city','')} "
                f"check-in {leg.get('start_at','')} → check-out {leg.get('end_at','')}"
            )
        elif leg["type"] == "transport":
            lines.append(
                f"  - {leg.get('mode','TRANSPORT').upper()} "
                f"{leg.get('from','')} → {leg.get('to','')} at {leg.get('start_at','')}"
            )
        elif leg["type"] == "meeting":
            lines.append(
                f"  - MEETING {leg.get('title','')} at {leg.get('location','')} "
                f"({leg.get('start_at','')})  importance={leg.get('importance','')}"
            )
    history = trip.get("disruption_history", [])
    if history:
        lines.append("Recent disruptions:")
        for ev in history[-3:]:
            lines.append(f"  - {ev.get('disruption_type','')}: {ev.get('details','')}")
    return "\n".join(lines)


def ask_chatbot(
    user_message: str,
    chat_history: list[dict[str, str]],
    trip: dict[str, Any] | None,
) -> str:
    """Send one user message and return the assistant's reply.

    chat_history is a list of {"role": "user"|"assistant", "content": "..."}
    items, NOT including the new user_message.

    Trip data is re-fetched through the MongoDB MCP server on every turn so
    the agent always reads the freshest state through the official partner
    integration. The caller's `trip` argument is used as the trip-id source
    (and as a fallback if MCP is unreachable).
    """
    client = _build_client()

    # Re-fetch via MCP so the agent's data path is the partner integration.
    refreshed_trip = trip
    if trip and trip.get("_id"):
        try:
            mcp_trip = fetch_trip_via_mcp(trip["_id"])
            if mcp_trip:
                refreshed_trip = mcp_trip
        except Exception:
            # If MCP fails mid-conversation, keep going with the caller's copy.
            pass

    trip_context = summarize_trip(refreshed_trip)
    system = f"{SYSTEM_PROMPT}\n\n--- Current trip context (fetched via MongoDB MCP server) ---\n{trip_context}"

    contents = []
    for msg in chat_history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
    contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.4,
        ),
    )
    return (response.text or "").strip()
