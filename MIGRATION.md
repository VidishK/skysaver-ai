# Migrating from Streamlit to Next.js + FastAPI

This document explains how to swap the Streamlit frontend for a Next.js (or any) frontend without rewriting the business logic.

## TL;DR — the architecture

**Today:**
```
┌─────────────────────────────────────────────────────────┐
│  Streamlit app (app.py)                                 │
│  - UI rendering                                          │
│  - Direct calls to mongo_helpers, chatbot, flight_search│
│  - Direct MongoDB MCP bridge calls                       │
└─────────────────────────────────────────────────────────┘
              ↓ direct Python imports
   mongo_helpers.py · chatbot.py · flight_search.py · cascade.py
   mcp_bridge.py · confirmation_scanner.py · ics_export.py
```

**After migration:**
```
┌──────────────────────┐    HTTPS/JSON     ┌────────────────────────┐
│  Next.js frontend    │ ◄──────────────► │  FastAPI backend       │
│  (React, Tailwind)   │                  │  (api.py)              │
└──────────────────────┘                  └────────────────────────┘
                                                     ↓ Python imports
                                          mongo_helpers · chatbot
                                          flight_search · cascade
                                          mcp_bridge · etc.
```

**The key insight:** every Python module *except* `app.py` is already independent of Streamlit. The business logic is reusable as-is. You only need to wrap it in HTTP endpoints.

---

## What stays, what changes

| File | Status | Notes |
|---|---|---|
| `mongo_helpers.py` | ✅ Stays | Pure DB logic, reused by FastAPI |
| `mcp_bridge.py` | ✅ Stays | MongoDB MCP integration, reused |
| `chatbot.py` | ✅ Stays | Gemini wrapper, reused |
| `flight_search.py` | ✅ Stays | SerpAPI wrapper, reused |
| `cascade.py` | ✅ Stays | Cascade calc, reused |
| `confirmation_scanner.py` | ✅ Stays | Gemini OCR, reused |
| `deep_links.py` | ✅ Stays | URL builders, reused |
| `ics_export.py` | ✅ Stays | Calendar export, reused |
| `airports.py` | ✅ Stays | Airport list, reused |
| `seed_trip.py` | ✅ Stays | Used for demo data, reused |
| `app.py` | ❌ Deleted | Replaced by `api.py` + Next.js frontend |
| `api.py` | 🆕 New | FastAPI server with HTTP endpoints |
| `frontend/` | 🆕 New | Next.js project directory |
| `Dockerfile` | 🛠 Updated | Builds both backend and frontend |

---

## Step 1 — Create the FastAPI layer

Create a new file `api.py` next to `app.py` (keep `app.py` running until you're ready to switch). This file wraps every piece of business logic as an HTTP endpoint.

```python
# api.py
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Cookie
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from typing import Any

from mongo_helpers import (
    authenticate_user, create_user, get_trip, save_trip, update_leg,
    add_leg, delete_leg, log_disruption, list_users, list_trips,
    create_session_token, lookup_session_token, delete_session_token,
)
from chatbot import ask_chatbot
from flight_search import search_flights
from cascade import calculate_cascade
from confirmation_scanner import scan_confirmation
from ics_export import trip_to_ics
from seed_trip import build_demo_trip

app = FastAPI(title="SkySaver API", version="1.0")

# Allow your Next.js frontend (local + Vercel)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://skysaver-ai.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Auth dependency ----
def current_user(session_token: str = Cookie(None)) -> dict:
    if not session_token:
        raise HTTPException(401, "Not authenticated")
    user = lookup_session_token(session_token)
    if not user:
        raise HTTPException(401, "Invalid session")
    return user


# ---- Models ----
class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ChatRequest(BaseModel):
    message: str
    history: list[dict[str, str]] = []


# ---- Auth ----
@app.post("/api/auth/signup")
def signup(req: SignupRequest):
    user = create_user(req.name, req.email, req.password)
    if user is None:
        raise HTTPException(409, "Email already registered")
    token = create_session_token(user["email"])
    response = JSONResponse({"ok": True, "user": user})
    response.set_cookie(
        "session_token", token,
        httponly=True, secure=True, samesite="lax", max_age=30*24*3600,
    )
    return response


@app.post("/api/auth/login")
def login(req: LoginRequest):
    user = authenticate_user(req.email, req.password)
    if user is None:
        raise HTTPException(401, "Invalid email or password")
    token = create_session_token(user["email"])
    response = JSONResponse({"ok": True, "user": user})
    response.set_cookie(
        "session_token", token,
        httponly=True, secure=True, samesite="lax", max_age=30*24*3600,
    )
    return response


@app.post("/api/auth/logout")
def logout(session_token: str = Cookie(None)):
    if session_token:
        delete_session_token(session_token)
    response = JSONResponse({"ok": True})
    response.delete_cookie("session_token")
    return response


@app.get("/api/me")
def me(user = Depends(current_user)):
    return {"ok": True, "user": user}


# ---- Trips ----
def _trip_id_for(user: dict) -> str:
    email = user["email"]
    return f"trip_{email.replace('@', '_at_').replace('.', '_')}"


@app.get("/api/trip")
def get_my_trip(user = Depends(current_user)):
    trip = get_trip(_trip_id_for(user))
    return {"ok": True, "trip": trip}


@app.post("/api/trip")
def create_my_trip(payload: dict, user = Depends(current_user)):
    payload["_id"] = _trip_id_for(user)
    payload["user_id"] = user["email"]
    save_trip(payload)
    return {"ok": True, "trip_id": payload["_id"]}


@app.patch("/api/trip/legs/{leg_id}")
def patch_leg(leg_id: str, changes: dict, user = Depends(current_user)):
    update_leg(_trip_id_for(user), leg_id, changes)
    return {"ok": True}


@app.delete("/api/trip/legs/{leg_id}")
def remove_leg(leg_id: str, user = Depends(current_user)):
    delete_leg(_trip_id_for(user), leg_id)
    return {"ok": True}


# ---- Flight search ----
@app.get("/api/flights/search")
def flights(origin: str, destination: str, date: str, user = Depends(current_user)):
    options = search_flights(origin, destination, date)
    return {"ok": True, "options": options}


# ---- Cascade preview ----
@app.post("/api/cascade")
def cascade(payload: dict, user = Depends(current_user)):
    trip = get_trip(_trip_id_for(user))
    if not trip:
        raise HTTPException(404, "No trip found")
    report = calculate_cascade(trip, payload["affected_leg_id"], payload["replacement"])
    return {"ok": True, "report": report.to_dict()}


# ---- Chat assistant ----
@app.post("/api/chat")
def chat(req: ChatRequest, user = Depends(current_user)):
    trip = get_trip(_trip_id_for(user))
    response = ask_chatbot(req.message, req.history, trip)
    return {"ok": True, "response": response}


# ---- Gemini OCR ----
@app.post("/api/scan-confirmation")
async def scan(file: UploadFile = File(...), user = Depends(current_user)):
    contents = await file.read()
    extracted = scan_confirmation(contents, file.filename or "upload")
    return {"ok": True, "extracted": extracted}


# ---- Disruptions ----
@app.post("/api/trip/simulate-cancellation/{leg_id}")
def simulate(leg_id: str, user = Depends(current_user)):
    trip_id = _trip_id_for(user)
    update_leg(trip_id, leg_id, {"status": "cancelled"})
    log_disruption(trip_id, {
        "disruption_id": f"dis_{leg_id}",
        "affected_leg_id": leg_id,
        "disruption_type": "cancelled",
        "details": "Simulated cancellation",
    })
    return {"ok": True}


# ---- Calendar export ----
@app.get("/api/trip/ics")
def export_ics(user = Depends(current_user)):
    trip = get_trip(_trip_id_for(user))
    if not trip:
        raise HTTPException(404, "No trip")
    ics_content = trip_to_ics(trip)
    return JSONResponse(
        content={"ok": True, "ics": ics_content},
        headers={"Content-Type": "application/json"},
    )


# ---- Admin ----
@app.get("/api/admin/users")
def admin_users(user = Depends(current_user)):
    return {"ok": True, "users": list_users()}


# ---- Healthcheck ----
@app.get("/api/health")
def health():
    return {"ok": True, "service": "skysaver-api"}
```

**Run locally:**
```bash
pip install fastapi uvicorn[standard] python-multipart
uvicorn api:app --reload --port 8000
```

Now your Python backend is callable at `http://localhost:8000/api/*` and `http://localhost:8000/docs` gives you free Swagger UI.

---

## Step 2 — Generate the Next.js frontend

You'll get the Next.js code from v0.dev / Claude.ai / Lovable using the prompts in `DESIGN_BRIEF.md`. Put it in a `frontend/` subfolder of this repo:

```
skysaver-ai/
├── api.py                ← FastAPI backend
├── mongo_helpers.py       ← reused
├── chatbot.py             ← reused
├── ... (other Python)
└── frontend/              ← Next.js project
    ├── app/
    ├── components/
    ├── lib/
    │   └── api.ts        ← API client (see below)
    └── package.json
```

---

## Step 3 — The frontend's API client

In `frontend/lib/api.ts` create a typed client that talks to FastAPI. The frontend never knows about MongoDB, Gemini, or MCP — it just calls these functions.

```ts
// frontend/lib/api.ts
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',  // send the HttpOnly session cookie
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
    ...init,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// --- Auth
export const signup = (body: { name: string; email: string; password: string }) =>
  request<{ ok: true; user: any }>('/api/auth/signup', {
    method: 'POST',
    body: JSON.stringify(body),
  });

export const login = (body: { email: string; password: string }) =>
  request<{ ok: true; user: any }>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify(body),
  });

export const logout = () => request<{ ok: true }>('/api/auth/logout', { method: 'POST' });

export const me = () => request<{ ok: true; user: any }>('/api/me');

// --- Trip
export const getMyTrip = () => request<{ ok: true; trip: any }>('/api/trip');

export const createMyTrip = (payload: any) =>
  request<{ ok: true; trip_id: string }>('/api/trip', {
    method: 'POST',
    body: JSON.stringify(payload),
  });

export const updateLeg = (legId: string, changes: any) =>
  request(`/api/trip/legs/${legId}`, {
    method: 'PATCH',
    body: JSON.stringify(changes),
  });

// --- Search + cascade
export const searchFlights = (origin: string, destination: string, date: string) =>
  request<{ ok: true; options: any[] }>(
    `/api/flights/search?origin=${origin}&destination=${destination}&date=${date}`
  );

export const previewCascade = (affectedLegId: string, replacement: any) =>
  request<{ ok: true; report: any }>('/api/cascade', {
    method: 'POST',
    body: JSON.stringify({ affected_leg_id: affectedLegId, replacement }),
  });

// --- Chat
export const askChatbot = (message: string, history: any[]) =>
  request<{ ok: true; response: string }>('/api/chat', {
    method: 'POST',
    body: JSON.stringify({ message, history }),
  });

// --- Disruption simulator (demo)
export const simulateCancellation = (legId: string) =>
  request(`/api/trip/simulate-cancellation/${legId}`, { method: 'POST' });

// --- OCR upload
export const scanConfirmation = async (file: File) => {
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch(`${API_BASE}/api/scan-confirmation`, {
    method: 'POST',
    credentials: 'include',
    body: fd,  // browser sets multipart Content-Type
  });
  if (!res.ok) throw new Error(`Scan failed: ${res.statusText}`);
  return res.json() as Promise<{ ok: true; extracted: any }>;
};
```

Use it in a component like:

```tsx
// frontend/app/dashboard/page.tsx
'use client';
import { useEffect, useState } from 'react';
import { getMyTrip } from '@/lib/api';

export default function Dashboard() {
  const [trip, setTrip] = useState<any>(null);
  useEffect(() => { getMyTrip().then(r => setTrip(r.trip)); }, []);
  if (!trip) return <div>Loading…</div>;
  return <div>Trip: {trip.title}</div>;
}
```

That's the *complete* wiring pattern. Every page in the frontend calls one or two functions from `lib/api.ts`. The frontend never imports anything from the Python backend directly.

---

## Step 4 — Run them both locally during development

Two terminals:

```bash
# Terminal 1 — Python backend
cd skysaver-ai
source venv/bin/activate
uvicorn api:app --reload --port 8000
```

```bash
# Terminal 2 — Next.js frontend
cd skysaver-ai/frontend
npm install
npm run dev   # runs at http://localhost:3000
```

The frontend's `NEXT_PUBLIC_API_BASE` env var points to `http://localhost:8000` and the browser calls FastAPI directly. CORS is configured on the FastAPI side to allow `http://localhost:3000`.

---

## Step 5 — Deploy

**Option A: Two separate deployments (recommended)**

- **Backend** → Cloud Run (the Dockerfile we already have, but with `CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080"]` instead of Streamlit).
- **Frontend** → Vercel (push the `frontend/` directory to a separate GitHub repo or Vercel monorepo).
- Set `NEXT_PUBLIC_API_BASE` in Vercel's env to the Cloud Run URL.
- Update FastAPI's CORS allowlist to include the Vercel domain.

Why split: Vercel is the best deploy target for Next.js (free, fast, edge cached), and Cloud Run is the best for the Python backend. They communicate over HTTPS.

**Option B: Single container (simpler, slower)**

- Build the Next.js app to static export, copy it into the Python container, have FastAPI serve the static files alongside `/api/*` routes.
- One deploy target (Cloud Run). One URL.
- Loses Vercel's edge caching and image optimization, but simpler to operate.

```python
# add to api.py
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="frontend/out", html=True), name="frontend")
```

```dockerfile
# Dockerfile additions
WORKDIR /app/frontend
RUN npm ci && npm run build && npm run export
WORKDIR /app
```

For the hackathon I'd recommend Option A — it's faster to ship and Vercel handles the frontend complexity for free.

---

## Migration timeline (honest estimate)

| Phase | Time |
|---|---|
| Build FastAPI `api.py` (paste the template above, test each endpoint) | 4–6h |
| Generate Next.js pages from `DESIGN_BRIEF.md` using v0.dev | 6–10h (lots of iteration) |
| Wire frontend to FastAPI via `lib/api.ts` | 2–4h |
| Auth flow (cookies, redirects, protected routes) | 2–4h |
| Polish, fix bugs, responsive | 4–8h |
| Deploy both to Vercel + Cloud Run | 2–3h |
| **Total** | **20–35 hours of focused work** |

That's **3–4 full days** of work. Your hackathon deadline is in 11 days.

---

## My honest recommendation

**For the hackathon:** ship the Streamlit version. It works, it's polished, the MCP integration is done. Spend the remaining time on Cloud Run deploy, demo video, and Devpost writeup.

**After the hackathon:** use this migration doc + `DESIGN_BRIEF.md` to build the Next.js version in July. You'll have a Series-A-quality product to show off, with zero deadline pressure.

The Python backend (`mongo_helpers.py`, `chatbot.py`, `mcp_bridge.py`, etc.) is the durable asset. The Streamlit UI is the demo asset. Both are usable. The next.js frontend is the *product* asset for after launch.
