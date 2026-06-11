"""
SkySaver AI — MongoDB helpers.

Single source of truth for talking to the trips collection. Every other module
(the agent's tools, the seed script, the cascade calculator) goes through these
helpers so we never write raw queries twice.

Schema details are documented in schema.md.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import certifi
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

load_dotenv()


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

_DB_NAME = "skysaver"
_TRIPS_COLLECTION = "trips"
_USERS_COLLECTION = "users"

_client: MongoClient | None = None


def get_client() -> MongoClient:
    """Return a cached MongoDB client. Lazy-initialised on first call."""
    global _client
    if _client is None:
        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri:
            raise RuntimeError("MONGO_URI is not set in the environment / .env file")
        _client = MongoClient(
            mongo_uri,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=5000,
        )
    return _client


def get_db() -> Database:
    """Return the skysaver database handle."""
    return get_client()[_DB_NAME]


def get_trips_collection() -> Collection:
    """Return the trips collection handle."""
    return get_db()[_TRIPS_COLLECTION]


def ping() -> bool:
    """Verify the connection works. Returns True on success, raises on failure."""
    get_client().admin.command("ping")
    return True


# ---------------------------------------------------------------------------
# Trip-level operations
# ---------------------------------------------------------------------------


def _now() -> str:
    """Current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def save_trip(trip: dict[str, Any]) -> str:
    """
    Upsert a full trip document. Sets created_at/updated_at automatically.
    Returns the trip's _id.
    """
    if "_id" not in trip:
        raise ValueError("Trip must include an _id (e.g., 'trip_001')")

    now = _now()
    trip.setdefault("created_at", now)
    trip["updated_at"] = now

    coll = get_trips_collection()
    coll.replace_one({"_id": trip["_id"]}, trip, upsert=True)
    return trip["_id"]


def get_trip(trip_id: str) -> dict[str, Any] | None:
    """Fetch a trip by ID. Returns None if not found."""
    return get_trips_collection().find_one({"_id": trip_id})


def list_trips(user_id: str | None = None) -> list[dict[str, Any]]:
    """List all trips, optionally filtered by user."""
    query = {"user_id": user_id} if user_id else {}
    return list(get_trips_collection().find(query))


def delete_trip(trip_id: str) -> bool:
    """Delete a trip. Returns True if a document was deleted."""
    result = get_trips_collection().delete_one({"_id": trip_id})
    return result.deleted_count > 0


# ---------------------------------------------------------------------------
# Leg-level operations
# ---------------------------------------------------------------------------


def find_leg(trip: dict[str, Any], leg_id: str) -> dict[str, Any] | None:
    """Return the leg dict from a trip by leg_id, or None."""
    for leg in trip.get("legs", []):
        if leg.get("leg_id") == leg_id:
            return leg
    return None


def update_leg(trip_id: str, leg_id: str, changes: dict[str, Any]) -> bool:
    """
    Apply a partial update to a single leg. `changes` is a flat dict of
    {field: new_value}. Returns True if the leg was found and updated.

    Example:
        update_leg("trip_001", "leg_002", {"start_at": "2026-05-28T14:00:00Z"})
    """
    coll = get_trips_collection()
    set_doc = {f"legs.$.{field}": value for field, value in changes.items()}
    set_doc["updated_at"] = _now()
    result = coll.update_one(
        {"_id": trip_id, "legs.leg_id": leg_id},
        {"$set": set_doc},
    )
    return result.modified_count > 0


def set_leg_status(trip_id: str, leg_id: str, status: str) -> bool:
    """Convenience wrapper to change a leg's status field."""
    return update_leg(trip_id, leg_id, {"status": status})


def add_leg(trip_id: str, leg: dict[str, Any]) -> bool:
    """Append a new leg to a trip. Returns True on success."""
    if "leg_id" not in leg:
        raise ValueError("Leg must include a leg_id")
    coll = get_trips_collection()
    result = coll.update_one(
        {"_id": trip_id},
        {
            "$push": {"legs": leg},
            "$set": {"updated_at": _now()},
        },
    )
    return result.modified_count > 0


def delete_leg(trip_id: str, leg_id: str) -> bool:
    """Remove a leg from a trip by leg_id."""
    coll = get_trips_collection()
    result = coll.update_one(
        {"_id": trip_id},
        {
            "$pull": {"legs": {"leg_id": leg_id}},
            "$set": {"updated_at": _now()},
        },
    )
    return result.modified_count > 0


def next_leg_id(trip: dict[str, Any]) -> str:
    """Generate the next sequential leg_id like 'leg_007' based on existing legs."""
    used: set[int] = set()
    for leg in trip.get("legs", []):
        lid = leg.get("leg_id", "")
        if lid.startswith("leg_"):
            try:
                used.add(int(lid.split("_", 1)[1]))
            except ValueError:
                continue
    n = 1
    while n in used:
        n += 1
    return f"leg_{n:03d}"


# ---------------------------------------------------------------------------
# Disruption logging
# ---------------------------------------------------------------------------


def log_disruption(trip_id: str, disruption: dict[str, Any]) -> bool:
    """
    Append a disruption record to a trip's disruption_history array.
    Auto-fills detected_at if missing. Returns True on success.
    """
    disruption.setdefault("detected_at", _now())
    coll = get_trips_collection()
    result = coll.update_one(
        {"_id": trip_id},
        {
            "$push": {"disruption_history": disruption},
            "$set": {"updated_at": _now()},
        },
    )
    return result.modified_count > 0


# ---------------------------------------------------------------------------
# User accounts
# ---------------------------------------------------------------------------

import hashlib  # noqa: E402  (kept near user code for clarity)


def get_users_collection() -> Collection:
    """Return the users collection handle."""
    return get_db()[_USERS_COLLECTION]


def _hash_password(password: str, salt: str = "skysaver-static-salt-2026") -> str:
    """Hash a password with SHA-256 + a static salt.

    This is deliberately simple for a hackathon demo. Production code should
    use bcrypt/argon2 with a per-user random salt. The hash is one-way — the
    plain password is never stored or recoverable.
    """
    h = hashlib.sha256()
    h.update((salt + password).encode("utf-8"))
    return h.hexdigest()


def create_user(name: str, email: str, password: str) -> dict[str, Any] | None:
    """Create a new user. Returns the user document on success, or None if the
    email is already registered."""
    email = email.strip().lower()
    coll = get_users_collection()
    if coll.find_one({"email": email}):
        return None
    user = {
        "_id": email,
        "name": name.strip(),
        "email": email,
        "password_hash": _hash_password(password),
        "created_at": _now(),
        "last_login_at": _now(),
        "login_count": 1,
    }
    coll.insert_one(user)
    return {k: v for k, v in user.items() if k != "password_hash"}


def authenticate_user(email: str, password: str) -> dict[str, Any] | None:
    """Validate email/password. Returns the safe user document on success.
    Also stamps last_login_at and increments login_count."""
    email = email.strip().lower()
    coll = get_users_collection()
    user = coll.find_one({"email": email})
    if user is None:
        return None
    if user.get("password_hash") != _hash_password(password):
        return None
    coll.update_one(
        {"email": email},
        {
            "$set": {"last_login_at": _now()},
            "$inc": {"login_count": 1},
        },
    )
    user = coll.find_one({"email": email})
    return {k: v for k, v in user.items() if k != "password_hash"}


def list_users() -> list[dict[str, Any]]:
    """Return all users (without password hashes)."""
    return [
        {k: v for k, v in u.items() if k != "password_hash"}
        for u in get_users_collection().find({})
    ]


# ---------------------------------------------------------------------------
# Sessions (persistent login tokens)
# ---------------------------------------------------------------------------

import secrets  # noqa: E402

_SESSIONS_COLLECTION = "sessions"
_SESSION_TTL_DAYS = 30


def get_sessions_collection() -> Collection:
    return get_db()[_SESSIONS_COLLECTION]


def create_session_token(email: str) -> str:
    """Generate a session token for a user, persist it, return it."""
    email = email.strip().lower()
    token = secrets.token_urlsafe(32)
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=_SESSION_TTL_DAYS)
    ).isoformat(timespec="seconds").replace("+00:00", "Z")
    get_sessions_collection().insert_one({
        "_id": token,
        "email": email,
        "created_at": _now(),
        "expires_at": expires_at,
    })
    return token


def lookup_session_token(token: str) -> dict[str, Any] | None:
    """Return the user document for a valid, unexpired session token, else None."""
    if not token:
        return None
    sess = get_sessions_collection().find_one({"_id": token})
    if sess is None:
        return None
    expires_at = sess.get("expires_at", "")
    if expires_at and expires_at < _now():
        # Expired — clean it up.
        get_sessions_collection().delete_one({"_id": token})
        return None
    email = sess.get("email")
    user = get_users_collection().find_one({"email": email})
    if user is None:
        return None
    return {k: v for k, v in user.items() if k != "password_hash"}


def delete_session_token(token: str) -> None:
    """Invalidate a session token (e.g. on sign out)."""
    if token:
        get_sessions_collection().delete_one({"_id": token})


