// SkySaver — Dashboard composition
const { useState: useStateM, useEffect: useEffectM } = React;

function Dashboard() {
  // Re-read from window.SKY on every render so the data-loaded event
  // (dispatched from data.js when /api/trip returns) updates the UI.
  const [tick, setTick] = useStateM(0);
  const TRIP = window.SKY.TRIP;
  const USER = window.SKY.USER;
  const ACTIVITY = window.SKY.ACTIVITY;
  const [collapsed, setCollapsed] = useStateM(false);
  const [disrupted, setDisrupted] = useStateM(false);
  const [disruptedLegId, setDisruptedLegId] = useStateM(null);
  const [booking, setBooking] = useStateM(null);
  const [clock, setClock] = useStateM('09:41:22');
  const [busyAction, setBusyAction] = useStateM('');

  // The actual leg the user's "Simulate disruption" cancelled — kept in sync
  // so LegCard, the alert banner, and RecoveryPanel all reference the same flight.
  const disruptedLeg = disruptedLegId
    ? (TRIP.legs || []).find(l => l.id === disruptedLegId)
    : null;
  const disruptedFlightLabel = disruptedLeg
    ? (disruptedLeg.code || (disruptedLeg.title || '').split('—')[0].trim() || 'Your flight')
    : 'Your flight';
  const disruptedRoute = disruptedLeg
    ? `${disruptedLeg.origin || '?'} → ${disruptedLeg.destination || '?'}`
    : '';

  useEffectM(() => {
    function onLoaded() { setTick(t => t + 1); }
    window.addEventListener('sky:trip-loaded', onLoaded);
    return () => window.removeEventListener('sky:trip-loaded', onLoaded);
  }, []);

  useEffectM(() => {
    const id = setInterval(() => {
      const d = new Date();
      setClock([d.getUTCHours(), d.getUTCMinutes(), d.getUTCSeconds()].map(n => String(n).padStart(2, '0')).join(':'));
    }, 1000);
    return () => clearInterval(id);
  }, []);

  async function triggerDisruption() {
    setBusyAction('disrupt');
    const firstFlight = (TRIP.legs || []).find(l => l.type === 'flight');
    try {
      if (firstFlight && window.SKY.LOADED_FROM_API) {
        await window.SkyAPI.trip.simulateCancellation(firstFlight.id);
      }
    } catch (_) { /* swallow — still trigger demo UI */ }
    if (firstFlight) setDisruptedLegId(firstFlight.id);
    setDisrupted(true);
    setBusyAction('');
  }

  async function loadDemoData() {
    setBusyAction('seed');
    try {
      await window.SkyAPI.trip.seedDemo();
      window.location.reload();
    } catch (e) {
      alert('Could not load demo data: ' + (e.message || e));
      setBusyAction('');
    }
  }

  async function logOut() {
    try { await window.SkyAPI.auth.logout(); } catch (_) {}
    window.location.href = '/auth.html';
  }

  async function deleteTrip() {
    if (!confirm('Delete your entire trip? Everything will be wiped — flights, hotels, history. Cannot be undone.')) return;
    setBusyAction('delete');
    try {
      await window.SkyAPI.trip.deleteTrip();
      window.location.reload();
    } catch (e) {
      alert('Could not delete trip: ' + (e.message || e));
      setBusyAction('');
    }
  }

  useEffectM(() => {
    if (disrupted) {
      setTimeout(() => {
        const el = document.querySelector('.recovery');
        if (el) window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - 80, behavior: 'smooth' });
      }, 120);
    }
  }, [disrupted]);

  const watchCount = TRIP.legs.filter(l => l.type === 'flight').length;

  return (
    <div className={'app' + (collapsed ? ' collapsed' : '')}>
      <Sidebar active="app" collapsed={collapsed} onToggle={() => setCollapsed(c => !c)} />
      <div>
        <TopBar user={USER} hasAlert={disrupted} onLogout={logOut} />
        <main className="main">
          <div className="hero-strip">
            <div>
              <h1>Welcome back, {USER.name}.</h1>
              <div className="greet-sub">
                {window.SKY.NO_TRIP
                  ? 'Plan your first trip to start the watch.'
                  : (TRIP.origin && TRIP.destinations && TRIP.destinations[0]
                      ? `Your ${TRIP.origin} → ${TRIP.destinations[0]} trip is fully watched.`
                      : 'Your trip is fully watched.')}
              </div>
            </div>
            <div className="live-badge">
              <span className="ping"><i /></span>
              <div>
                <div className="lt">LIVE · watching {watchCount} flight{watchCount > 1 ? 's' : ''}</div>
                <div className="ls">Last check: {clock} UTC</div>
              </div>
            </div>
          </div>

          {disrupted && (
            <div className="alert-banner">
              <div className="siren"><Icon name="siren" size={24} /></div>
              <div className="at" style={{ flex: 1 }}>
                <b>{disruptedFlightLabel} cancelled by carrier{disruptedRoute ? ' — ' + disruptedRoute : ''} — recovery ready below</b>
                <span>SkySaver searched Google Flights for alternatives on this route and ranked them against your preferences.</span>
              </div>
              <button className="btn btn-danger btn-sm" onClick={() => document.querySelector('.recovery').scrollIntoView({ behavior: 'smooth', block: 'start' })}>View options</button>
              <button className="btn btn-ghost btn-sm" onClick={() => { setDisrupted(false); setDisruptedLegId(null); }}>Dismiss</button>
            </div>
          )}

          {/* Empty state for new users with no trip */}
          {window.SKY.NO_TRIP && (
            <div className="cols">
              <div className="col-left">
                <div style={{ background: 'linear-gradient(135deg,#EEF2FF,#F5F3FF)', border: '1px dashed #C7D2FE', borderRadius: 18, padding: 48, textAlign: 'center', marginTop: 12 }}>
                  <div style={{ fontSize: '3rem', lineHeight: 1, marginBottom: 14 }}>🗺️</div>
                  <h3 style={{ fontSize: '1.5rem', fontWeight: 700, letterSpacing: '-0.02em', margin: '0 0 8px', color: '#0F172A' }}>No trip yet</h3>
                  <p style={{ color: 'var(--slate-500)', maxWidth: 460, margin: '0 auto 24px', fontSize: 14.5 }}>Plan your first trip and SkySaver will watch every leg 24/7. Or load the Singapore demo to see the recovery flow in action.</p>
                  <div style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap' }}>
                    <a className="btn btn-primary" href="/plan.html"><Icon name="plus" size={16} /> Plan a trip</a>
                    <button className="btn btn-ghost" onClick={loadDemoData} disabled={busyAction === 'seed'}>
                      <Icon name="sparkles" size={16} /> {busyAction === 'seed' ? 'Loading…' : 'Load demo data'}
                    </button>
                  </div>
                </div>
              </div>
              <div className="col-right">
                <ChatRail />
              </div>
            </div>
          )}

          {!window.SKY.NO_TRIP && (
          <div className="cols">
            <div className="col-left">
              <div className="tiles">
                <Tile label="Current trip" value={TRIP.origin && TRIP.destinations[0] ? `${TRIP.origin}→${TRIP.destinations[0]}` : 'Active'} sub={TRIP.dates} color="var(--grad-brand)" />
                <Tile label="Legs" value={TRIP.metrics.legs} sub={`${TRIP.legs.filter(l => l.booked).length} booked · ${TRIP.legs.filter(l => !l.booked).length} pending`} color="linear-gradient(90deg,#8B5CF6,#C084FC)" />
                <Tile label="Flights" value={TRIP.metrics.flights} sub="watched 24/7" color="linear-gradient(90deg,#3B82F6,#6366F1)" />
                <Tile label="Disruptions" value={disrupted ? 1 : 0} sub={disrupted ? '1 active' : 'all clear'} color={disrupted ? 'linear-gradient(90deg,#EF4444,#EC4899)' : 'linear-gradient(90deg,#10B981,#3B82F6)'} />
              </div>

              <div className="rainbow" />

              <div className="sec-h" style={{ flexWrap: 'wrap', gap: 8 }}>
                <h2>Itinerary</h2>
                <div style={{ display: 'flex', gap: 8, marginLeft: 'auto', flexWrap: 'wrap' }}>
                  {!disrupted && (
                    <button className="btn btn-ghost btn-sm" onClick={triggerDisruption} disabled={busyAction === 'disrupt'} title="Demo: simulate a cancellation">
                      <Icon name="zap" size={15} /> {busyAction === 'disrupt' ? 'Cancelling…' : 'Simulate disruption'}
                    </button>
                  )}
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={deleteTrip}
                    disabled={busyAction === 'delete'}
                    title="Wipe this trip and start fresh"
                    style={{ color: '#B91C1C' }}
                  >
                    <Icon name="trash" size={15} /> {busyAction === 'delete' ? 'Deleting…' : 'Delete trip & start over'}
                  </button>
                </div>
              </div>

              <div className="leg-list">
                {TRIP.legs.map(leg => (
                  <LegCard key={leg.id} leg={leg} broken={disrupted && leg.id === disruptedLegId} />
                ))}
              </div>

              <Expander title="Trip preferences" icon="sliders">
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, fontSize: 13.5 }}>
                  {[['Seat class', 'Business'], ['Max layover', '3h 30m'], ['Hotel tier', '5★ · King'], ['Ground', 'Grab Premium'], ['Direct flights', 'Strongly prefer'], ['Meal', 'Veg · Asian veg']].map(([k, v]) => (
                    <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--slate-100)' }}>
                      <span style={{ color: 'var(--slate-500)' }}>{k}</span><b>{v}</b>
                    </div>
                  ))}
                </div>
                <a className="btn btn-ghost btn-sm" href="/preferences.html" style={{ marginTop: 14 }}>Edit all preferences <Icon name="arrowRight" size={14} /></a>
              </Expander>

              <Expander title="Recent activity" icon="activity">
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  {ACTIVITY.map((a, i) => (
                    <div key={i} style={{ display: 'flex', gap: 12, alignItems: 'center', padding: '10px 0', borderBottom: i < ACTIVITY.length - 1 ? '1px solid var(--slate-100)' : 'none' }}>
                      <span className={'cascade-dot tone-' + a.tone} style={{ width: 8, height: 8, borderRadius: 99, background: a.tone === 'success' ? 'var(--emerald-500)' : a.tone === 'info' ? 'var(--blue-500)' : 'var(--slate-300)' }} />
                      <span style={{ fontSize: 13.5, flex: 1 }}>{a.text}</span>
                      <span className="mono" style={{ fontSize: 12, color: 'var(--slate-400)' }}>{a.t}</span>
                    </div>
                  ))}
                </div>
              </Expander>
            </div>

            <div className="col-right">
              <ChatRail />
            </div>
          </div>
          )}

          {disrupted && !window.SKY.NO_TRIP && <RecoveryPanel cancelledLeg={disruptedLeg} onBook={setBooking} />}
        </main>
      </div>
      {booking && <BookingDialog opt={booking} onClose={() => setBooking(null)} />}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<Dashboard />);
