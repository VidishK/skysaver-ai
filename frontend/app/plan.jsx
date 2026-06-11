// SkySaver — Plan a trip wizard
const { useState, useRef } = React;

const STEPS = ['Where', 'When', 'Who', 'Bags', 'Stay', 'Ground', 'Meetings', 'Notes'];

// Full 120-airport list from window.SKY_AIRPORTS (loaded via airports.js).
const CITIES = (window.SKY_AIRPORTS && window.SKY_AIRPORTS.length) ? window.SKY_AIRPORTS : [
  { code: 'DXB', city: 'Dubai', country: 'UAE' },
  { code: 'SIN', city: 'Singapore', country: 'Singapore' },
  { code: 'LHR', city: 'London', country: 'UK' },
];

function Stepper({ count, set }) {
  return (
    <div className="pw-stepper">
      {STEPS.map((s, i) => (
        <div key={i} className={'pw-dot' + (i === count ? ' active' : '') + (i < count ? ' done' : '')}>
          <span className="d">{i < count ? <Icon name="check" size={13} stroke={3} /> : i + 1}</span>
          <span className="l">{s}</span>
        </div>
      ))}
    </div>
  );
}

function Combo({ label, value, onPick, placeholder }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const list = CITIES.filter(c => (c.city + c.code + c.country).toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="combo">
      <label>{label}</label>
      <div className="combo-input" onClick={() => setOpen(o => !o)}>
        <Icon name="mapPin" size={17} style={{ color: 'var(--slate-400)' }} />
        {value ? <span className="combo-val">{value.city} <b>{value.code}</b></span> : <span className="combo-ph">{placeholder}</span>}
        <Icon name="chevronDown" size={16} style={{ marginLeft: 'auto', color: 'var(--slate-400)' }} />
      </div>
      {open && (
        <div className="combo-pop">
          <div className="combo-search"><Icon name="search" size={15} /><input autoFocus value={q} onChange={e => setQ(e.target.value)} placeholder="City or airport code…" /></div>
          <div className="combo-list thin-scroll">
            {list.map(c => (
              <div key={c.code} className="combo-opt" onClick={() => { onPick(c); setOpen(false); setQ(''); }}>
                <div><b>{c.city}</b> <span style={{ color: 'var(--slate-400)' }}>· {c.country}</span></div>
                <span className="combo-code">{c.code}</span>
              </div>
            ))}
            {list.length === 0 && <div style={{ padding: 14, color: 'var(--slate-400)', fontSize: 13 }}>No matches</div>}
          </div>
        </div>
      )}
    </div>
  );
}

function Stepper2({ label, value, set, min = 0 }) {
  return (
    <div className="stepper2">
      <div><b>{label}</b></div>
      <div className="st2-ctl">
        <button onClick={() => set(Math.max(min, value - 1))} disabled={value <= min}><Icon name="minus" size={16} /></button>
        <span>{value}</span>
        <button onClick={() => set(value + 1)}><Icon name="plus" size={16} /></button>
      </div>
    </div>
  );
}

function Chip({ active, onClick, children }) {
  return <button className={'pw-chip' + (active ? ' active' : '')} onClick={onClick}>{children}</button>;
}

const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'];

// Real, working month calendar. First-of-month is placed in the correct
// day-of-week column, and the selection range reflects the active chip.
function TripCalendar({ when }) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const [view, setView] = useState({ y: today.getFullYear(), m: today.getMonth() });

  // Build the selected range from the chip choice (relative to today).
  let range = null;
  if (when === 'Weekend') {
    // Next Sat → Sun (or this weekend if today is already Sat/Sun).
    const d0 = new Date(today);
    const dow = d0.getDay(); // 0 Sun, 6 Sat
    const daysToSat = dow === 6 ? 0 : (6 - dow) % 7;
    const sat = new Date(d0); sat.setDate(d0.getDate() + daysToSat);
    const sun = new Date(sat); sun.setDate(sat.getDate() + 1);
    range = { start: sat, end: sun };
  } else if (when === '1 week') {
    const end = new Date(today); end.setDate(today.getDate() + 6);
    range = { start: today, end };
  } else if (when === '2 weeks') {
    const end = new Date(today); end.setDate(today.getDate() + 13);
    range = { start: today, end };
  }

  const firstOfMonth = new Date(view.y, view.m, 1);
  const startOffset = firstOfMonth.getDay(); // 0..6 Sun..Sat
  const daysInMonth = new Date(view.y, view.m + 1, 0).getDate();
  const totalCells = startOffset + daysInMonth;
  const rows = Math.ceil(totalCells / 7);

  function step(delta) {
    setView(v => {
      const m = v.m + delta;
      if (m < 0) return { y: v.y - 1, m: 11 };
      if (m > 11) return { y: v.y + 1, m: 0 };
      return { y: v.y, m };
    });
  }

  function classFor(day) {
    if (!day) return 'cal-day cal-empty';
    const date = new Date(view.y, view.m, day);
    let cls = 'cal-day';
    if (date.getTime() === today.getTime()) cls += ' today';
    if (range) {
      const s = range.start.getTime(), e = range.end.getTime(), t = date.getTime();
      if (t >= s && t <= e) cls += ' sel';
      if (t === s || t === e) cls += ' edge';
    }
    return cls;
  }

  const cells = [];
  for (let i = 0; i < startOffset; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);
  while (cells.length < rows * 7) cells.push(null);

  return (
    <div className="cal-mock">
      <div className="cal-head">
        <b>{MONTH_NAMES[view.m]} {view.y}</b>
        <div style={{ display: 'flex', gap: 6 }}>
          <span className="cal-nav" onClick={() => step(-1)} style={{ cursor: 'pointer' }}><Icon name="chevronLeft" size={15} /></span>
          <span className="cal-nav" onClick={() => step(1)} style={{ cursor: 'pointer' }}><Icon name="chevronRight" size={15} /></span>
        </div>
      </div>
      <div className="cal-grid">
        {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((x, i) => <span key={'dow' + i} className="cal-dow">{x}</span>)}
        {cells.map((day, i) => (
          <span key={i} className={classFor(day)}>{day || ''}</span>
        ))}
      </div>
    </div>
  );
}

function Wizard() {
  const [step, setStep] = useState(0);
  const [dir, setDir] = useState(1);
  const [done, setDone] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [d, setD] = useState({
    origin: null, dest: null,
    when: '', adults: 1, children: 0, infants: 0,
    carryon: 0, checked: 0, special: '',
    stay: '', stars: 0, budget: 0,
    ground: '', tier: '',
    meetings: [], notes: '',
  });
  const set = (k, v) => setD(s => ({ ...s, [k]: v }));
  const go = (n) => { setDir(n > step ? 1 : -1); setStep(n); };

  function addMeeting() { set('meetings', [...d.meetings, { title: '', date: '', time: '' }]); }
  function updMeeting(i, k, v) { const m = [...d.meetings]; m[i] = { ...m[i], [k]: v }; set('meetings', m); }

  // Build a real trip document and POST it to the backend, then redirect.
  async function finish() {
    if (!d.origin || !d.dest) {
      setSaveError('Please pick an origin and destination.');
      setStep(0);
      return;
    }
    setSaving(true);
    setSaveError('');

    // Derive ISO dates 7 days out (or based on user's "when" choice).
    // If they didn't pick, default to a week away — they can edit on Trip details.
    const daysOut = { '3 days': 3, '1 week': 7, '2 weeks': 14, '1 month': 30 }[d.when] || 7;
    const now = Date.now();
    const depart = new Date(now + daysOut * 24 * 3600 * 1000);
    const ret = new Date(now + (daysOut + 5) * 24 * 3600 * 1000);
    const isoStart = (date, hour) => { date.setUTCHours(hour, 0, 0, 0); return date.toISOString().replace('.000Z', 'Z'); };

    // Skeleton legs — the user can finalize each on Trip details later
    const legs = [
      {
        leg_id: 'leg_001', type: 'flight', status: 'scheduled',
        start_at: isoStart(new Date(depart), 10), end_at: isoStart(new Date(depart), 17),
        airline: '', flight_number: 'TBD',
        origin: d.origin.code, destination: d.dest.code,
        stops: 0, duration_minutes: 420, price_usd: 0, currency: 'USD',
        booking_reference: null, booking_method: 'pending', ticket_class: 'economy',
        notes: 'Auto-generated. Open Trip details → Find & finalize to pick a real flight.',
      },
    ];
    // Only add a stay leg if the user actually picked one (not empty, not "Don't need…")
    if (d.stay && d.stay !== 'Don\'t need a stay') {
      legs.push({
        leg_id: 'leg_002', type: 'hotel', status: 'scheduled',
        start_at: isoStart(new Date(depart.getTime() + 24 * 3600 * 1000), 15),
        end_at: isoStart(new Date(ret), 11),
        name: 'TBD ' + d.stay.toLowerCase(),
        stay_type: d.stay,
        city: d.dest.city, address: '',
        nightly_rate_usd: d.budget || 0, total_usd: (d.budget || 0) * 4,
        confirmation_code: '',
        notes: 'Auto-generated.',
      });
    }
    // Only add a transport leg if the user picked a mode
    if (d.ground && d.ground !== 'I\'ll figure it out') {
      legs.push({
        leg_id: 'leg_003', type: 'transport', status: 'scheduled',
        start_at: isoStart(new Date(depart.getTime() + 24 * 3600 * 1000), 11),
        end_at: isoStart(new Date(depart.getTime() + 24 * 3600 * 1000), 12),
        mode: 'rideshare', from: d.dest.city + ' airport', to: d.dest.city + ' city',
        estimated_cost_usd: 35,
        notes: '',
      });
    }
    (d.meetings || []).forEach((m, i) => {
      if (!m.title) return;
      legs.push({
        leg_id: 'leg_meet_' + (i + 1), type: 'meeting', status: 'scheduled',
        start_at: isoStart(new Date(depart.getTime() + 2 * 24 * 3600 * 1000), 10),
        end_at: isoStart(new Date(depart.getTime() + 2 * 24 * 3600 * 1000), 11),
        title: m.title, location: d.dest.city,
        attendees: [], importance: 'medium', buffer_before_minutes: 60,
      });
    });
    legs.push({
      leg_id: 'leg_return', type: 'flight', status: 'scheduled',
      start_at: isoStart(new Date(ret), 23), end_at: isoStart(new Date(ret.getTime() + 24 * 3600 * 1000), 6),
      airline: '', flight_number: 'TBD',
      origin: d.dest.code, destination: d.origin.code,
      stops: 0, duration_minutes: 480, price_usd: 0, currency: 'USD',
      booking_method: 'pending', ticket_class: 'economy',
      notes: 'Auto-generated. Open Trip details → Find & finalize to pick a real flight.',
    });

    const intake = {
      legs,
      preferences: {
        prefers_direct: true,
        seat_class: d.tier === 'Premium' ? 'business' : 'economy',
        carry_on_bags: d.carryon, checked_bags: d.checked, checked_baggage: d.checked > 0,
        hotel_min_stars: d.stars || 3, hotel_breakfast: true,
        preferred_ride_app: 'uber',
        preferred_ride_tier: (d.tier || 'comfort').toLowerCase(),
        budget_sensitivity: 'medium', currency: 'USD',
      },
    };
    const title = `${d.origin.city.split(' ')[0]} → ${d.dest.city.split(' ')[0]}`;

    try {
      await window.SkyAPI.trip.create(title, intake);
      setDone(true); fireConfetti();
      // After confetti, jump to the dashboard which will load the real trip.
      setTimeout(() => { window.location.href = '/app.html'; }, 1500);
    } catch (e) {
      setSaveError(e.message || 'Could not save trip — please retry.');
      setSaving(false);
    }
  }

  if (done) return <DoneScreen d={d} />;

  return (
    <div className="pw">
      <header className="pw-top">
        <a className="pw-brand" href="/index.html"><span className="mark"><Icon name="plane" size={17} stroke={2.2} /></span>SkySaver <span style={{ fontWeight: 500, color: 'var(--slate-400)' }}>AI</span></a>
        <a className="pw-exit" href="/app.html"><Icon name="x" size={16} /> Save &amp; exit</a>
      </header>

      <Stepper count={step} set={go} />

      <div className="pw-body">
        <div className="pw-main">
          <div key={step} className={'pw-step ' + (dir > 0 ? 'in-r' : 'in-l')}>
            {step === 0 && (
              <Panel n="Where are you going?" sub="Add your origin and destination. SkySaver supports multi-stop trips.">
                <div className="combo-row">
                  <Combo label="From" value={d.origin} onPick={v => set('origin', v)} placeholder="Select origin" />
                  <div className="combo-arrow"><Icon name="arrowRight" size={18} /></div>
                  <Combo label="To" value={d.dest} onPick={v => set('dest', v)} placeholder="Select destination" />
                </div>
              </Panel>
            )}
            {step === 1 && (
              <Panel n="When are you traveling?" sub="Pick a date range, or start from a quick option.">
                <div className="chip-row">
                  {['Weekend', '1 week', '2 weeks', 'Custom'].map(w => <Chip key={w} active={d.when === w} onClick={() => set('when', w)}>{w}</Chip>)}
                </div>
                <TripCalendar when={d.when} />
              </Panel>
            )}
            {step === 2 && (
              <Panel n="Who's traveling?" sub="We'll match seat and fare preferences for each traveler.">
                <div className="stepper2-list">
                  <Stepper2 label="Adults" value={d.adults} set={v => set('adults', v)} min={1} />
                  <Stepper2 label="Children" value={d.children} set={v => set('children', v)} />
                  <Stepper2 label="Infants" value={d.infants} set={v => set('infants', v)} />
                </div>
              </Panel>
            )}
            {step === 3 && (
              <Panel n="What are you carrying?" sub="So SkySaver can flag baggage rules on alternatives.">
                <div className="stepper2-list">
                  <Stepper2 label="Carry-on bags" value={d.carryon} set={v => set('carryon', v)} />
                  <Stepper2 label="Checked bags" value={d.checked} set={v => set('checked', v)} />
                </div>
                <div className="fld2"><label>Special items</label><input value={d.special} onChange={e => set('special', e.target.value)} placeholder="e.g. golf clubs, stroller, ski bag" /></div>
              </Panel>
            )}
            {step === 4 && (
              <Panel n="Where are you staying?" sub="SkySaver keeps your stay in sync if flights shift.">
                <div className="chip-row">{['Hotel', 'AirBnB', 'Hostel', 'With friends'].map(s => <Chip key={s} active={d.stay === s} onClick={() => set('stay', s)}>{s}</Chip>)}</div>
                <div className="slider-fld">
                  <div className="sf-head"><label>Minimum star rating</label><span className="sf-val">{d.stars ? d.stars + '★' : 'any'}</span></div>
                  <input type="range" min="0" max="5" value={d.stars || 0} onChange={e => set('stars', +e.target.value)} />
                </div>
                <div className="slider-fld">
                  <div className="sf-head"><label>Max nightly budget</label><span className="sf-val">{d.budget ? '$' + d.budget : 'any'}</span></div>
                  <input type="range" min="0" max="800" step="10" value={d.budget || 0} onChange={e => set('budget', +e.target.value)} />
                </div>
              </Panel>
            )}
            {step === 5 && (
              <Panel n="Getting around" sub="Your preferred way to move on the ground.">
                <div className="chip-row">{['Ride-share', 'Rental', 'Public', 'Mix'].map(s => <Chip key={s} active={d.ground === s} onClick={() => set('ground', s)}>{s}</Chip>)}</div>
                <label className="block-label">Preferred ride tier</label>
                <div className="chip-row">{['Economy', 'Comfort', 'Premium', 'XL'].map(s => <Chip key={s} active={d.tier === s} onClick={() => set('tier', s)}>{s}</Chip>)}</div>
              </Panel>
            )}
            {step === 6 && (
              <Panel n="Any meetings?" sub="SkySaver protects your meeting buffers when rebooking.">
                {d.meetings.map((m, i) => (
                  <div key={i} className="meeting-row">
                    <input value={m.title} onChange={e => updMeeting(i, 'title', e.target.value)} placeholder="Meeting title" style={{ flex: 2 }} />
                    <input value={m.date} onChange={e => updMeeting(i, 'date', e.target.value)} placeholder="Date" style={{ flex: 1 }} />
                    <input value={m.time} onChange={e => updMeeting(i, 'time', e.target.value)} placeholder="Time" style={{ width: 90 }} />
                  </div>
                ))}
                <button className="add-btn" onClick={addMeeting}><Icon name="plus" size={16} /> Add a meeting</button>
              </Panel>
            )}
            {step === 7 && (
              <Panel n="Anything else?" sub="Lounges, dietary needs, accessibility — anything SkySaver should know.">
                <textarea className="pw-textarea" value={d.notes} onChange={e => set('notes', e.target.value)} placeholder="e.g. I always want a lounge in long layovers; prefer aisle seats; vegetarian meals." />
              </Panel>
            )}
          </div>
        </div>

        <aside className="pw-summary">
          <div className="pws-head"><Icon name="route" size={17} style={{ color: 'var(--indigo-500)' }} /> Trip summary</div>
          <SummaryRow k="Route" v={(d.origin && d.dest) ? `${d.origin.code} → ${d.dest.code}` : '—'} />
          <SummaryRow k="Dates" v={d.when || '—'} />
          <SummaryRow k="Travelers" v={`${d.adults} adult${d.adults > 1 ? 's' : ''}${d.children ? ', ' + d.children + ' child' : ''}${d.infants ? ', ' + d.infants + ' infant' : ''}`} />
          <SummaryRow k="Bags" v={`${d.carryon} carry-on · ${d.checked} checked`} />
          <SummaryRow k="Stay" v={d.stay ? `${d.stay}${d.stars ? ' · ' + d.stars + '★' : ''}${d.budget ? ' · ≤$' + d.budget : ''}` : '—'} />
          <SummaryRow k="Ground" v={d.ground ? `${d.ground}${d.tier ? ' · ' + d.tier : ''}` : '—'} />
          <SummaryRow k="Meetings" v={d.meetings.filter(m => m.title).length || '—'} />
          <div className="pws-foot"><span className="ping"><i /></span> SkySaver will watch all of this 24/7</div>
        </aside>
      </div>

      {saveError && (
        <div style={{ position: 'fixed', bottom: 88, left: '50%', transform: 'translateX(-50%)', background: '#FEF2F2', border: '1px solid #FECACA', color: '#991B1B', padding: '10px 16px', borderRadius: 10, fontSize: 14, zIndex: 50, boxShadow: 'var(--sh-md)' }}>
          {saveError}
        </div>
      )}
      <footer className="pw-foot">
        <button className="btn btn-ghost" onClick={() => go(Math.max(0, step - 1))} disabled={step === 0 || saving}><Icon name="chevronLeft" size={16} /> Back</button>
        <div className="pw-foot-mid">Step {step + 1} of {STEPS.length}</div>
        {step < STEPS.length - 1
          ? <button className="btn btn-primary" onClick={() => go(step + 1)}>Next <Icon name="arrowRight" size={16} /></button>
          : <button className="btn btn-primary" onClick={finish} disabled={saving}>
              <Icon name="check" size={16} /> {saving ? 'Saving…' : 'Create trip'}
            </button>}
      </footer>
    </div>
  );
}

function Panel({ n, sub, children }) {
  return (
    <div>
      <h2 className="pw-q">{n}</h2>
      <p className="pw-qs">{sub}</p>
      <div className="pw-fields">{children}</div>
    </div>
  );
}
function SummaryRow({ k, v }) { return <div className="pws-row"><span className="k">{k}</span><span className="v">{v}</span></div>; }

function DoneScreen({ d }) {
  return (
    <div className="pw-done">
      <div className="done-check"><Icon name="check" size={44} stroke={3} /></div>
      <h1>Your trip is being watched.</h1>
      <p>{(d.origin && d.dest) ? `${d.origin.city} → ${d.dest.city}` : 'Your trip'} is live. SkySaver is monitoring every leg against real-time data — you can stop thinking about it now.</p>
      <a className="btn btn-primary btn-lg" href="/app.html">Go to dashboard <Icon name="arrowRight" size={17} /></a>
    </div>
  );
}

function fireConfetti() {
  const colors = ['#4F46E5', '#8B5CF6', '#EC4899', '#F59E0B', '#10B981', '#3B82F6'];
  const c = document.createElement('div'); c.className = 'confetti'; document.body.appendChild(c);
  for (let i = 0; i < 120; i++) {
    const p = document.createElement('i');
    p.style.left = Math.random() * 100 + 'vw';
    p.style.background = colors[i % colors.length];
    p.style.animationDelay = Math.random() * 0.6 + 's';
    p.style.animationDuration = 1.8 + Math.random() * 1.4 + 's';
    p.style.transform = `rotate(${Math.random() * 360}deg)`;
    c.appendChild(p);
  }
  setTimeout(() => c.remove(), 3600);
}

ReactDOM.createRoot(document.getElementById('root')).render(<Wizard />);
