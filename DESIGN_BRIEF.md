# SkySaver AI — Frontend Design Brief

**For:** v0.dev / Claude.ai / Lovable / a frontend engineer
**From:** SkySaver AI engineering
**Reference benchmarks:** Stripe (motion + gradient), Linear (density + clarity), Vercel (typography + spacing), Notion (warmth), Arc Browser (organic color)

---

## 1. Product summary

SkySaver AI is an **autonomous travel guardian agent**. Users add their trip — flights, hotels, transport, meetings. SkySaver watches it 24/7 against real-time data. The moment a flight cancels, it autonomously detects the disruption, searches Google Flights for alternatives, ranks them against the user's stored preferences, and shows a *cascade preview* — what each option does to the user's hotel check-in, meeting buffer, and downstream connections.

The user picks one option, pays on the airline's site, uploads the confirmation PDF, and Gemini reads it via OCR and updates everything in MongoDB. The trip stays coherent without the user thinking.

**Built on:** Gemini 2.5 Flash (Vertex AI), MongoDB Atlas (via official MongoDB MCP server), Google Flights data (SerpAPI), Duffel sandbox for booking primitives.

**One-line positioning:** *Travel that handles itself.*

**Hero headline candidate:** *"Meet your travel guardian."*

**Hero subhead:** *"When your flight cancels at 2am, SkySaver has already booked your alternative. Powered by Gemini, watching every itinerary 24/7."*

---

## 2. Brand voice

- Decisive, calm, never panicky.
- Senior travel operations manager who happens to be AI — not a chatbot.
- Concise: "I rebooked you onto SQ305. Hotel shifted 2h later. Meeting is still on time."
- Never apologetic. Never wordy.

---

## 3. Visual language

### 3.1 Color palette

**Primary (indigo/violet/pink gradient)**
- `#4F46E5` indigo-600 — primary
- `#6366F1` indigo-500 — primary hover/light
- `#8B5CF6` violet-500 — gradient mid
- `#EC4899` pink-500 — gradient end / accent
- `#C084FC` purple-400 — soft accent

**Neutrals**
- `#0F172A` slate-900 — body text
- `#475569` slate-600 — secondary text
- `#94A3B8` slate-400 — tertiary text
- `#E2E8F0` slate-200 — borders
- `#F8FAFC` slate-50 — soft backgrounds
- `#FFFFFF` — surface

**Semantic**
- `#10B981` emerald-500 — success, "low risk"
- `#3B82F6` blue-500 — info, "shifted cleanly"
- `#F59E0B` amber-500 — warning, "tight buffer"
- `#EF4444` red-500 — danger, "broken / cancelled"

**Leg category accents (Linear-style):**
- Flights → blue gradient `#EFF6FF` → `#DBEAFE`, border `#BFDBFE`
- Hotels → purple gradient `#FAF5FF` → `#F3E8FF`, border `#E9D5FF`
- Transport → amber gradient `#FFFBEB` → `#FEF3C7`, border `#FDE68A`
- Meetings → emerald gradient `#ECFDF5` → `#D1FAE5`, border `#A7F3D0`

### 3.2 Typography

- **Font:** Inter (variable). Display weight 800 for hero, 700 for headlines, 500–600 for UI.
- **H1 hero:** 72–96px desktop, letter-spacing -0.04em, line-height 0.95.
- **H2 section:** 40–48px, -0.025em.
- **H3 card titles:** 20–24px, -0.015em.
- **Body:** 16px, line-height 1.6, color slate-700.
- **Caption:** 13–14px, slate-500, letter-spacing 0.02em.
- **Eyebrow / label:** 11–12px, 700 weight, uppercase, letter-spacing 0.16em, indigo-600.

### 3.3 Motion + interactions

- **Easing:** `cubic-bezier(0.22, 1, 0.36, 1)` — sharp out, slow in (Linear's curve).
- **Page transitions:** 200ms cross-fade with 8px translateY rise.
- **Buttons:** 250ms lift on hover (-2px), tinted shadow in button color, white sweep gloss (Stripe-style).
- **Cards:** 300ms hover lift (-2px) with indigo-tinted glow.
- **Alerts:** slide-in from above 450ms + pulsing red glow box-shadow every 2.2s.
- **Live indicators:** green dot with expanding ping ring every 1.6s.
- **Gradient backgrounds:** subtle background-position shift across 6–8 seconds for non-static feel.
- **Scroll-triggered animations:** fade + 20px rise on entering viewport.

### 3.4 Stripe-style flowing gradient ribbon

The hero should include a Stripe-style flowing color ribbon (orange → pink → purple → blue → cyan) sweeping diagonally across the right two-thirds of the hero. Use SVG with feTurbulence + feDisplacementMap or a static PNG with parallax scroll. Critical: must feel organic, not blocky.

---

## 4. Page-by-page brief

### 4.1 Landing page (`/`)

**Goal:** convert visitors to sign up in one screen.

**Layout, top to bottom:**

1. **Sticky top nav** (translucent glass, blurred backdrop):
   - Left: `✈ SkySaver AI` brand mark (gradient text)
   - Center: `Features` `How it works` `Pricing` `Docs`
   - Right: `Sign in` ghost button + `Get started — free` gradient button
   - Height 64px, padding 14px 28px
   - Becomes opaque white at 80px scroll

2. **Hero** (full viewport height, 100vh):
   - Left two-thirds: text content
   - Right one-third: **flowing Stripe-style gradient ribbon** (orange → pink → violet → blue, organic curves)
   - Pill eyebrow: `✦ TRAVEL THAT HANDLES ITSELF` (indigo-100 background, indigo-700 text)
   - H1: `Meet your travel guardian.` (gradient on "travel guardian" — indigo→violet→pink)
   - Subhead: 1.25rem, slate-600, max-width 560px
   - Two CTAs:
     - Primary: `Get started — free` (gradient button with sweep gloss)
     - Secondary: `See how it works` (ghost button)
   - Below CTAs, a small metric strip:
     `12,481 trips watched · 3,209 cancellations resolved · ~30s avg recovery`

3. **Logo strip** (used by [logos]):
   - Light gray, 60% opacity, single row of 6–8 fictional company logos

4. **Feature triad** (three columns):
   - Each card: icon (lucide-react), title, two-line description
   - On hover: lift -2px, indigo glow
   - Cards:
     - 🛡 **24/7 monitoring** — Real-time flight, hotel, and transit status. Disruptions surfaced before they catch you.
     - 🧠 **Cascade-aware planning** — Every alternative shows the ripple effect across your trip before you commit.
     - ⚡ **One-tap recovery** — Pick an option, SkySaver updates downstream and hands you off to pay.

5. **Product demo (animated mockup)**:
   - Glassmorphism browser frame with the dashboard inside
   - Auto-play a 12-second loop: itinerary visible → red alert banner slides in → 3 options appear → option selected → trip recovers
   - Looped MP4 or Lottie

6. **Long-form sections (3–4 of them)**, alternating left/right image + text:
   - "Plan once. Travel without thinking."
   - "When something breaks, you'll already have an answer."
   - "Powered by Gemini. Watched by MongoDB MCP."
   - "Stays, transport, and meetings — all in sync."

7. **Big quote** from a fictional user, large card, italic 28px.

8. **Pricing strip** (three tiers):
   - Free · $0 · personal trips, manual booking confirmation
   - Pro · $9/mo · auto-booking, SMS alerts, calendar sync
   - Team · $29/seat · shared trips, admin controls, SSO

9. **Final CTA section** — dark gradient background, big "Start watching your next trip" headline, single button.

10. **Footer** — five columns of links, social icons, small print.

---

### 4.2 Auth (`/login`, `/signup`)

- Two-column layout: left 50% is dark gradient hero with brand + value prop, right 50% is the form on white surface.
- Forms have soft 12px rounded inputs with focus indigo glow.
- Both sign-in and sign-up have `Continue with Google` button at top (mock, actual OAuth deferred).
- Below form: link to switch between modes.
- Password requirements show inline as the user types.

---

### 4.3 Plan-a-trip onboarding (`/plan`)

A multi-step wizard, not a single long form. **Steps:**

1. **Where** — origin and destination(s) with autocomplete combobox (City + IATA). Multi-select for destinations.
2. **When** — calendar picker (date range), with quick-pick chips like "Weekend," "1 week," "2 weeks."
3. **Who** — adults / children / infants with `+`/`−` steppers.
4. **What you're carrying** — carry-on count, checked bag count, special items text field.
5. **Stay** — type (Hotel / AirBnB / Hostel / With friends), min star rating, max nightly budget.
6. **Ground transport** — primary mode chips (Ride-share / Rental / Public / Mix), preferred ride tier.
7. **Meetings** — optional, "Add a meeting" button reveals a date/time/title row, can stack.
8. **Anything else** — free-text notes.

UX:
- Progress dots at the top showing step 4 of 8.
- "Back" / "Next" at the bottom, sticky.
- Animated transitions between steps (slide left/right, 300ms).
- A persistent right-side summary card showing what's been entered so far.
- Final step: "Create trip" → confetti micro-animation → redirect to Dashboard.

---

### 4.4 Dashboard (`/app`)

The primary workspace. Layout:

- **Top app bar** (sticky): brand, search, notification bell, user avatar dropdown.
- **Left sidebar** (collapsible 240px): nav items with type-coded icons (Dashboard, Trip details, Plan a trip, Preferences, Settings).
- **Main area** — two columns:

**Left column (60%):**

1. **Hero strip** — *Welcome back, {name}.* + **🟢 LIVE · watching {N} flights** badge with pinging green dot + *Last check: HH:MM:SS UTC*.
2. **Alert banner** — only when active. Red gradient, spinning siren icon, pulsing glow, two buttons.
3. **Metric tiles** — 4 cards: Current trip, Legs, Flights, Disruptions. Each has a 3px gradient top border and soft hover lift.
4. **Rainbow accent divider** — 4px gradient bar.
5. **Itinerary heading** — "### Itinerary"
6. **Leg cards** — stacked, type-coded by gradient. Each card:
   - Type icon + title (e.g. `✈ EK308 — DXB → SIN`)
   - Time range (e.g. `Sat 14 Jun 22:00 UTC → Sun 15 Jun 09:30 UTC`)
   - Meta (e.g. `$510 · Terminal 3`)
   - Status badge top right (color-coded)
   - Footer link: "Manage flight ↗" / "Order Uber ↗" / etc.
7. **Preferences quick-view expander** (collapsed by default).
8. **Recent activity expander** (collapsed by default).

**Right column (40%):**

A **sticky chat side rail** spanning the column height:

- Gradient header (indigo → violet → pink): `💬 Ask SkySaver — Powered by Gemini · reads trip via MongoDB MCP`
- Scrollable history (max 520px)
- Empty state shows three example prompts as clickable chips
- Chat input pinned at bottom

**When a disruption is active**, both columns continue and the **recovery panel** opens full-width below them with the filterable, sortable alternatives + cascade previews.

---

### 4.5 Trip details (`/app/trip/{id}`)

- Top: trip summary banner (origin → destinations, dates, traveler count).
- Below: **Add a new leg** primary CTA, revealing a type picker (Flight / Hotel / Transport / Meeting) and type-specific form.
- Below: **All legs** displayed as a vertical timeline. Each leg is expandable.
- When expanded, shows the full editor with type-specific fields, **Find & finalize** panel (live Google Flights for unbooked flights), and **I booked externally** form for entering real PNRs.
- A floating "Save" button appears when changes are unsaved.

---

### 4.6 Preferences (`/app/preferences`)

Tabbed layout:
- **✈ Flights:** direct preference toggle, seat class, carry-on count, checked count, max layover slider, arrival window, meal preference, seat preference, preferred airlines multi-select, avoid airlines multi-select, frequent flyer numbers
- **🏨 Hotels:** stay type, min stars slider, room type, breakfast toggle, bed type, smoking, quiet floor, preferred hotel chains, loyalty programs
- **🚖 Ground transport:** preferred ride app, preferred tier, public transit toggle, rental car toggle, max ride cost

Each tab has a sticky "Save preferences" button at the bottom.

---

### 4.7 Settings (`/app/settings`)

Three sections in cards:
- **Your account** — name, email, password change, account creation date, last sign-in, sign-ins to date
- **Notifications & general** — email, SMS toggles, currency, auto-book low-risk recoveries toggle, "Pause monitoring" big red button
- **Database** — metric tiles for signups, sign-ins, active today + admin table of signups

---

### 4.8 Recovery panel (state, not a page)

Triggers when an active disruption exists. Renders below the dashboard's two columns.

- **Header strip:** big red banner with the disrupted flight and a one-line sentence.
- **Filter bar:** preferred departure window, max price slider, airline multi-select, direct-only checkbox, **sort by** dropdown (Best for you / Cheapest / Fastest / Earliest / Latest / Fewest stops), show count (3/5/10/15/20/30/50), compact-view checkbox.
- **Result list:** option cards (standard or compact view).
  - Standard card: airline name big, price big-right, route + duration + stops, severity badge top right ("Low risk · fits cleanly" etc.), expandable cascade table.
  - Compact card: one-row layout for scanning lots of options.
- **Book this option** button on each card opens the booking dialog.

---

### 4.9 Booking dialog (state, not a page)

A two-step modal that scrolls into view smoothly.

**Step 1 — Pay:**
- Info banner explaining SkySaver doesn't process payment directly.
- Two big buttons side by side:
  - Primary: `✈ Open {Airline}` (deep links with route + date pre-filled when supported)
  - Secondary: `🔎 Compare on Google Flights`
- A confirmation button: `✅ I've paid — show me Step 2`

**Step 2 — Confirm:**
- File uploader (PDF / PNG / JPG) — "Upload your booking confirmation, SkySaver will read it" — Gemini Vision OCR pre-fills the form.
- Confirmation reference text field (pre-filled if scanned).
- Payment method dropdown (pre-filled if scanned).
- Expandable "Show extracted details" reveals all OCR'd fields.
- `Save booking` primary button.

---

### 4.10 Chat assistant (component, lives in dashboard right column)

- Gradient header.
- Scrollable history with role-coded bubbles (user right-aligned indigo bubble, assistant left-aligned white bubble with subtle drop shadow).
- Typing indicator (three dots animating).
- Empty state with three example prompts as clickable chips.
- Chat input with rounded full pill, send button as gradient icon button.
- Each assistant message can have inline action buttons ("Open Uber ↗", "Open Booking.com ↗") rendered as little outlined buttons.

---

## 5. Components library

Generate these as a shared library. Each should have variants and states.

- **Button** — primary, secondary, ghost, danger, icon-only. States: default, hover, pressed, focus, disabled, loading.
- **Input** — text, email, password, number, search, date, time, currency. With label, helper text, error state.
- **Combobox** — for IATA airport autocomplete, async loading state.
- **Select** — single + multi.
- **Toggle** — pill style.
- **Slider** — with displayed value badge above the thumb.
- **Card** — base, with hover lift.
- **Modal / Dialog** — center-screen with backdrop blur, slide-up animation.
- **Toast** — top-right corner, slide-in from above.
- **Badge** — colored pill (success/warn/danger/info/neutral).
- **Avatar** — with optional status indicator dot.
- **Tabs** — pill style on light background.
- **Accordion / Expander** — chevron icon rotates 180° on open.
- **Date range picker** — calendar with quick-pick chips below.
- **Empty state** — illustration + headline + action button.
- **Skeleton loader** — pulse animation for cards and rows.

---

## 6. Iconography

Use **lucide-react** throughout. Specific mappings:
- Flight → `Plane`
- Hotel → `BedDouble`
- Transport → `Car`
- Meeting → `Calendar`
- Live tracking → `Activity` (with animated dot overlay)
- Search → `Search`
- Settings → `Settings2`
- User → `User`
- Notification → `Bell`
- Sign out → `LogOut`
- Edit → `PencilLine`
- Delete → `Trash2`

---

## 7. Responsive behavior

- **Desktop ≥ 1280px** — full two-column dashboard with chat side-rail.
- **Tablet 768–1280px** — collapse to single column; chat becomes a slide-out drawer from the right (FAB button).
- **Mobile < 768px** — bottom tab nav, single column, chat as a full-screen modal triggered by a floating button.

---

## 8. Technical stack

- **Framework:** Next.js 15 (App Router)
- **Styling:** Tailwind CSS + shadcn/ui base components, customized to match the brief
- **Icons:** lucide-react
- **Animations:** Framer Motion for page transitions, CSS for hover/loops
- **Charts:** Recharts (for any metrics over time)
- **State:** Zustand for client state, React Query for server cache
- **API client:** typed fetch wrappers calling the existing Python FastAPI backend
- **Auth:** the existing email/password + persistent session token (token stored in HttpOnly cookie now, not URL)

---

## 9. Backend integration contract

The Python backend exposes (or will expose via a FastAPI layer):

```
POST   /api/auth/signup           → { name, email, password }
POST   /api/auth/login            → { email, password }
POST   /api/auth/logout
GET    /api/me                    → user profile

GET    /api/trips                  → list of the user's trips
GET    /api/trips/{id}             → single trip with all legs
POST   /api/trips                  → create a new trip (full intake payload)
PATCH  /api/trips/{id}             → update trip-level fields
DELETE /api/trips/{id}

POST   /api/trips/{id}/legs        → add a leg
PATCH  /api/trips/{id}/legs/{leg_id}
DELETE /api/trips/{id}/legs/{leg_id}

POST   /api/trips/{id}/disruptions/simulate    → demo trigger
GET    /api/trips/{id}/disruptions             → history
POST   /api/trips/{id}/recover                 → execute a chosen alternative

GET    /api/flights/search?origin=&destination=&date=    → SerpAPI results
POST   /api/cascade                                      → cascade preview

POST   /api/chat                  → { message, history } → assistant response
POST   /api/scan-confirmation     → multipart file upload → extracted fields

GET    /api/preferences            → trip's preferences
PATCH  /api/preferences

GET    /api/admin/users            → admin: list signups + login activity
```

All endpoints return JSON with `{ ok: true|false, data, error }` shape.

---

## 10. Deliverables

1. **Next.js project** with all pages above implemented end-to-end.
2. **Components library** as a shared `/components` directory.
3. **Storybook** documenting each component's variants.
4. **CSS variables** for the design tokens listed in §3.
5. **Animations** as documented in §3.3.
6. **Responsive breakpoints** as documented in §7.
7. **Empty / loading / error states** for every async surface.
8. **Accessibility:** keyboard nav, focus rings, ARIA labels, color contrast AA minimum.
9. **Performance:** 90+ Lighthouse score on the landing.
10. **A Vercel preview deployment** for review.

---

## 11. Out of scope (for now)

- Real airline OAuth and live booking — we hand off to airline sites.
- Real-time flight status feed — we poll MongoDB every 10s and simulate for demos. Production swap-in is a FlightAware/Cirium integration.
- Mobile native apps — web responsive only.

---

## 12. Inspiration links

- **Stripe** — flowing gradient hero, motion, typography, generous whitespace
- **Linear** — sidebar nav, density, category color coding, microinteractions
- **Vercel** — bold typography, gradient text, dot grid backgrounds
- **Notion** — warmth, playful illustrations, conversational tone
- **Arc Browser** — organic color blending, rainbow accents
- **Cursor** — modern AI-product polish
- **Resend** — clean dashboards, status indicators
- **Raycast** — command-bar interactions, smooth animations

Match the *quality bar* of these products. The result should not look like a hackathon project. It should look like a venture-backed early-stage SaaS at Series A.
