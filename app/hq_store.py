"""Phase 3 — PARDEX AI company headquarters: departments, budgets and durable records.

Local SQLite only. Nothing here calls an AI, spends money, opens accounts or publishes.
Every job starts as ``proposed`` and needs the owner's explicit approval.
"""
import contextlib
import datetime as dt
import json
import re
import sqlite3
import uuid
from pathlib import Path

import core

DATABASE = core.HOME / 'hq' / 'company.sqlite3'

# Token tiers: K0 = deterministic/local (0 token), K1 = small/local model, K2 = strong model (code/critical).
TIERS = {
    'K0': 'Kural, betik ve test — 0 token',
    'K1': 'Küçük veya yerel model — özet, taslak, sınıflama',
    'K2': 'Güçlü model — yalnızca kod ve kritik karar',
}

# key: (name, mission, default weekly AI-call budget, default tier)
DEPARTMENTS = {
    'ceo':       ('CEO · Genel Müdür', 'Onaylı planı iş paketlerine böler, sırayı ve modelleri belirler', 10, 'K1'),
    'arge':      ('Ar-Ge & İnternet Radarı', 'Kaynaklı fikir, fırsat ve şirket gelişimi araştırması', 8, 'K1'),
    'urun':      ('Ürün Müdürü', 'Patronla plan sohbeti yapar, ürün tarifini (spec) yazar', 15, 'K1'),
    'oyun':      ('Oyun Stüdyosu', 'Godot ve diğer motorlarda oyun kodu', 40, 'K2'),
    'uygulama':  ('Uygulama & Sistemler', 'Web/mobil araçlar ve şirketin kendi yazılımı', 40, 'K2'),
    'otomasyon': ('Otomasyon & Makro', 'Kendi projeler için test botu ve iş akışı makroları', 4, 'K2'),
    'medya':     ('Medya & Video', 'Video senaryosu, sahne listesi, altyazı ve tanıtım metni', 6, 'K1'),
    'kalite':    ('Kalite & Güvenlik', 'Otomatik test ve farklı AI ile bağımsız kod incelemesi', 40, 'K1'),
    'finans':    ('Finans & Token', 'Bütçe, gider, gelir ve başabaş takibi', 0, 'K0'),
    'buyume':    ('Büyüme & Yayın', 'Mağaza sayfası ve sosyal medya taslakları; yayın yalnızca sahiple', 4, 'K1'),
    'gelisim':   ('Gelişim Konseyi', 'Hatalardan ders çıkarır, sistem iyileştirmesi önerir', 1, 'K1'),
}

JOB_KINDS = ('code', 'text', 'local')
RISKS = ('Düşük', 'Orta', 'Yüksek')
JOB_STATES = ('proposed', 'approved', 'running', 'delivered', 'accepted', 'rejected', 'failed', 'blocked')
IDEA_STAGES = ('fikir', 'degerlendirme', 'onay', 'uretim', 'kalite', 'yayin', 'gelir', 'arsiv')
LEDGER_KINDS = ('ai_call', 'income', 'expense')

DEFAULT_SETTINGS = {
    'paused': False,
    'weekly_call_limit': 200,
    'day_call_limit': 40,
    'projects_root': str(Path.home() / 'PardexProjeler'),
    'routing': {},
    'budgets': {k: v[2] for k, v in DEPARTMENTS.items()},
    'ollama_model': '',
    'default_project': '',
    'currency': 'TRY',
}


@contextlib.contextmanager
def _conn(path=None):
    path = Path(path or DATABASE)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path), timeout=10)
    db.row_factory = sqlite3.Row
    db.executescript('''
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS goals(id TEXT PRIMARY KEY, text TEXT NOT NULL, project TEXT,
        status TEXT NOT NULL, created_at TEXT NOT NULL, planner TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, goal_id TEXT, dept TEXT NOT NULL,
        title TEXT NOT NULL, kind TEXT NOT NULL, tier TEXT NOT NULL, est_calls INTEGER NOT NULL,
        risk TEXT NOT NULL, project TEXT, action TEXT, status TEXT NOT NULL, note TEXT,
        output TEXT, task_id TEXT, idea_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS ideas(id TEXT PRIMARY KEY, title TEXT NOT NULL, source TEXT,
        revenue INTEGER NOT NULL, effort INTEGER NOT NULL, cost INTEGER NOT NULL, fit INTEGER NOT NULL,
        score INTEGER NOT NULL, stage TEXT NOT NULL, note TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS ledger(id TEXT PRIMARY KEY, at TEXT NOT NULL, week TEXT NOT NULL,
        dept TEXT NOT NULL, kind TEXT NOT NULL, amount REAL NOT NULL, provider TEXT, job_id TEXT, note TEXT);
    CREATE TABLE IF NOT EXISTS lessons(id TEXT PRIMARY KEY, dept TEXT NOT NULL, text TEXT NOT NULL,
        source TEXT, hits INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS route_stats(role TEXT NOT NULL, provider TEXT NOT NULL, n INTEGER NOT NULL,
        ok INTEGER NOT NULL, PRIMARY KEY(role, provider));
    CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL,
        actor TEXT NOT NULL, action TEXT NOT NULL, ref TEXT, note TEXT);
    CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status);
    CREATE INDEX IF NOT EXISTS ledger_week ON ledger(week, dept, kind);
    ''')
    cols = {r[1] for r in db.execute('PRAGMA table_info(ideas)')}
    if 'sources' not in cols:
        db.execute('ALTER TABLE ideas ADD COLUMN sources TEXT')
    try:
        with db:
            yield db
    finally:
        db.close()


def week_key(day=None):
    y, w, _ = (day or dt.date.today()).isocalendar()
    return f'{y}-W{w:02d}'


def _clean(text, limit):
    return core.redact_log_output(str(text or '')).strip()[:limit]


def event(actor, action, ref='', note='', path=None):
    with _conn(path) as db:
        db.execute('INSERT INTO events(at,actor,action,ref,note) VALUES(?,?,?,?,?)',
                   (core.now(), actor[:30], action[:40], str(ref)[:40], _clean(note, 300)))


def events(limit=40, path=None):
    with _conn(path) as db:
        return [dict(r) for r in db.execute('SELECT * FROM events ORDER BY id DESC LIMIT ?', (int(limit),))]


# ---------------- settings & budgets ----------------
def settings_raw(path=None):
    out = {}
    with _conn(path) as db:
        for row in db.execute('SELECT key,value FROM settings'):
            try:
                out[row['key']] = json.loads(row['value'])
            except ValueError:
                pass
    return out


def depts(path=None, include_inactive=False):
    """Live organisation: key -> (name, mission, budget, tier). Falls back to the seed list."""
    try:
        import hq_org
        return {k: (v['name'], v['mission'], v['budget'], v['tier'])
                for k, v in hq_org.departments(path, include_inactive).items()}
    except ImportError:
        return dict(DEPARTMENTS)


def settings(path=None):
    out = json.loads(json.dumps(DEFAULT_SETTINGS))
    with _conn(path) as db:
        for row in db.execute('SELECT key,value FROM settings'):
            try:
                out[row['key']] = json.loads(row['value'])
            except ValueError:
                pass
    budgets = dict(DEFAULT_SETTINGS['budgets'])
    known = depts(path, include_inactive=True)
    budgets.update({k: v for k, v in (out.get('budgets') or {}).items() if k in known})
    for k in known:
        budgets.setdefault(k, 0)
    out['budgets'] = budgets
    return out


def update_settings(changes, path=None):
    allowed = {'paused', 'weekly_call_limit', 'day_call_limit', 'budgets', 'ollama_model', 'default_project',
               'currency', 'projects_root', 'routing'}
    if not isinstance(changes, dict) or not set(changes) <= allowed:
        raise ValueError('Bilinmeyen ayar')
    cur = settings(path)
    if 'paused' in changes:
        cur['paused'] = bool(changes['paused'])
    if 'weekly_call_limit' in changes:
        v = changes['weekly_call_limit']
        if type(v) is not int or not 0 <= v <= 500:
            raise ValueError('Haftalık sınır 0-500 olmalı')
        cur['weekly_call_limit'] = v
    if 'day_call_limit' in changes:
        v = changes['day_call_limit']
        if type(v) is not int or not 0 <= v <= 200:
            raise ValueError('Günlük sınır 0-200 olmalı')
        cur['day_call_limit'] = v
    if 'projects_root' in changes:
        root = Path(str(changes['projects_root'] or '')).expanduser().resolve()
        if not str(changes['projects_root'] or '').strip():
            raise ValueError('Proje klasörü gerekli')
        if root == core.BASE or core.BASE in root.parents:
            raise ValueError('Ürünler şirket deposunun içinde olamaz; ayrı bir klasör seç')
        cur['projects_root'] = str(root)
    if 'routing' in changes:
        r = changes['routing']
        if not isinstance(r, dict):
            raise ValueError('Yönlendirme tablosu geçersiz')
        clean = {}
        for role, v in r.items():
            if not re.fullmatch(r'[a-z_]{2,20}', str(role)) or not isinstance(v, dict):
                raise ValueError('Yönlendirme rolü geçersiz')
            prov = v.get('provider', '')
            if prov not in ('', 'Claude', 'Codex', 'Gemini', 'Copilot'):
                raise ValueError('Sağlayıcı Claude/Codex/Gemini/Copilot olmalı')
            model, effort = str(v.get('model', '')), str(v.get('effort', ''))
            if model and not re.fullmatch(r'[a-zA-Z0-9_.:-]{2,60}', model):
                raise ValueError('Model adı geçersiz')
            if effort not in ('', 'low', 'medium', 'high'):
                raise ValueError('Effort low/medium/high olmalı')
            if prov:
                clean[role] = {'provider': prov, 'model': model, 'effort': effort}
        cur['routing'] = clean
    if 'budgets' in changes:
        b = changes['budgets']
        if not isinstance(b, dict) or not set(b) <= set(depts(path, include_inactive=True)):
            raise ValueError('Bilinmeyen departman')
        for k, v in b.items():
            if type(v) is not int or not 0 <= v <= 200:
                raise ValueError('Departman bütçesi 0-200 olmalı')
            cur['budgets'][k] = v
    if 'ollama_model' in changes:
        m = str(changes['ollama_model'] or '').strip()
        if m and not re.fullmatch(r'[a-zA-Z0-9_.:/-]{2,100}', m):
            raise ValueError('Geçersiz yerel model adı')
        cur['ollama_model'] = m
    if 'default_project' in changes:
        p = str(changes['default_project'] or '').strip()
        if p and (not Path(p).is_dir() or core.project_type(Path(p)) == 'unknown'):
            raise ValueError('Tanınan bir proje klasörü gerekli')
        cur['default_project'] = str(Path(p).resolve()) if p else ''
    if 'currency' in changes:
        c = str(changes['currency']).upper()
        if c not in ('TRY', 'USD', 'EUR'):
            raise ValueError('Para birimi TRY/USD/EUR')
        cur['currency'] = c
    with _conn(path) as db:
        for k in changes:
            db.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)', (k, json.dumps(cur[k], ensure_ascii=False)))
    event('patron', 'settings', '', ','.join(sorted(changes)), path)
    return cur


def calls_used(dept=None, week=None, path=None):
    week = week or week_key()
    q = 'SELECT COALESCE(SUM(amount),0) FROM ledger WHERE week=? AND kind="ai_call"'
    args = [week]
    if dept:
        q += ' AND dept=?'
        args.append(dept)
    with _conn(path) as db:
        return int(db.execute(q, args).fetchone()[0])


def budget_check(dept, calls, path=None):
    """Return (ok, reason). K0 jobs (calls=0) always pass unless the company is paused."""
    s = settings(path)
    if s['paused']:
        return False, 'Şirket acil durdurmada; patron yeniden başlatmalı'
    if calls <= 0:
        return True, ''
    if calls_used(dept, path=path) + calls > s['budgets'].get(dept, 0):
        return False, f'{depts(path, True).get(dept, (dept,))[0]} haftalık çağrı bütçesi yetmiyor'
    if calls_used(path=path) + calls > s['weekly_call_limit']:
        return False, 'Şirket haftalık toplam çağrı sınırı doldu'
    if core.usage_count() + calls > s['day_call_limit']:
        return False, f'Günlük AI çağrı sınırı ({s["day_call_limit"]}) doldu'
    return True, ''


def record(dept, kind, amount, provider='', job_id='', note='', path=None):
    if dept not in depts(path, include_inactive=True) or kind not in LEDGER_KINDS:
        raise ValueError('Geçersiz defter kaydı')
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        raise ValueError('Tutar sayı olmalı')
    if not 0 <= amount <= 10_000_000:
        raise ValueError('Tutar aralık dışı')
    ident = 'L-' + uuid.uuid4().hex[:10]
    with _conn(path) as db:
        db.execute('INSERT INTO ledger VALUES(?,?,?,?,?,?,?,?,?)',
                   (ident, core.now(), week_key(), dept, kind, amount, provider[:20], job_id[:40], _clean(note, 200)))
    return ident


def ledger(limit=60, path=None):
    with _conn(path) as db:
        return [dict(r) for r in db.execute('SELECT * FROM ledger ORDER BY at DESC LIMIT ?', (int(limit),))]


def finance_summary(path=None):
    month = dt.date.today().strftime('%Y-%m')
    with _conn(path) as db:
        rows = db.execute('SELECT kind, COALESCE(SUM(amount),0) s FROM ledger WHERE substr(at,1,7)=? GROUP BY kind',
                          (month,)).fetchall()
    tot = {r['kind']: r['s'] for r in rows}
    income, expense = tot.get('income', 0.0), tot.get('expense', 0.0)
    return {'month': month, 'income': round(income, 2), 'expense': round(expense, 2),
            'net': round(income - expense, 2), 'ai_calls_month': int(tot.get('ai_call', 0)),
            'currency': settings(path)['currency'],
            'note': 'Gelir/gider yalnızca senin girdiğin kayıtlardır; abonelik kotası okunamaz.'}


# ---------------- goals & jobs ----------------
def add_goal(text, project='', planner='K0', path=None):
    text = _clean(text, 600)
    if len(text) < 6:
        raise ValueError('Hedef en az 6 karakter olmalı')
    ident = 'G-' + uuid.uuid4().hex[:9]
    with _conn(path) as db:
        db.execute('INSERT INTO goals VALUES(?,?,?,?,?,?)', (ident, text, project or '', 'open', core.now(), planner))
    event('patron', 'goal', ident, text[:120], path)
    return ident


def goals(limit=30, path=None):
    with _conn(path) as db:
        return [dict(r) for r in db.execute('SELECT * FROM goals ORDER BY created_at DESC LIMIT ?', (int(limit),))]


def add_job(dept, title, kind, tier, est_calls, risk='Düşük', goal_id='', project='', action='',
            status='proposed', note='', idea_id='', path=None):
    if dept not in depts(path) or kind not in JOB_KINDS or tier not in TIERS or risk not in RISKS:
        raise ValueError('Geçersiz iş tanımı')
    if status not in ('proposed', 'blocked'):
        raise ValueError('Yeni iş yalnızca önerilir')
    if type(est_calls) is not int or not 0 <= est_calls <= 3:
        raise ValueError('Bir iş en fazla 3 AI çağrısı planlayabilir')
    if tier == 'K0' and est_calls:
        raise ValueError('K0 iş AI çağrısı yapamaz')
    title = _clean(title, 600)
    if len(title) < 6:
        raise ValueError('İş tanımı en az 6 karakter')
    if kind == 'code' and status != 'blocked':
        if not project or not Path(project).is_dir() or core.project_type(Path(project)) == 'unknown':
            status, note = 'blocked', 'Kod işi için Ayarlar’dan bir proje seç'
    ident = 'J-' + uuid.uuid4().hex[:10]
    t = core.now()
    with _conn(path) as db:
        db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                   (ident, goal_id, dept, title, kind, tier, est_calls, risk, project or '', action[:30],
                    status, _clean(note, 300), '', '', idea_id, t, t))
    return get_job(ident, path)


def get_job(ident, path=None):
    with _conn(path) as db:
        r = db.execute('SELECT * FROM jobs WHERE id=?', (ident,)).fetchone()
    if not r:
        raise KeyError('İş bulunamadı')
    return dict(r)


def jobs(status=None, limit=200, path=None):
    with _conn(path) as db:
        if status:
            rows = db.execute('SELECT * FROM jobs WHERE status=? ORDER BY created_at DESC LIMIT ?', (status, int(limit)))
        else:
            rows = db.execute('SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?', (int(limit),))
        return [dict(r) for r in rows]


def transition(ident, old, new, note=None, output=None, task_id=None, actor='sistem', path=None):
    if new not in JOB_STATES:
        raise ValueError('Geçersiz durum')
    old = (old,) if isinstance(old, str) else tuple(old)
    sets, args = ['status=?', 'updated_at=?'], [new, core.now()]
    if note is not None:
        sets.append('note=?'); args.append(_clean(note, 300))
    if output is not None:
        sets.append('output=?'); args.append(_clean(output, 8000))
    if task_id is not None:
        sets.append('task_id=?'); args.append(task_id[:40])
    with _conn(path) as db:
        db.execute('BEGIN IMMEDIATE')
        cur = db.execute(f'UPDATE jobs SET {",".join(sets)} WHERE id=? AND status IN ({",".join("?"*len(old))})',
                         args + [ident] + list(old))
        if cur.rowcount != 1:
            db.rollback()
            raise ValueError('Bu işin durumu bu işleme uygun değil')
        db.commit()
    event(actor, new, ident, note or '', path)
    return get_job(ident, path)


# ---------------- ideas (fikirden gelire hat) ----------------
def idea_score(revenue, effort, cost, fit):
    """K0 score 0-100: revenue and fit up, effort and cost down. All inputs 1-5."""
    return round(((revenue * 2 + fit) - (effort + cost) + 7) / 20 * 100)


def add_idea(title, revenue=3, effort=3, cost=3, fit=3, source='patron', note='', path=None, sources=()):
    vals = (revenue, effort, cost, fit)
    if not all(type(v) is int and 1 <= v <= 5 for v in vals):
        raise ValueError('Puanlar 1-5 olmalı')
    title = _clean(title, 200)
    if len(title) < 4:
        raise ValueError('Fikir başlığı en az 4 karakter')
    ident = 'I-' + uuid.uuid4().hex[:9]
    t = core.now()
    with _conn(path) as db:
        urls = [str(u)[:300] for u in sources if str(u).startswith(('https://', 'http://'))][:6]
        db.execute('INSERT INTO ideas(id,title,source,revenue,effort,cost,fit,score,stage,note,created_at,updated_at,sources) '
                   'VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                   (ident, title, source[:30], *vals, idea_score(*vals), 'degerlendirme', _clean(note, 900), t, t,
                    json.dumps(urls)))
    event(source, 'idea', ident, title, path)
    return ident


def ideas(path=None):
    with _conn(path) as db:
        return [dict(r) for r in db.execute('SELECT * FROM ideas ORDER BY score DESC, created_at DESC')]


def move_idea(ident, stage, path=None):
    if stage not in IDEA_STAGES:
        raise ValueError('Bilinmeyen aşama')
    with _conn(path) as db:
        cur = db.execute('UPDATE ideas SET stage=?, updated_at=? WHERE id=?', (stage, core.now(), ident))
        if cur.rowcount != 1:
            raise KeyError('Fikir bulunamadı')
    event('patron', 'idea-' + stage, ident, '', path)


# ---------------- dashboard ----------------
def pipeline(path=None):
    counts = {s: 0 for s in IDEA_STAGES}
    for i in ideas(path):
        counts[i['stage']] += 1
    js = jobs(path=path)
    counts['onay'] += sum(j['status'] == 'proposed' for j in js)
    counts['uretim'] += sum(j['status'] in ('approved', 'running') for j in js)
    counts['kalite'] += sum(j['status'] == 'delivered' for j in js)
    return counts


def department_board(path=None):
    s = settings(path)
    js = jobs(path=path)
    out = []
    for key, (name, mission, _, tier) in depts(path).items():
        mine = [j for j in js if j['dept'] == key]
        active = next((j for j in mine if j['status'] in ('running', 'approved')), None)
        waiting = next((j for j in mine if j['status'] == 'proposed'), None)
        delivered = next((j for j in mine if j['status'] == 'delivered'), None)
        if s['paused']:
            state = 'durdu'
        elif active:
            state = 'calisiyor'
        elif waiting or delivered:
            state = 'onay'
        else:
            state = 'bosta'
        cur = active or waiting or delivered
        out.append({'key': key, 'name': name, 'mission': mission, 'tier': tier, 'state': state,
                    'current': cur['title'] if cur else '', 'budget': s['budgets'].get(key, 0),
                    'used': calls_used(key, path=path),
                    'done': sum(j['status'] == 'accepted' for j in mine)})
    return out


def briefing(path=None):
    """Zero-token morning briefing assembled from local records."""
    js = jobs(path=path)
    s = settings(path)
    proposed = [j for j in js if j['status'] == 'proposed']
    delivered = [j for j in js if j['status'] == 'delivered']
    failed = [j for j in js if j['status'] in ('failed', 'blocked')]
    top = ideas(path)
    used, limit = calls_used(path=path), s['weekly_call_limit']
    lines = []
    if s['paused']:
        lines.append(('Durum', 'Şirket acil durdurmada. Hiçbir iş çalışmıyor.'))
    if proposed:
        lines.append(('Senden istenen', f'{len(proposed)} iş onayını bekliyor.'))
    if delivered:
        lines.append(('Teslim', f'{len(delivered)} iş teslim edildi; kabul veya geri çevirme bekliyor.'))
    live = [i for i in top if i['stage'] not in ('arsiv', 'gelir')]
    if live:
        lines.append(('Fırsat', f'En yüksek puanlı fikir: {live[0]["title"]} ({live[0]["score"]}/100).'))
    if failed:
        lines.append(('Risk', f'{len(failed)} iş takıldı veya engellendi; nedenleri İşler ekranında.'))
    pct = round(used / limit * 100) if limit else 0
    lines.append(('Bütçe', f'Bu hafta {used}/{limit} AI çağrısı kullanıldı (%{pct}).'))
    if not js and not top:
        lines.append(('Başlangıç', 'Şirkete ilk hedefini ver; CEO işleri departmanlara böler.'))
    return [{'label': a, 'text': b} for a, b in lines]


def dashboard(path=None):
    s = settings(path)
    js = jobs(path=path)
    return {
        'paused': s['paused'], 'week': week_key(),
        'kpi': {'pending': sum(j['status'] == 'proposed' for j in js),
                'delivered_week': sum(j['status'] == 'accepted' and j['updated_at'][:10] >= (dt.date.today() - dt.timedelta(days=7)).isoformat() for j in js),
                'calls_used': calls_used(path=path), 'calls_limit': s['weekly_call_limit'],
                'calls_today': core.usage_count(), 'day_limit': s['day_call_limit']},
        'finance': finance_summary(path), 'briefing': briefing(path),
        'departments': department_board(path), 'pipeline': pipeline(path),
        'approvals': [j for j in js if j['status'] in ('proposed', 'delivered')][:30],
    }


# ---------------- learning: department lessons & routing evidence ----------------
def _norm(text):
    return re.sub(r'\W+', ' ', str(text).lower()).strip()[:160]


def add_lesson(dept, text, source='', path=None):
    """K0 learning: a short, test-backed lesson for one department (deduplicated)."""
    if dept not in depts(path, include_inactive=True):
        raise ValueError('Bilinmeyen departman')
    text = _clean(text, 240)
    if len(text) < 10:
        return None
    key = _norm(text)
    with _conn(path) as db:
        for r in db.execute('SELECT id,text FROM lessons WHERE dept=?', (dept,)):
            if _norm(r['text']) == key:
                db.execute('UPDATE lessons SET hits=hits+1, updated_at=? WHERE id=?', (core.now(), r['id']))
                return r['id']
        ident = 'D-' + uuid.uuid4().hex[:9]
        db.execute('INSERT INTO lessons VALUES(?,?,?,?,?,?,?)', (ident, dept, text, source[:60], 1, core.now(), core.now()))
        n = db.execute('SELECT count(*) FROM lessons WHERE dept=?', (dept,)).fetchone()[0]
        if n > 40:  # keep memory small: drop the least-hit oldest
            db.execute('DELETE FROM lessons WHERE id IN (SELECT id FROM lessons WHERE dept=? '
                       'ORDER BY hits ASC, updated_at ASC LIMIT ?)', (dept, n - 40))
    event(dept, 'lesson', ident, text[:120], path)
    return ident


def lessons(dept=None, limit=40, path=None):
    with _conn(path) as db:
        if dept:
            rows = db.execute('SELECT * FROM lessons WHERE dept=? ORDER BY hits DESC, updated_at DESC LIMIT ?', (dept, int(limit)))
        else:
            rows = db.execute('SELECT * FROM lessons ORDER BY updated_at DESC LIMIT ?', (int(limit),))
        return [dict(r) for r in rows]


def delete_lesson(ident, path=None):
    with _conn(path) as db:
        if db.execute('DELETE FROM lessons WHERE id=?', (ident,)).rowcount != 1:
            raise KeyError('Ders bulunamadı')
    event('patron', 'lesson-delete', ident, '', path)


def route_result(role, provider, ok, path=None):
    with _conn(path) as db:
        db.execute('INSERT INTO route_stats VALUES(?,?,1,?) ON CONFLICT(role,provider) DO UPDATE SET n=n+1, ok=ok+?',
                   (role, provider, int(bool(ok)), int(bool(ok))))


def route_stats(path=None):
    with _conn(path) as db:
        return [dict(r) for r in db.execute('SELECT * FROM route_stats ORDER BY role, provider')]


def department_report(dept, path=None):
    """Zero-token report the owner asks for: work, budget, lessons."""
    d = depts(path, include_inactive=True)
    if dept not in d:
        raise ValueError('Bilinmeyen departman')
    mine = [j for j in jobs(path=path) if j['dept'] == dept]
    with _conn(path) as db:
        evs = [dict(r) for r in db.execute('SELECT * FROM events WHERE actor=? OR ref IN (SELECT id FROM jobs WHERE dept=?) '
                                           'ORDER BY id DESC LIMIT 12', (dept, dept))]
    s = settings(path)
    return {'dept': dept, 'name': d[dept][0], 'mission': d[dept][1],
            'week_calls': calls_used(dept, path=path), 'budget': s['budgets'].get(dept, 0),
            'counts': {st: sum(j['status'] == st for j in mine) for st in JOB_STATES},
            'lessons': lessons(dept, 10, path), 'recent': evs}
