"""
SkySaver AI — FastAPI backend.

Serves:
  - /api/*  → JSON endpoints (auth, trips, search, cascade, chat, OCR…)
  - /       → the React frontend in `frontend/` (static files)

Run locally:
    uvicorn api:app --reload --port 8000

Production (Cloud Run):
    uvicorn api:app --host 0.0.0.0 --port ${PORT:-8080}

Architecture
------------
This is a thin HTTP wrapper around our existing Python modules. Every endpoint
delegates to a domain module (`mongo_helpers`, `chatbot`, `flight_search`,
`cascade`, `confirmation_scanner`, `mcp_bridge`). Nothing meaningful lives in
this file — it's just the public API surface.
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import (
    Cookie,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Response,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field

from cascade import calculate_cascade
from chatbot import ask_chatbot
from confirmation_scanner import scan_confirmation
from deep_links import (
    airline_booking_link,
    google_flights_link,
    hotel_search_link,
    uber_link,
)
from flight_search import search_flights
from ics_export import trip_to_ics
from mongo_helpers import (
    add_leg,
    authenticate_user,
    create_session_token,
    create_user,
    delete_leg,
    delete_session_token,
    get_trip,
    list_trips,
    list_users,
    log_disruption,
    lookup_session_token,
    next_leg_id,
    save_trip,
    update_leg,
)
from seed_trip import build_demo_trip

load_dotenv()


FRONTEND_DIR = Path(__file__).parent / "frontend"
SESSION_COOKIE = "skysaver_session"


app = FastAPI(title="SkySaver AI", version="1.0.0")


# ---------------------------------------------------------------------------
# CORS — relaxed for local dev, tight for prod
# ---------------------------------------------------------------------------

ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://localhost:8080",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8080",
]
if os.getenv("CORS_EXTRA_ORIGIN"):
    ALLOWED_ORIGINS.append(os.getenv("CORS_EXTRA_ORIGIN"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------


def current_user(skysaver_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict[str, Any]:
    if not skysaver_session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = lookup_session_token(skysaver_session)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid session")
    return user


def optional_user(skysaver_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict[str, Any] | None:
    if not skysaver_session:
        return None
    return lookup_session_token(skysaver_session)


def _trip_id_for(user: dict) -> str:
    """One trip per user. Hackathon scope."""
    email = (user.get("email") or "").strip().lower()
    if not email:
        return "trip_anon"
    safe = email.replace("@", "_at_").replace(".", "_")
    return f"trip_{safe}"


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=False,  # set True in production HTTPS
        samesite="lax",
        max_age=30 * 24 * 3600,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class SignupRequest(BaseModel):
    name: str = Field(..., min_length=1)
    email: EmailStr
    password: str = Field(..., min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ChatRequest(BaseModel):
    message: str
    history: list[dict[str, str]] = []


class CascadeRequest(BaseModel):
    affected_leg_id: str
    replacement: dict[str, Any]


class CreateTripRequest(BaseModel):
    title: str
    intake: dict[str, Any]


class LegPatchRequest(BaseModel):
    changes: dict[str, Any]


class AddLegRequest(BaseModel):
    leg: dict[str, Any]


# ---------------------------------------------------------------------------
# Health + meta
# ---------------------------------------------------------------------------


@app.get("/api/health")
def healthcheck() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "skysaver-ai-api",
        "version": "1.0.0",
        "now": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@app.post("/api/auth/signup")
def signup(payload: SignupRequest) -> Response:
    user = create_user(payload.name, payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=409, detail="An account with that email already exists.")
    token = create_session_token(user["email"])
    response = JSONResponse({"ok": True, "user": _public_user(user)})
    _set_session_cookie(response, token)
    return response


@app.post("/api/auth/login")
def login(payload: LoginRequest) -> Response:
    user = authenticate_user(payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    token = create_session_token(user["email"])
    response = JSONResponse({"ok": True, "user": _public_user(user)})
    _set_session_cookie(response, token)
    return response


@app.post("/api/auth/logout")
def logout(skysaver_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> Response:
    if skysaver_session:
        delete_session_token(skysaver_session)
    response = JSONResponse({"ok": True})
    _clear_session_cookie(response)
    return response


@app.get("/api/me")
def me(user=Depends(current_user)) -> dict[str, Any]:
    return {"ok": True, "user": _public_user(user)}


def _public_user(user: dict) -> dict:
    """Strip anything we never want sent to the browser."""
    return {
        "name": user.get("name"),
        "email": user.get("email"),
        "initials": _initials(user.get("name", "")),
        "plan": "Pro",
        "created_at": user.get("created_at"),
        "last_login_at": user.get("last_login_at"),
        "login_count": user.get("login_count"),
    }


def _initials(name: str) -> str:
    parts = [p for p in name.strip().split() if p]
    if not parts:
        return "U"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


# ---------------------------------------------------------------------------
# Trip CRUD
# ---------------------------------------------------------------------------


@app.get("/api/trip")
def get_my_trip(user=Depends(current_user)) -> dict[str, Any]:
    trip = get_trip(_trip_id_for(user))
    return {"ok": True, "trip": trip}


@app.post("/api/trip/seed-demo")
def seed_demo(user=Depends(current_user)) -> dict[str, Any]:
    new_trip = build_demo_trip(days_out=7)
    new_trip["_id"] = _trip_id_for(user)
    new_trip["user_id"] = user["email"]
    save_trip(new_trip)
    return {"ok": True, "trip": new_trip}


@app.post("/api/trip")
def create_trip(payload: CreateTripRequest, user=Depends(current_user)) -> dict[str, Any]:
    trip = {
        "_id": _trip_id_for(user),
        "user_id": user["email"],
        "title": payload.title,
        "status": "active",
        "intake": payload.intake,
        "legs": payload.intake.get("legs", []),
        "preferences": payload.intake.get("preferences", {}),
        "disruption_history": [],
    }
    save_trip(trip)
    return {"ok": True, "trip": trip}


@app.delete("/api/trip")
def delete_my_trip(user=Depends(current_user)) -> dict[str, Any]:
    """Wipe the user's trip entirely so they get a fresh empty dashboard."""
    from mongo_helpers import get_trips_collection
    get_trips_collection().delete_one({"_id": _trip_id_for(user)})
    return {"ok": True}


# ---- Legs ----


@app.post("/api/trip/legs")
def post_leg(payload: AddLegRequest, user=Depends(current_user)) -> dict[str, Any]:
    trip = get_trip(_trip_id_for(user)) or {}
    leg = payload.leg
    leg.setdefault("leg_id", next_leg_id(trip))
    add_leg(_trip_id_for(user), leg)
    return {"ok": True, "leg_id": leg["leg_id"]}


@app.patch("/api/trip/legs/{leg_id}")
def patch_leg(leg_id: str, payload: LegPatchRequest, user=Depends(current_user)) -> dict[str, Any]:
    ok = update_leg(_trip_id_for(user), leg_id, payload.changes)
    return {"ok": ok}


@app.delete("/api/trip/legs/{leg_id}")
def remove_leg(leg_id: str, user=Depends(current_user)) -> dict[str, Any]:
    ok = delete_leg(_trip_id_for(user), leg_id)
    return {"ok": ok}


# ---------------------------------------------------------------------------
# Flight search + cascade
# ---------------------------------------------------------------------------


@app.get("/api/flights/search")
def flights_search(origin: str, destination: str, date: str, user=Depends(current_user)) -> dict[str, Any]:
    options = search_flights(origin, destination, date)
    # Drop heavy 'raw' payloads before serialising
    slim = [{k: v for k, v in opt.items() if k != "raw"} for opt in options[:50]]
    return {"ok": True, "options": slim, "count": len(options)}


@app.post("/api/cascade")
def cascade_preview(payload: CascadeRequest, user=Depends(current_user)) -> dict[str, Any]:
    trip = get_trip(_trip_id_for(user))
    if trip is None:
        raise HTTPException(status_code=404, detail="No trip found.")
    report = calculate_cascade(trip, payload.affected_leg_id, payload.replacement)
    return {"ok": True, "report": report.to_dict()}


# ---------------------------------------------------------------------------
# Disruption simulator (demo trigger)
# ---------------------------------------------------------------------------


@app.post("/api/trip/simulate-cancellation/{leg_id}")
def simulate_cancellation(leg_id: str, user=Depends(current_user)) -> dict[str, Any]:
    trip_id = _trip_id_for(user)
    update_leg(trip_id, leg_id, {"status": "cancelled"})
    ts = int(datetime.now(timezone.utc).timestamp())
    log_disruption(
        trip_id,
        {
            "disruption_id": f"dis_{leg_id}_{ts}",
            "affected_leg_id": leg_id,
            "disruption_type": "cancelled",
            "details": f"Simulated airline cancellation of leg {leg_id}.",
        },
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


@app.post("/api/chat")
def chat(payload: ChatRequest, user=Depends(current_user)) -> dict[str, Any]:
    trip = get_trip(_trip_id_for(user))
    response = ask_chatbot(payload.message, payload.history, trip)
    return {"ok": True, "response": response}


# ---------------------------------------------------------------------------
# Gemini OCR scan
# ---------------------------------------------------------------------------


@app.post("/api/scan-confirmation")
async def scan(file: UploadFile = File(...), user=Depends(current_user)) -> dict[str, Any]:
    data = await file.read()
    extracted = scan_confirmation(data, file.filename or "upload")
    return {"ok": True, "extracted": extracted}


# ---------------------------------------------------------------------------
# Deep link helpers (so the frontend doesn't have to know airline mappings)
# ---------------------------------------------------------------------------


@app.get("/api/deep-link/airline")
def deep_link_airline(airline_code: str = "", origin: str = "", destination: str = "", date: str = "", airline_name: str = "") -> dict[str, Any]:
    return {
        "ok": True,
        "url": airline_booking_link(airline_code, origin, destination, airline_name, date),
    }


@app.get("/api/deep-link/google-flights")
def deep_link_gflights(origin: str, destination: str, date: str | None = None) -> dict[str, Any]:
    return {"ok": True, "url": google_flights_link(origin, destination, date)}


@app.get("/api/deep-link/uber")
def deep_link_uber(pickup: str = "", dropoff: str = "") -> dict[str, Any]:
    return {"ok": True, "url": uber_link(pickup or None, dropoff or None)}


@app.get("/api/deep-link/hotel")
def deep_link_hotel(name: str = "", city: str = "") -> dict[str, Any]:
    return {"ok": True, "url": hotel_search_link(name, city)}


# ---------------------------------------------------------------------------
# Calendar export (.ics)
# ---------------------------------------------------------------------------


@app.get("/api/trip/ics")
def get_ics(user=Depends(current_user)) -> Response:
    trip = get_trip(_trip_id_for(user))
    if trip is None:
        raise HTTPException(status_code=404, detail="No trip found.")
    ics = trip_to_ics(trip)
    return Response(
        content=ics,
        media_type="text/calendar",
        headers={"Content-Disposition": f"attachment; filename=skysaver_{trip['_id']}.ics"},
    )


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------


@app.get("/api/admin/users")
def admin_users(user=Depends(current_user)) -> dict[str, Any]:
    return {"ok": True, "users": list_users()}


@app.get("/api/admin/trips")
def admin_trips(user=Depends(current_user)) -> dict[str, Any]:
    return {"ok": True, "trips": list_trips()}


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------

# Serve the assets folders directly under their canonical paths so the HTML
# files can reference `app/main.jsx`, `styles/tokens.css`, etc.
app.mount("/styles", StaticFiles(directory=str(FRONTEND_DIR / "styles")), name="styles")
app.mount("/app", StaticFiles(directory=str(FRONTEND_DIR / "app")), name="app_assets")
app.mount(
    "/screenshots",
    StaticFiles(directory=str(FRONTEND_DIR / "screenshots")),
    name="screenshots",
)


# Page routes — each maps to an HTML file at the project root.
def _serve_html(name: str) -> FileResponse:
    path = FRONTEND_DIR / name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Page {name} not found")
    return FileResponse(str(path))


@app.get("/")
def page_root() -> FileResponse:
    return _serve_html("index.html")


@app.get("/index.html")
def page_index() -> FileResponse:
    return _serve_html("index.html")


@app.get("/auth.html")
def page_auth() -> FileResponse:
    return _serve_html("auth.html")


@app.get("/login")
@app.get("/signup")
def page_auth_alias() -> FileResponse:
    return _serve_html("auth.html")


@app.get("/app.html")
def page_app(user=Depends(optional_user)) -> Response:
    if user is None:
        return RedirectResponse(url="/auth.html", status_code=302)
    return _serve_html("app.html")


@app.get("/dashboard")
def page_dashboard(user=Depends(optional_user)) -> Response:
    return page_app(user)


@app.get("/plan.html")
def page_plan(user=Depends(optional_user)) -> Response:
    if user is None:
        return RedirectResponse(url="/auth.html", status_code=302)
    return _serve_html("plan.html")


@app.get("/preferences.html")
def page_prefs(user=Depends(optional_user)) -> Response:
    if user is None:
        return RedirectResponse(url="/auth.html", status_code=302)
    return _serve_html("preferences.html")


@app.get("/settings.html")
def page_settings(user=Depends(optional_user)) -> Response:
    if user is None:
        return RedirectResponse(url="/auth.html", status_code=302)
    return _serve_html("settings.html")


@app.get("/trip.html")
def page_trip(user=Depends(optional_user)) -> Response:
    if user is None:
        return RedirectResponse(url="/auth.html", status_code=302)
    return _serve_html("trip.html")


# ---------------------------------------------------------------------------
# Local dev entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)
