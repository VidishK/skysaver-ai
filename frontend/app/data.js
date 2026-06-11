// SkySaver — runtime data layer.
//
// Originally this file shipped hardcoded sample data on window.SKY.
// Now it fetches the real trip + user from the backend on page load and
// patches window.SKY in place. The original mock is kept as a fallback so
// the marketing/landing pages still render even without a session.

(function () {
  // ---- Fallback mock used when not logged in or backend is down ----
  const MOCK_TRIP = {
    id: 'dxb-sin',
    title: 'Dubai → Singapore',
    origin: 'DXB',
    destinations: ['SIN'],
    dates: '14–17 Jun 2026',
    travelers: 1,
    legs: [
      { id: 'l1', type: 'flight', title: 'EK308 — DXB → SIN', carrier: 'Emirates', time: 'Sat 14 Jun · 22:00 → 09:30 UTC', meta: '$510 · Terminal 3 · Seat 14A', status: 'monitoring', statusLabel: 'On time', booked: true, code: 'EK308' },
      { id: 'l2', type: 'hotel',  title: 'Marina Bay Sands',  carrier: 'Hotel',    time: 'Check-in Sun 15 Jun · 14:00 → Tue 17 Jun · 11:00', meta: '$420/night · King · 2 nights', status: 'booked',     statusLabel: 'Booked',   booked: true,  code: 'MBS' },
      { id: 'l3', type: 'transport', title: 'Airport → Marina Bay', carrier: 'Grab', time: 'Sun 15 Jun · 10:00 SGT', meta: 'GrabCar Premium · ~$28', status: 'planned', statusLabel: 'Planned', booked: false, code: 'GRB' },
      { id: 'l4', type: 'meeting', title: 'Investor sync — Raffles Place', carrier: 'Meeting', time: 'Mon 16 Jun · 10:00 SGT', meta: 'Vantage Partners · 18h buffer', status: 'confirmed', statusLabel: 'Buffer 18h', booked: true, code: 'MTG' },
    ],
    metrics: { legs: 4, flights: 1, disruptions: 0 },
  };

  const MOCK_USER = { name: 'Maya', initials: 'MK', email: 'maya.kapoor@gmail.com', plan: 'Pro' };

  const MOCK_ACTIVITY = [
    { t: '09:41 UTC', text: 'Checked EK308 status — on time', tone: 'success' },
    { t: '09:31 UTC', text: 'Polled SerpAPI for DXB → SIN fares', tone: 'neutral' },
    { t: '08:00 UTC', text: 'Marina Bay Sands reservation confirmed', tone: 'info' },
    { t: 'Yesterday', text: 'Trip created · 4 legs added', tone: 'neutral' },
  ];

  const CHAT_SUGGESTIONS = [
    'What happens to my hotel if my flight is delayed 3 hours?',
    'Find me a lounge at the airport',
    'Move my ride pickup to 11am',
  ];

  // Hardcoded recovery alternatives as fallback. The disruption flow will
  // request live options from /api/flights/search when triggered.
  const MOCK_ALTERNATIVES = [
    { id: 'a1', airline: 'Singapore Airlines', flight: 'SQ305', price: 540, route: 'DXB → SIN', depart: '23:40', arrive: '11:05', duration: '7h 25m', stops: 0, severity: 'low',  severityLabel: 'Low risk · fits cleanly', score: 96, cascade: [{ leg: 'Hotel · Marina Bay Sands', effect: 'Check-in shifts 2h later — within free window', tone: 'info' }, { leg: 'Transport · Grab pickup', effect: 'Auto-rescheduled to 12:00 SGT', tone: 'info' }, { leg: 'Meeting · Investor sync', effect: 'Untouched — 16h buffer remains', tone: 'success' }] },
    { id: 'a2', airline: 'Qatar Airways',      flight: 'QR1376', price: 478, route: 'DXB → DOH → SIN', depart: '20:15', arrive: '13:50', duration: '11h 10m', stops: 1, severity: 'warn', severityLabel: 'Tight buffer · 1 stop', score: 81, cascade: [{ leg: 'Hotel · Marina Bay Sands', effect: 'Check-in shifts 4h later', tone: 'warn' }, { leg: 'Transport · Grab pickup', effect: 'Rescheduled to 14:30 SGT', tone: 'info' }, { leg: 'Meeting · Investor sync', effect: 'Buffer drops to 12h — still safe', tone: 'warn' }] },
    { id: 'a3', airline: 'Emirates',           flight: 'EK354',  price: 612, route: 'DXB → SIN',       depart: '03:10', arrive: '14:50', duration: '7h 40m',  stops: 0, severity: 'info', severityLabel: 'Shifts hotel night', score: 74, cascade: [{ leg: 'Hotel · Marina Bay Sands', effect: 'Loses night 1 — rebook needed (+$420)', tone: 'danger' }, { leg: 'Transport · Grab pickup', effect: 'Rescheduled to 15:30 SGT', tone: 'info' }, { leg: 'Meeting · Investor sync', effect: 'Untouched', tone: 'success' }] },
  ];

  const DISRUPTION = {
    legId: 'l1', flight: 'EK308', route: 'DXB → SIN',
    sentence: 'Your tracked flight was cancelled. SkySaver found alternatives that fit your trip.',
    detectedAt: '02:04 UTC',
  };

  // Empty trip placeholder — the mock above is ONLY for the recovery panel's
  // ALTERNATIVES fallback if SerpAPI returns nothing. Real users never see
  // the Dubai → Singapore demo unless they explicitly click "Load demo data".
  const EMPTY_TRIP = {
    id: '', title: '', origin: '', destinations: [], dates: '',
    travelers: 1, legs: [],
    metrics: { legs: 0, flights: 0, disruptions: 0 },
  };

  // Initial seed: empty trip + NO_TRIP=true. If the user has a real trip in
  // MongoDB, loadFromApi() overwrites these. Landing page / non-auth pages
  // never call loadFromApi(), so they're free to read these as-is.
  window.SKY = {
    TRIP: EMPTY_TRIP,
    USER: MOCK_USER,
    ACTIVITY: [],
    CHAT_SUGGESTIONS,
    ALTERNATIVES: MOCK_ALTERNATIVES,
    DISRUPTION,
    LOADED_FROM_API: false,
    NO_TRIP: true,
  };

  // ---- Helpers to convert a MongoDB trip → the shape this UI expects ----
  function fmtRange(start, end) {
    if (!start) return '';
    try {
      const a = new Date(start.replace('Z', '+00:00'));
      const b = end ? new Date(end.replace('Z', '+00:00')) : null;
      const opts = { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'UTC' };
      const left = new Intl.DateTimeFormat('en-GB', opts).format(a);
      const right = b ? new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' }).format(b) : '';
      return right ? `${left} → ${right} UTC` : left;
    } catch (e) { return start; }
  }

  function tripDates(legs) {
    if (!legs || !legs.length) return '';
    const starts = legs.map(l => l.start_at).filter(Boolean).sort();
    const ends   = legs.map(l => l.end_at).filter(Boolean).sort();
    if (!starts.length) return '';
    try {
      const opts = { day: 'numeric', month: 'short', year: 'numeric' };
      const a = new Date(starts[0].replace('Z', '+00:00'));
      const b = new Date(ends[ends.length - 1].replace('Z', '+00:00'));
      const fa = new Intl.DateTimeFormat('en-GB', opts).format(a);
      const fb = new Intl.DateTimeFormat('en-GB', opts).format(b);
      return `${fa} – ${fb}`;
    } catch (e) { return ''; }
  }

  function legToCard(l) {
    const type = l.type || 'meeting';
    let title = '', carrier = '', meta = '', code = l.flight_number || l.name || l.title || l.leg_id;
    if (type === 'flight') {
      const airline = (l.airline || '').toString();
      const fnum = (l.flight_number || '').toString();
      const label = fnum.toUpperCase().startsWith(airline.toUpperCase()) ? fnum : (airline + fnum);
      title = label + ' — ' + (l.origin || '?') + ' → ' + (l.destination || '?');
      carrier = airline || 'Airline';
      meta = '$' + (l.price_usd || '?') + ' · Terminal ' + (l.departure_terminal || '?');
    } else if (type === 'hotel') {
      title = l.name || 'Hotel';
      carrier = l.city || 'Hotel';
      meta = '$' + (l.total_usd || '?') + ' total' + (l.confirmation_code ? ' · ' + l.confirmation_code : '');
    } else if (type === 'transport') {
      title = (l.mode || 'Transport') + ' — ' + (l.from || '?') + ' → ' + (l.to || '?');
      carrier = (l.mode || 'Transport');
      meta = '~$' + (l.estimated_cost_usd || '?');
    } else if (type === 'meeting') {
      title = l.title || 'Meeting';
      carrier = 'Meeting';
      meta = (l.location || '') + (l.importance ? ' · ' + l.importance + ' importance' : '');
    }
    const statusMap = {
      scheduled:   { label: 'On time',     status: type === 'flight' ? 'monitoring' : 'planned' },
      in_progress: { label: 'In progress', status: 'monitoring' },
      completed:   { label: 'Completed',   status: 'booked' },
      rebooked:    { label: 'Rebooked',    status: 'booked' },
      disrupted:   { label: 'Disrupted',   status: 'monitoring' },
      cancelled:   { label: 'Cancelled',   status: 'monitoring' },
    };
    const sm = statusMap[l.status || 'scheduled'] || statusMap.scheduled;
    return {
      id: l.leg_id, type, title, carrier,
      time: fmtRange(l.start_at, l.end_at),
      meta, status: sm.status, statusLabel: sm.label, booked: !!l.booking_reference, code,
      rawStatus: l.status || 'scheduled',
      origin: l.origin, destination: l.destination, start_at: l.start_at, end_at: l.end_at,
    };
  }

  function tripToView(t) {
    if (!t || !t.legs) return null;
    const legs = t.legs.map(legToCard);
    const flights = legs.filter(l => l.type === 'flight').length;
    const firstFlight = t.legs.find(l => l.type === 'flight') || {};
    return {
      id: t._id, title: t.title || 'My trip',
      origin: firstFlight.origin || '',
      destinations: [firstFlight.destination || ''].filter(Boolean),
      dates: tripDates(t.legs),
      travelers: (t.travelers && t.travelers.adults) || 1,
      legs, metrics: { legs: legs.length, flights, disruptions: (t.disruption_history || []).length },
      raw: t,
    };
  }

  function activityFromTrip(t) {
    if (!t || !t.disruption_history || !t.disruption_history.length) return MOCK_ACTIVITY;
    return t.disruption_history.slice(-6).reverse().map(d => ({
      t: (d.detected_at || '').slice(11, 16) + ' UTC',
      text: d.details || `${d.disruption_type} on ${d.affected_leg_id}`,
      tone: d.disruption_type === 'cancelled' ? 'danger' : d.disruption_type === 'recovered' ? 'success' : 'info',
    }));
  }

  window.skyHelpers = { tripToView, activityFromTrip, legToCard };

  // ---- Boot: try to fetch the real user + trip, fall back silently ----
  async function loadFromApi() {
    if (!window.SkyAPI) return;
    let isLoggedIn = false;
    try {
      const meRes = await window.SkyAPI.auth.me();
      if (meRes && meRes.user) {
        isLoggedIn = true;
        window.SKY.USER = {
          name: meRes.user.name || 'Traveller',
          initials: meRes.user.initials || 'U',
          email: meRes.user.email || '',
          plan: meRes.user.plan || 'Free',
        };
      }
    } catch (_) { /* not logged in */ }

    if (isLoggedIn) {
      try {
        const tripRes = await window.SkyAPI.trip.get();
        const trip = tripRes && tripRes.trip;
        const view = tripToView(trip);
        if (view && view.legs && view.legs.length) {
          // Real trip → render it.
          window.SKY.TRIP = view;
          window.SKY.ACTIVITY = activityFromTrip(trip);
          window.SKY.LOADED_FROM_API = true;
          window.SKY.NO_TRIP = false;
        } else {
          // Logged-in but no trip → stay on empty state.
          window.SKY.NO_TRIP = true;
          window.SKY.LOADED_FROM_API = true;
        }
      } catch (_) {
        // API unreachable — keep empty state rather than leak the mock.
        window.SKY.NO_TRIP = true;
      }
      window.dispatchEvent(new CustomEvent('sky:trip-loaded', { detail: window.SKY.TRIP }));
    }
  }

  if (typeof document !== 'undefined' && document.readyState !== 'loading') {
    loadFromApi();
  } else if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', loadFromApi);
  }
})();
