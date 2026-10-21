/* PARDEX Şirket Merkezi — vanilla JS, no external requests. */
(function () {
  'use strict';
  const TOKEN = document.querySelector('meta[name="pardex-token"]').content;
  const $ = (s) => document.querySelector(s);
  const esc = (v) => String(v == null ? '' : v).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const STATUS = { proposed: 'Onay bekliyor', approved: 'Onaylandı', running: 'Çalışıyor', delivered: 'Teslim edildi', accepted: 'Kabul edildi', rejected: 'Reddedildi', failed: 'Takıldı', blocked: 'Engellendi' };
  const STAGES = [['fikir', 'Fikir'], ['degerlendirme', 'Değerlendir'], ['onay', 'Patron onayı'], ['uretim', 'Üretim'], ['kalite', 'Kalite'], ['yayin', 'Yayın'], ['gelir', 'Gelir'], ['arsiv', 'Arşiv']];
  const DSTATE = { calisiyor: 'Çalışıyor', onay: 'Onay bekliyor', bosta: 'Boşta', durdu: 'Durduruldu' };
  let META = null, DASH = null, JOBS = [], FILTER = 'all', VIEW = 'office', poll = null, PID = '';
  const PSTAGE = { planlama: 'Planlama', uretim: 'Üretimde', soru: 'Karar bekliyor', teslim: 'Teslim edildi', tamamlandi: 'Tamamlandı', durdu: 'Durdu', iptal: 'İptal' };
  const KSTATE = { bekliyor: 'Sırada', calisiyor: 'Çalışıyor', duzeltme: 'Düzeltmede', kayit: 'Kayıt bekliyor', tamam: 'Kontrolden geçti', takildi: 'Takıldı', atlandi: 'Atlandı' };

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
    $('#office-questions').innerHTML = questionCards(d.questions || []);
    $('#approvals').innerHTML = d.approvals.length ? d.approvals.map(jobCard).join('') : '<div class="empty">Bekleyen karar yok. Aşağıdan şirkete bir hedef ver.</div>';
    $('#briefing').innerHTML = d.briefing.map((b) => `<div><b>${esc(b.label)}:</b> ${esc(b.text)}</div>`).join('');
    $('#dept-mini').innerHTML = d.departments.map((x) => `<div class="dept"><div class="dept-head"><span class="dept-name">${esc(x.name)}</span><span class="chip ${x.state}">${DSTATE[x.state]}</span></div>
      <div class="dept-cur">${esc(x.current || x.mission)}</div><div class="dept-meta">${esc(x.tier)} · bütçe ${x.used}/${x.budget} · ${x.done} teslim</div></div>`).join('');
    const p = d.pipeline;
    $('#pipeline').innerHTML = STAGES.slice(0, 7).map(([key, label], i) => `<div class="stage${key === 'onay' ? ' you' : ''}${key === 'gelir' ? ' money' : ''}">
      <span class="s">Adım ${i + 1}</span><b>${label}</b><span class="n">${p[key] || 0}</span></div>`).join('');
    bars($('#view-office'));
    const pill = $('#status-pill');
    pill.textContent = d.paused ? 'Şirket durduruldu' : (d.production.running ? 'Üretim sürüyor' : (d.run.running ? 'Bir iş çalışıyor' : 'Şirket çalışıyor'));
    pill.className = 'pill' + (d.paused ? ' paused' : '');
    $('#pause-btn').textContent = d.paused ? 'Çalışmayı başlat' : 'Acil durdur';
    if (d.run.error) toast(d.run.error, true);
    if (d.production.error) toast(d.production.error, true);
    if (d.production.running) startPoll();
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
        ${i.note ? `<div class="small muted">${esc(i.note.slice(0, 260))}</div>` : ''}
        ${srcLinks(i.sources)}
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
        <button class="btn btn-line" type="button" data-report="${x.key}">Rapor iste (0 token)</button>
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
    $('#set-day').value = s.day_call_limit; $('#set-root').value = s.projects_root || '';
    $('#budget-grid').innerHTML = Object.entries(m.departments).map(([k, v]) => `<div><label for="b-${k}">${esc(v.name)}</label><input id="b-${k}" data-budget="${k}" type="number" min="0" max="200" value="${s.budgets[k]}"></div>`).join('');
    $('#l-dept').innerHTML = Object.entries(m.departments).map(([k, v]) => `<option value="${k}"${k === 'finans' ? ' selected' : ''}>${esc(v.name)}</option>`).join('');
    $('#events').innerHTML = evs.length ? evs.map((e) => `<div>${esc(e.at.slice(0, 16).replace('T', ' '))} · <b>${esc(e.actor)}</b> · ${esc(e.action)} ${esc(e.ref)} ${esc(e.note)}</div>`).join('') : '<div>Kayıt yok.</div>';
  }


  /* ---------- questions (only important decisions reach the owner) ---------- */
  function questionCards(qs) {
    return qs.map((q) => `<div class="job ask"><div class="job-main">
      <div class="dept-tag">Karar gerekiyor · ${esc(q.product || '')}</div>
      <div class="job-title">${esc(q.text)}</div>
      <div class="job-actions">${(q.options || []).map((o) => `<button class="btn btn-teal" data-q="${q.id}" data-a="${esc(o)}">${esc(o)}</button>`).join('')}</div>
      <form class="q-free" data-qf="${q.id}"><label class="small" for="qa-${q.id}">${(q.options || []).length ? 'Ya da kendi cevabın' : 'Cevabın'}</label>
        <input id="qa-${q.id}" type="text" placeholder="Kısaca yaz"><button class="btn btn-dark" type="submit">Gönder</button></form>
    </div></div>`).join('');
  }
  async function onQuestion(ev) {
    const b = ev.target.closest('button[data-q]'); if (!b) return;
    await act(() => api(`/api/question/${b.dataset.q}/answer`, { answer: b.dataset.a }), 'Cevaplandı — ekip devam ediyor'); startPoll();
  }
  async function onQuestionFree(ev) {
    const f = ev.target.closest('form[data-qf]'); if (!f) return; ev.preventDefault();
    const v = f.querySelector('input').value.trim(); if (v.length < 2) return toast('Cevap boş', true);
    await act(() => api(`/api/question/${f.dataset.qf}/answer`, { answer: v }), 'Cevaplandı — ekip devam ediyor'); startPoll();
  }
  const srcLinks = (raw) => {
    let list = []; try { list = JSON.parse(raw || '[]'); } catch (e) { list = []; }
    return list.length ? `<div class="srcs">${list.map((u, n) => `<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">Kaynak ${n + 1}</a>`).join(' ')}</div>` : '';
  };

  /* ---------- projects ---------- */
  function renderProducts(list) {
    $('#product-list').innerHTML = list.length ? list.map((p) => `<button type="button" class="prod${p.id === PID ? ' sel' : ''}" data-pid="${p.id}">
      <span class="prod-name">${esc(p.name)}</span><span class="chip ${p.open_questions ? 'onay' : (p.stage === 'uretim' ? 'calisiyor' : '')}">${p.open_questions ? 'Karar bekliyor' : PSTAGE[p.stage]}</span>
      <span class="small muted">${p.kind === 'oyun' ? 'Oyun' : 'Uygulama'} · ${esc(p.engine || 'motor seçilmedi')} · ${p.used_calls}/${p.approved_calls} çağrı</span></button>`).join('') : '<div class="empty">Henüz proje yok.</div>';
  }
  function stepper(p) {
    const done = (p.packages || []).filter((k) => k.status === 'tamam').length, all = (p.packages || []).length;
    const idx = { planlama: 0, uretim: 1, soru: 1, durdu: 1, teslim: 3, tamamlandi: 4, iptal: 0 }[p.stage];
    const steps = ['Planlama', 'Üretim', 'Kontrol & düzeltme', 'Teslim', 'Tamam'];
    return `<ol class="steps">${steps.map((s, i) => `<li class="${i < idx ? 'done' : (i === idx ? 'now' : '')}">${s}</li>`).join('')}</ol>
      ${all ? `<div class="small muted">${done}/${all} paket kontrolden geçti</div><div class="bar"><span data-w="${Math.round(done / all * 100)}"></span></div>` : ''}`;
  }
  function specCard(sp) {
    const li = (a) => (a || []).map((x) => `<li>${esc(x)}</li>`).join('');
    return `<div class="spec"><h3>Ürün tarifi</h3>
      <div><b>${esc(sp.name || '')}</b> · ${esc(sp.engine || 'motor ?')} · ${esc(sp.platform || '')}</div>
      <div class="small">${esc(sp.summary || 'Henüz özet yok')}</div>
      ${sp.features && sp.features.length ? `<div class="small muted">Özellikler</div><ul>${li(sp.features)}</ul>` : ''}
      ${sp.acceptance && sp.acceptance.length ? `<div class="small muted">Kabul ölçütleri</div><ul>${li(sp.acceptance)}</ul>` : ''}
      ${sp.out_of_scope && sp.out_of_scope.length ? `<div class="small muted">Kapsam dışı</div><ul>${li(sp.out_of_scope)}</ul>` : ''}
      ${sp.assumptions && sp.assumptions.length ? `<div class="small muted">Varsayımlar</div><ul>${li(sp.assumptions)}</ul>` : ''}</div>`;
  }
  function renderProduct(p) {
    const running = DASH && DASH.production.running === p.id;
    let body = '';
    if (p.stage === 'planlama') {
      const needFolder = p.spec.engine && !['godot', 'web', 'flutter'].includes(p.spec.engine);
      body = `<div class="chat" id="chat-log">${p.chat.map((m) => `<div class="msg ${m.role}"><span class="who">${m.role === 'patron' ? 'Sen' : 'Ürün Müdürü'}</span>${esc(m.text)}</div>`).join('')}</div>
        <form id="chat-form" class="row"><label class="sr" for="chat-text">Mesaj</label><textarea id="chat-text" rows="2" placeholder="Ana hatları anlat…"></textarea>
          <button class="btn btn-dark" type="submit">Gönder</button></form>
        ${specCard(p.spec)}
        ${needFolder ? `<label for="exist-folder">Bu motorda proje resmi editörde açılır. Oluşturduğun klasörün yolu:</label><input id="exist-folder" type="text">` : ''}
        <div class="row"><button class="btn btn-teal" id="do-it" type="button">Bunu yap</button><button class="btn btn-link" id="p-cancel" type="button">Projeyi iptal et</button></div>`;
    } else {
      const qs = p.questions.filter((q) => q.status === 'acik').map((q) => Object.assign({ product: p.name }, q));
      body = `${questionCards(qs)}
        <div class="small muted wrapall">Klasör (ayrı depo): ${esc(p.folder)}</div>
        <div class="stack">${p.packages.map((k) => `<div class="pkg ${k.status}"><div class="pkg-head"><b>${k.seq}. ${esc(k.title)}</b><span class="chip ${k.status === 'calisiyor' || k.status === 'duzeltme' ? 'calisiyor' : (k.status === 'takildi' ? 'onay' : '')}">${KSTATE[k.status]}</span></div>
          <div class="small muted">${esc(META ? (META.departments[k.dept] || {}).name : k.dept)}${k.provider ? ' · ' + esc(k.provider) + ' ' + esc(k.model) : ''}${k.attempts ? ' · ' + k.attempts + ' düzeltme turu' : ''}</div>
          ${k.findings ? `<div class="small">Kontrol: ${esc(k.findings)}</div>` : ''}${k.summary ? `<div class="small">Yapılan: ${esc(k.summary)}</div>` : ''}</div>`).join('')}</div>
        ${p.stage === 'teslim' || p.stage === 'tamamlandi' ? `<pre class="report">${esc(p.report)}</pre>` : ''}
        <div class="row">
          ${p.stage === 'uretim' && p.packages.length === 0 && !running ? '<button class="btn btn-teal" id="p-retry-plan" type="button">İş planını yeniden dene</button>' : ''}
          ${(p.stage === 'uretim' || p.stage === 'durdu') && p.packages.some((k) => ['bekliyor', 'duzeltme', 'calisiyor', 'kayit'].includes(k.status)) && !running ? '<button class="btn btn-dark" id="p-run" type="button">Üretime devam et</button>' : ''}
          ${running ? '<span class="muted">Ekip çalışıyor… (bu sayfa kendini yeniler)</span>' : ''}
          ${p.stage === 'teslim' ? '<button class="btn btn-teal" id="p-accept" type="button">Teslimi kabul et</button>' : ''}
        </div>
        ${(p.stage === 'teslim' || p.stage === 'tamamlandi' || (p.stage === 'durdu' && !running)) ? `<form id="change-form"><label for="change-text">${p.stage === 'durdu' ? 'Değişiklik iste (ekip yeni bir paketle yeniden dener)' : 'Değişiklik iste (ekip düzeltip yeniden teslim eder)'}</label><textarea id="change-text" rows="2"></textarea><div class="row"><button class="btn btn-line" type="submit">Değişikliği gönder</button></div></form>` : ''}`;
    }
    $('#product-detail').innerHTML = `<div class="card-head"><h2>${esc(p.name)}</h2><span class="chip">${PSTAGE[p.stage]}</span></div>${stepper(p)}${body}`;
    bars($('#product-detail'));
    const log = $('#chat-log'); if (log) log.scrollTop = log.scrollHeight;
  }
  async function onProductClick(ev) {
    const t = ev.target.closest('button'); if (!t) return;
    if (t.id === 'do-it') {
      const f = $('#exist-folder');
      if (!confirm('Tarif dondurulacak, proje ayrı klasörde açılacak ve üretim başlayacak. CEO iş paylaşımı için 1 çağrı, sonra her paket için yaklaşık 2 çağrı kullanılır. Başlasın mı?')) return;
      t.disabled = true; t.textContent = 'CEO işleri paylaştırıyor…';
      try {
        const result = await act(() => api(`/api/product/${PID}/start`, { folder: f ? f.value.trim() : '' }), 'Üretim başladı');
        if (result) startPoll();
      } finally {
        t.disabled = false;
        t.textContent = 'Bunu yap';
      }
      return;
    }
    if (t.id === 'p-retry-plan') {
      t.disabled = true; t.textContent = 'İş planı hazırlanıyor…';
      try {
        const result = await act(() => api(`/api/product/${PID}/start`, {}), 'İş planı hazır; üretim başladı');
        if (result) startPoll();
      } finally {
        t.disabled = false; t.textContent = 'İş planını yeniden dene';
      }
      return;
    }
    if (t.id === 'p-run') {
      const result = await act(() => api(`/api/product/${PID}/run`, {}), 'Üretim sürüyor');
      if (result) startPoll();
      return;
    }
    if (t.id === 'p-accept') return act(() => api(`/api/product/${PID}/accept`, {}), 'Proje tamamlandı');
    if (t.id === 'p-cancel') { if (confirm('Proje iptal edilsin mi?')) act(() => api(`/api/product/${PID}/cancel`, {}), 'İptal edildi'); return; }
    return onQuestion(ev);
  }


  /* ---------- Yönetim Kurulu ---------- */
  let ORG = null;
  const HOOKNAME = { '': 'Doğrudan iş', plan_sonrasi: 'Plan sonrası', paket_sonrasi: 'Paket sonrası', teslim_oncesi: 'Teslim öncesi' };
  const MODENAME = { '': '-', rapor: 'Rapor', denetim: 'Denetim (PASS/FAIL)', kod: 'Kod' };
  const PSTATUS = { bekliyor: 'Onay bekliyor', uygulandi: 'Uygulandı', reddedildi: 'Reddedildi' };
  const CORESTATE = { hazirlandi: 'Hazırlandı', kod_hazir: 'Kod yazıldı', test_gecti: 'Test geçti', onaya_hazir: 'Kuruluma hazır', reddedildi: 'Reddedildi', kuruldu: 'Kuruldu' };
  function renderBoard(b, o) {
    ORG = o;
    $('#gmy-log').innerHTML = b.chat.length ? b.chat.map((m) => `<div class="msg ${m.role === 'patron' ? 'patron' : ''}"><span class="who">${m.role === 'patron' ? 'Sen' : 'Genel Müdür Yardımcısı'}</span>${esc(m.text)}</div>`).join('') :
      '<div class="msg"><span class="who">Genel Müdür Yardımcısı</span>Merhaba. Şirkette ne değiştirmek istersin? Departman kurabilir, kapatabilir, görevleri ve iş akışını yeniden düzenleyebilirim. Her öneri senin onayınla uygulanır.</div>';
    const log = $('#gmy-log'); log.scrollTop = log.scrollHeight;
    const pend = b.proposals.filter((p) => p.status === 'bekliyor');
    const past = b.proposals.filter((p) => p.status !== 'bekliyor').slice(0, 5);
    $('#proposals').innerHTML = (pend.length ? pend.map((p) => `<div class="job ask"><div class="job-main">
        <div class="dept-tag">${p.source === 'k0' ? 'Sağlık analizi önerisi' : 'Genel Müdür Yardımcısı önerisi'}</div>
        <div class="job-title">${esc(p.summary)}</div>
        <ul class="small">${p.lines.map((l) => `<li>${esc(l)}</li>`).join('')}</ul>
        ${p.impact ? `<div class="small muted">Etki: ${esc(p.impact)}</div>` : ''}
        ${p.code_request ? `<div class="small">Kod değişikliği gerekiyor: ${esc(p.code_request)}</div>` : ''}
        ${p.error ? `<div class="small">Uygulanamadı: ${esc(p.error)}</div>` : ''}
        <div class="job-actions"><button class="btn btn-line" data-prop="${p.id}" data-pa="reject">Reddet</button>
          ${p.ops.length ? `<button class="btn btn-teal" data-prop="${p.id}" data-pa="approve">Onayla ve uygula</button>` : ''}
          ${p.code_request ? `<button class="btn btn-dark" data-coreprop="${esc(p.code_request)}" data-prop="${p.id}">Çekirdek talebi başlat</button>` : ''}</div>
      </div></div>`).join('') : '<div class="empty">Bekleyen öneri yok.</div>') +
      (past.length ? `<div class="small muted">Son kararlar: ${past.map((p) => `${esc(p.summary)} (${PSTATUS[p.status]})`).join(' · ')}</div>` : '');
    const h = b.health;
    $('#health-summary').innerHTML = `<div>Bu hafta <b>${h.summary.week_calls}/${h.summary.week_limit}</b> çağrı · ${h.summary.departments} departman · takılan paket ${h.summary.stuck_packages}</div>
      <div class="small muted">Kurulu AI: ${esc(h.summary.installed_ai.join(', ') || 'yok')}</div>` + h.notes.map((n) => `<div class="small">• ${esc(n)}</div>`).join('');
    $('#health-suggestions').innerHTML = h.suggestions.length ? h.suggestions.map((x, i) => `<div class="sugg"><span>${esc(x.text)}</span><button class="btn btn-line" data-sugg="${i}" type="button">Öneri yap</button></div>`).join('') : '<div class="small muted">Şu an veriye dayalı bir öneri yok. Projeler çalıştıkça burası dolacak.</div>';
    $('#health-body').innerHTML = h.departments.map((r) => `<tr><td>${esc(r.name)}</td><td>${r.week_calls}/${r.budget}</td><td>${r.first_pass == null ? '-' : '%' + r.first_pass}</td><td>${r.stuck}</td><td>${r.lessons}</td></tr>`).join('');
    $('#org-list').innerHTML = Object.values(o.departments).map((d) => `<div class="dept${d.active ? '' : ' off'}"><div class="dept-head"><span class="dept-name">${esc(d.name)}</span>
      <span class="chip">${d.active ? (d.required ? 'Çekirdek' : 'Aktif') : 'Kapalı'}</span></div>
      <div class="dept-cur">${esc(d.mission)}</div>
      <div class="dept-meta">${esc(d.tier)} · bütçe ${d.budget} · ${HOOKNAME[d.hook]}${d.mode ? ' / ' + MODENAME[d.mode] : ''}</div>
      <button class="btn btn-line" type="button" data-edit="${d.key}">Düzenle</button></div>`).join('');
    const w = o.workflow, makers = Object.values(o.departments).filter((d) => d.active && !d.hook && ['K1', 'K2'].includes(d.tier));
    $('#wf-fixes').value = w.max_fixes; $('#wf-packages').value = w.max_packages; $('#wf-reviews').value = String(w.reviews); $('#wf-lessons').value = w.lessons_per_prompt;
    const opt = (sel) => makers.map((d) => `<option value="${d.key}"${d.key === sel ? ' selected' : ''}>${esc(d.name)}</option>`).join('');
    $('#wf-oyun').innerHTML = opt(w.kind_dept.oyun); $('#wf-uyg').innerHTML = opt(w.kind_dept.uygulama);
    $('#versions').innerHTML = o.versions.length ? o.versions.map((v) => `<div class="ver${v.rolled_back ? ' off' : ''}"><div><b>V${v.id}</b> · ${esc(v.at.slice(0, 16).replace('T', ' '))} · ${esc(v.note || '')}${v.rolled_back ? ' (geri alındı)' : ''}</div>
      <ul class="small">${v.lines.map((l) => `<li>${esc(l)}</li>`).join('')}</ul>
      ${v.rolled_back ? '' : `<button class="btn btn-link" data-rollback="${v.id}" type="button">Bu değişiklikten öncesine dön</button>`}</div>`).join('') : '<div class="empty">Henüz değişiklik yok.</div>';
    const rq = b.core_requirements;
    $('#core-req').innerHTML = [['codex', 'Codex CLI'], ['claude', 'Claude Code'], ['gemini', 'Antigravity CLI (Gemini)'], ['docker', 'Docker'], ['test_image', 'Test imajı (PARDEX_TEST_IMAGE)']]
      .map(([k, l]) => `<span class="chip ${rq[k] ? 'calisiyor' : 'onay'}">${rq[k] ? '✓' : '✗'} ${l}</span>`).join('');
    const cs = b.core_state.running;
    $('#core-list').innerHTML = b.core.map((c) => `<div class="pkg"><div class="pkg-head"><b>${esc(c.goal.slice(0, 90))}</b><span class="chip">${esc(CORESTATE[c.state] || c.state)}</span></div>
      ${c.note ? `<div class="small">${esc(c.note)}</div>` : ''}
      <div class="job-actions">${[['kod', 'Kodu yazdır'], ['test', 'Test et'], ['incele', 'İki AI denetimi'], ['kur', 'Kur']].map(([st, l]) => `<button class="btn ${st === 'kur' ? 'btn-teal' : 'btn-line'}" type="button" data-core="${c.id}" data-step="${st}"${cs || (st === 'kur' && !c.ready) ? ' disabled' : ''}>${l}</button>`).join('')}</div></div>`).join('') +
      (cs ? '<div class="small muted">Çekirdek adımı çalışıyor…</div>' : '') + (b.core_state.error ? `<div class="small">Son hata: ${esc(b.core_state.error)}</div>` : '');
    if (cs) startPoll();
  }
  function openDept(key) {
    const d = key ? ORG.departments[key] : { key: '', name: '', mission: '', prompt: '', tier: 'K1', budget: 4, hook: '', mode: '', active: 1, required: 0 };
    $('#dept-title').textContent = key ? d.name + ' — düzenle' : 'Yeni departman';
    $('#d-key').value = d.key; $('#d-key').disabled = !!key;
    $('#d-name').value = d.name; $('#d-mission').value = d.mission; $('#d-prompt').value = d.prompt; $('#d-tier').value = d.tier; $('#d-budget').value = d.budget;
    $('#d-hook').innerHTML = Object.keys(ORG.hooks).map((h) => `<option value="${h}"${h === d.hook ? ' selected' : ''}>${esc(ORG.hooks[h])}</option>`).join('');
    $('#d-hook').disabled = !!d.required;
    const modes = () => { const h = $('#d-hook').value; $('#d-mode').innerHTML = ORG.modes[h].map((m) => `<option value="${m}"${m === d.mode ? ' selected' : ''}>${MODENAME[m]}</option>`).join(''); };
    $('#d-hook').onchange = modes; modes();
    $('#d-active').checked = !!d.active; $('#d-active').disabled = !!d.required;
    $('#dept-form').dataset.key = key || '';
    $('#dept-dialog').showModal();
  }


  /* ---------- Kurulum ---------- */
  let SETUP = null;
  function renderSetup(s) {
    SETUP = s;
    $('#setup-badge').hidden = s.ready;
    const done = s.items.filter((i) => i.ok).length;
    $('#setup-summary').innerHTML = `<div class="setup-head ${s.ready ? 'ok' : 'todo'}">
        <b>${s.ready ? 'Şirket çalışmaya hazır' : 'Kurulum tamamlanmadı'}</b> · ${done}/${s.items.length} hazır · çalışabilir AI: ${s.usable_ai}</div>
      <div class="setup-next">Sıradaki adım: ${esc(s.next)}</div>
      ${s.ready ? '<div class="row"><button class="btn btn-teal" type="button" data-goto="projects">İlk projeni başlat</button></div>' : ''}`;
    $('#setup-list').innerHTML = s.items.map((i) => {
      const job = s.jobs[i.key];
      const chip = i.ok ? ['calisiyor', 'Hazır'] : (i.installed && i.login === 'unknown' ? ['onay', 'Kontrol et'] : ['onay', 'Eksik']);
      const btn = (a) => ({
        install: `<button class="btn btn-teal" type="button" data-setup="install" data-tool="${i.key}">Kur</button>`,
        update: `<button class="btn btn-link" type="button" data-setup="install" data-tool="${i.key}">Güncelle</button>`,
        login: `<button class="btn btn-dark" type="button" data-setup="login" data-tool="${i.key}">Giriş yap</button>`,
        verify: `<button class="btn btn-teal" type="button" data-setup="verify" data-tool="${i.key}">Test et</button>`,
      })[a] || '';
      return `<div class="setup-row"><div class="job-main">
          <div class="pkg-head"><b>${esc(i.name)}${i.plan ? ` <span class="muted small">· ${esc(i.plan)}</span>` : ''}</b><span class="chip ${chip[0]}">${chip[1]}</span></div>
          <div class="small muted">${esc(i.why || '')}${i.version ? ' · sürüm ' + esc(i.version) : ''}</div>
          <div class="small">${esc(i.detail || '')}</div>
          ${job ? `<div class="small muted">Kurulum: ${job.state === 'running' ? 'sürüyor…' : (job.state === 'ok' ? 'tamamlandı' : 'başarısız')} ${job.state === 'failed' ? esc(job.tail) : ''}</div>` : ''}
        </div><div class="job-actions">${(i.actions || []).map(btn).join('')}</div></div>`;
    }).join('');
    if (Object.values(s.jobs).some((j) => j.state === 'running')) setTimeout(() => { if (VIEW === 'setup') loadSetup(true); }, 4000);
  }
  async function loadSetup(force) {
    try { renderSetup(await api('/api/setup' + (force ? '?force=1' : ''))); } catch (e) { toast(e.message, true); }
  }

  /* ---------- routing ---------- */
  function renderRouting(r) {
    $('#routing-installed').textContent = 'Kurulu araçlar: ' + (r.installed.length ? r.installed.join(', ') : 'yok — Claude / Codex / Gemini / Copilot CLI kur ve giriş yap') + '. Sürüm numarası yazılmaz; takma adlar (sonnet, opus, haiku, flash, pro) aboneliğindeki en güncel modele gider.';
    const ov = (META && META.settings.routing) || {};
    $('#routing-body').innerHTML = r.rows.map((x) => { const o = ov[x.role] || {}; return `<tr data-route="${x.role}"><td>${esc(x.label)}</td><td>${esc(x.provider)} ${esc(x.model)} ${esc(x.effort)}<div class="small muted">${esc(x.reason)}</div></td>
      <td><select class="r-prov" aria-label="Sağlayıcı"><option value="">Otomatik</option>${['Claude', 'Codex', 'Gemini', 'Copilot'].map((p) => `<option${o.provider === p ? ' selected' : ''}>${p}</option>`).join('')}</select></td>
      <td><input class="r-model" aria-label="Model" value="${esc(o.model || '')}" placeholder="sonnet / pro…"></td>
      <td><select class="r-eff" aria-label="Effort">${['', 'low', 'medium', 'high'].map((e) => `<option value="${e}"${(o.effort || '') === e ? ' selected' : ''}>${e || '-'}</option>`).join('')}</select></td></tr>`; }).join('');
  }

  /* ---------- refresh / nav ---------- */
  async function refresh() {
    DASH = await api('/api/dashboard');
    if (!META) META = await api('/api/settings');
    renderOffice(DASH);
    if (VIEW === 'jobs') { JOBS = await api('/api/jobs'); renderJobs(); }
    if (VIEW === 'projects') { renderProducts(await api('/api/products')); if (PID) renderProduct(await api('/api/product/' + PID)); }
    if (VIEW === 'ideas') renderIdeas(await api('/api/ideas'));
    if (VIEW === 'depts') renderDepts(DASH);
    if (VIEW === 'finance') renderFinance(DASH, await api('/api/ledger'));
    if (VIEW === 'board') renderBoard(await api('/api/board'), await api('/api/org'));
    if (VIEW === 'setup') renderSetup(await api('/api/setup'));
    if (VIEW === 'settings') { META = await api('/api/settings'); renderSettings(META, await api('/api/events')); renderRouting(await api('/api/routing')); }
    if (!DASH.run.running && !DASH.production.running && poll) { clearInterval(poll); poll = null; }
  }
  function startPoll() { if (!poll) poll = setInterval(() => refresh().catch(() => {}), 3000); }
  function show(view) {
    VIEW = view;
    document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('active', t.dataset.view === view));
    document.querySelectorAll('.view').forEach((v) => { v.hidden = v.id !== 'view-' + view; });
    refresh().catch((e) => toast(e.message, true));
  }

  /* ---------- events ---------- */
  $('#advanced-toggle').addEventListener('click', () => {
    const button = $('#advanced-toggle');
    const expanded = button.getAttribute('aria-expanded') !== 'true';
    button.setAttribute('aria-expanded', String(expanded));
    button.textContent = expanded ? 'Daha az göster' : 'Diğer bölümler';
    button.closest('nav').classList.toggle('expanded', expanded);
    if (!expanded && $('.tab.active.advanced-tab')) show('office');
  });
  document.querySelectorAll('[data-open-view]').forEach((button) => {
    button.addEventListener('click', () => show(button.dataset.openView));
  });
  document.querySelectorAll('.tab').forEach((t) => t.addEventListener('click', () => show(t.dataset.view)));
  $('#approvals').addEventListener('click', onJobClick);
  $('#office-questions').addEventListener('click', onQuestion);
  $('#office-questions').addEventListener('submit', onQuestionFree);
  $('#product-detail').addEventListener('click', onProductClick);
  $('#product-detail').addEventListener('submit', async (e) => {
    if (e.target.closest('form[data-qf]')) return onQuestionFree(e);
    e.preventDefault();
    if (e.target.id === 'chat-form') {
      const ta = $('#chat-text'); const text = ta.value.trim(); if (!text) return;
      ta.value = ''; const btn = e.target.querySelector('button'); btn.disabled = true; btn.textContent = 'Ürün Müdürü yazıyor…';
      try { renderProduct(await api(`/api/product/${PID}/chat`, { text })); } catch (err) { toast(err.message, true); btn.disabled = false; btn.textContent = 'Gönder'; }
    }
    if (e.target.id === 'change-form') {
      await act(() => api(`/api/product/${PID}/changes`, { note: $('#change-text').value }), 'Ekip düzeltmeye başladı'); startPoll();
    }
  });
  $('#product-list').addEventListener('click', (e) => { const b = e.target.closest('[data-pid]'); if (b) { PID = b.dataset.pid; refresh(); } });
  $('#new-product').addEventListener('submit', async (e) => {
    e.preventDefault();
    const p = await act(() => api('/api/product', { name: $('#np-name').value, kind: $('#np-kind').value }), 'Proje açıldı — Ürün Müdürü bekliyor');
    if (p) { PID = p.id; $('#np-name').value = ''; refresh(); }
  });
  $('#research-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!confirm('Ar-Ge 1 AI çağrısıyla internette araştırma yapacak. Devam?')) return;
    $('#rs-status').textContent = 'Ar-Ge araştırıyor ve kaynakları doğruluyor…';
    try {
      const r = await api('/api/research', { focus: $('#rs-focus').value, topic: $('#rs-topic').value });
      $('#rs-result').innerHTML = `<div><b>${r.accepted.length}</b> kaynaklı fikir eklendi (${esc(r.provider)}).</div>` +
        r.rejected.map((x) => `<div class="small muted">Elendi: ${esc(x.title)} — ${esc(x.reason)}</div>`).join('');
      $('#rs-status').textContent = ''; refresh();
    } catch (err) { $('#rs-status').textContent = ''; toast(err.message, true); }
  });

  $('#gmy-form').addEventListener('submit', async (e) => {
    e.preventDefault(); const ta = $('#gmy-text'); const text = ta.value.trim(); if (!text) return;
    const btn = e.target.querySelector('button'); btn.disabled = true; btn.textContent = 'Düşünüyor…';
    try { const r = await api('/api/board/message', { text }); ta.value = ''; if (r.proposal) toast('Öneri hazır — onayını bekliyor'); }
    catch (err) { toast(err.message, true); }
    btn.disabled = false; btn.textContent = 'Gönder (1 çağrı)'; refresh();
  });
  $('#view-board').addEventListener('click', async (e) => {
    const b = e.target.closest('button'); if (!b) return;
    if (b.dataset.coreprop) {
      if (!confirm('Çekirdek değişiklik talebi oluşturulsun mu? Kod, şirket yazılımının bir kopyasında yazılır; sen kurmadıkça hiçbir şey değişmez.')) return;
      await act(() => api('/api/core', { goal: b.dataset.coreprop }), 'Çekirdek talebi oluşturuldu');
      return act(() => api(`/api/board/proposal/${b.dataset.prop}/reject`, {}), null);
    }
    if (b.dataset.pa) {
      if (b.dataset.pa === 'approve' && !confirm('Bu değişiklikler uygulanacak (sürüm olarak kaydedilir, geri alınabilir). Onaylıyor musun?')) return;
      return act(() => api(`/api/board/proposal/${b.dataset.prop}/${b.dataset.pa}`, {}), b.dataset.pa === 'approve' ? 'Uygulandı' : 'Reddedildi').then(() => { META = null; });
    }
    if (b.dataset.sugg) return act(() => api('/api/board/suggestion', { index: Number(b.dataset.sugg) }), 'Öneri onay masasına eklendi');
    if (b.dataset.rollback) {
      if (!confirm(`V${b.dataset.rollback} ve sonrasındaki bütün değişiklikler geri alınacak. Emin misin?`)) return;
      return act(() => api('/api/org/rollback', { version: Number(b.dataset.rollback) }), 'Geri alındı').then(() => { META = null; });
    }
    if (b.dataset.edit) return openDept(b.dataset.edit);
    if (b.id === 'new-dept') return openDept('');
    if (b.dataset.core) {
      const step = b.dataset.step;
      const msg = { kod: 'Codex, şirket yazılımının kopyasında kodu yazacak (1 çağrı).', test: 'Kopya, izole Docker testinden geçirilecek.', incele: 'Claude ve Gemini değişikliği bağımsız denetleyecek (2 çağrı).', kur: 'Onaylı değişiklik şirket yazılımına kurulacak; yedek alınır, geri alınabilir. Sonra paneli yeniden aç.' }[step];
      if (!confirm(msg + ' Devam?')) return;
      await act(() => api(`/api/core/${b.dataset.core}/${step}`, {}), 'Başladı'); startPoll(); return;
    }
    if (b.id === 'core-rollback') { if (confirm('Son çekirdek kurulumu geri alınsın mı?')) act(() => api('/api/core/rollback', {}), 'Geri alındı; paneli yeniden aç'); }
  });
  $('#core-form').addEventListener('submit', (e) => { e.preventDefault(); const g = $('#core-goal').value.trim(); if (g.length < 20) return toast('En az 20 karakterle açıkla', true);
    act(() => api('/api/core', { goal: g }), 'Çekirdek talebi oluşturuldu').then(() => { $('#core-goal').value = ''; }); });
  $('#wf-form').addEventListener('submit', (e) => {
    e.preventDefault(); const w = ORG.workflow, ops = [];
    [['max_fixes', '#wf-fixes'], ['max_packages', '#wf-packages'], ['reviews', '#wf-reviews'], ['lessons_per_prompt', '#wf-lessons']].forEach(([f, sel]) => {
      const v = Number($(sel).value); if (v !== w[f]) ops.push({ op: 'set_workflow', field: f, value: v }); });
    const kd = { oyun: $('#wf-oyun').value, uygulama: $('#wf-uyg').value };
    if (kd.oyun !== w.kind_dept.oyun || kd.uygulama !== w.kind_dept.uygulama) ops.push({ op: 'set_workflow', field: 'kind_dept', value: kd });
    if (!ops.length) return toast('Değişiklik yok');
    act(() => api('/api/org/apply', { ops, note: 'İş akışı düzenlendi' }), 'İş akışı güncellendi');
  });
  $('#dept-close').addEventListener('click', () => $('#dept-dialog').close());
  $('#dept-form').addEventListener('submit', (e) => {
    e.preventDefault(); const key = e.target.dataset.key, d = key ? ORG.departments[key] : null, ops = [];
    const f = { name: $('#d-name').value.trim(), mission: $('#d-mission').value.trim(), prompt: $('#d-prompt').value.trim(), tier: $('#d-tier').value, hook: $('#d-hook').value, mode: $('#d-mode').value };
    const budget = Number($('#d-budget').value);
    if (!key) ops.push(Object.assign({ op: 'add_department', key: $('#d-key').value.trim(), budget }, f));
    else {
      const ch = {}; Object.entries(f).forEach(([k, v]) => { if (v !== d[k]) ch[k] = v; });
      if (d.required) { delete ch.hook; delete ch.mode; }
      if (Object.keys(ch).length) ops.push(Object.assign({ op: 'update_department', key }, ch));
      if (budget !== d.budget) ops.push({ op: 'set_budget', key, budget });
      if (!d.required && $('#d-active').checked !== !!d.active) ops.push({ op: $('#d-active').checked ? 'activate_department' : 'deactivate_department', key });
    }
    if (!ops.length) { $('#dept-dialog').close(); return; }
    act(() => api('/api/org/apply', { ops, note: key ? f.name + ' düzenlendi' : 'Yeni departman: ' + f.name }), 'Kaydedildi (sürüm)').then((r) => { if (r) { $('#dept-dialog').close(); META = null; } });
  });
  $('#dept-full').addEventListener('click', async (e) => {
    const b = e.target.closest('[data-report]'); if (!b) return;
    try {
      const r = await api('/api/report/' + b.dataset.report);
      const c = Object.entries(r.counts).filter(([, v]) => v).map(([k, v]) => `${STATUS[k] || k}: ${v}`).join(' · ') || 'Henüz iş yok';
      $('#out-title').textContent = r.name + ' — rapor';
      $('#out-body').textContent = `Görev: ${r.mission}\nBu hafta: ${r.week_calls}/${r.budget} AI çağrısı\nİşler: ${c}\n\nÖğrenilen dersler:\n` +
        (r.lessons.length ? r.lessons.map((l) => `• ${l.text} (${l.hits} kez)`).join('\n') : '• Henüz ders yok') +
        '\n\nSon hareketler:\n' + (r.recent.length ? r.recent.map((x) => `• ${x.at.slice(0, 16).replace('T', ' ')} ${x.action} ${x.note || ''}`).join('\n') : '• Kayıt yok');
      $('#out-dialog').showModal();
    } catch (err) { toast(err.message, true); }
  });
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
    const routing = {}; document.querySelectorAll('[data-route]').forEach((row) => {
      const prov = row.querySelector('.r-prov').value; if (prov) routing[row.dataset.route] = { provider: prov, model: row.querySelector('.r-model').value.trim(), effort: row.querySelector('.r-eff').value };
    });
    act(() => api('/api/settings', { default_project: $('#set-project').value, ollama_model: $('#set-ollama').value.trim(), weekly_call_limit: Number($('#set-limit').value), day_call_limit: Number($('#set-day').value), projects_root: $('#set-root').value.trim(), currency: $('#set-currency').value, budgets, routing }), 'Ayarlar kaydedildi')
      .then(() => { META = null; });
  });

  $('#setup-refresh').addEventListener('click', () => loadSetup(true));
  $('#view-setup').addEventListener('click', async (e) => {
    const g = e.target.closest('[data-goto]'); if (g) return show(g.dataset.goto);
    const b = e.target.closest('[data-setup]'); if (!b) return;
    const tool = b.dataset.tool, act = b.dataset.setup;
    if (act === 'install' && !confirm('Kurulum resmî paket kaynağından yapılacak. Devam?')) return;
    if (act === 'verify' && !confirm('Giriş testi 1 küçük AI çağrısı deneyebilir; şirket bütçesine 1 deneme kaydedilir. Devam?')) return;
    b.disabled = true;
    try {
      const r = await api(`/api/setup/${act}/${tool}`, {});
      if (r.manual && r.url) window.open(r.url, '_blank', 'noopener');
      toast(r.message || 'Başladı');
    } catch (err) { toast(err.message, true); }
    loadSetup(true);
  });
  score();
  refresh().catch((e) => toast(e.message, true));
  api('/api/setup').then((s) => { renderSetup(s); if (!s.ready) show('setup'); }).catch(() => {});
  setInterval(() => { if (!poll) refresh().catch(() => {}); }, 20000);
})();
