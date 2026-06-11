"""
SkySaver AI — booking confirmation scanner.

Uses Gemini's multimodal input to read a booking confirmation (PDF, PNG, JPG)
and pull out the structured fields SkySaver needs:
  - confirmation reference (PNR)
  - airline (IATA code if recognisable, plus human name)
  - flight number
  - departure / arrival times
  - price (USD)
  - payment method (if visible)

The user uploads the file from the confirmation dialog after paying on the
airline's site. SkySaver scans it and pre-fills Step 2 — no manual typing.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()


MODEL_NAME = "gemini-2.5-flash"


SCAN_PROMPT = """\
You are a careful travel ops assistant. The attached file is a flight booking
confirmation (PDF, screenshot, or email). Extract the structured booking
details and return them as a single JSON object with these keys:

{
  "confirmation_reference": "PNR or booking code, e.g. 'EK-Z7P2KL'",
  "airline_code": "2-letter IATA code if you can determine it, else null",
  "airline_name": "Full airline name as printed",
  "flight_number": "Flight number, e.g. '308' or 'EK308'",
  "origin": "Origin airport IATA code, e.g. 'DXB'",
  "destination": "Destination airport IATA code, e.g. 'SIN'",
  "departure_at": "ISO 8601 datetime if visible, else null",
  "arrival_at": "ISO 8601 datetime if visible, else null",
  "price_usd": "numeric price in USD if visible, else null",
  "paid_with": "payment method if visible (Card / PayPal / Apple Pay / Google Pay / Other), else null",
  "passenger_name": "passenger name if visible, else null",
  "raw_notes": "anything else important the user might need"
}

Rules:
- Return ONLY the JSON object, no prose, no markdown fences.
- Use null for any field you can't confidently extract.
- For prices in non-USD, convert if you can; otherwise leave as null.
- Booking references are short alphanumeric codes (4-10 chars typically).
"""


def _build_client() -> genai.Client:
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    if not project:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT not set in .env")
    return genai.Client(vertexai=True, project=project, location=location)


def _normalize_mime(filename: str, fallback: str | None = None) -> str:
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        return "application/pdf"
    if name.endswith(".png"):
        return "image/png"
    if name.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if name.endswith(".webp"):
        return "image/webp"
    if name.endswith(".heic"):
        return "image/heic"
    return fallback or "application/octet-stream"


def _strip_fences(text: str) -> str:
    """Some models wrap JSON in ```json ... ``` despite being asked not to."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def scan_confirmation(file_bytes: bytes, filename: str) -> dict[str, Any]:
    """Send the uploaded file to Gemini and return the extracted booking dict.

    On any failure, returns a dict with an 'error' key so the caller can
    display it without crashing.
    """
    if not file_bytes:
        return {"error": "Empty file."}
    mime_type = _normalize_mime(filename)

    client = _build_client()
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[
                types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
                SCAN_PROMPT,
            ],
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
            ),
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Gemini call failed: {exc}"}

    text = (response.text or "").strip()
    if not text:
        return {"error": "Gemini returned an empty response."}

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            return json.loads(_strip_fences(text))
        except json.JSONDecodeError as exc:
            return {"error": f"Couldn't parse the model's response as JSON: {exc}", "raw_text": text[:600]}
