// SkySaver — typed fetch client used by every page.
// Lives on window.SkyAPI. Sends cookies automatically (HttpOnly session).

(function () {
  const BASE = '';

  async function request(path, opts = {}) {
    const init = {
      credentials: 'include',
      headers: {
        Accept: 'application/json',
        ...(opts.body && !(opts.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}),
        ...(opts.headers || {}),
      },
      method: opts.method || 'GET',
    };
    if (opts.body !== undefined) {
      init.body = opts.body instanceof FormData ? opts.body : JSON.stringify(opts.body);
    }
    const res = await fetch(BASE + path, init);
    let body = null;
    try {
      body = await res.json();
    } catch (_) {
      body = null;
    }
    if (!res.ok) {
      const message = (body && (body.detail || body.error)) || res.statusText || `HTTP ${res.status}`;
      const err = new Error(message);
      err.status = res.status;
      err.body = body;
      throw err;
    }
    return body;
  }

  // ---- Auth ----
  async function signup(name, email, password) { return request('/api/auth/signup', { method: 'POST', body: { name, email, password } }); }
  async function login(email, password)         { return request('/api/auth/login',  { method: 'POST', body: { email, password } }); }
  async function logout()                       { return request('/api/auth/logout', { method: 'POST' }); }
  async function me()                            { return request('/api/me'); }

  // ---- Trip ----
  async function getTrip()                       { return request('/api/trip'); }
  async function createTrip(title, intake)       { return request('/api/trip', { method: 'POST', body: { title, intake } }); }
  async function seedDemo()                      { return request('/api/trip/seed-demo', { method: 'POST' }); }
  async function patchLeg(legId, changes)        { return request('/api/trip/legs/' + encodeURIComponent(legId), { method: 'PATCH', body: { changes } }); }
  async function addLeg(leg)                     { return request('/api/trip/legs', { method: 'POST', body: { leg } }); }
  async function deleteLeg(legId)                { return request('/api/trip/legs/' + encodeURIComponent(legId), { method: 'DELETE' }); }
  async function simulateCancellation(legId)     { return request('/api/trip/simulate-cancellation/' + encodeURIComponent(legId), { method: 'POST' }); }
  async function deleteTrip()                    { return request('/api/trip', { method: 'DELETE' }); }

  // ---- Flights ----
  async function searchFlights(origin, destination, date) {
    const qs = new URLSearchParams({ origin, destination, date });
    return request('/api/flights/search?' + qs.toString());
  }

  async function previewCascade(affectedLegId, replacement) {
    return request('/api/cascade', { method: 'POST', body: { affected_leg_id: affectedLegId, replacement } });
  }

  // ---- Chat ----
  async function chat(message, history) {
    return request('/api/chat', { method: 'POST', body: { message, history: history || [] } });
  }

  // ---- OCR ----
  async function scanConfirmation(file) {
    const fd = new FormData();
    fd.append('file', file);
    return request('/api/scan-confirmation', { method: 'POST', body: fd });
  }

  // ---- Deep links ----
  async function deepLinkAirline(params) {
    const qs = new URLSearchParams(params || {}).toString();
    return request('/api/deep-link/airline?' + qs);
  }
  async function deepLinkGoogleFlights(origin, destination, date) {
    const qs = new URLSearchParams({ origin, destination, ...(date ? { date } : {}) });
    return request('/api/deep-link/google-flights?' + qs.toString());
  }
  async function deepLinkUber(pickup, dropoff) {
    const qs = new URLSearchParams({ pickup: pickup || '', dropoff: dropoff || '' });
    return request('/api/deep-link/uber?' + qs.toString());
  }
  async function deepLinkHotel(name, city) {
    const qs = new URLSearchParams({ name: name || '', city: city || '' });
    return request('/api/deep-link/hotel?' + qs.toString());
  }

  window.SkyAPI = {
    request,
    auth: { signup, login, logout, me },
    trip: { get: getTrip, create: createTrip, seedDemo, patchLeg, addLeg, deleteLeg, simulateCancellation, deleteTrip },
    flights: { search: searchFlights, previewCascade },
    chat,
    scanConfirmation,
    links: { airline: deepLinkAirline, googleFlights: deepLinkGoogleFlights, uber: deepLinkUber, hotel: deepLinkHotel },
  };
})();
