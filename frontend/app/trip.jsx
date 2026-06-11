// SkySaver — Trip details
const { useState, useEffect } = React;

const TYPES = [
  { id: 'flight', label: 'Flight', icon: 'plane', ink: 'var(--flight-ink)', bg: 'var(--flight-to)' },
  { id: 'hotel', label: 'Hotel', icon: 'bed', ink: 'var(--hotel-ink)', bg: 'var(--hotel-to)' },
  { id: 'transport', label: 'Transport', icon: 'car', ink: 'var(--transport-ink)', bg: 'var(--transport-to)' },
  { id: 'meeting', label: 'Meeting', icon: 'calendar', ink: 'var(--meeting-ink)', bg: 'var(--meeting-to)' },
];

function AddLeg({ onAdd }) {
  const [open, setOpen] = useState(false);
  const [type, setType] = useState(null);
  if (!open) return (
    <button className="btn btn-primary" onClick={() => setOpen(true)} style={{ marginBottom: 20 }}>
      <Icon name="plus" size={17} /> Add a new leg
    </button>
  );
  return (
    <div className="card card-pad" style={{ marginBottom: 22 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <b style={{ fontSize: 15 }}>What are you adding?</b>
        <button className="modal-close" onClick={() => { setOpen(false); setType(null); }}><Icon name="x" size={18} /></button>
      </div>
      <div className="type-picker">
        {TYPES.map(t => (
          <div key={t.id} className={'type-opt' + (type === t.id ? ' sel' : '')} onClick={() => setType(t.id)}>
            <div className="to-ic" style={{ background: t.bg, color: t.ink }}><Icon name={t.icon} size={22} /></div>
            <b>{t.label}</b>
          </div>
        ))}
      </div>
      {type && (
        <div style={{ marginTop: 20 }}>
          <div className="form-grid">
            {type === 'flight' && <>
              <div className="ff"><label>Flight number</label><input placeholder="e.g. EK308" /></div>
              <div className="ff"><label>Carrier</label><input placeholder="Emirates" /></div>
              <div className="ff"><label>From</label><input placeholder="DXB" /></div>
              <div className="ff"><label>To</label><input placeholder="SIN" /></div>
            </>}
            {type === 'hotel' && <>
              <div className="ff full"><label>Hotel name</label><input placeholder="Marina Bay Sands" /></div>
              <div className="ff"><label>Check-in</label><input placeholder="15 Jun · 14:00" /></div>
              <div className="ff"><label>Check-out</label><input placeholder="17 Jun · 11:00" /></div>
            </>}
            {type === 'transport' && <>
              <div className="ff"><label>Mode</label><select><option>GrabCar</option><option>Uber</option><option>Rental</option></select></div>
              <div className="ff"><label>When</label><input placeholder="15 Jun · 10:00" /></div>
              <div className="ff full"><label>Route</label><input placeholder="Changi Airport → Marina Bay" /></div>
            </>}
            {type === 'meeting' && <>
              <div className="ff full"><label>Title</label><input placeholder="Investor sync" /></div>
              <div className="ff"><label>Date</label><input placeholder="16 Jun" /></div>
              <div className="ff"><label>Time</label><input placeholder="10:00" /></div>
            </>}
          </div>
          <button className="btn btn-primary btn-sm" style={{ marginTop: 16 }} onClick={() => { onAdd(); setOpen(false); setType(null); }}>
            <Icon name="check" size={15} /> Add leg
          </button>
        </div>
      )}
    </div>
  );
}

// Real Confirm-booking panel: takes airline + flight number + PNR + seat + fare,
// PATCHes the leg, and reloads so the dashboard flips to "Booked" and the
// "Manage flight" deep link points at the right carrier.
function ExternalFlightBooking({ leg }) {
  const existingCode = leg.code || '';
  // Try to split "EK308" → ("EK", "308") for the prefilled airline + number.
  const m = existingCode.match(/^([A-Z]{2})\s*[·\.\-]?\s*(\d{1,5})/i);
  const [airlineCode, setAirlineCode] = useState(m ? m[1].toUpperCase() : '');
  const [flightNum, setFlightNum] = useState(m ? m[2] : '');
  const [pnr, setPnr] = useState('');
  const [seat, setSeat] = useState('');
  const [fare, setFare] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [open, setOpen] = useState(!leg.booked);

  // Common airline name lookup so the saved record carries a proper name
  // (the dashboard derives the deep link from the 2-letter code anyway).
  const AIRLINE_NAMES = {
    EK: 'Emirates', SQ: 'Singapore Airlines', BA: 'British Airways',
    QR: 'Qatar Airways', AI: 'Air India', AF: 'Air France', KL: 'KLM',
    LH: 'Lufthansa', TK: 'Turkish Airlines', ET: 'Ethiopian Airlines',
    EY: 'Etihad', SV: 'Saudia', DL: 'Delta', AA: 'American Airlines',
    UA: 'United', AC: 'Air Canada', CX: 'Cathay Pacific', JL: 'Japan Airlines',
    NH: 'ANA', KE: 'Korean Air', TG: 'Thai Airways', MH: 'Malaysia Airlines',
    GA: 'Garuda Indonesia', '6E': 'IndiGo', FZ: 'flydubai', MS: 'EgyptAir',
    QF: 'Qantas',
  };

  async function confirm() {
    const code = (airlineCode || '').trim().toUpperCase();
    const num = (flightNum || '').trim();
    if (!code || !num) { setError('Airline code and flight number are required.'); return; }
    if (!pnr.trim()) { setError('PNR / confirmation code is required to mark this as booked.'); return; }
    setError(''); setSaving(true);
    try {
      await window.SkyAPI.trip.patchLeg(leg.id, {
        airline: AIRLINE_NAMES[code] || code,
        airline_code: code,
        flight_number: code + num,
        booking_reference: pnr.trim(),
        seat: seat.trim() || null,
        price_usd: fare ? parseFloat(fare) : 0,
        currency: 'USD',
        status: 'completed',
        booking_method: 'external',
      });
      window.location.reload();
    } catch (e) {
      setError(e.message || 'Could not save — please retry.');
      setSaving(false);
    }
  }

  if (leg.booked) {
    return (
      <div style={{ marginTop: 14, padding: 14, background: '#ECFDF5', border: '1px solid #A7F3D0', borderRadius: 12, display: 'flex', alignItems: 'center', gap: 10 }}>
        <Icon name="check" size={16} style={{ color: 'var(--emerald-500)' }} />
        <div style={{ flex: 1, fontSize: 13.5, color: '#065F46' }}>
          <b>{leg.code || 'Booked'}</b> — SkySaver is watching this flight. Open it from the dashboard with “Manage flight”.
        </div>
        <button className="btn btn-ghost btn-sm" onClick={() => setOpen(o => !o)}>{open ? 'Hide' : 'Edit'}</button>
      </div>
    );
  }

  return (
    <div className="confirm-booking" style={{ marginTop: 14, padding: 16, background: 'var(--slate-50)', border: '1px solid var(--slate-200)', borderRadius: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
        <Icon name="check" size={16} style={{ color: 'var(--indigo-500)' }} />
        <b style={{ fontSize: 14 }}>I booked this externally — confirm to start the watch</b>
      </div>
      <div className="form-grid">
        <div className="ff"><label>Airline (IATA code)</label>
          <input value={airlineCode} onChange={e => setAirlineCode(e.target.value.toUpperCase().slice(0, 3))} placeholder="EK" maxLength={3} />
        </div>
        <div className="ff"><label>Flight number</label>
          <input value={flightNum} onChange={e => setFlightNum(e.target.value.replace(/\D/g, '').slice(0, 5))} placeholder="308" />
        </div>
        <div className="ff"><label>Confirmation / PNR</label>
          <input value={pnr} onChange={e => setPnr(e.target.value.toUpperCase())} placeholder="SQ-7K2P9X" />
        </div>
        <div className="ff"><label>Seat (optional)</label>
          <input value={seat} onChange={e => setSeat(e.target.value)} placeholder="14A" />
        </div>
        <div className="ff full"><label>Fare paid (USD)</label>
          <input value={fare} onChange={e => setFare(e.target.value)} placeholder="540" type="number" />
        </div>
      </div>
      {error && (
        <div style={{ marginTop: 10, padding: '8px 12px', background: '#FEF2F2', border: '1px solid #FECACA', color: '#B91C1C', borderRadius: 8, fontSize: 13 }}>
          {error}
        </div>
      )}
      <div style={{ display: 'flex', gap: 10, marginTop: 14, alignItems: 'center' }}>
        <button className="btn btn-primary" onClick={confirm} disabled={saving}>
          <Icon name="check" size={16} /> {saving ? 'Saving…' : 'Confirm booking'}
        </button>
        <span style={{ fontSize: 12.5, color: 'var(--slate-500)' }}>
          We'll start watching this flight 24/7. The dashboard will show "Manage flight" linking straight to {AIRLINE_NAMES[airlineCode] || 'your carrier'}.
        </span>
      </div>
    </div>
  );
}

// Live Google Flights finalize — shows real options for THIS leg's route+date,
// with times, duration, stops, and a "View on Google Flights" link.
function FlightFinalize({ leg }) {
  const [options, setOptions] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [picking, setPicking] = useState('');

  // Derive route + date — prefer the structured fields, fall back to parsing title.
  const titleMatch = (leg.title || '').match(/([A-Z]{3})\s*→\s*([A-Z]{3})/);
  const origin = leg.origin || (titleMatch && titleMatch[1]) || '';
  const destination = leg.destination || (titleMatch && titleMatch[2]) || '';
  const isoDate = (leg.start_at || '').slice(0, 10)
    || new Date(Date.now() + 7 * 24 * 3600 * 1000).toISOString().slice(0, 10);

  const gflightsUrl = (origin && destination)
    ? `https://www.google.com/travel/flights?q=${encodeURIComponent('Flights from ' + origin + ' to ' + destination + ' on ' + isoDate)}`
    : 'https://www.google.com/travel/flights';

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!origin || !destination) { setLoading(false); return; }
      try {
        const res = await window.SkyAPI.flights.search(origin, destination, isoDate);
        if (cancelled) return;
        setOptions((res && res.options) || []);
      } catch (e) {
        if (!cancelled) setError(e.message || 'Search unavailable');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [origin, destination, isoDate]);

  function fmtDuration(mins) {
    if (!mins) return '';
    return Math.floor(mins / 60) + 'h ' + (mins % 60) + 'm';
  }

  async function selectOption(opt) {
    setPicking(opt.flight_number || opt.airline);
    try {
      const code = (opt.airline_code || (opt.flight_number || '').slice(0, 2) || '').toUpperCase();
      await window.SkyAPI.trip.patchLeg(leg.id, {
        airline: opt.airline || '',
        airline_code: code,
        flight_number: opt.flight_number || '',
        origin, destination,
        stops: opt.stops || 0,
        duration_minutes: opt.duration_minutes || 0,
        price_usd: opt.price_usd || 0,
        currency: 'USD',
        status: 'confirmed',
        booking_method: 'pending',
      });
      window.location.reload();
    } catch (e) {
      alert('Could not save selection: ' + (e.message || e));
      setPicking('');
    }
  }

  return (
    <div className="finalize">
      <div className="finalize-h" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Icon name="search" size={15} style={{ color: 'var(--indigo-500)' }} />
        <span>Find &amp; finalize — live Google Flights</span>
        <span style={{ flex: 1 }} />
        <a className="btn btn-ghost btn-sm" href={gflightsUrl} target="_blank" rel="noopener noreferrer"
           onClick={e => { try { window.open(gflightsUrl, '_blank', 'noopener,noreferrer'); e.preventDefault(); } catch (_) {} }}>
          <Icon name="arrowUpRight" size={13} /> View on Google Flights
        </a>
      </div>

      {loading && (
        <div style={{ padding: 18, textAlign: 'center', color: 'var(--slate-400)', fontSize: 13.5 }}>
          <span className="ping" style={{ marginRight: 8 }}><i /></span>
          Searching {origin || '?'} → {destination || '?'} on {isoDate}…
        </div>
      )}

      {!loading && error && (
        <div style={{ padding: 14, fontSize: 13, color: '#B45309', background: '#FFFBEB', border: '1px solid #FDE68A', borderRadius: 10 }}>
          Search unavailable: {error}. Open Google Flights above to browse directly.
        </div>
      )}

      {!loading && !error && options && options.length === 0 && (
        <div style={{ padding: 14, fontSize: 13, color: 'var(--slate-500)' }}>
          No live results for this route on {isoDate}. Try Google Flights for the full list.
        </div>
      )}

      {!loading && options && options.map((o, i) => {
        const stopsLabel = (o.stops || 0) === 0 ? 'nonstop' : (o.stops + (o.stops === 1 ? ' stop' : ' stops'));
        const isPicking = picking === (o.flight_number || o.airline);
        return (
          <div key={i} className="flight-result" style={{ flexWrap: 'wrap', gap: 12, alignItems: 'stretch' }}>
            <div style={{ flex: '1 1 280px', minWidth: 0 }}>
              <div className="fr-air" style={{ fontWeight: 600 }}>
                {o.airline || 'Airline'} · {o.flight_number || ''}
              </div>
              <div style={{ fontSize: 12.5, color: 'var(--slate-500)', marginTop: 3 }}>
                {o.origin || origin} → {o.destination || destination} · {stopsLabel}
                {o.duration_minutes ? ' · ' + fmtDuration(o.duration_minutes) : ''}
              </div>
              <div style={{ display: 'flex', gap: 14, fontSize: 13, marginTop: 6, color: 'var(--slate-700)' }}>
                {o.departure_time && <span><b>{o.departure_time}</b> <span style={{ color: 'var(--slate-400)' }}>dep</span></span>}
                {o.arrival_time && <span><b>{o.arrival_time}</b> <span style={{ color: 'var(--slate-400)' }}>arr</span></span>}
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
              <span className="fr-price">${o.price_usd || 0}</span>
              <span style={{ fontSize: 11, color: 'var(--slate-400)' }}>per traveler</span>
            </div>
            <button className="btn btn-primary btn-sm" disabled={isPicking} onClick={() => selectOption(o)} style={{ alignSelf: 'center' }}>
              {isPicking ? 'Saving…' : 'Select'}
            </button>
          </div>
        );
      })}
    </div>
  );
}

function HotelEditor({ leg }) {
  const [hotelLink, setHotelLink] = useState('');
  const cityGuess = (() => {
    const t = (leg.title || '') + ' ' + (leg.meta || '');
    if (/marina bay sands|singapore/i.test(t)) return 'Singapore';
    if (/dubai|burj/i.test(t)) return 'Dubai';
    if (/london|hyde|kensington/i.test(t)) return 'London';
    return '';
  })();

  useEffect(() => {
    (async () => {
      try {
        const r = await window.SkyAPI.links.hotel(leg.title || '', cityGuess);
        if (r && r.url) setHotelLink(r.url);
      } catch (_) {}
    })();
  }, [leg.title]);

  return (
    <div className="tl-editor">
      <div className="form-grid" style={{ marginTop: 14 }}>
        <div className="ff full"><label>Hotel name</label><input defaultValue={leg.title} /></div>
        <div className="ff"><label>City</label><input defaultValue={cityGuess} placeholder="Singapore" /></div>
        <div className="ff"><label>Star rating</label>
          <select defaultValue="5"><option>3 ★</option><option>4 ★</option><option>5 ★</option></select>
        </div>
        <div className="ff full"><label>Address</label><input placeholder="10 Bayfront Avenue, Singapore 018956" /></div>
        <div className="ff"><label>Check-in</label><input defaultValue={(leg.time || '').split('→')[0]} /></div>
        <div className="ff"><label>Check-out</label><input defaultValue={(leg.time || '').split('→')[1] || ''} /></div>
        <div className="ff"><label>Room type</label>
          <select defaultValue="king"><option value="standard">Standard · Queen</option><option value="king">King</option><option value="suite">Suite</option><option value="executive">Executive</option></select>
        </div>
        <div className="ff"><label>Nightly rate (USD)</label><input defaultValue="420" type="number" min="0" step="10" /></div>
        <div className="ff"><label>Nights</label><input defaultValue="2" type="number" min="1" /></div>
        <div className="ff"><label>Total (USD)</label><input defaultValue="840" type="number" min="0" step="10" /></div>
        <div className="ff full"><label>Amenities (toggle as needed)</label>
          <div style={{ display:'flex', flexWrap:'wrap', gap:8, marginTop:4 }}>
            {['Breakfast','Wi-Fi','Pool','Spa','Gym','Quiet floor','Late check-out','Smoking room'].map(a => (
              <button key={a} type="button" className="pw-chip">{a}</button>
            ))}
          </div>
        </div>
        <div className="ff full"><label>Notes</label><input defaultValue={leg.meta} placeholder="Anything SkySaver should remember" /></div>
      </div>

      <div className="finalize" style={{ marginTop: 18 }}>
        <div className="finalize-h"><Icon name="search" size={15} style={{ color: 'var(--indigo-500)' }} /> Manage this stay</div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 10 }}>
          <a className="btn btn-ghost btn-sm" href={hotelLink || '#'} target="_blank" rel="noopener noreferrer"
             onClick={e => { if (!hotelLink) e.preventDefault(); }}>
            <Icon name="search" size={14} /> View on Booking.com {!hotelLink && '(loading…)'}
          </a>
          <a className="btn btn-ghost btn-sm" href={'https://www.airbnb.com/s/' + encodeURIComponent(cityGuess || leg.title || '') + '/homes'} target="_blank" rel="noopener noreferrer">
            <Icon name="search" size={14} /> Open Airbnb
          </a>
          <a className="btn btn-ghost btn-sm" href={'https://www.google.com/maps/search/' + encodeURIComponent(leg.title || '')} target="_blank" rel="noopener noreferrer">
            <Icon name="mapPin" size={14} /> View on map
          </a>
        </div>
      </div>

      <details style={{ marginTop: 14 }}>
        <summary style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--slate-600)', cursor: 'pointer' }}>I booked this externally — enter confirmation</summary>
        <div className="form-grid" style={{ marginTop: 12 }}>
          <div className="ff"><label>Confirmation code</label><input placeholder="MBS-99281" /></div>
          <div className="ff"><label>Total paid (USD)</label><input placeholder="840" type="number" /></div>
        </div>
      </details>
    </div>
  );
}

function TimelineLeg({ leg }) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState('finalize');
  return (
    <div className="tl-item">
      <div className={'tl-node ' + leg.type}><Icon name={{ flight: 'plane', hotel: 'bed', transport: 'car', meeting: 'calendar' }[leg.type]} size={13} /></div>
      <div className="tl-card">
        <div className={'tl-card-head' + (open ? ' open' : '')} onClick={() => setOpen(o => !o)}>
          <div className="tt"><b>{leg.title}</b><span>{leg.time}</span></div>
          <Badge tone={leg.booked ? 'success' : 'warn'}>{leg.booked ? 'Booked' : 'Unbooked'}</Badge>
          <Icon name="chevronDown" size={18} className="chev" />
        </div>
        {open && (leg.type === 'hotel' ? <HotelEditor leg={leg} /> :
          <div className="tl-editor">
            <div className="form-grid" style={{ marginTop: 14 }}>
              <div className="ff"><label>Title</label><input defaultValue={leg.title} /></div>
              <div className="ff"><label>Time</label><input defaultValue={leg.time} /></div>
              <div className="ff full"><label>Notes / meta</label><input defaultValue={leg.meta} /></div>
            </div>

            {/* Flight-specific finalize panel — real Google Flights via SerpAPI */}
            {leg.type === 'flight' && !leg.booked && <FlightFinalize leg={leg} />}

            {/* Real Confirm-booking — PATCHes the leg and flips it to "Booked" */}
            {leg.type === 'flight' && <ExternalFlightBooking leg={leg} />}

            {leg.type === 'transport' && (
              <details style={{ marginTop: 14 }}>
                <summary style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--slate-600)', cursor: 'pointer' }}>I booked this externally — enter ride details</summary>
                <div className="form-grid" style={{ marginTop: 12 }}>
                  <div className="ff"><label>Provider</label>
                    <select><option>GrabCar</option><option>Uber</option><option>Lyft</option><option>Bolt</option><option>Ola</option><option>Local taxi</option><option>Rental car</option></select>
                  </div>
                  <div className="ff"><label>Booking ref (optional)</label><input placeholder="GR-2K4P9" /></div>
                  <div className="ff"><label>Vehicle tier</label>
                    <select><option>Economy</option><option>Comfort</option><option>Premium</option><option>XL</option></select>
                  </div>
                  <div className="ff"><label>Fare (USD)</label><input placeholder="28" type="number" /></div>
                </div>
              </details>
            )}

            {leg.type === 'meeting' && (
              <details style={{ marginTop: 14 }}>
                <summary style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--slate-600)', cursor: 'pointer' }}>Meeting details</summary>
                <div className="form-grid" style={{ marginTop: 12 }}>
                  <div className="ff full"><label>Location</label><input placeholder="1 Raffles Place, Singapore" /></div>
                  <div className="ff"><label>Importance</label>
                    <select defaultValue="high"><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select>
                  </div>
                  <div className="ff"><label>Required buffer (min)</label><input placeholder="90" type="number" /></div>
                  <div className="ff full"><label>Attendees (comma-separated emails)</label><input placeholder="alice@acme.com, bob@acme.com" /></div>
                </div>
              </details>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function TripDetails() {
  // Re-render whenever the trip is loaded from the API so we never show mock data.
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const onLoaded = () => setTick(t => t + 1);
    window.addEventListener('sky:trip-loaded', onLoaded);
    return () => window.removeEventListener('sky:trip-loaded', onLoaded);
  }, []);

  const T = window.SKY.TRIP;
  const [legs, setLegs] = useState(T.legs);
  useEffect(() => { setLegs(T.legs); }, [tick]);
  const [dirty, setDirty] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Look up the real city name for an IATA code from our airport list.
  function cityFor(code) {
    if (!code) return '';
    const a = (window.SKY_AIRPORTS || []).find(x => x.code === code);
    return a ? a.city : code;
  }
  const originCity = cityFor(T.origin);
  const destCode = (T.destinations && T.destinations[0]) || '';
  const destCity = cityFor(destCode);

  async function handleDeleteTrip() {
    if (!confirm('Delete your entire trip? This cannot be undone — all legs and history will be wiped.')) return;
    setDeleting(true);
    try {
      await window.SkyAPI.trip.deleteTrip();
      window.location.href = '/app.html';
    } catch (e) {
      alert('Could not delete trip: ' + (e.message || e));
      setDeleting(false);
    }
  }

  return (
    <Shell active="trip">
      <div className="page-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1>Trip details</h1>
          <p>Edit every leg of your trip. SkySaver re-checks the whole itinerary when you change one.</p>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={handleDeleteTrip} disabled={deleting} style={{ color: '#B91C1C' }}>
          <Icon name="trash" size={15} /> {deleting ? 'Deleting…' : 'Delete entire trip'}
        </button>
      </div>

      <div className="trip-banner">
        <div className="tb-route">
          <div className="tb-city"><b>{T.origin || '—'}</b><span>{originCity || '—'}</span></div>
          <div className="tb-plane"><Icon name="plane" size={22} /></div>
          <div className="tb-city"><b>{destCode || '—'}</b><span>{destCity || '—'}</span></div>
        </div>
        <div className="tb-divide" />
        <div className="tb-stats">
          <div className="tb-stat"><b>{T.dates || '—'}</b><span>Travel dates</span></div>
          <div className="tb-stat"><b>{T.travelers || 1}</b><span>Traveler</span></div>
          <div className="tb-stat"><b>{legs.length}</b><span>Legs</span></div>
        </div>
      </div>

      <AddLeg onAdd={() => setDirty(true)} />

      <div className="card">
        <div className="card-h">
          <div className="ci" style={{ background: 'var(--indigo-50)', color: 'var(--indigo-600)' }}><Icon name="route" size={19} /></div>
          <div><h2>All legs</h2><p>{legs.length} legs · tap any to expand and edit</p></div>
        </div>
        <div className="card-pad">
          <div className="timeline">
            {legs.map(leg => <TimelineLeg key={leg.id} leg={leg} />)}
          </div>
        </div>
      </div>

      {dirty && (
        <div className="save-bar">
          <button className="btn btn-primary save-float" onClick={() => setDirty(false)}><Icon name="check" size={16} /> Save changes</button>
        </div>
      )}
    </Shell>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<TripDetails />);
