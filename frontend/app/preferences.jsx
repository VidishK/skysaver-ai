// SkySaver — Preferences (tabbed)
const { useState } = React;

function Toggle({ on, onClick }) { return <button className={'toggle' + (on ? ' on' : '')} onClick={onClick}><i /></button>; }

function Seg({ value, options, onChange }) {
  return <div className="seg">{options.map(o => <button key={o} className={value === o ? 'on' : ''} onClick={() => onChange(o)}>{o}</button>)}</div>;
}

function Multi({ options, selected, onToggle, avoid }) {
  return <div className="multi">{options.map(o => <span key={o} className={'multi-chip' + (avoid ? ' avoid' : '') + (selected.includes(o) ? ' on' : '')} onClick={() => onToggle(o)}>{o}</span>)}</div>;
}

function Row({ title, sub, children }) {
  return <div className="pref-row"><div className="pl"><b>{title}</b>{sub && <span>{sub}</span>}</div><div className="pref-ctl">{children}</div></div>;
}

function Slider({ value, min, max, step, onChange, fmt }) {
  return <div className="mini-slider"><input type="range" min={min} max={max} step={step} value={value} onChange={e => onChange(+e.target.value)} /><span className="mini-val">{fmt ? fmt(value) : value}</span></div>;
}

const TABS = [
  { id: 'flights', label: 'Flights', icon: 'plane' },
  { id: 'hotels', label: 'Hotels', icon: 'bed' },
  { id: 'ground', label: 'Ground transport', icon: 'car' },
];

const AIRLINES = [
  { code: 'EK', name: 'Emirates' },
  { code: 'SQ', name: 'Singapore Airlines' },
  { code: 'QR', name: 'Qatar Airways' },
  { code: 'EY', name: 'Etihad Airways' },
  { code: 'LH', name: 'Lufthansa' },
  { code: 'BA', name: 'British Airways' },
  { code: 'CX', name: 'Cathay Pacific' },
  { code: 'AF', name: 'Air France' },
  { code: 'KL', name: 'KLM' },
  { code: 'TK', name: 'Turkish Airlines' },
  { code: 'AI', name: 'Air India' },
  { code: 'JL', name: 'Japan Airlines' },
  { code: 'NH', name: 'ANA' },
  { code: 'DL', name: 'Delta' },
  { code: 'AA', name: 'American Airlines' },
  { code: 'UA', name: 'United' },
  { code: 'QF', name: 'Qantas' },
  { code: 'ET', name: 'Ethiopian' },
  { code: 'MS', name: 'EgyptAir' },
  { code: '6E', name: 'IndiGo' },
];
const CHAINS = ['Marriott', 'Hilton', 'Hyatt', 'IHG', 'Accor', 'Four Seasons', 'Mandarin Oriental', 'Ritz-Carlton', 'Shangri-La', 'Aman'];

function Preferences() {
  const [tab, setTab] = useState('flights');
  const [dirty, setDirty] = useState(false);
  const T = window.SKY.TRIP;
  const flights = (T && T.legs || []).filter(l => l.type === 'flight');
  const hotels  = (T && T.legs || []).filter(l => l.type === 'hotel');
  const rides   = (T && T.legs || []).filter(l => l.type === 'transport');
  const [s, setS] = useState({
    direct: true, seat: 'Business', carryon: 1, checked: 1, layover: 210, arrival: 'Daytime',
    meal: 'Asian veg', seatPref: 'Aisle', airlines: ['EK', 'SQ'], avoid: [],
    stay: 'Hotel', stars: 5, room: 'King', breakfast: true, bed: 'King', smoking: false, quiet: true, chains: ['Marriott'],
    rideApp: 'Grab', tier: 'Premium', transit: true, rental: false, maxRide: 60,
  });
  const set = (k, v) => { setS(p => ({ ...p, [k]: v })); setDirty(true); };
  const toggleArr = (k, o) => { const a = s[k]; set(k, a.includes(o) ? a.filter(x => x !== o) : [...a, o]); };

  return (
    <Shell active="preferences">
      <div className="page-head">
        <h1>Preferences</h1>
        <p>SkySaver uses these to rank alternatives during a disruption. Start by reviewing the trip we're watching.</p>
      </div>

      {/* Your current trip — anchor everything in the user's real flights */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-h">
          <div className="ci" style={{ background: 'var(--blue-50, #EFF6FF)', color: '#1D4ED8' }}><Icon name="plane" size={19} /></div>
          <div>
            <h2>Your tracked flights &amp; stays</h2>
            <p>{flights.length ? `${flights.length} flight${flights.length > 1 ? 's' : ''} · ${hotels.length} stay${hotels.length === 1 ? '' : 's'} · ${rides.length} ride${rides.length === 1 ? '' : 's'} on this trip` : 'No active trip — add one to set per-flight preferences.'}</p>
          </div>
        </div>
        {flights.length > 0 && (
          <div className="card-pad">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
              {flights.map(f => (
                <div key={f.id} style={{ border: '1px solid var(--slate-200)', borderRadius: 12, padding: 14, background: 'linear-gradient(135deg,#EFF6FF,#DBEAFE)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <Icon name="plane" size={15} style={{ color: '#1D4ED8' }} />
                    <b style={{ fontSize: 14.5 }}>{f.title}</b>
                  </div>
                  <div style={{ fontSize: 12.5, color: 'var(--slate-600)' }}>{f.time}</div>
                  <div style={{ fontSize: 12, color: 'var(--slate-500)', marginTop: 4 }}>{f.meta}</div>
                  <div style={{ marginTop: 10, display: 'flex', gap: 6, alignItems: 'center' }}>
                    <Badge tone={f.booked ? 'success' : 'warn'}>{f.booked ? 'Booked' : 'Unbooked'}</Badge>
                    <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--slate-500)' }}>Cabin: <b>{s.seat}</b></span>
                  </div>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 14, padding: '10px 14px', background: 'var(--slate-50)', borderRadius: 10, fontSize: 13, color: 'var(--slate-600)' }}>
              💡 These flights are what SkySaver is watching. Your preferences below decide which replacements rank highest if one of them cancels.
            </div>
          </div>
        )}
        {flights.length === 0 && (
          <div className="card-pad">
            <div style={{ padding: 18, background: 'var(--slate-50)', borderRadius: 10, fontSize: 13.5, color: 'var(--slate-600)', textAlign: 'center' }}>
              You don't have any tracked flights yet. <a href="/plan.html" style={{ color: 'var(--indigo-600)', fontWeight: 600 }}>Plan a trip →</a>
            </div>
          </div>
        )}
      </div>

      <div className="tabs">
        {TABS.map(t => <button key={t.id} className={'tab' + (tab === t.id ? ' active' : '')} onClick={() => setTab(t.id)}><Icon name={t.icon} size={16} /> {t.label}</button>)}
      </div>

      {tab === 'flights' && (
        <div className="card card-pad">
          <Row title="Prefer direct flights" sub="Avoid layovers when possible"><Toggle on={s.direct} onClick={() => set('direct', !s.direct)} /></Row>
          <Row title="Seat class"><Seg value={s.seat} options={['Economy', 'Premium', 'Business', 'First']} onChange={v => set('seat', v)} /></Row>
          <Row title="Max layover" sub="Skip alternatives over this"><Slider value={s.layover} min={30} max={480} step={15} onChange={v => set('layover', v)} fmt={v => Math.floor(v / 60) + 'h ' + (v % 60) + 'm'} /></Row>
          <Row title="Arrival window"><Seg value={s.arrival} options={['Anytime', 'Daytime', 'Red-eye']} onChange={v => set('arrival', v)} /></Row>
          <Row title="Carry-on bags"><Slider value={s.carryon} min={0} max={3} step={1} onChange={v => set('carryon', v)} /></Row>
          <Row title="Checked bags"><Slider value={s.checked} min={0} max={4} step={1} onChange={v => set('checked', v)} /></Row>
          <Row title="Meal preference"><select className="pref-select" value={s.meal} onChange={e => set('meal', e.target.value)}><option>None</option><option>Vegetarian</option><option>Asian veg</option><option>Halal</option><option>Kosher</option></select></Row>
          <Row title="Seat preference"><Seg value={s.seatPref} options={['Window', 'Aisle', 'Any']} onChange={v => set('seatPref', v)} /></Row>
          <Row title="Preferred airlines" sub="SkySaver weighs these higher when ranking alternatives">
            <div className="multi" style={{ maxWidth: 600 }}>
              {AIRLINES.map(a => (
                <span key={a.code} className={'multi-chip' + (s.airlines.includes(a.code) ? ' on' : '')}
                      onClick={() => toggleArr('airlines', a.code)}
                      style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, opacity: 0.7 }}>{a.code}</span>
                  {a.name}
                </span>
              ))}
            </div>
          </Row>
          <Row title="Avoid airlines" sub="SkySaver will skip these unless nothing else works">
            <div className="multi" style={{ maxWidth: 600 }}>
              {AIRLINES.map(a => (
                <span key={a.code} className={'multi-chip avoid' + (s.avoid.includes(a.code) ? ' on' : '')}
                      onClick={() => toggleArr('avoid', a.code)}
                      style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, opacity: 0.7 }}>{a.code}</span>
                  {a.name}
                </span>
              ))}
            </div>
          </Row>

          {/* After-save action — let the user open Google Flights or the preferred airline */}
          <div style={{ marginTop: 24, padding: 18, background: 'linear-gradient(135deg, #EEF2FF, #F5F3FF)', border: '1px solid #C7D2FE', borderRadius: 12 }}>
            <div style={{ fontWeight: 700, marginBottom: 6, color: '#3730A3' }}>Want to browse flights now?</div>
            <div style={{ fontSize: 13.5, color: 'var(--slate-600)', marginBottom: 12 }}>
              SkySaver doesn't book directly. Use these to compare or book yourself, then come back and add the confirmation.
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <a className="btn btn-primary btn-sm" href="https://www.google.com/travel/flights" target="_blank" rel="noopener noreferrer">
                <Icon name="search" size={14} /> Open Google Flights
              </a>
              {s.airlines.slice(0, 3).map(code => {
                const a = AIRLINES.find(x => x.code === code);
                if (!a) return null;
                return (
                  <a key={code} className="btn btn-ghost btn-sm" target="_blank" rel="noopener noreferrer"
                     href={`https://www.google.com/search?q=${encodeURIComponent(a.name + ' book flights official site')}`}>
                    <Icon name="plane" size={14} /> {a.name}
                  </a>
                );
              })}
              {s.airlines.length === 0 && (
                <span style={{ alignSelf: 'center', fontSize: 12.5, color: 'var(--slate-500)' }}>Pick at least one preferred airline above to see its website here.</span>
              )}
            </div>
          </div>
        </div>
      )}

      {tab === 'hotels' && (
        <div className="card card-pad">
          <Row title="Stay type"><Seg value={s.stay} options={['Hotel', 'AirBnB', 'Hostel']} onChange={v => set('stay', v)} /></Row>
          <Row title="Minimum stars"><Slider value={s.stars} min={1} max={5} step={1} onChange={v => set('stars', v)} fmt={v => v + '★'} /></Row>
          <Row title="Room type"><select className="pref-select" value={s.room} onChange={e => set('room', e.target.value)}><option>Standard</option><option>King</option><option>Suite</option></select></Row>
          <Row title="Breakfast included"><Toggle on={s.breakfast} onClick={() => set('breakfast', !s.breakfast)} /></Row>
          <Row title="Bed type"><Seg value={s.bed} options={['Twin', 'Queen', 'King']} onChange={v => set('bed', v)} /></Row>
          <Row title="Smoking room"><Toggle on={s.smoking} onClick={() => set('smoking', !s.smoking)} /></Row>
          <Row title="Quiet floor"><Toggle on={s.quiet} onClick={() => set('quiet', !s.quiet)} /></Row>
          <Row title="Preferred chains"><Multi options={CHAINS} selected={s.chains} onToggle={o => toggleArr('chains', o)} /></Row>
        </div>
      )}

      {tab === 'ground' && (
        <div className="card card-pad">
          <Row title="Preferred ride app"><Seg value={s.rideApp} options={['Grab', 'Uber', 'Bolt']} onChange={v => set('rideApp', v)} /></Row>
          <Row title="Preferred tier"><Seg value={s.tier} options={['Economy', 'Comfort', 'Premium']} onChange={v => set('tier', v)} /></Row>
          <Row title="Use public transit" sub="When faster or cheaper"><Toggle on={s.transit} onClick={() => set('transit', !s.transit)} /></Row>
          <Row title="Rental car" sub="Include rentals in options"><Toggle on={s.rental} onClick={() => set('rental', !s.rental)} /></Row>
          <Row title="Max ride cost"><Slider value={s.maxRide} min={10} max={200} step={5} onChange={v => set('maxRide', v)} fmt={v => '$' + v} /></Row>
        </div>
      )}

      {dirty && (
        <div className="save-bar">
          <button className="btn btn-primary save-float" onClick={() => setDirty(false)}><Icon name="check" size={16} /> Save preferences</button>
        </div>
      )}
    </Shell>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<Preferences />);
