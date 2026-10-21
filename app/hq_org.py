"""Phase 5 — data-driven organisation: departments, workflow and stage hooks, with versioned changes.

The company can be restructured without touching code: add/close departments, change missions and
instructions, budgets, workflow parameters and model routing. Every change set is validated first,
applied atomically, saved as a version and can be rolled back with one action.
Core departments the project line depends on can be edited but never closed.
"""
import json
import re

import core
import hq_store as store

REQUIRED = ('ceo', 'urun', 'oyun', 'uygulama', 'kalite', 'arge', 'finans')
HOOKS = {'': 'Kanca yok (yalnızca doğrudan iş alır)',
         'plan_sonrasi': 'Plan onaylandıktan sonra, iş paylaşımından önce rapor yazar',
         'paket_sonrasi': 'Her paket kontrolden geçtikten sonra ek denetim yapar',
         'teslim_oncesi': 'Teslimden önce son adımı yapar (rapor veya kod)'}
MODES = {'plan_sonrasi': ('rapor',), 'paket_sonrasi': ('denetim',), 'teslim_oncesi': ('rapor', 'kod'), '': ('',)}
WORKFLOW_DEFAULT = {'max_fixes': 2, 'max_packages': 8, 'reviews': 1, 'lessons_per_prompt': 4,
                    'kind_dept': {'oyun': 'oyun', 'uygulama': 'uygulama'}}
WORKFLOW_RANGES = {'max_fixes': (0, 3), 'max_packages': (2, 12), 'reviews': (1, 2), 'lessons_per_prompt': (0, 8)}
LIMIT_FIELDS = {'weekly_call_limit': (0, 500), 'day_call_limit': (0, 200)}

PROMPTS = {
    'urun': ('Sen PARDEX yazılım şirketinin Ürün Müdürüsün. Patronla konuşarak oyun/uygulamanın ana hatlarını '
             'netleştirirsin. Kısa ve net Türkçe konuş; bir seferde en fazla 3 soru sor. Patronun söylemediği '
             'şeyleri uydurma; makul varsayımları "varsayım" diye belirt. Kapsamı ilk sürüm için küçük tut.'),
    'ceo': ('Sen PARDEX CEO’susun. Onaylanmış ürün tarifini, sırayla yapılabilecek bağımsız ve test edilebilir '
            'iş paketlerine bölersin. Her paket tek seferde bitirilebilecek kadar küçük olmalı.'),
    'oyun': 'Sen PARDEX Oyun Stüdyosunda kıdemli oyun programcısısın.',
    'uygulama': 'Sen PARDEX Uygulama ekibinde kıdemli yazılım geliştiricisisin.',
    'kalite': ('Sen PARDEX Kalite ekibinde bağımsız kod denetçisisin. Kodu sen yazmadın. Yalnızca gerçek hata, '
               'eksik kabul ölçütü, güvenlik sorunu veya çalışmayı engelleyen sorun için FAIL ver; zevk farkı için verme.'),
}
UNSAFE = re.compile(r'(yok say|görmezden gel|ignore (all|previous|the)|onay(sız| almadan| olmadan)|bypass|'
                    r'push et|yayınla|satın al|ödeme yap|hesap aç|sudo|rm -rf|\.env)', re.I)
KEY = re.compile(r'[a-z][a-z0-9_]{1,19}')


def _schema(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS org_departments(key TEXT PRIMARY KEY, name TEXT NOT NULL, mission TEXT NOT NULL,
        prompt TEXT NOT NULL, tier TEXT NOT NULL, hook TEXT NOT NULL, mode TEXT NOT NULL, required INTEGER NOT NULL,
        active INTEGER NOT NULL, ord INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS org_versions(id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, actor TEXT NOT NULL,
        note TEXT NOT NULL, before TEXT NOT NULL, ops TEXT NOT NULL, rolled_back INTEGER NOT NULL DEFAULT 0);
    ''')


def _seed(db):
    if db.execute('SELECT count(*) FROM org_departments').fetchone()[0]:
        return
    for i, (k, (name, mission, _budget, tier)) in enumerate(store.DEPARTMENTS.items()):
        db.execute('INSERT INTO org_departments VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                   (k, name, mission, PROMPTS.get(k, f'Sen PARDEX şirketinde {name} departmanısın. Görevin: {mission}.'),
                    tier, '', '', int(k in REQUIRED), 1, i, core.now(), core.now()))


def _rows(path=None, include_inactive=False):
    with store._conn(path) as db:
        _schema(db)
        _seed(db)
        q = 'SELECT * FROM org_departments ' + ('' if include_inactive else 'WHERE active=1 ') + 'ORDER BY ord, key'
        return [dict(r) for r in db.execute(q)]


def departments(path=None, include_inactive=False):
    """key -> row (name, mission, prompt, tier, hook, mode, required, active, budget)."""
    budgets = (store.settings_raw(path).get('budgets') or {})
    out = {}
    for r in _rows(path, include_inactive):
        r['budget'] = int(budgets.get(r['key'], store.DEPARTMENTS.get(r['key'], (0, 0, 0))[2]))
        out[r['key']] = r
    return out


def prompt(dept, path=None):
    d = departments(path, include_inactive=True).get(dept)
    return d['prompt'] if d else ''


def workflow(path=None):
    w = json.loads(json.dumps(WORKFLOW_DEFAULT))
    saved = store.settings_raw(path).get('workflow') or {}
    for k in WORKFLOW_RANGES:
        if type(saved.get(k)) is int:
            w[k] = saved[k]
    if isinstance(saved.get('kind_dept'), dict):
        w['kind_dept'].update({k: v for k, v in saved['kind_dept'].items() if k in ('oyun', 'uygulama')})
    return w


def hooks(stage, path=None):
    return [d for d in departments(path).values() if d['hook'] == stage]


# ---------------- change sets ----------------
def _text(v, n, field):
    v = core.redact_log_output(str(v or '')).strip()
    if len(v) > n:
        raise ValueError(f'{field} en fazla {n} karakter')
    if UNSAFE.search(v):
        raise ValueError(f'{field} güvenlik kurallarını aşmaya çalışan ifade içeriyor')
    return v


def validate(ops, path=None):
    """Dry-run every operation against a simulated state. Returns normalised ops or raises ValueError."""
    if not isinstance(ops, list) or not 1 <= len(ops) <= 20:
        raise ValueError('Değişiklik listesi 1-20 işlem olmalı')
    depts = {k: dict(v) for k, v in departments(path, include_inactive=True).items()}
    wf = workflow(path)
    import hq_router
    out = []
    for i, op in enumerate(ops, 1):
        if not isinstance(op, dict):
            raise ValueError(f'{i}. işlem geçersiz')
        kind = op.get('op')
        n = dict(op=kind)
        if kind in ('add_department', 'update_department'):
            key = str(op.get('key', ''))
            if not KEY.fullmatch(key):
                raise ValueError(f'{i}. işlem: departman anahtarı küçük harf/rakam olmalı (örn. tasarim)')
            if kind == 'add_department' and key in depts:
                raise ValueError(f'{i}. işlem: {key} zaten var')
            if kind == 'update_department' and key not in depts:
                raise ValueError(f'{i}. işlem: {key} departmanı yok')
            cur = depts.get(key, {'name': '', 'mission': '', 'prompt': '', 'tier': 'K1', 'hook': '', 'mode': '',
                                  'required': 0, 'active': 1, 'budget': 0})
            for f, lim in (('name', 40), ('mission', 240), ('prompt', 1200)):
                if f in op:
                    n[f] = _text(op[f], lim, f)
            name = n.get('name', cur['name'])
            if len(name) < 2:
                raise ValueError(f'{i}. işlem: departman adı gerekli')
            if kind == 'add_department':
                n.setdefault('mission', '')
                if len(n['mission']) < 6:
                    raise ValueError(f'{i}. işlem: departmanın görevi (mission) yazılmalı')
                n.setdefault('prompt', f"Sen PARDEX şirketinde {name} departmanısın. Görevin: {n['mission']}")
            tier = op.get('tier', cur['tier'])
            if tier not in store.TIERS:
                raise ValueError(f'{i}. işlem: kademe K0/K1/K2 olmalı')
            hook = op.get('hook', cur['hook']) or ''
            mode = op.get('mode', cur['mode'] if hook == cur['hook'] else MODES.get(hook, ('',))[0]) or MODES.get(hook, ('',))[0]
            if hook not in HOOKS or mode not in MODES[hook]:
                raise ValueError(f'{i}. işlem: kanca/mod uyumsuz ({hook}/{mode})')
            if hook and cur['required']:
                raise ValueError(f'{i}. işlem: çekirdek departmanlara kanca eklenmez; yeni departman aç')
            if hook and tier == 'K0':
                raise ValueError(f'{i}. işlem: kancalı departman AI kullanır; kademe K1 veya K2 olmalı')
            n.update(key=key, tier=tier, hook=hook, mode=mode)
            if 'budget' in op or kind == 'add_department':
                b = op.get('budget', 4)
                if type(b) is not int or not 0 <= b <= 200:
                    raise ValueError(f'{i}. işlem: bütçe 0-200 olmalı')
                n['budget'] = b
            cur.update({k: v for k, v in n.items() if k != 'op'})
            depts[key] = cur
        elif kind in ('deactivate_department', 'activate_department'):
            key = str(op.get('key', ''))
            if key not in depts:
                raise ValueError(f'{i}. işlem: {key} departmanı yok')
            if kind == 'deactivate_department':
                if depts[key]['required']:
                    raise ValueError(f'{i}. işlem: {depts[key]["name"]} çekirdek departman; kapatılamaz')
                if key in wf['kind_dept'].values():
                    raise ValueError(f'{i}. işlem: bu departman şu an üretimde görevli; önce görevi devret')
            depts[key]['active'] = int(kind == 'activate_department')
            n['key'] = key
        elif kind == 'set_budget':
            key, b = str(op.get('key', '')), op.get('budget')
            if key not in depts or type(b) is not int or not 0 <= b <= 200:
                raise ValueError(f'{i}. işlem: bütçe için geçerli departman ve 0-200 değer gerekli')
            n.update(key=key, budget=b)
        elif kind == 'set_workflow':
            field, v = op.get('field'), op.get('value')
            if field in WORKFLOW_RANGES:
                lo, hi = WORKFLOW_RANGES[field]
                if type(v) is not int or not lo <= v <= hi:
                    raise ValueError(f'{i}. işlem: {field} {lo}-{hi} olmalı')
            elif field == 'kind_dept':
                if not isinstance(v, dict) or not set(v) <= {'oyun', 'uygulama'}:
                    raise ValueError(f'{i}. işlem: kind_dept {{"oyun":"..","uygulama":".."}} olmalı')
                for t, d in v.items():
                    if d not in depts or not depts[d]['active'] or depts[d]['hook']:
                        raise ValueError(f'{i}. işlem: {t} üretimi için aktif ve kancasız bir departman gerekli')
                wf['kind_dept'].update(v)
            else:
                raise ValueError(f'{i}. işlem: bilinmeyen iş akışı alanı')
            n.update(field=field, value=v)
        elif kind == 'set_routing':
            role = op.get('role')
            if role not in hq_router.ROLES:
                raise ValueError(f'{i}. işlem: bilinmeyen rol')
            prov = op.get('provider', '') or ''
            if prov not in ('', 'Claude', 'Codex', 'Gemini', 'Copilot'):
                raise ValueError(f'{i}. işlem: sağlayıcı Claude/Codex/Gemini/Copilot olmalı')
            model, effort = str(op.get('model', '') or ''), str(op.get('effort', '') or '')
            if model and not re.fullmatch(r'[a-zA-Z0-9_.:-]{2,60}', model):
                raise ValueError(f'{i}. işlem: model adı geçersiz')
            if effort not in ('', 'low', 'medium', 'high'):
                raise ValueError(f'{i}. işlem: effort low/medium/high olmalı')
            n.update(role=role, provider=prov, model=model, effort=effort)
        elif kind == 'set_limit':
            field, v = op.get('field'), op.get('value')
            if field not in LIMIT_FIELDS or type(v) is not int or not LIMIT_FIELDS[field][0] <= v <= LIMIT_FIELDS[field][1]:
                raise ValueError(f'{i}. işlem: sınır alanı/değeri geçersiz')
            n.update(field=field, value=v)
        else:
            raise ValueError(f'{i}. işlem: izinli olmayan işlem "{kind}"')
        out.append(n)
    return out


def describe(op, path=None):
    """Human-readable Turkish line for an operation (for the owner's approval card)."""
    d = departments(path, include_inactive=True)
    name = lambda k: d.get(k, {}).get('name', k)
    k = op['op']
    if k == 'add_department':
        h = f", {HOOKS[op['hook']].lower()}" if op.get('hook') else ''
        return f"Yeni departman: {op['name']} ({op['tier']}, haftalık {op.get('budget', 0)} çağrı{h}) — {op['mission']}"
    if k == 'update_department':
        parts = [f for f in ('name', 'mission', 'prompt', 'tier', 'hook', 'budget') if f in op]
        return f"{name(op['key'])} güncellenir: {', '.join(parts)}"
    if k == 'deactivate_department':
        return f"{name(op['key'])} kapatılır"
    if k == 'activate_department':
        return f"{name(op['key'])} yeniden açılır"
    if k == 'set_budget':
        return f"{name(op['key'])} haftalık bütçesi → {op['budget']} çağrı"
    if k == 'set_workflow':
        return f"İş akışı: {op['field']} → {op['value']}"
    if k == 'set_routing':
        return f"Model yönlendirme: {op['role']} → {op['provider'] or 'otomatik'} {op['model']} {op['effort']}".strip()
    if k == 'set_limit':
        return f"Sınır: {op['field']} → {op['value']}"
    return k


def snapshot(path=None):
    s = store.settings_raw(path)
    return {'departments': _rows(path, include_inactive=True),
            'settings': {k: s.get(k) for k in ('workflow', 'budgets', 'routing', 'weekly_call_limit', 'day_call_limit')
                         if k in s}}


def _restore(snap, path=None):
    with store._conn(path) as db:
        _schema(db)
        db.execute('DELETE FROM org_departments')
        for r in snap['departments']:
            db.execute('INSERT INTO org_departments VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                       (r['key'], r['name'], r['mission'], r['prompt'], r['tier'], r['hook'], r['mode'], r['required'],
                        r['active'], r['ord'], r['created_at'], r['updated_at']))
        for k in ('workflow', 'budgets', 'routing', 'weekly_call_limit', 'day_call_limit'):
            if k in snap['settings']:
                db.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)',
                           (k, json.dumps(snap['settings'][k], ensure_ascii=False)))
            else:
                db.execute('DELETE FROM settings WHERE key=?', (k,))


def apply(ops, note='', actor='patron', path=None):
    """Validate, snapshot, apply all-or-nothing, record version. Returns version id."""
    ops = validate(ops, path)
    before = snapshot(path)
    try:
        for op in ops:
            _apply_one(op, path)
        validate_state(path)
    except Exception:
        _restore(before, path)
        raise
    with store._conn(path) as db:
        _schema(db)
        vid = db.execute('INSERT INTO org_versions(at,actor,note,before,ops) VALUES(?,?,?,?,?)',
                         (core.now(), actor[:20], core.redact_log_output(note)[:300],
                          json.dumps(before, ensure_ascii=False), json.dumps(ops, ensure_ascii=False))).lastrowid
    store.event(actor, 'org-change', f'V{vid}', '; '.join(describe(o, path) for o in ops)[:280], path)
    return vid


def validate_state(path=None):
    wf = workflow(path)
    d = departments(path)
    for t, k in wf['kind_dept'].items():
        if k not in d:
            raise ValueError(f'{t} üretimi için görevli departman aktif değil')
    for k in REQUIRED:
        if k not in d:
            raise ValueError(f'Çekirdek departman {k} kapatılamaz')


def _apply_one(op, path):
    k = op['op']
    s = store.settings_raw(path)
    if k in ('add_department', 'update_department'):
        with store._conn(path) as db:
            _schema(db)
            if k == 'add_department':
                o = db.execute('SELECT COALESCE(MAX(ord),0)+1 FROM org_departments').fetchone()[0]
                db.execute('INSERT INTO org_departments VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                           (op['key'], op['name'], op['mission'], op['prompt'], op['tier'], op['hook'], op['mode'],
                            0, 1, o, core.now(), core.now()))
            else:
                fields = {f: op[f] for f in ('name', 'mission', 'prompt', 'tier', 'hook', 'mode') if f in op}
                fields['updated_at'] = core.now()
                db.execute(f'UPDATE org_departments SET {",".join(f + "=?" for f in fields)} WHERE key=?',
                           (*fields.values(), op['key']))
        if 'budget' in op:
            _set_raw('budgets', dict(s.get('budgets') or {}, **{op['key']: op['budget']}), path)
    elif k in ('deactivate_department', 'activate_department'):
        with store._conn(path) as db:
            _schema(db)
            db.execute('UPDATE org_departments SET active=?, updated_at=? WHERE key=?',
                       (int(k == 'activate_department'), core.now(), op['key']))
    elif k == 'set_budget':
        _set_raw('budgets', dict(s.get('budgets') or {}, **{op['key']: op['budget']}), path)
    elif k == 'set_workflow':
        wf = dict(s.get('workflow') or {})
        if op['field'] == 'kind_dept':
            wf['kind_dept'] = dict(wf.get('kind_dept') or {}, **op['value'])
        else:
            wf[op['field']] = op['value']
        _set_raw('workflow', wf, path)
    elif k == 'set_routing':
        r = dict(s.get('routing') or {})
        if op['provider']:
            r[op['role']] = {'provider': op['provider'], 'model': op['model'], 'effort': op['effort']}
        else:
            r.pop(op['role'], None)
        _set_raw('routing', r, path)
    elif k == 'set_limit':
        _set_raw(op['field'], op['value'], path)


def _set_raw(key, value, path):
    with store._conn(path) as db:
        db.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)', (key, json.dumps(value, ensure_ascii=False)))


def versions(limit=30, path=None):
    with store._conn(path) as db:
        _schema(db)
        rows = [dict(r) for r in db.execute('SELECT id,at,actor,note,ops,rolled_back FROM org_versions ORDER BY id DESC LIMIT ?',
                                            (int(limit),))]
    for r in rows:
        r['ops'] = json.loads(r['ops'])
        r['lines'] = [describe(o, path) for o in r['ops']]
    return rows


def rollback(vid, path=None):
    """Restore the state from before version `vid` (and therefore undo it and every later change)."""
    with store._conn(path) as db:
        _schema(db)
        row = db.execute('SELECT * FROM org_versions WHERE id=? AND rolled_back=0', (int(vid),)).fetchone()
        if not row:
            raise KeyError('Geri alınabilecek sürüm bulunamadı')
        later = db.execute('SELECT count(*) FROM org_versions WHERE id>? AND rolled_back=0', (int(vid),)).fetchone()[0]
        before = json.loads(row['before'])
    _restore(before, path)
    with store._conn(path) as db:
        db.execute('UPDATE org_versions SET rolled_back=1 WHERE id>=?', (int(vid),))
    store.event('patron', 'org-rollback', f'V{vid}', f'{later} sonraki değişiklik de geri alındı' if later else '', path)
    return {'restored_before': vid, 'also_undone': later}
