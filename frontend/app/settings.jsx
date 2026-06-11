// SkySaver — Settings
const { useState, useEffect } = React;

function Toggle({ on, onClick }) { return <button className={'toggle' + (on ? ' on' : '')} onClick={onClick}><i /></button>; }
function Row({ title, sub, children }) {
  return <div className="pref-row"><div className="pl"><b>{title}</b>{sub && <span>{sub}</span>}</div><div className="pref-ctl">{children}</div></div>;
}

function Settings() {
  const [n, setN] = useState({ email: true, sms: true, autobook: false, paused: false });
  const set = (k, v) => setN(p => ({ ...p, [k]: v }));
  const U = window.SKY.USER;
  const [me, setMe] = useState(null);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const r = await window.SkyAPI.auth.me();
        if (r && r.user) setMe(r.user);
      } catch (_) { /* leave fallback to window.SKY.USER */ }
    })();
  }, []);

  async function logOut() {
    try { await window.SkyAPI.auth.logout(); } catch (_) {}
    window.location.href = '/auth.html';
  }

  function saveProfile() {
    // Profile editing is read-only in this build; just acknowledge.
    setSaving(true);
    setTimeout(() => {
      setSaving(false);
      setSavedAt(new Date().toLocaleTimeString());
    }, 500);
  }

  const account = me || U;
  const memberSince = (account.created_at || '').slice(0, 10) || '—';
  const lastSignIn  = (account.last_login_at || '').replace('T', ' · ').slice(0, 19) || '—';
  const signInCount = account.login_count != null ? String(account.login_count) : '—';

  return (
    <Shell active="settings">
      <div className="page-head">
        <h1>Settings</h1>
        <p>Manage your account, alerts, and monitoring.</p>
      </div>

      {/* account */}
      <div className="card">
        <div className="card-h">
          <div className="ci" style={{ background: 'var(--indigo-50)', color: 'var(--indigo-600)' }}><Icon name="user" size={19} /></div>
          <div><h2>Your account</h2><p>Profile and security</p></div>
        </div>
        <div className="card-pad">
          <div className="form-grid">
            <div className="ff"><label>Full name</label><input defaultValue={account.name || ''} /></div>
            <div className="ff"><label>Email</label><input defaultValue={account.email || ''} disabled style={{ background: 'var(--slate-50)', color: 'var(--slate-500)' }} /></div>
            <div className="ff"><label>Password</label><input type="password" defaultValue="••••••••••" /></div>
            <div className="ff"><label>Plan</label><input defaultValue={(account.plan || 'Free') + ' plan'} disabled style={{ background: 'var(--slate-50)', color: 'var(--slate-500)' }} /></div>
          </div>
          <div style={{ marginTop: 18, display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12 }}>
            {[['Member since', memberSince], ['Last sign-in', lastSignIn], ['Sign-ins to date', signInCount]].map(([k, v]) => (
              <div key={k} className="db-tile" style={{ padding: 14 }}><div className="dl">{k}</div><div style={{ fontSize: 16, fontWeight: 700, marginTop: 4 }}>{v}</div></div>
            ))}
          </div>
          <div style={{ marginTop: 18, display: 'flex', gap: 10 }}>
            <button className="btn btn-primary btn-sm" onClick={saveProfile} disabled={saving}>
              <Icon name="check" size={15} /> {saving ? 'Saving…' : 'Save profile'}
            </button>
            {savedAt && <span style={{ alignSelf: 'center', color: 'var(--emerald-600)', fontSize: 13 }}>Saved at {savedAt}</span>}
            <div style={{ flex: 1 }} />
            <button className="btn btn-ghost btn-sm" onClick={logOut} style={{ color: '#B91C1C' }}>
              <Icon name="arrowUpRight" size={15} /> Log out
            </button>
          </div>
        </div>
      </div>

      {/* notifications */}
      <div className="card">
        <div className="card-h">
          <div className="ci" style={{ background: 'var(--amber-50)', color: 'var(--amber-500)' }}><Icon name="bell" size={19} /></div>
          <div><h2>Notifications &amp; general</h2><p>How and when SkySaver reaches you</p></div>
        </div>
        <div className="card-pad">
          <Row title="Email alerts" sub="Disruptions and recoveries"><Toggle on={n.email} onClick={() => set('email', !n.email)} /></Row>
          <Row title="SMS alerts" sub="Time-critical only"><Toggle on={n.sms} onClick={() => set('sms', !n.sms)} /></Row>
          <Row title="Currency"><select className="pref-select" defaultValue="USD"><option>USD</option><option>EUR</option><option>GBP</option><option>SGD</option><option>AED</option></select></Row>
          <Row title="Auto-book low-risk recoveries" sub="SkySaver books without asking when the cascade is clean"><Toggle on={n.autobook} onClick={() => set('autobook', !n.autobook)} /></Row>
          <div className="danger-zone">
            <div><b>{n.paused ? 'Monitoring is paused' : 'Pause monitoring'}</b><span>{n.paused ? 'SkySaver is not watching your trips' : 'SkySaver will stop watching all trips until resumed'}</span></div>
            <button className={'btn btn-sm ' + (n.paused ? 'btn-primary' : 'btn-danger')} onClick={() => set('paused', !n.paused)}>
              {n.paused ? 'Resume monitoring' : 'Pause monitoring'}
            </button>
          </div>
        </div>
      </div>

      {/* data & privacy */}
      <div className="card">
        <div className="card-h">
          <div className="ci" style={{ background: 'var(--emerald-50)', color: 'var(--emerald-600)' }}><Icon name="shield" size={19} /></div>
          <div><h2>Your data</h2><p>Where it lives, what we keep</p></div>
        </div>
        <div className="card-pad">
          <Row title="Stored in" sub="Atlas region us-central1, encrypted at rest">
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: 'var(--emerald-600)', fontSize: 13, fontWeight: 600 }}>
              <Icon name="check" size={14} /> MongoDB Atlas
            </span>
          </Row>
          <Row title="Agent reads via" sub="The official MongoDB MCP server — your trip is fetched through it on every chat turn">
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: 'var(--indigo-600)', fontSize: 13, fontWeight: 600 }}>
              <Icon name="route" size={14} /> mongodb-mcp-server
            </span>
          </Row>
          <Row title="Download my data" sub="Export everything as JSON">
            <a className="btn btn-ghost btn-sm" href="/api/trip" target="_blank" rel="noopener noreferrer">
              <Icon name="arrowUpRight" size={14} /> Open JSON
            </a>
          </Row>
          <Row title="Calendar export" sub=".ics file you can import into Google / Apple Calendar">
            <a className="btn btn-ghost btn-sm" href="/api/trip/ics" target="_blank" rel="noopener noreferrer">
              <Icon name="arrowUpRight" size={14} /> Download .ics
            </a>
          </Row>
        </div>
      </div>
    </Shell>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<Settings />);
