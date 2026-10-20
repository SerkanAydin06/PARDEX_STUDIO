/* PARDEX Şirket Merkezi — vanilla JS, no external requests. */
(function () {
  'use strict';
  const TOKEN = document.querySelector('meta[name="pardex-token"]').content;
  const $ = (s) => document.querySelector(s);
  const esc = (v) => String(v == null ? '' : v).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const STATUS = { proposed: 'Onay bekliyor', approved: 'Onaylandı', running: 'Çalışıyor', delivered: 'Teslim edildi', accepted: 'Kabul edildi', rejected: 'Reddedildi', failed: 'Takıldı', blocked: 'Engellendi' };
  const STAGES = [['fikir', 'Fikir'], ['degerlendirme', 'Değerlendir'], ['onay', 'Patron onayı'], ['uretim', 'Üretim'], ['kalite', 'Kalite'], ['yayin', 'Yayın'], ['gelir', 'Gelir'], ['arsiv', 'Arşiv']];
  const DSTATE = { calisiyor: 'Çalışıyor', onay: 'Onay bekliyor', bosta: 'Boşta', durdu: 'Durduruldu' };
  let META = null, DASH = null, JOBS = [], FILTER = 'all', VIEW = 'office', poll = null;

  async function api(path, body) {
    const opt = { headers: { 'X-PARDEX-Token': TOKEN } };
    if (body !== undefined) { opt.method = 'POST'; opt.headers['Content-Type'] = 'application/json'; opt.body = JSON.stringify(body); }
    const r = await fetch(path, opt);
    const data = await r.json().catch(() => ({ ok: false, error: 'Yanıt okunamadı' }));
    if (!r.ok || data.ok === false) throw new Error(data.error || ('Hata ' + r.status));
    return body !== undefined ? data.data : data;
  }
  function toast(msg, err) {
    const t = $('#toast'); t.textContent = msg; t.className = 'toast show' + (err ? ' err' : '');
    clearTimeout(t._h); t._h = setTimeout(() => { t.className = 'toast'; }, 3800);
  }
  async function act(fn, okMsg) {
    try { const r = await fn(); if (okMsg) toast(okMsg); await refresh(); return r; }
    catch (e) { toast(e.message, true); }
  }
  const deptName = (k) => (META && META.departments[k] ? META.departments[k].name : k);
  const money = (n) => Number(n || 0).toLocaleString('tr-TR', { maximumFractionDigits: 2 }) + ' ' + ((DASH && DASH.finance.currency) || '');
  function bars(root) { root.querySelectorAll('[data-w]').forEach((el) => { el.style.width = Math.min(100, Number(el.dataset.w)) + '%'; }); }

  /* ---------- job card ---------- */
  function jobCard(j) {
    const cls = j.status === 'accepted' ? ' ok' : (['rejected', 'failed', 'blocked'].includes(j.status) ? ' bad' : '');
    const calls = j.est_calls ? j.est_calls + ' çağrı' : '0 token';
    let btns = '';
    if (j.status === 'proposed') btns = `<button class="btn btn-line" data-act="reject" data-id="${j.id}">Reddet</button><button class="btn btn-teal" data-act="approve" data-id="${j.id}">Onayla</button>`;
    else if (j.status === 'approved') btns = `<button class="btn btn-line" data-act="reject" data-id="${j.id}">İptal</button><button class="btn btn-dark" data-act="run" data-id="${j.id}" data-calls="${j.est_calls}">Şimdi çalıştır</button>`;
    else if (j.status === 'delivered') btns = `<button class="btn btn-line" data-act="view" data-id="${j.id}">Teslimi gör</button><button class="btn btn-line" data-act="reject" data-id="${j.id}">Geri çevir</button><button class="btn btn-teal" data-act="accept" data-id="${j.id}">Kabul et</button>`;
    else if (j.status === 'running') btns = '<span class="muted small">Çalışıyor…</span>';
    else if (j.output) btns = `<button class="btn btn-line" data-act="view" data-id="${j.id}">Çıktıyı gör</button>`;
    if (['failed', 'blocked'].includes(j.status)) btns += `<button class="btn btn-link" data-act="reject" data-id="${j.id}">Arşivle</button>`;
    return `<div class="job${cls}"><div class="job-main">
      <div class="dept-tag">${esc(deptName(j.dept))}</div>
      <div class="job-title">${esc(j.title)}</div>
      <div class="tags"><span>${esc(j.tier)}</span><span>${calls}</span><span>Risk: ${esc(j.risk)}</span><span>${esc(STATUS[j.status] || j.status)}</span></div>
      ${j.note ? `<div class="job-note">${esc(j.note)}</div>` : ''}
    </div><div class="job-actions">${btns}</div></div>`;
  }

  async function onJobClick(ev) {
    const b = ev.target.closest('button[data-act]'); if (!b) return;
    const id = b.dataset.id, a = b.dataset.act;
    if (a === 'view') {
      const j = JOBS.find((x) => x.id === id) || (DASH.approvals || []).find((x) => x.id === id);
      $('#out-title').textContent = j ? j.title : 'Teslim'; $('#out-body').textContent = (j && (j.output || j.note)) || 'Çıktı yok.';
      $('#out-dialog').showModal(); return;
    }
    if (a === 'run') {
      const c = Number(b.dataset.calls || 0);
      const msg = c ? `Bu iş ${c} AI çağrısı kullanacak (abonelik/kota harcar). Başlatılsın mı?` : 'Bu iş yerel çalışır (0 token). Başlatılsın mı?';
      if (!confirm(msg)) return;
      await act(() => api(`/api/job/${id}/run`, {}), 'İş başladı'); startPoll(); return;
    }
    if (a === 'reject') {
      const reason = prompt('Kısa gerekçe (öğrenme için kaydedilir):', '') ;
      if (reason === null) return;
      return act(() => api(`/api/job/${id}/reject`, { reason: reason || 'Patron reddetti' }), 'Kaydedildi');
    }
    return act(() => api(`/api/job/${id}/${a}`, {}), a === 'approve' ? 'Onaylandı — sıraya alındı' : 'Kabul edildi');
  }

  /* ---------- office ---------- */
  function renderOffice(d) {
    const k = d.kpi, pct = k.calls_limit ? Math.round(k.calls_used / k.calls_limit * 100) : 0;
    $('#kpis').innerHTML = `
      <div class="kpi"><div class="kpi-label">Onayını bekleyen</div><div class="kpi-value amber">${k.pending}</div><div class="kpi-label">iş</div></div>
      <div class="kpi"><div class="kpi-label">Son 7 gün kabul edilen</div><div class="kpi-value">${k.delivered_week}</div><div class="kpi-label">teslim</div></div>
      <div class="kpi"><div class="kpi-label">Haftalık AI bütçesi</div><div class="kpi-value">%${pct}</div>
        <div class="bar${pct > 80 ? ' warn' : ''}"><span data-w="${pct}"></span></div><div class="kpi-label">${k.calls_used}/${k.calls_limit} çağrı · bugün ${k.calls_today}/${k.day_limit}</div></div>
      <div class="kpi"><div class="kpi-label">Bu ay net (${esc(d.finance.month)})</div><div class="kpi-value">${esc(money(d.finance.net))}</div><div class="kpi-label">gelir ${esc(money(d.finance.income))} · gider ${esc(money(d.finance.expense))}</div></div>`;
    $('#approvals').innerHTML = d.approvals.length ? d.approvals.map(jobCard).join('') : '<div class="empty">Bekleyen karar yok. Aşağıdan şirkete bir hedef ver.</div>';
    $('#briefing').innerHTML = d.briefing.map((b) => `<div><b>${esc(b.label)}:</b> ${esc(b.text)}</div>`).join('');
    $('#dept-mini').innerHTML = d.departments.map((x) => `<div class="dept"><div class="dept-head"><span class="dept-name">${esc(x.name)}</span><span class="chip ${x.state}">${DSTATE[x.state]}</span></div>
      <div class="dept-cur">${esc(x.current || x.mission)}</div><div class="dept-meta">${esc(x.tier)} · bütçe ${x.used}/${x.budget} · ${x.done} teslim</div></div>`).join('');
    const p = d.pipeline;
    $('#pipeline').innerHTML = STAGES.slice(0, 7).map(([key, label], i) => `<div class="stage${key === 'onay' ? ' you' : ''}${key === 'gelir' ? ' money' : ''}">
      <span class="s">Adım ${i + 1}</span><b>${label}</b><span class="n">${p[key] || 0}</span></div>`).join('');
    bars($('#view-office'));
    const pill = $('#status-pill');
    pill.textContent = d.paused ? 'Şirket durduruldu' : (d.run.running ? 'Bir iş çalışıyor' : 'Şirket çalışıyor');
    pill.className = 'pill' + (d.paused ? ' paused' : '');
    $('#pause-btn').textContent = d.paused ? 'Çalışmayı başlat' : 'Acil durdur';
    if (d.run.error) toast(d.run.error, true);
  }

  /* ---------- jobs ---------- */
  function renderJobs() {
    const keys = ['all', 'proposed', 'approved', 'delivered', 'accepted', 'failed', 'rejected'];
    $('#job-filters').innerHTML = keys.map((k) => `<button type="button" data-f="${k}" aria-pressed="${FILTER === k}">${k === 'all' ? 'Hepsi' : STATUS[k]} (${k === 'all' ? JOBS.length : JOBS.filter((j) => j.status === k || (k === 'failed' && j.status === 'blocked')).length})</button>`).join('');
    const list = JOBS.filter((j) => FILTER === 'all' || j.status === FILTER || (FILTER === 'failed' && j.status === 'blocked'));
    $('#job-list').innerHTML = list.length ? list.map(jobCard).join('') : '<div class="empty">Bu durumda iş yok.</div>';
  }

  /* ---------- ideas ---------- */
  function score() {
    const v = (id) => Number($('#s-' + id).value);
    ['revenue', 'fit', 'effort', 'cost'].forEach((id) => { $('#o-' + id).textContent = v(id); });
    $('#idea-score').textContent = Math.round(((v('revenue') * 2 + v('fit')) - (v('effort') + v('cost')) + 7) / 20 * 100);
  }
  function renderIdeas(list) {
    const opts = STAGES.map(([k, l]) => `<option value="${k}">${l}</option>`).join('');
    $('#idea-board').innerHTML = STAGES.map(([key, label]) => {
      const items = list.filter((i) => i.stage === key);
      return `<div class="col"><h3>${label} (${items.length})</h3>${items.map((i) => `<div class="idea">
        <div>${esc(i.title)}</div><div><b>${i.score}</b>/100 · gelir ${i.revenue} · emek ${i.effort}</div>
        <label class="small" for="st-${i.id}">Aşama</label>
        <select id="st-${i.id}" data-idea="${i.id}">${opts.replace(`value="${key}"`, `value="${key}" selected`)}</select>
        ${['fikir', 'degerlendirme', 'onay'].includes(key) ? `<button class="btn btn-teal" data-build="${i.id}" type="button">Üretime al</button>` : ''}
      </div>`).join('')}</div>`;
    }).join('');
  }

  /* ---------- departments ---------- */
  function renderDepts(d) {
    $('#dept-full').innerHTML = d.departments.map((x) => {
      const pct = x.budget ? Math.round(x.used / x.budget * 100) : 0;
      return `<div class="dept"><div class="dept-head"><span class="dept-name">${esc(x.name)}</span><span class="chip ${x.state}">${DSTATE[x.state]}</span></div>
        <div class="dept-cur">${esc(x.mission)}</div>
        <div class="dept-meta">Kademe ${esc(x.tier)} · bu hafta ${x.used}/${x.budget} çağrı · ${x.done} kabul edilmiş iş</div>
        <div class="bar${pct > 80 ? ' warn' : ''}"><span data-w="${pct}"></span></div>
        <form data-dept="${x.key}"><label class="small" for="dj-${x.key}">Bu departmana iş ver</label>
          <input id="dj-${x.key}" type="text" placeholder="Kısaca ne yapılsın?"><button class="btn btn-dark" type="submit">Öner</button></form></div>`;
    }).join('');
    bars($('#dept-full'));
  }

  /* ---------- finance ---------- */
  function renderFinance(d, rows) {
    const f = d.finance;
    $('#fin-kpis').innerHTML = `
      <div class="kpi"><div class="kpi-label">Bu ay gelir</div><div class="kpi-value">${esc(money(f.income))}</div></div>
      <div class="kpi"><div class="kpi-label">Bu ay gider</div><div class="kpi-value">${esc(money(f.expense))}</div></div>
      <div class="kpi"><div class="kpi-label">Net</div><div class="kpi-value">${esc(money(f.net))}</div></div>
      <div class="kpi"><div class="kpi-label">Bu ay AI çağrısı</div><div class="kpi-value">${f.ai_calls_month}</div><div class="kpi-label">${esc(f.note)}</div></div>`;
    const kinds = { income: 'Gelir', expense: 'Gider', ai_call: 'AI çağrısı' };
    $('#ledger-body').innerHTML = rows.length ? rows.map((r) => `<tr><td>${esc(r.at.slice(0, 16).replace('T', ' '))}</td><td>${esc(deptName(r.dept))}</td><td>${kinds[r.kind]}${r.provider ? ' · ' + esc(r.provider) : ''}</td><td>${r.kind === 'ai_call' ? r.amount : esc(money(r.amount))}</td><td>${esc(r.note)}</td></tr>`).join('') : '<tr><td colspan="5" class="muted">Henüz kayıt yok.</td></tr>';
  }

  /* ---------- settings ---------- */
  function renderSettings(m, evs) {
    const s = m.settings;
    $('#set-project').innerHTML = '<option value="">— Seçilmedi —</option>' + m.projects.map((p) => `<option value="${esc(p.path)}"${p.path === s.default_project ? ' selected' : ''}>${esc(p.name)} (${esc(p.engine)})</option>`).join('');
    $('#set-ollama').value = s.ollama_model || ''; $('#set-limit').value = s.weekly_call_limit; $('#set-currency').value = s.currency;
    $('#budget-grid').innerHTML = Object.entries(m.departments).map(([k, v]) => `<div><label for="b-${k}">${esc(v.name)}</label><input id="b-${k}" data-budget="${k}" type="number" min="0" max="200" value="${s.budgets[k]}"></div>`).join('');
    $('#l-dept').innerHTML = Object.entries(m.departments).map(([k, v]) => `<option value="${k}"${k === 'finans' ? ' selected' : ''}>${esc(v.name)}</option>`).join('');
    $('#events').innerHTML = evs.length ? evs.map((e) => `<div>${esc(e.at.slice(0, 16).replace('T', ' '))} · <b>${esc(e.actor)}</b> · ${esc(e.action)} ${esc(e.ref)} ${esc(e.note)}</div>`).join('') : '<div>Kayıt yok.</div>';
  }

  /* ---------- refresh / nav ---------- */
  async function refresh() {
    DASH = await api('/api/dashboard');
    if (!META) META = await api('/api/settings');
    renderOffice(DASH);
    if (VIEW === 'jobs') { JOBS = await api('/api/jobs'); renderJobs(); }
    if (VIEW === 'ideas') renderIdeas(await api('/api/ideas'));
    if (VIEW === 'depts') renderDepts(DASH);
    if (VIEW === 'finance') renderFinance(DASH, await api('/api/ledger'));
    if (VIEW === 'settings') { META = await api('/api/settings'); renderSettings(META, await api('/api/events')); }
    if (!DASH.run.running && poll) { clearInterval(poll); poll = null; }
  }
  function startPoll() { if (!poll) poll = setInterval(() => refresh().catch(() => {}), 3000); }
  function show(view) {
    VIEW = view;
    document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('active', t.dataset.view === view));
    document.querySelectorAll('.view').forEach((v) => { v.hidden = v.id !== 'view-' + view; });
    refresh().catch((e) => toast(e.message, true));
  }

  /* ---------- events ---------- */
  document.querySelectorAll('.tab').forEach((t) => t.addEventListener('click', () => show(t.dataset.view)));
  $('#approvals').addEventListener('click', onJobClick);
  $('#job-list').addEventListener('click', onJobClick);
  $('#job-filters').addEventListener('click', (e) => { const b = e.target.closest('[data-f]'); if (b) { FILTER = b.dataset.f; renderJobs(); } });
  $('#out-close').addEventListener('click', () => $('#out-dialog').close());
  $('#pause-btn').addEventListener('click', () => {
    const paused = !(DASH && DASH.paused);
    if (paused && !confirm('Şirketi acil durdur: yeni iş başlatılamaz. Devam?')) return;
    act(() => api('/api/pause', { paused }), paused ? 'Şirket durduruldu' : 'Şirket yeniden çalışıyor');
  });
  async function sendGoal(ai) {
    const text = $('#goal-text').value.trim();
    if (text.length < 6) return toast('Hedefi biraz daha açık yaz', true);
    if (ai && !confirm('CEO planı için 1 AI çağrısı yapılacak. Devam?')) return;
    const r = await act(() => api('/api/goal', { text, ai }), null);
    if (r) { $('#goal-text').value = ''; toast(r.jobs.length + ' iş önerildi — Onay Masasında'); }
  }
  $('#goal-form').addEventListener('submit', (e) => { e.preventDefault(); sendGoal(false); });
  $('#goal-ai').addEventListener('click', () => sendGoal(true));
  ['revenue', 'fit', 'effort', 'cost'].forEach((id) => $('#s-' + id).addEventListener('input', score));
  $('#idea-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const v = (id) => Number($('#s-' + id).value);
    const r = await act(() => api('/api/idea', { title: $('#idea-title').value, revenue: v('revenue'), effort: v('effort'), cost: v('cost'), fit: v('fit') }), 'Fikir eklendi');
    if (r) $('#idea-title').value = '';
  });
  $('#idea-board').addEventListener('change', (e) => { const s = e.target.closest('select[data-idea]'); if (s) act(() => api(`/api/idea/${s.dataset.idea}/stage`, { stage: s.value }), 'Aşama güncellendi'); });
  $('#idea-board').addEventListener('click', (e) => { const b = e.target.closest('[data-build]'); if (b) act(() => api(`/api/idea/${b.dataset.build}/build`, {}), 'CEO işleri önerdi — Onay Masasında'); });
  $('#dept-full').addEventListener('submit', async (e) => {
    e.preventDefault(); const f = e.target.closest('form[data-dept]'); const inp = f.querySelector('input');
    const r = await act(() => api('/api/dept-job', { dept: f.dataset.dept, title: inp.value }), 'İş önerildi — Onay Masasında');
    if (r) inp.value = '';
  });
  $('#ledger-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const r = await act(() => api('/api/ledger', { kind: $('#l-kind').value, amount: Number($('#l-amount').value), dept: $('#l-dept').value, note: $('#l-note').value }), 'Deftere yazıldı');
    if (r) { $('#l-amount').value = ''; $('#l-note').value = ''; }
  });
  $('#settings-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const budgets = {}; document.querySelectorAll('[data-budget]').forEach((i) => { budgets[i.dataset.budget] = Number(i.value); });
    act(() => api('/api/settings', { default_project: $('#set-project').value, ollama_model: $('#set-ollama').value.trim(), weekly_call_limit: Number($('#set-limit').value), currency: $('#set-currency').value, budgets }), 'Ayarlar kaydedildi')
      .then(() => { META = null; });
  });

  score();
  refresh().catch((e) => toast(e.message, true));
  setInterval(() => { if (!poll) refresh().catch(() => {}); }, 20000);
})();
