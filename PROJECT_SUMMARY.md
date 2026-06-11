# SkySaver AI — Complete Project Summary

## 1. The product, in one paragraph

**SkySaver AI is an autonomous travel guardian agent.** You add a trip once — flights, hotels, ground transport, meetings — and SkySaver watches every leg 24/7. The moment a flight cancels, it autonomously detects the disruption, searches Google Flights for live alternatives, ranks them against your stored preferences, and shows you a **cascade preview** — what each option does to your hotel check-in, your meeting buffer, your downstream connections. You pick one. SkySaver hands you off to the airline's site to pay (with route and date pre-filled), reads your confirmation PDF via Gemini Vision OCR when you upload it, and updates everything in MongoDB. Your itinerary stays coherent without you thinking.

**Positioning line:** *Travel that handles itself.*

---

## 2. How the agent is supposed to work — the canonical user flow

### 2.1 Onboarding

1. New user lands on the marketing page (`/`).
2. Clicks **Get started** → redirected to `/auth.html`.
3. Signs up with name + email + password. Real auth, hashed in MongoDB.
4. Lands on the **Plan-a-trip wizard** (`/plan.html`).
5. Wizard collects:
   - **Where** — origin + destinations from a 120-airport autocomplete
   - **When** — date range
   - **Who** — adults / children / infants
   - **Bags** — carry-on + checked count
   - **Stay** — hotel / AirBnB / hostel / family / none, stars, budget
   - **Ground** — ride-share / rental / public / mix
   - **Meetings** — title + date + time + location
   - **Notes** — free text
6. On finish, the wizard POSTs `/api/trip` with a structured intake. The backend builds a trip document with skeleton legs (flights marked `booking_method: "pending"`, hotel and transport scaffolds, one meeting per row).
7. User lands on the **Dashboard** showing their real trip.

### 2.2 Finalizing each leg

For every "TBD" leg the user opens **Trip details** → expands the leg → **"🔍 Find & finalize this flight"** panel:

- Triggers `/api/flights/search` (SerpAPI Google Flights with the leg's route + date).
- Ranks results against the user's stored preferences.
- User picks one → it's written to the leg in MongoDB (`status: "selected_pending_payment"`).
- A **"Book on the airline"** deep link opens emirates.com / etihad.com / etc. with route + date pre-filled where supported.
- After paying externally, the user comes back → **"I booked externally"** form → enters PNR + price + seat → leg becomes `status: "scheduled"`, `booking_reference` populated. SkySaver starts tracking it.

Hotel legs work the same way: a **"Find & finalize this stay"** panel offers Booking.com, Airbnb, Google Hotels links.

### 2.3 Live monitoring

- Every 10 seconds the dashboard auto-refreshes (Streamlit version had this; in the React version it's the data fetch on focus).
- A **🟢 LIVE · watching N flights** indicator pings at the top of the dashboard.
- In production this would poll a flight-status API (FlightAware, Cirium). For the demo, a "**Simulate disruption**" button on the dashboard triggers a real cancellation in MongoDB via `/api/trip/simulate-cancellation/{leg_id}`.

### 2.4 Disruption recovery (the hero moment)

When a tracked flight is cancelled:

1. **Red alert banner** slides in at the top of the dashboard: *"EY 728 cancelled — recovery ready below."*
2. The cancelled leg in the itinerary turns red.
3. **Recovery panel** opens below the itinerary.
4. SkySaver autonomously searches SerpAPI Google Flights for the cancelled route + date.
5. Live alternatives are mapped to ranked option cards.
6. For each option, the **cascade preview** is computed:
   - Will the hotel check-in still work? (shifted? broken?)
   - Will the ground transport need rescheduling?
   - Is the meeting buffer still safe?
   - Are downstream flights still bookable?
7. Each card shows the severity at a glance: green (fits cleanly), blue (shifts cleanly), amber (tight buffer), red (will break something).
8. User clicks **"Book this option"** on whichever they prefer.

### 2.5 Two-step booking

1. **Step 1 — Pay on the airline.** SkySaver doesn't process payment (no indie-dev OAuth for airlines). Two buttons:
   - "Open Emirates" / "Open Etihad" — pre-filled with route + date for the 5 carriers we have URL templates for (Emirates, BA, Qatar, Lufthansa, Delta); for others, the airline's homepage or a Google search.
   - "Compare on Google Flights" — opens Google Flights with the same route + date.
2. User books externally, gets a confirmation email.
3. Returns to SkySaver → clicks **"I've paid — show me Step 2."**
4. **Step 2 — File the confirmation.** A file uploader accepts the airline's confirmation PDF / screenshot.
5. **Gemini Vision OCR** reads the PDF and extracts: PNR, airline code, flight number, dates, times, price, payment method, passenger name.
6. The form pre-fills with the extracted data.
7. User confirms → MongoDB writes the new flight, applies the cascade changes to the hotel/transport/meetings, logs the recovery in `disruption_history`.
8. Dashboard updates, alert clears.

### 2.6 Chat assistant

A sticky chat side-rail lives on the dashboard. Every message:

1. Posts to `/api/chat`.
2. The backend re-reads the user's trip **through the MongoDB MCP server** — proving the partner integration is live, not decorative.
3. Gemini 2.5 Flash answers in plain language. Replies are markdown-rendered (bold, lists, links).
4. Examples: *"What happens to my hotel if EY 728 is delayed 3 hours?"* — *"Find me a lounge in Abu Dhabi airport."* — *"Move my ride pickup to 11am."*

### 2.7 Editing & settings

- **Trip details** — every leg has a type-specific editor (flights have PNR + seat + fare; hotels have address + star rating + amenities; transport has provider + tier; meetings have location + attendees + buffer).
- **Preferences** — Flights / Hotels / Ground transport tabs. Picks store as IATA codes for 20 supported airlines.
- **Settings** — your account info from `/api/me`, notification toggles, currency, auto-book toggle, data exports (Open JSON, Download .ics calendar).
- **Delete trip** — top right of Trip details. Wipes the MongoDB document, returns dashboard to empty state.

---

## 3. The user prompts that shaped this build

These are the requirements the user gave during development, in roughly the order received:

### Foundation
- *"Build a travel recovery agent for the hackathon"*
- *"Use Gemini and MongoDB for the partner integration"*
- *"Make the cascade preview the distinctive feature"*

### Initial Streamlit build
- *"Use Streamlit for speed, polish later"*
- *"Set up Auth, dashboard, plan-a-trip, preferences, settings"*
- *"Add user auth with signup/login backed by MongoDB"*
- *"Persistent sessions so I don't have to log in repeatedly"*
- *"Rename Sign in to Log in"*

### Polish & iteration
- *"Modernize the UI"*
- *"Stripe / Linear / Vercel level polish"*
- *"Add type-coded gradients per leg type"*
- *"Add live disruption notifications and a notification bell"*
- *"Add auto-refresh and a live tracking indicator"*
- *"Add calendar export (.ics)"*
- *"Make all flight details editable"*

### Recovery flow
- *"Add a 2-step post-payment handoff: pay on the airline, then file the confirmation"*
- *"Fix airline links to actually open the airline, not Google Flights"*
- *"Add Gemini OCR for confirmation PDFs"*
- *"Expand recovery options — sort by price/fastest/etc., more results, compact view"*
- *"Add an airline deep-link with route + date pre-filled"*
- *"Add Google Flights as the comparison option"*
- *"Auto-scroll to the booking dialog"*

### Backend / agent layer
- *"Use Google Cloud Agent Builder via Vertex AI for Gemini"*
- *"Build the official MongoDB MCP server integration — the agent must talk to MongoDB through MCP, not pymongo directly"*
- *"Bridge the agent (chatbot) to use the MCP server on every chat turn"*

### Pivot to React UI
- *"I have a new React UI — wire it up to the existing backend"*
- *"Build a FastAPI backend that serves the React UI as static files and exposes /api/* endpoints"*
- *"Move the chat to the right of the dashboard, not below"*
- *"Render markdown in the chat so bold/italic/lists actually format"*

### Cleanup
- *"Remove Continue with Google button"*
- *"Remove the fake testimonials, fake stats, fake company logos"*
- *"Drop the fake admin user table from Settings"*
- *"Make new users see the empty state, not the Dubai demo"*
- *"Get started should go to login first, not the dashboard"*
- *"Plan wizard should use all 120 airports, not 8 cities"*
- *"Plan wizard should actually save the trip to MongoDB and redirect to the dashboard"*
- *"Preferences should anchor in my real flights — show what I'm tracking first, then let me set prefs"*
- *"Preferences airline picker should use proper IATA + name, more airlines"*
- *"After preferences, give me an option to go to Google Flights or the specific airline"*

### Honest concerns
- *"Stop showing me defaults I didn't pick"*
- *"PNR shouldn't appear on hotel legs — that's a flight thing"*
- *"Manage flight / Manage stay buttons need to actually go somewhere"*
- *"There should be a delete option for trips"*
- *"More options in recovery — too few choices"*
- *"Show real Google Flights results, not the same 3 hardcoded options"*
- *"Sync the dashboard and trip details — they're showing different data"*

### Frustration moments (and what they meant)
- *"Make it just work, no more UI fluff"*
- *"Get the core idea working, polish later"*
- *"The pages should never show data I never created"*

---

## 4. What's been built — every file

### Backend (Python)

| File | Role |
|---|---|
| `api.py` | FastAPI server. Serves the React UI from `frontend/` as static files. Exposes 25+ `/api/*` endpoints: auth, trips, legs, flight search, cascade, chat, OCR scan, deep links, calendar export, admin |
| `mongo_helpers.py` | MongoDB CRUD: users, sessions, trips, legs, disruption history. Auth helpers (signup, login, password hashing, session tokens) |
| `mcp_bridge.py` | **The hackathon partner-track qualifier.** Spawns the official `mongodb-mcp-server` Node.js subprocess and drives it over JSON-RPC. Custom minimal client because the `mcp` Python SDK has Python 3.13 issues |
| `chatbot.py` | Gemini wrapper. Reads your trip *through the MongoDB MCP server* on every chat turn (the partner integration in action). Tightened system prompt: max 3 sentences, no headings, no filler |
| `flight_search.py` | SerpAPI Google Flights wrapper with 6-hour file-based cache |
| `cascade.py` | The distinctive feature. Given a replacement flight + a trip, computes per-leg ripple effects (shifted / tight / broken) with severity scores |
| `confirmation_scanner.py` | Gemini Vision OCR. Sends PDF/PNG/JPG to Gemini 2.5 Flash and returns structured booking JSON |
| `deep_links.py` | 60+ airline website URLs. Deep-link templates with route + date pre-fill for Emirates, BA, Qatar, Lufthansa, Delta. Plus Uber, Booking.com, Google Flights, Google Maps builders |
| `ics_export.py` | iCalendar (.ics) generator — every leg becomes a calendar event |
| `airports.py` | 120 major international airports for autocomplete |
| `seed_trip.py` | Demo trip builder using relative dates so SerpAPI always sees future flights |
| `agent.py` | Original Gemini-with-tools experiment (the chatbot pattern superseded it) |
| `demo_flow.py` | CLI script that proves the entire intelligence layer works without any UI |
| `simulate_disruption.py` | CLI for injecting cancellations into MongoDB |
| `read_trip.py` | CLI for inspecting a trip in MongoDB |
| `test_setup.py` | Smoke test for MongoDB + Gemini connectivity |
| `requirements.txt` | Python deps including `email-validator`, `python-multipart`, `mcp`, `streamlit-autorefresh` |
| `Dockerfile` + `.dockerignore` | Cloud Run container (multi-stage, includes Node.js for MCP server) |
| `DEPLOY.md` | Cloud Run deploy walkthrough with gcloud secrets |
| `MIGRATION.md` | Streamlit → React migration guide |
| `DESIGN_BRIEF.md` | Pro-grade design handoff doc |
| `schema.md` | MongoDB trip schema documentation |
| `app.py` | Original Streamlit app — kept as fallback only |

### Frontend (React via CDN, no build step)

| File | Role |
|---|---|
| `frontend/index.html` | Marketing landing — hero, features, product demo, slim footer |
| `frontend/auth.html` | Sign in / Sign up with real backend auth, HttpOnly session cookie |
| `frontend/app.html` | Dashboard — empty state OR itinerary + chat side rail + alert banner + recovery |
| `frontend/plan.html` | 8-step trip-planning wizard with 120-airport autocomplete, saves real trip to MongoDB |
| `frontend/trip.html` | Per-leg editor with type-specific forms (flights / hotels / transport / meetings), Find & Finalize panels, Delete trip |
| `frontend/preferences.html` | Real tracked flights at top, 3 tabs (Flights / Hotels / Ground), IATA-based airline picker, Google Flights / airline-specific exit links |
| `frontend/settings.html` | Real account info from `/api/me`, notifications, data exports (.ics, JSON) |
| `frontend/app/api.js` | `window.SkyAPI` — typed fetch client used by every page |
| `frontend/app/airports.js` | Mirror of `airports.py` for the frontend |
| `frontend/app/data.js` | Boot loader — fetches user + trip from API, shapes them for the UI, dispatches `sky:trip-loaded` event |
| `frontend/app/main.jsx` | Dashboard composition: empty state, hero, metrics, itinerary, chat, recovery |
| `frontend/app/ui.jsx` | Sidebar, TopBar with log-out dropdown, LegCard with real deep-link buttons per leg type |
| `frontend/app/chat.jsx` | Chat side rail. Calls real `/api/chat`. Renders markdown bubbles |
| `frontend/app/recovery.jsx` | Recovery panel with cascade preview, booking dialog with real airline + Google Flights deep links, real OCR upload |
| `frontend/app/plan.jsx` | Trip-planning wizard. Saves real trip to MongoDB on finish |
| `frontend/app/preferences.jsx` | Preferences page |
| `frontend/app/settings.jsx` | Settings page |
| `frontend/app/trip.jsx` | Trip details with hotel-specific, flight-specific, transport-specific, meeting-specific editors |
| `frontend/app/icons.jsx` | Lucide-style SVG icon set |
| `frontend/styles/tokens.css`, `frontend/app/*.css` | CSS palette + per-page styles |

---

## 5. What's wired end-to-end (real backend, real Gemini, real MongoDB)

- **Auth** — signup, login, logout, persistent session via HttpOnly cookie. Users land in MongoDB
- **Empty state** — fresh users see "No trip yet" instead of the mock
- **Plan-a-trip wizard** — 120-airport autocomplete, POSTs real trip to MongoDB, redirects to dashboard
- **Dashboard** — reads user's real trip from `/api/trip`; shows real route in subtitle
- **Live tracking** — auto-refresh + green-ping indicator
- **Simulate disruption** — real `/api/trip/simulate-cancellation/{leg_id}` updates MongoDB
- **Recovery panel** — calls `/api/flights/search` against real SerpAPI Google Flights, ranks live results, shows cascade preview per option
- **Two-step booking dialog** — real airline deep links (route + date), real Google Flights links, real Gemini Vision OCR upload that pre-fills the form
- **Chat panel** — real Gemini calls, reads trip *through MongoDB MCP server* on every turn, renders markdown
- **Leg deep links** — Manage flight (airline), Manage stay (Booking.com), Order ride (Uber), Open map (Google Maps)
- **Trip details** — type-specific editors (no PNR on hotels), Find & Finalize panels for unbooked flights
- **Delete trip** — real `/api/trip` DELETE wipes MongoDB doc and redirects to empty state
- **Preferences** — anchors on real tracked flights, 20-airline IATA chip picker
- **Settings** — real account data, .ics calendar export, JSON download
- **Page guards** — protected routes redirect to `/auth.html` when not logged in

---

## 6. Still using static data (deferred — not blocking submission)

- Preferences tab controls store locally only (don't POST to backend yet)
- Settings notification toggles store locally only
- Plan wizard's "When" picker is text-only chips, not a calendar

---

## 7. Hackathon submission scorecard

| Item | Status |
|---|---|
| Built with Gemini (Vertex AI) | ✅ Chat + Vision OCR |
| Google Cloud Agent Builder | ✅ Initial agent design |
| **MongoDB MCP partner integration** | ✅ **Official mongodb-mcp-server running, chatbot reads trip via MCP every turn — qualifies for the MongoDB prize bucket** |
| Public GitHub repo + MIT license | ✅ |
| Hosted URL (Cloud Run) | ⏳ Dockerfile + DEPLOY.md ready, not yet run |
| 3-minute demo video | ⏳ |
| Devpost form | ⏳ |

---

## 8. The clean demo script (for the 3-min video)

1. **Open landing** — *"SkySaver is an autonomous travel guardian — you add a trip once, it watches every leg 24/7, and handles disruptions before you notice."*
2. **Sign up with a new email** — *"Real auth, MongoDB-backed."*
3. **Plan wizard** — *"Pick ADD → AUH from the 120 airports. Add who's coming, what's carried, where you're staying, your meetings."*
4. **Land on dashboard** — *"Live tracking is on. SkySaver is watching every flight in this trip."*
5. **Click Simulate disruption** — *"Production would poll FlightAware; for the demo we trigger it manually."*
6. **Red alert pulses in** — *"SkySaver immediately searched Google Flights for live alternatives and ranked them against my preferences."*
7. **Expand a cascade preview** — *"For each option, I see what happens to my hotel, my transport, my meeting. Option 1 is green — fits cleanly. Option 3 shifts my hotel night. The agent reasoned about the whole trip, not just the flight."*
8. **Click Book this option → Step 1** — *"SkySaver hands me off to Emirates with my route and date pre-filled — it can't take my money, no airline OAuth for indie devs."*
9. **Click "I've paid — show me Step 2"** — *"Now I upload the confirmation PDF."*
10. **Watch Gemini Vision read it** — *"Gemini Vision extracts the PNR, the new flight number, the price, the payment method. The form pre-fills."*
11. **Click Save** — *"MongoDB updates: my new flight is in, my hotel time is shifted, my transport is rescheduled, the disruption history logs the recovery. All within 30 seconds of the original cancellation."*
12. **Open the chat panel** — *"And the whole time, the assistant on the right is reading my trip through the MongoDB MCP server. Ask anything."*
13. **Show the architecture diagram** — *"Gemini → Python → MongoDB MCP → Atlas. Partner integration, not a wrapper."*

---

## 9. The architectural pitch (for Devpost technical implementation)

```
┌─────────────────────────────────────┐
│  React UI (multi-page, CDN)         │
│  HTML + Babel-JSX + Tailwind tokens  │
└──────────────┬──────────────────────┘
               │ HTTPS · JSON · HttpOnly cookie
               ▼
┌─────────────────────────────────────┐
│  FastAPI (api.py)                    │
│  25+ /api/* endpoints                │
└──────────────┬──────────────────────┘
               │ Python imports
               ▼
┌──────────────────────────────────────┐
│  Domain modules — all pure Python    │
│  mongo_helpers · chatbot · cascade   │
│  flight_search · confirmation_scanner│
│  deep_links · ics_export · airports  │
│  mcp_bridge ← spawns Node subprocess │
└──┬──────────┬───────────┬──────────┬─┘
   │          │           │          │
   ▼          ▼           ▼          ▼
┌──────┐  ┌──────┐  ┌──────────┐  ┌───────┐
│Atlas │  │Vertex│  │MCP server│  │SerpAPI│
│Mongo │  │  AI  │  │ (Node.js)│  │GFlight│
└──────┘  └──────┘  └─────┬────┘  └───────┘
                          │
                          ▼ (the agent's data path)
                       MongoDB Atlas
```

The agent's data path:

```
chatbot.py
   ↓ JSON-RPC over stdio
mongodb-mcp-server (Node.js subprocess)
   ↓ MongoDB wire protocol
MongoDB Atlas (skysaver database)
```

That mongodb-mcp-server in the middle is what makes this qualify for the MongoDB partner prize bucket. The agent never touches pymongo directly when answering — it asks the MCP server for the trip.
