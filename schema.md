# SkySaver AI — MongoDB Trip Schema

This document describes the shape of a `trip` document stored in MongoDB. Every trip the agent manages is one document in the `trips` collection of the `skysaver` database.

The shape is intentionally rich because the agent needs to reason about more than just flights — it needs to know about hotels, ground transport, meetings, and how each piece relates to the others, so it can compute "cascade impact" when a flight changes.

## Collection layout

- Database: `skysaver`
- Collection: `trips`
- One document per trip

## Top-level trip document

```jsonc
{
  "_id": "trip_001",                           // string ID we set ourselves (easier than ObjectId for demos)
  "user_id": "user_vidish",                    // who owns the trip
  "title": "Singapore Business Trip",          // human-readable label
  "status": "active",                          // active | completed | cancelled
  "created_at": "2026-05-26T18:00:00Z",
  "updated_at": "2026-05-26T18:00:00Z",

  "preferences": { ... },                      // see "Preferences" below
  "legs": [ ... ],                             // ordered list of trip legs (see "Legs")
  "disruption_history": [ ... ]                // log of every disruption + recovery
}
```

## Preferences

Captured once during onboarding. The agent reads these to rank alternative flights.

```jsonc
"preferences": {
  "budget_sensitivity": "medium",              // low | medium | high (how much price matters)
  "prefers_direct": true,                      // dislikes layovers
  "preferred_airlines": ["SQ", "EK", "BA"],    // IATA codes, in order of preference
  "avoid_airlines": [],                        // never recommend these
  "max_layover_hours": 4,
  "preferred_arrival_window": "morning",       // morning | afternoon | evening | any
  "seat_class": "economy",                     // economy | premium_economy | business | first
  "checked_baggage": true,
  "loyalty_programs": {
    "SQ": "KrisFlyer-1234567"
  }
}
```

## Legs

A leg is one piece of the trip. Legs are stored in time order. There are four leg types: `flight`, `hotel`, `transport`, `meeting`. They share a few common fields and have their own type-specific fields.

### Common to all legs

```jsonc
{
  "leg_id": "leg_001",                         // unique within trip
  "type": "flight",                            // flight | hotel | transport | meeting
  "status": "scheduled",                       // scheduled | in_progress | completed | disrupted | cancelled | rebooked
  "start_at": "2026-05-27T09:25:00Z",          // ISO 8601, UTC
  "end_at":   "2026-05-27T19:55:00Z",
  "notes": ""
}
```

### Flight leg

```jsonc
{
  "leg_id": "leg_001",
  "type": "flight",
  "status": "scheduled",
  "start_at": "2026-05-27T09:25:00Z",
  "end_at":   "2026-05-27T19:55:00Z",

  "airline": "SQ",
  "flight_number": "SQ305",
  "origin": "LHR",
  "destination": "SIN",
  "departure_terminal": "2",
  "arrival_terminal": "3",
  "stops": 0,
  "duration_minutes": 770,
  "price_usd": 946,
  "currency": "USD",
  "booking_reference": null,                   // filled in after booking
  "booking_method": null,                      // duffel_sandbox | deep_link | mock
  "ticket_class": "economy"
}
```

### Hotel leg

```jsonc
{
  "leg_id": "leg_002",
  "type": "hotel",
  "status": "scheduled",
  "start_at": "2026-05-28T15:00:00Z",          // check-in
  "end_at":   "2026-05-30T11:00:00Z",          // check-out

  "name": "Marina Bay Sands",
  "city": "Singapore",
  "address": "10 Bayfront Avenue, Singapore",
  "confirmation_code": "MBS-99281",
  "nightly_rate_usd": 420,
  "total_usd": 840
}
```

### Transport leg

Ground transport between airport and hotel, or hotel and meeting.

```jsonc
{
  "leg_id": "leg_003",
  "type": "transport",
  "status": "scheduled",
  "start_at": "2026-05-28T06:00:00Z",
  "end_at":   "2026-05-28T06:45:00Z",

  "mode": "taxi",                              // taxi | train | rental_car | rideshare | private_transfer
  "from": "Changi Airport T3",
  "to":   "Marina Bay Sands",
  "estimated_cost_usd": 35
}
```

### Meeting leg

Meetings the user has during the trip — important because flight changes can put these at risk.

```jsonc
{
  "leg_id": "leg_004",
  "type": "meeting",
  "status": "scheduled",
  "start_at": "2026-05-29T10:00:00Z",
  "end_at":   "2026-05-29T11:30:00Z",

  "title": "Q3 review with Acme APAC",
  "location": "Acme Singapore HQ, 1 Raffles Place",
  "attendees": ["alice@acme.com", "bob@acme.com"],
  "importance": "high",                        // low | medium | high (used when scoring cascade impact)
  "buffer_before_minutes": 90                  // minimum buffer needed before this meeting
}
```

## Disruption history

Every time the agent detects and recovers from a disruption, it logs the event here. This becomes the agent's memory for future preference learning and gives judges something tangible to point at during the demo.

```jsonc
"disruption_history": [
  {
    "disruption_id": "dis_001",
    "detected_at": "2026-05-27T07:14:00Z",
    "affected_leg_id": "leg_001",
    "disruption_type": "cancelled",            // cancelled | delayed | gate_change | missed_connection
    "details": "Flight DL482 cancelled by airline due to crew issue",

    "alternatives_considered": [               // top 3 the agent evaluated
      { "summary": "SQ305 direct, $946, 4.5h meeting buffer", "score": 0.92 },
      { "summary": "SQ317 direct, $964, 2.5h meeting buffer", "score": 0.78 },
      { "summary": "EK8 + EK314 via DXB, $1120, critical risk", "score": 0.41 }
    ],
    "chosen_alternative": "SQ305 direct, $946, 4.5h meeting buffer",
    "user_confirmed_at": "2026-05-27T07:15:30Z",
    "booking_method": "duffel_sandbox",
    "new_booking_reference": "ORD-X9P2KL",

    "cascade_changes": [                       // what else changed as a result
      { "leg_id": "leg_002", "field": "start_at", "from": "2026-05-28T15:00:00Z", "to": "2026-05-28T14:00:00Z" },
      { "leg_id": "leg_004", "field": "buffer_before_minutes", "from": 90, "to": 270 }
    ]
  }
]
```

## Design choices and why

**Why one document per trip, not one per leg?**
Trips are read and written together. MongoDB's document model is exactly right when a single conceptual entity has nested structure — the agent almost always wants the whole trip, never just one leg in isolation. Storing legs as an embedded array keeps reads to one query.

**Why string IDs (`trip_001`) instead of ObjectIds?**
Demo-friendly and easier to talk about during the pitch. We're not under any scale pressure for the hackathon — readability beats convention.

**Why store preferences inline instead of in a separate users collection?**
For the hackathon scope, every trip has one user and preferences are small. Keeping them inline means the agent reads everything it needs in one query. A real production system would split them out.

**Why a disruption_history array?**
Two reasons. First, it's the agent's "what happened on this trip" memory — useful if the user asks "what changed last week?" Second, it's a compelling thing to display in the demo: judges see a tangible record of agentic decisions.
