/**
 * property-results-renderer.js
 * 
 * DROP THIS FILE INTO: web/property-results-renderer.js
 * 
 * Then in your existing HTML template (web/index.html or wherever
 * the chat response is rendered), add ONE script tag:
 * 
 *   <script src="/static/property-results-renderer.js"></script>
 *
 * FastAPI already serves web/ as static files, so this just works.
 *
 * ─────────────────────────────────────────────────────────────
 * HOW TO USE IN YOUR EXISTING CHAT CODE
 * ─────────────────────────────────────────────────────────────
 * When you receive an AI response that contains property results,
 * instead of inserting raw text into the chat bubble, call:
 *
 *   const html = PropertyResultsRenderer.render(responseData);
 *   chatBubbleElement.innerHTML = html;
 *   PropertyResultsRenderer.bindEvents(chatBubbleElement);
 *
 * Where `responseData` is shaped like:
 * {
 *   summary: "Found 2 detached properties...",
 *   properties: [
 *     {
 *       address: "108 High Street",
 *       town: "Epsom", postcode: "RH1 58NU",
 *       price: 1332000, date: "17 Apr 2024",
 *       tenure: "Freehold", type: "Detached",
 *       station: "Epsom", distance: "0.4 mi",
 *       badge: "Recent Sale"   // optional
 *     }, ...
 *   ],
 *   sql: "SELECT ...",         // optional — shown in evidence panel
 *   note: "Bedroom count...",  // optional — shown as tip
 *   meta: {                    // optional stats for evidence panel
 *     rows: 2,
 *     postcodes: "KT17, KT18, KT19",
 *     filter: "Detached"
 *   }
 * }
 * ─────────────────────────────────────────────────────────────
 */

const PropertyResultsRenderer = (() => {

  function formatPrice(p) {
    return '£' + Number(p).toLocaleString('en-GB');
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function highlightSql(sql) {
    const keywords = ['SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'ORDER BY', 'LIMIT',
                      'LIKE', 'AS', 'IN', 'NOT', 'NULL', 'IS', 'UPPER', 'DISTINCT'];
    let safe = escapeHtml(sql);
    keywords.forEach(kw => {
      const re = new RegExp(`\\b(${kw})\\b`, 'g');
      safe = safe.replace(re, `<span class="pr-sql-kw">${kw}</span>`);
    });
    return safe;
  }

  function renderCard(p) {
    const badge = p.badge
      ? `<span class="pr-badge">${escapeHtml(p.badge)}</span>`
      : '';
    return `
      <div class="pr-card">
        <div class="pr-card-accent"></div>
        <div class="pr-card-top">
          <div class="pr-card-left">
            ${badge}
            <div class="pr-card-address">${escapeHtml(p.address)}</div>
            <div class="pr-card-sub">${escapeHtml(p.town)} · ${escapeHtml(p.postcode)}</div>
          </div>
          <div class="pr-card-right">
            <div class="pr-card-price">${formatPrice(p.price)}</div>
            <div class="pr-card-date">Sold ${escapeHtml(p.date)}</div>
          </div>
        </div>
        <div class="pr-tags">
          <span class="pr-tag">🏠 ${escapeHtml(p.type)}</span>
          <span class="pr-tag">📋 ${escapeHtml(p.tenure)}</span>
          <span class="pr-tag">🚉 ${escapeHtml(p.station)} Station · ${escapeHtml(p.distance)}</span>
        </div>
      </div>`;
  }

  function renderEvidence(data) {
    if (!data.sql && !data.meta) return '';
    const sqlBlock = data.sql ? `
      <div class="pr-sql-wrap">
        <div class="pr-sql-header">
          <span class="pr-sql-label">SQL Query</span>
          <button class="pr-copy-btn" data-copy="${escapeHtml(data.sql)}">Copy</button>
        </div>
        <pre class="pr-sql-body">${highlightSql(data.sql)}</pre>
      </div>` : '';

    const meta = data.meta || {};
    const statsBlock = `
      <div class="pr-stats">
        <div class="pr-stat"><div class="pr-stat-val">${escapeHtml(String(meta.rows ?? data.properties?.length ?? '–'))}</div><div class="pr-stat-lbl">Rows Returned</div></div>
        <div class="pr-stat"><div class="pr-stat-val">${escapeHtml(String(meta.postcodes ?? '–'))}</div><div class="pr-stat-lbl">Postcodes</div></div>
        <div class="pr-stat"><div class="pr-stat-val">${escapeHtml(String(meta.filter ?? '–'))}</div><div class="pr-stat-lbl">Filter</div></div>
      </div>`;

    return `
      <div class="pr-evidence" style="display:none">
        ${sqlBlock}
        ${statsBlock}
      </div>`;
  }

  function render(data) {
    const count = (data.properties || []).length;
    const cards = (data.properties || []).map(renderCard).join('');
    const note = data.note
      ? `<div class="pr-note">💡 <span>${escapeHtml(data.note)}</span></div>`
      : '';

    return `
      <style>
        .pr-wrap { font-family: 'Segoe UI', 'Helvetica Neue', sans-serif; max-width: 660px; }
        .pr-header { background: linear-gradient(135deg, #1a3a5c 0%, #2e6da4 100%); border-radius: 14px 14px 0 0; padding: 18px 22px; display:flex; align-items:center; gap:12px; }
        .pr-header-icon { width:38px; height:38px; border-radius:50%; background:rgba(255,255,255,0.15); display:flex; align-items:center; justify-content:center; font-size:18px; flex-shrink:0; }
        .pr-header-title { color:#fff; font-weight:700; font-size:15px; }
        .pr-header-sub { color:rgba(255,255,255,0.65); font-size:12px; margin-top:2px; }
        .pr-header-count { margin-left:auto; background:rgba(255,255,255,0.15); border-radius:20px; padding:4px 13px; color:#fff; font-size:13px; font-weight:600; white-space:nowrap; }
        .pr-body { background:#fff; border:1px solid #e0e4ec; border-top:none; border-radius:0 0 14px 14px; padding:20px 22px; display:flex; flex-direction:column; gap:14px; box-shadow:0 4px 20px rgba(0,0,0,0.07); }
        .pr-summary { margin:0; color:#4a5568; font-size:14px; line-height:1.65; background:#f8faff; border-left:3px solid #2e6da4; padding:10px 14px; border-radius:0 8px 8px 0; }
        .pr-card { background:#fff; border:1px solid #e8eaed; border-radius:12px; padding:18px 20px; display:flex; flex-direction:column; gap:12px; box-shadow:0 2px 8px rgba(0,0,0,0.05); position:relative; overflow:hidden; transition:box-shadow 0.2s; }
        .pr-card:hover { box-shadow:0 6px 24px rgba(0,0,0,0.1); }
        .pr-card-accent { position:absolute; top:0; left:0; right:0; height:4px; background:linear-gradient(90deg,#1a3a5c,#2e6da4); }
        .pr-card-top { display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:8px; }
        .pr-badge { display:inline-block; background:#e8f4e8; color:#1e7e34; font-size:11px; font-weight:700; letter-spacing:.06em; text-transform:uppercase; padding:3px 9px; border-radius:20px; margin-bottom:5px; }
        .pr-card-address { font-size:16px; font-weight:700; color:#111; font-family:Georgia,serif; }
        .pr-card-sub { font-size:13px; color:#5f6368; margin-top:2px; }
        .pr-card-right { text-align:right; }
        .pr-card-price { font-size:21px; font-weight:800; color:#1a3a5c; font-family:Georgia,serif; letter-spacing:-.5px; }
        .pr-card-date { font-size:12px; color:#888; margin-top:2px; }
        .pr-tags { display:flex; gap:7px; flex-wrap:wrap; }
        .pr-tag { display:inline-flex; align-items:center; gap:5px; background:#f1f4f9; color:#3c4858; font-size:12px; font-weight:500; padding:5px 10px; border-radius:7px; }
        .pr-note { display:flex; gap:9px; align-items:flex-start; background:#fffbeb; border:1px solid #f6d860; border-radius:9px; padding:11px 13px; font-size:13px; color:#7a5c00; line-height:1.6; }
        .pr-evidence-toggle { display:flex; align-items:center; gap:7px; background:none; border:1px solid #d0d7e3; color:#4a5568; font-size:12.5px; font-weight:600; padding:7px 13px; border-radius:8px; cursor:pointer; transition:background .15s; }
        .pr-evidence-toggle:hover { background:#f1f4f9; }
        .pr-evidence { margin-top:10px; display:flex; flex-direction:column; gap:10px; }
        .pr-sql-wrap { background:#0f1923; border-radius:9px; overflow:hidden; }
        .pr-sql-header { display:flex; justify-content:space-between; align-items:center; padding:7px 13px; background:#1b2836; }
        .pr-sql-label { color:#7a8a9a; font-family:monospace; font-size:11px; letter-spacing:.08em; text-transform:uppercase; }
        .pr-copy-btn { background:none; border:1px solid #334; color:#7a8a9a; font-size:11px; padding:3px 9px; border-radius:5px; cursor:pointer; }
        .pr-copy-btn:hover { color:#fff; border-color:#556; }
        .pr-sql-body { margin:0; padding:13px 15px; color:#c9d1d9; font-family:'Courier New',monospace; font-size:12.5px; line-height:1.65; overflow-x:auto; }
        .pr-sql-kw { color:#58a6ff; font-weight:600; }
        .pr-stats { display:flex; gap:10px; }
        .pr-stat { flex:1; background:#f8faff; border:1px solid #e0e4ec; border-radius:9px; padding:11px 14px; text-align:center; }
        .pr-stat-val { font-size:18px; font-weight:800; color:#1a3a5c; }
        .pr-stat-lbl { font-size:11px; color:#6b7280; margin-top:2px; }
        .pr-feedback { display:flex; align-items:center; gap:9px; padding-top:4px; border-top:1px solid #f0f0f0; }
        .pr-feedback-lbl { font-size:12px; color:#9ca3af; }
        .pr-fb-btn { background:none; border:1px solid #e0e4ec; color:#4a5568; font-size:12px; padding:4px 12px; border-radius:20px; cursor:pointer; transition:all .15s; }
        .pr-fb-btn:hover { background:#e8f4e8; border-color:#4caf50; }
        .pr-fb-btn.negative:hover { background:#fce8e8; border-color:#f44336; }
        .pr-chevron { display:inline-block; transition:transform .2s; font-size:10px; }
        .pr-chevron.open { transform:rotate(180deg); }
      </style>
      <div class="pr-wrap">
        <div class="pr-header">
          <div class="pr-header-icon">🏘</div>
          <div>
            <div class="pr-header-title">Property Search Results</div>
            <div class="pr-header-sub">${escapeHtml(data.filterLabel || 'Detached · Epsom area')}</div>
          </div>
          <div class="pr-header-count">${count} result${count !== 1 ? 's' : ''}</div>
        </div>
        <div class="pr-body">
          <p class="pr-summary">${escapeHtml(data.summary || '')}</p>
          ${cards}
          ${note}
          <div>
            <button class="pr-evidence-toggle" onclick="PropertyResultsRenderer._toggleEvidence(this)">
              🔍 View Evidence &amp; SQL <span class="pr-chevron">▼</span>
            </button>
            ${renderEvidence(data)}
          </div>
          <div class="pr-feedback">
            <span class="pr-feedback-lbl">Was this helpful?</span>
            <button class="pr-fb-btn" onclick="PropertyResultsRenderer._feedback(this, 'helpful')">👍 Helpful</button>
            <button class="pr-fb-btn negative" onclick="PropertyResultsRenderer._feedback(this, 'needsfix')">👎 Needs Fix</button>
          </div>
        </div>
      </div>`;
  }

  // ── Event handlers (called via inline onclick) ──────────────────

  function _toggleEvidence(btn) {
    const panel = btn.parentElement.querySelector('.pr-evidence');
    const chevron = btn.querySelector('.pr-chevron');
    const isOpen = panel.style.display !== 'none';
    panel.style.display = isOpen ? 'none' : 'flex';
    chevron.classList.toggle('open', !isOpen);
    btn.childNodes[0].textContent = (!isOpen ? '🔍 Hide' : '🔍 View') + ' Evidence & SQL ';
  }

  function _feedback(btn, type) {
    btn.style.background = type === 'helpful' ? '#e8f4e8' : '#fce8e8';
    btn.style.borderColor = type === 'helpful' ? '#4caf50' : '#f44336';
    btn.textContent = type === 'helpful' ? '👍 Thanks!' : '👎 Noted';
    btn.disabled = true;
    // Fire your existing feedback handler if present
    if (window.submitCopilotFeedback) {
      window.submitCopilotFeedback(type);
    }
  }

  // Attach copy button events after inserting HTML into the DOM
  function bindEvents(container) {
    container.querySelectorAll('.pr-copy-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const text = btn.getAttribute('data-copy');
        navigator.clipboard.writeText(text).then(() => {
          const orig = btn.textContent;
          btn.textContent = '✓ Copied';
          setTimeout(() => btn.textContent = orig, 1800);
        });
      });
    });
  }

  return { render, bindEvents, _toggleEvidence, _feedback };

})();
