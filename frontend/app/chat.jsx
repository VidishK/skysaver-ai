// SkySaver — Gemini chat side rail
const { useState: useStateC, useRef: useRefC, useEffect: useEffectC } = React;

// ----- Tiny markdown renderer for chat bubbles -----
// Handles **bold**, *italic*, `code`, [link](url), bullet lists (* / -),
// blank-line paragraphs, and inline line breaks. Stays under ~50 lines so it
// can live with the chat component without pulling in a markdown dep.
function escapeHtml(s) {
  return s.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function renderInline(s) {
  // Bold: **text** or __text__
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/__([^_]+)__/g, '<strong>$1</strong>');
  // Italic: *text* or _text_  (skip leading bullet markers handled separately)
  s = s.replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>');
  s = s.replace(/(^|[^_])_([^_\n]+)_/g, '$1<em>$2</em>');
  // Inline code: `code`
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Links: [label](url)
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  return s;
}

function renderMarkdown(text) {
  if (!text) return '';
  const safe = escapeHtml(text);
  const lines = safe.split(/\r?\n/);
  const out = [];
  let inList = false;
  let para = [];

  function flushPara() {
    if (para.length) {
      out.push('<p>' + renderInline(para.join(' ')) + '</p>');
      para = [];
    }
  }

  for (const raw of lines) {
    const line = raw.trim();
    const bullet = line.match(/^[*\-]\s+(.+)/);
    if (bullet) {
      flushPara();
      if (!inList) { out.push('<ul>'); inList = true; }
      out.push('<li>' + renderInline(bullet[1]) + '</li>');
    } else if (line === '') {
      flushPara();
      if (inList) { out.push('</ul>'); inList = false; }
    } else {
      if (inList) { out.push('</ul>'); inList = false; }
      para.push(line);
    }
  }
  flushPara();
  if (inList) out.push('</ul>');
  return out.join('');
}

function ChatRail() {
  const SUG = window.SKY.CHAT_SUGGESTIONS;
  const [msgs, setMsgs] = useStateC([]);
  const [val, setVal] = useStateC('');
  const [typing, setTyping] = useStateC(false);
  const bodyRef = useRefC(null);

  useEffectC(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
  }, [msgs, typing]);

  async function send(text) {
    const q = (text || val).trim();
    if (!q) return;
    const userMsg = { role: 'user', text: q };
    setMsgs(m => [...m, userMsg]);
    setVal(''); setTyping(true);

    try {
      // Build the history payload in the shape our backend expects
      // (role: 'user' | 'assistant', content: string).
      const history = msgs.map(m => ({ role: m.role === 'user' ? 'user' : 'assistant', content: m.text }));
      const res = await window.SkyAPI.chat(q, history);
      const text = (res && res.response) || 'I\'m not sure — try rephrasing?';
      setMsgs(m => [...m, { role: 'bot', text, actions: [] }]);
    } catch (err) {
      const offline = err && err.status === 401
        ? 'You need to sign in for the chat to read your trip.'
        : 'I had trouble reaching the model — ' + (err && err.message || 'unknown error');
      setMsgs(m => [...m, { role: 'bot', text: offline, actions: [] }]);
    } finally {
      setTyping(false);
    }
  }

  return (
    <div className="chat-rail">
      <div className="chat-head">
        <div className="ch-t"><Icon name="sparkles" size={18} /> Ask SkySaver</div>
        <div className="ch-s">Powered by Gemini · reads your trip via MongoDB MCP</div>
      </div>
      <div className="chat-body thin-scroll" ref={bodyRef}>
        {msgs.length === 0 && (
          <div className="chat-empty">
            <div className="ce-ic"><Icon name="sparkles" size={26} /></div>
            <h4>Your trip, in plain language</h4>
            <p>Ask anything — SkySaver reads your live itinerary to answer.</p>
            {SUG.map((s, i) => (
              <button key={i} className="chip" onClick={() => send(s)}>{s}</button>
            ))}
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={'bubble ' + (m.role === 'user' ? 'user' : 'bot')}>
            {m.role === 'user'
              ? <span>{m.text}</span>
              : <div className="bubble-md" dangerouslySetInnerHTML={{ __html: renderMarkdown(m.text) }} />}
            {m.actions && m.actions.length > 0 && (
              <div className="bubble-actions">
                {m.actions.map((a, j) => (
                  <a key={j} className="bubble-act"><Icon name={a.icon} size={13} /> {a.label} <Icon name="arrowUpRight" size={11} /></a>
                ))}
              </div>
            )}
          </div>
        ))}
        {typing && <div className="typing"><i /><i /><i /></div>}
      </div>
      <div className="chat-input">
        <input value={val} onChange={e => setVal(e.target.value)} onKeyDown={e => e.key === 'Enter' && send()} placeholder="Ask about your trip…" />
        <button className="send-btn" onClick={() => send()} disabled={!val.trim()}><Icon name="send" size={18} /></button>
      </div>
    </div>
  );
}

window.ChatRail = ChatRail;
