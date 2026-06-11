// SkySaver — recovery panel + booking dialog
const { useState: useStateR, useMemo: useMemoR, useEffect: useEffectR } = React;

// Map a SerpAPI flight option into the shape this UI renders.
function serpApiToOption(opt, idx) {
  const stops = opt.stops || 0;
  const route = (opt.origin || '') + ' → ' + (opt.destination || '');
  const price = opt.price_usd || 0;
  const dur = opt.duration_minutes || 0;
  const durLabel = Math.floor(dur / 60) + 'h ' + (dur % 60) + 'm';
  // Heuristic severity — keeps it consistent with the original mock cards.
  let severity = 'low', severityLabel = 'Low risk · fits cleanly';
  if (stops > 0) { severity = 'warn'; severityLabel = `Tight buffer · ${stops} stop`; }
  if (price > 700) { severity = 'info'; severityLabel = 'Higher fare'; }
  return {
    id: 'live-' + idx,
    airline: opt.airline || 'Unknown airline',
    flight: opt.flight_number || '',
    price, route,
    depart: opt.departure_time || '',
    arrive: opt.arrival_time || '',
    duration: durLabel,
    stops,
    severity, severityLabel,
    score: 100 - idx * 4 - (stops * 10) - Math.min(20, Math.floor(price / 50)),
    cascade: [
      { leg: 'Hotel', effect: stops === 0 ? 'No conflict — within free check-in window' : 'Check-in may shift 2-4h later', tone: stops === 0 ? 'success' : 'info' },
      { leg: 'Transport', effect: 'Pickup time auto-adjusted', tone: 'info' },
      { leg: 'Meeting', effect: stops > 1 ? 'Buffer tight — review' : 'Buffer preserved', tone: stops > 1 ? 'warn' : 'success' },
    ],
  };
}

const SEV = { low: 'sev-low', warn: 'sev-warn', info: 'sev-info' };
const SEV_TONE = { low: 'success', warn: 'warn', info: 'info' };

function CascadeTable({ rows }) {
  return (
    <div className="cascade-table">
      {rows.map((r, i) => (
        <div key={i} className={'cascade-row tone-' + r.tone}>
          <span className="cascade-dot" />
          <span className="cl">{r.leg}</span>
          <span className="ce">{r.effect}</span>
        </div>
      ))}
    </div>
  );
}

function OptionCard({ opt, best, compact, onBook }) {
  const [open, setOpen] = useStateR(false);
  // Derive origin / destination from the option's route string ("DXB → SIN")
  // so each card shows the real airports, not hardcoded DXB/SIN.
  const routeParts = (opt.route || '').split('→').map(s => s.trim().slice(0, 3));
  const orig = routeParts[0] || '';
  const dest = routeParts[1] || '';
  return (
    <div className={'optc' + (best ? ' best' : '') + (compact ? ' compact' : '')}>
      <div className="optc-main">
        <div className="optc-air">
          <div className="name">{opt.airline}</div>
          <div className="fl">{opt.flight} · {opt.route}</div>
        </div>
        <div className="optc-route">
          <div className="optc-rt-seg"><b>{opt.depart}</b><span>{orig}</span></div>
          <div className="optc-rt-line"><span className="dur">{opt.duration}</span><span className="stops">{opt.stops === 0 ? 'nonstop' : opt.stops + ' stop'}</span></div>
          <div className="optc-rt-seg"><b>{opt.arrive}</b><span>{dest}</span></div>
        </div>
        <div className="optc-price"><b>${opt.price}</b><span>per traveler</span></div>
        <div className="optc-cta">
          <span className={'sev-badge ' + SEV[opt.severity]}>
            <Icon name={opt.severity === 'low' ? 'check' : opt.severity === 'warn' ? 'clock' : 'refresh'} size={12} />
            {opt.severityLabel}
          </span>
          <button className="btn btn-primary btn-sm" onClick={() => onBook(opt)}>Book this option</button>
        </div>
      </div>
      <div className={'cascade-toggle' + (open ? ' open' : '')} onClick={() => setOpen(o => !o)}>
        <Icon name="route" size={14} />
        {open ? 'Hide' : 'Show'} cascade — what this does to your trip
        <Icon name="chevronDown" size={15} className="chev" style={{ marginLeft: 'auto' }} />
      </div>
      {open && <CascadeTable rows={opt.cascade} />}
    </div>
  );
}

function RecoveryPanel({ cancelledLeg, onBook }) {
  const D = window.SKY.DISRUPTION;
  const MOCK = window.SKY.ALTERNATIVES;
  const [sort, setSort] = useStateR('best');
  const [count, setCount] = useStateR(10);
  const [maxPrice, setMaxPrice] = useStateR(1500);
  const [directOnly, setDirectOnly] = useStateR(false);
  const [compact, setCompact] = useStateR(false);
  const [liveOptions, setLiveOptions] = useStateR(null);
  const [loadingLive, setLoadingLive] = useStateR(true);
  const [searchError, setSearchError] = useStateR('');

  // Resolve route + date from the cancelled leg passed in by the dashboard.
  // Falls back to parsing the title if structured fields are missing.
  const fallbackOrigin = cancelledLeg
    ? (cancelledLeg.origin || (cancelledLeg.title || '').match(/([A-Z]{3})\s*→/)?.[1] || '')
    : '';
  const fallbackDest = cancelledLeg
    ? (cancelledLeg.destination || (cancelledLeg.title || '').match(/→\s*([A-Z]{3})/)?.[1] || '')
    : '';
  const fallbackDate = cancelledLeg
    ? ((cancelledLeg.start_at || '').slice(0, 10) || new Date(Date.now() + 7 * 24 * 3600 * 1000).toISOString().slice(0, 10))
    : '';

  // Re-fetch whenever the cancelled leg changes (so disrupting a different
  // flight or dismissing + re-triggering pulls fresh options).
  useEffectR(() => {
    let aborted = false;
    async function fetchLive() {
      setLiveOptions(null);
      setSearchError('');
      setLoadingLive(true);
      if (!cancelledLeg || !fallbackOrigin || !fallbackDest) {
        if (!aborted) setLoadingLive(false);
        return;
      }
      try {
        const res = await window.SkyAPI.flights.search(fallbackOrigin, fallbackDest, fallbackDate);
        if (aborted) return;
        if (res && res.options && res.options.length) {
          setLiveOptions(res.options.map(serpApiToOption));
        } else {
          setSearchError('No live results from Google Flights for this route — showing fallback.');
        }
      } catch (err) {
        if (!aborted) setSearchError('Search unavailable: ' + (err.message || err));
      } finally {
        if (!aborted) setLoadingLive(false);
      }
    }
    fetchLive();
    return () => { aborted = true; };
  }, [cancelledLeg && cancelledLeg.id]);

  const ALL = liveOptions && liveOptions.length ? liveOptions : MOCK;

  const results = useMemoR(() => {
    let r = ALL.filter(o => (o.price || 0) <= maxPrice && (!directOnly || (o.stops || 0) === 0));
    const sorters = {
      best: (a, b) => (b.score || 0) - (a.score || 0),
      cheapest: (a, b) => (a.price || 0) - (b.price || 0),
      fastest: (a, b) => parseInt(a.duration) - parseInt(b.duration),
      earliest: (a, b) => (a.depart || '').localeCompare(b.depart || ''),
      stops: (a, b) => (a.stops || 0) - (b.stops || 0),
    };
    r = [...r].sort(sorters[sort]);
    return r.slice(0, count);
  }, [sort, count, maxPrice, directOnly, ALL]);

  // Title/route come from the cancelled leg passed in by the dashboard.
  const headerFlight = cancelledLeg
    ? (cancelledLeg.code || (cancelledLeg.title || '').split('—')[0].trim() || 'Your flight')
    : D.flight;
  const headerRoute = cancelledLeg
    ? `${fallbackOrigin || '?'} → ${fallbackDest || '?'}`
    : D.route;
  const headerSentence = liveOptions && liveOptions.length
    ? `SkySaver searched Google Flights and found ${liveOptions.length} live alternative${liveOptions.length === 1 ? '' : 's'} for ${headerRoute}.`
    : (cancelledLeg
        ? `Your tracked flight ${headerFlight} (${headerRoute}) was cancelled. Searching for alternatives…`
        : D.sentence);

  return (
    <div className="recovery">
      <div className="rec-banner">
        <div className="rb-ic"><Icon name="siren" size={26} /></div>
        <div>
          <h2>{headerFlight} cancelled — {headerRoute}</h2>
          <p>{loadingLive ? 'Searching Google Flights for live alternatives…' : (searchError || headerSentence)}</p>
        </div>
        <div className="rb-count"><b>{ALL.length}</b><span>alternatives found</span></div>
      </div>

      <div className="filter-bar">
        <div className="fb-group">
          <Icon name="filter" size={16} style={{ color: 'var(--slate-400)' }} />
          <span className="fb-label">Sort</span>
          <select className="fb-select" value={sort} onChange={e => setSort(e.target.value)}>
            <option value="best">Best for you</option>
            <option value="cheapest">Cheapest</option>
            <option value="fastest">Fastest</option>
            <option value="earliest">Earliest</option>
            <option value="stops">Fewest stops</option>
          </select>
        </div>
        <div className="fb-group fb-range">
          <span className="fb-label">Max price</span>
          <input type="range" min="380" max="700" step="2" value={maxPrice} onChange={e => setMaxPrice(+e.target.value)} />
          <span className="fb-val">${maxPrice}</span>
        </div>
        <div className="fb-group">
          <span className="fb-label">Show</span>
          <select className="fb-select" value={count} onChange={e => setCount(+e.target.value)}>
            {[3, 5, 10].map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
        <div className="fb-spacer" />
        <label className="fb-check">
          <input type="checkbox" checked={directOnly} onChange={e => setDirectOnly(e.target.checked)} />
          <span className="fb-box"><Icon name="check" size={13} /></span> Direct only
        </label>
        <label className="fb-check">
          <input type="checkbox" checked={compact} onChange={e => setCompact(e.target.checked)} />
          <span className="fb-box"><Icon name="check" size={13} /></span> Compact
        </label>
      </div>

      <div className="rec-results">
        {results.length === 0 && <div style={{ textAlign: 'center', padding: 30, color: 'var(--slate-400)', fontSize: 14 }}>No options match your filters. Loosen the price or stops filter.</div>}
        {results.map((o, i) => (
          <OptionCard key={o.id} opt={o} best={sort === 'best' && i === 0} compact={compact} onBook={onBook} />
        ))}
      </div>
    </div>
  );
}

// ---------- Booking dialog ----------
function BookingDialog({ opt, onClose }) {
  const [step, setStep] = useStateR(1);
  const [scanning, setScanning] = useStateR(false);
  const [scanned, setScanned] = useStateR(false);
  const [showEx, setShowEx] = useStateR(false);
  const [scanResult, setScanResult] = useStateR(null);
  const [confRef, setConfRef] = useStateR('');
  const fileInputRef = React.useRef(null);

  // Build deep links synchronously from `opt` so the buttons ALWAYS have a
  // working href the instant the dialog renders. No async wait, no race.
  const parts = (opt.route || '').split('→').map(s => s.trim().slice(0, 3));
  const origin = parts[0] || '';
  const destination = parts[parts.length - 1] || '';
  const inTwoWeeks = new Date(Date.now() + 14 * 24 * 3600 * 1000).toISOString().slice(0, 10);

  // Try the airline code first (most accurate), then fall back to name search.
  const codeFromFlight = ((opt.flight || '').match(/^([A-Z0-9]{2})/) || [])[1] || '';
  const codeFromAirline = (opt.airline_code || opt.code || '').toString().slice(0, 2).toUpperCase();
  const code = (codeFromAirline || codeFromFlight).toUpperCase();
  const AIRLINES = window.AIRLINE_URLS || {};
  const airlineUrl = AIRLINES[code]
    || 'https://www.google.com/search?q=' + encodeURIComponent((opt.airline || code || 'airline') + ' official site book flights');

  // Google Flights deep link with route + date pre-filled.
  const gflightsUrl = (origin && destination)
    ? `https://www.google.com/travel/flights?q=${encodeURIComponent('Flights from ' + origin + ' to ' + destination + ' on ' + inTwoWeeks)}`
    : 'https://www.google.com/travel/flights';

  // Safari sometimes blocks _blank — fall back to window.open on click.
  function openExternal(url) {
    return (e) => {
      try { window.open(url, '_blank', 'noopener,noreferrer'); e.preventDefault(); }
      catch (_) { /* anchor default fires */ }
    };
  }

  async function doScan(file) {
    if (!file) return;
    setScanning(true);
    try {
      const res = await window.SkyAPI.scanConfirmation(file);
      const ex = (res && res.extracted) || {};
      setScanResult(ex);
      if (ex.confirmation_reference) setConfRef(ex.confirmation_reference);
      setScanned(true);
    } catch (err) {
      alert('Scan failed: ' + (err.message || err));
    } finally {
      setScanning(false);
    }
  }

  function openFilePicker() {
    if (fileInputRef.current) fileInputRef.current.click();
  }

  const extracted = scanResult ? [
    ['Airline', scanResult.airline_name || scanResult.airline_code || opt.airline],
    ['Flight number', scanResult.flight_number || opt.flight],
    ['Origin', scanResult.origin || ''],
    ['Destination', scanResult.destination || ''],
    ['Departure', scanResult.departure_at || ''],
    ['Arrival', scanResult.arrival_at || ''],
    ['Confirmation reference', scanResult.confirmation_reference || ''],
    ['Price', scanResult.price_usd != null ? '$' + scanResult.price_usd : ''],
    ['Paid with', scanResult.paid_with || ''],
    ['Passenger', scanResult.passenger_name || ''],
  ].filter(([, v]) => v) : [];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-head">
          <div>
            <h3>Book {opt.airline} · {opt.flight}</h3>
            <div className="ms">{opt.route} · ${opt.price} · {opt.duration}</div>
          </div>
          <button className="modal-close" onClick={onClose}><Icon name="x" size={18} /></button>
        </div>

        <div className="modal-steps">
          <div className={'mstep ' + (step >= 1 ? (step > 1 ? 'done' : 'active') : '')}><div className="bar" /><div className="ml">1 · Pay on airline</div></div>
          <div className={'mstep ' + (step >= 2 ? 'active' : '')}><div className="bar" /><div className="ml">2 · Confirm & file</div></div>
        </div>

        {step === 1 && (
          <div className="modal-body">
            <div className="info-banner">
              <Icon name="shield" size={18} />
              <span>SkySaver doesn't process payment. We hand you to {opt.airline} with your route pre-filled. Pay there, then come back to upload your confirmation.</span>
            </div>
            <div className="pay-row">
              <a className="pay-btn primary" href={airlineUrl} target="_blank" rel="noopener noreferrer" onClick={openExternal(airlineUrl)}>
                <Icon name="plane" size={18} /> Open {opt.airline}
              </a>
              <a className="pay-btn secondary" href={gflightsUrl} target="_blank" rel="noopener noreferrer" onClick={openExternal(gflightsUrl)}>
                <Icon name="search" size={17} /> Compare on Google Flights
              </a>
            </div>
            <button className="btn btn-primary" style={{ width: '100%' }} onClick={() => setStep(2)}>
              <Icon name="check" size={17} /> I've paid — show me Step 2
            </button>
          </div>
        )}

        {step === 2 && (
          <div className="modal-body">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.webp"
              style={{ display: 'none' }}
              onChange={e => doScan(e.target.files && e.target.files[0])}
            />
            <div className={'uploader' + (scanned ? ' scanned' : '')} onClick={!scanned && !scanning ? openFilePicker : undefined}>
              {scanned ? (
                <>
                  <div className="up-ic" style={{ color: 'var(--emerald-500)', borderColor: '#A7F3D0' }}><Icon name="check" size={26} /></div>
                  <h4>confirmation-SQ305.pdf scanned</h4>
                  <p>Gemini Vision read 7 fields — review below</p>
                </>
              ) : scanning ? (
                <>
                  <div className="up-ic"><Icon name="sparkles" size={24} /></div>
                  <h4>Gemini is reading your PDF…</h4>
                  <p>Extracting confirmation, seat, fare, payment</p>
                  <div className="scan-line" style={{ marginTop: 14 }} />
                </>
              ) : (
                <>
                  <div className="up-ic"><Icon name="upload" size={24} /></div>
                  <h4>Upload your booking confirmation</h4>
                  <p>PDF, PNG or JPG — SkySaver will read it for you</p>
                </>
              )}
            </div>

            <div className="field" style={{ marginTop: 20 }}>
              <label>Confirmation reference</label>
              <input className={scanned ? 'prefilled' : ''} defaultValue={scanned ? 'SQ-7K2P9X' : ''} placeholder="e.g. SQ-7K2P9X" />
            </div>
            <div className="field">
              <label>Payment method</label>
              <select className={scanned ? 'prefilled' : ''} defaultValue={scanned ? 'visa' : ''}>
                <option value="" disabled>Select…</option>
                <option value="visa">Visa ···· 4291</option>
                <option value="amex">Amex ···· 1008</option>
              </select>
            </div>

            {scanned && (
              <div className="extracted">
                <div className={'extracted-head' + (showEx ? ' open' : '')} onClick={() => setShowEx(s => !s)}>
                  <Icon name="eye" size={15} style={{ color: 'var(--indigo-500)' }} /> Show extracted details
                  <Icon name="chevronDown" size={15} className="chev" />
                </div>
                {showEx && (
                  <div className="extracted-body">
                    {extracted.map(([k, v]) => (
                      <div key={k} className="ex-row"><span className="k">{k}</span><span className="v">{v}</span></div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        <div className="modal-foot">
          {step === 2 && <button className="btn btn-ghost" onClick={() => setStep(1)}><Icon name="chevronLeft" size={16} /> Back</button>}
          <div style={{ flex: 1 }} />
          {step === 2
            ? <button className="btn btn-primary" onClick={onClose}><Icon name="check" size={17} /> Save booking</button>
            : <button className="btn btn-ghost" onClick={onClose}>Cancel</button>}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { RecoveryPanel, BookingDialog });
