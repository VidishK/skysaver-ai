// SkySaver — shell + leg cards + atoms
const { useState, useEffect, useRef } = React;
const Icon = window.Icon;

function Badge({ tone = 'neutral', children }) {
  return <span className={'badge badge-' + tone}>{children}</span>;
}

const NAV = [
  { id: 'app', label: 'Dashboard', icon: 'dashboard' },
  { id: 'trip', label: 'Trip details', icon: 'route' },
  { id: 'plan', label: 'Plan a trip', icon: 'plus' },
  { id: 'preferences', label: 'Preferences', icon: 'sliders' },
  { id: 'settings', label: 'Settings', icon: 'settings' },
];

const PAGE_LINK = {
  app: '/app.html', trip: '/trip.html', plan: '/plan.html',
  preferences: '/preferences.html', settings: '/settings.html',
};

function Sidebar({ active, collapsed, onToggle }) {
  const T = window.SKY.TRIP;
  return (
    <aside className="sidebar">
      <a className="sb-brand" href="/index.html">
        <span className="mark"><Icon name="plane" size={17} stroke={2.2} /></span>
        <span>SkySaver <span style={{ fontWeight: 500, color: 'var(--slate-400)' }}>AI</span></span>
      </a>
      <nav className="sb-nav">
        {NAV.map(n => (
          <a key={n.id} className={'sb-item' + (active === n.id ? ' active' : '')} href={PAGE_LINK[n.id]} title={n.label}>
            <span className="ico"><Icon name={n.icon} size={19} stroke={active === n.id ? 2.2 : 1.9} /></span>
            <span className="lbl">{n.label}</span>
          </a>
        ))}
      </nav>
      <div className="sb-spacer" />
      <div className="sb-trip">
        <div className="lbl">Active trip</div>
        <div className="nm">{T.title}</div>
        <div className="dt">{T.dates} · {T.legs.length} legs</div>
      </div>
      <div className="sb-collapse" onClick={onToggle}>
        <Icon name={collapsed ? 'chevronRight' : 'chevronLeft'} size={18} />
        <span>Collapse</span>
      </div>
    </aside>
  );
}

function TopBar({ user, onToggleSidebar, hasAlert, onLogout }) {
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <header className="topbar">
      <div className="tb-search">
        <Icon name="search" size={17} />
        <input placeholder="Search trips, legs, airports…" />
        <kbd>⌘K</kbd>
      </div>
      <div className="tb-spacer" />
      <div className="tb-icon" title="What's new"><Icon name="sparkles" size={19} /></div>
      <div className="tb-icon" title="Notifications">
        <Icon name="bell" size={19} />
        {hasAlert && <span className="dot" />}
      </div>
      <div className="tb-user" style={{ position: 'relative', cursor: 'pointer' }} onClick={() => setMenuOpen(o => !o)}>
        <div className="avatar">{user.initials}</div>
        <div>
          <div className="un">{user.name}</div>
          <div className="up">{user.plan} plan</div>
        </div>
        <Icon name="chevronDown" size={15} style={{ color: 'var(--slate-400)' }} />
        {menuOpen && (
          <div style={{ position: 'absolute', top: 'calc(100% + 6px)', right: 0, background: '#fff', border: '1px solid var(--slate-200)', borderRadius: 12, boxShadow: 'var(--sh-md)', minWidth: 200, zIndex: 50, overflow: 'hidden' }}>
            <a href="/settings.html" style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '11px 14px', color: 'var(--slate-700)', fontSize: 14, textDecoration: 'none' }}>
              <Icon name="settings" size={15} /> Settings
            </a>
            <a href="/preferences.html" style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '11px 14px', color: 'var(--slate-700)', fontSize: 14, textDecoration: 'none', borderTop: '1px solid var(--slate-100)' }}>
              <Icon name="sliders" size={15} /> Preferences
            </a>
            <div onClick={(e) => { e.stopPropagation(); if (onLogout) onLogout(); }} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '11px 14px', color: '#B91C1C', fontSize: 14, borderTop: '1px solid var(--slate-100)' }}>
              <Icon name="arrowUpRight" size={15} /> Log out
            </div>
          </div>
        )}
      </div>
    </header>
  );
}

function Tile({ label, value, sub, color }) {
  return (
    <div className="tile">
      <div className="bar" style={{ background: color }} />
      <div className="tl">{label}</div>
      <div className="tv">{value}</div>
      <div className="tvs">{sub}</div>
    </div>
  );
}

const LEG_ICON = { flight: 'plane', hotel: 'bed', transport: 'car', meeting: 'calendar' };
const LEG_LINK = { flight: 'Manage flight', hotel: 'Manage stay', transport: 'Order ride', meeting: 'Open map' };

// Airline IATA → official booking URL (with route + date when supported).
const AIRLINE_URLS = {
  EK: 'https://www.emirates.com/',
  SQ: 'https://www.singaporeair.com/',
  BA: 'https://www.britishairways.com/',
  QR: 'https://www.qatarairways.com/',
  AI: 'https://www.airindia.com/',
  AF: 'https://www.airfrance.com/',
  KL: 'https://www.klm.com/',
  LH: 'https://www.lufthansa.com/',
  TK: 'https://www.turkishairlines.com/',
  ET: 'https://www.ethiopianairlines.com/',
  EY: 'https://www.etihad.com/',
  SV: 'https://www.saudia.com/',
  DL: 'https://www.delta.com/',
  AA: 'https://www.aa.com/',
  UA: 'https://www.united.com/',
  AC: 'https://www.aircanada.com/',
  CX: 'https://www.cathaypacific.com/',
  JL: 'https://www.jal.com/',
  NH: 'https://www.ana.co.jp/',
  KE: 'https://www.koreanair.com/',
  TG: 'https://www.thaiairways.com/',
  MH: 'https://www.malaysiaairlines.com/',
  GA: 'https://www.garuda-indonesia.com/',
  '6E': 'https://www.goindigo.in/',
  FZ: 'https://www.flydubai.com/',
  MS: 'https://www.egyptair.com/',
  QF: 'https://www.qantas.com/',
};

// Build the destination URL synchronously from the leg's data. Never returns
// empty — falls back to a Google search so clicking always opens something.
function buildLegUrl(leg) {
  if (leg.type === 'flight') {
    const code = (leg.code || leg.airline || '').toString().slice(0, 2).toUpperCase();
    if (AIRLINE_URLS[code]) return AIRLINE_URLS[code];
    const name = leg.carrier || code || 'airline booking';
    return 'https://www.google.com/search?q=' + encodeURIComponent(name + ' official site book flights');
  }
  if (leg.type === 'hotel') {
    const name = leg.title || '';
    const city = leg.carrier || '';
    return 'https://www.booking.com/search.html?ss=' + encodeURIComponent((name + ' ' + city).trim());
  }
  if (leg.type === 'transport') {
    const parts = (leg.title || '').split('→').map(s => s.replace(/^[a-z]+ — /i, '').trim());
    const pickup = parts[0] || '';
    const dropoff = parts[1] || '';
    if (pickup || dropoff) {
      return 'https://m.uber.com/ul/?action=setPickup' +
        (pickup ? '&pickup=' + encodeURIComponent(pickup) : '') +
        (dropoff ? '&dropoff[formatted_address]=' + encodeURIComponent(dropoff) : '');
    }
    return 'https://m.uber.com/ul/';
  }
  if (leg.type === 'meeting') {
    const q = leg.title || leg.meta || '';
    return 'https://www.google.com/maps/search/' + encodeURIComponent(q);
  }
  return '#';
}

function LegCard({ leg, broken }) {
  const tone = leg.status === 'monitoring' ? 'success' : leg.status === 'confirmed' ? 'info'
    : leg.status === 'planned' ? 'warn' : 'neutral';

  // URL is computed once at render time — no async wait, click always works.
  const url = broken ? '#recovery' : buildLegUrl(leg);

  function handleClick(e) {
    if (broken) {
      e.preventDefault();
      const rec = document.querySelector('.recovery');
      if (rec) rec.scrollIntoView({ behavior: 'smooth', block: 'start' });
      return;
    }
    // Defensive: if window.open is blocked, fall back to setting location
    // — Safari sometimes blocks _blank when not user-initiated.
    if (url && !e.defaultPrevented) {
      try { window.open(url, '_blank', 'noopener,noreferrer'); e.preventDefault(); }
      catch (_) { /* let the anchor's default fire */ }
    }
  }

  return (
    <div className={'legc ' + (broken ? 'broken' : leg.type)}>
      <div className="legc-top">
        <div className="legc-ic"><Icon name={broken ? 'siren' : LEG_ICON[leg.type]} size={20} /></div>
        <div className="legc-body">
          <div className="legc-title">{broken ? leg.title + ' — cancelled' : leg.title}</div>
          <div className="legc-time">{leg.time}</div>
          <div className="legc-meta">{leg.meta}</div>
        </div>
        {broken ? <Badge tone="danger">Cancelled</Badge> : <Badge tone={tone}>{leg.statusLabel}</Badge>}
      </div>
      <div className="legc-foot">
        <a
          className="legc-link"
          href={url}
          target={broken ? undefined : '_blank'}
          rel="noopener noreferrer"
          onClick={handleClick}
          style={{ cursor: 'pointer' }}
        >
          {broken ? 'See alternatives' : LEG_LINK[leg.type]} <Icon name="arrowUpRight" size={14} />
        </a>
        {leg.type === 'flight' && !broken && (
          <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--slate-500)' }}>
            <span className="ping"><i /></span> watching
          </span>
        )}
      </div>
    </div>
  );
}

function Expander({ title, icon, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="expander">
      <div className={'exp-head' + (open ? ' open' : '')} onClick={() => setOpen(o => !o)}>
        <Icon name={icon} size={18} style={{ color: 'var(--slate-400)' }} />
        <span className="et">{title}</span>
        <Icon name="chevronDown" size={18} className="chev" />
      </div>
      {open && <div className="exp-body">{children}</div>}
    </div>
  );
}

Object.assign(window, { Badge, Sidebar, TopBar, Tile, LegCard, Expander, NAV, PAGE_LINK, AIRLINE_URLS, buildLegUrl });

function Shell({ active, children }) {
  const [collapsed, setCollapsed] = useState(false);
  return (
    <div className={'app' + (collapsed ? ' collapsed' : '')}>
      <Sidebar active={active} collapsed={collapsed} onToggle={() => setCollapsed(c => !c)} />
      <div>
        <TopBar user={window.SKY.USER} />
        <main className="main">{children}</main>
      </div>
    </div>
  );
}
window.Shell = Shell;
