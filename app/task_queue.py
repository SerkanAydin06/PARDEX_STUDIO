"""Owner-controlled persistent queue. No daemon, auto-retry, deployment, or API billing."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
import uuid
import core

DATABASE=core.HOME/'task_queue.sqlite3'
KINDS=('Yeni ozellik / Kod','Hata duzeltme','Mimari / Plan','Inceleme / Analiz','Tasarim karari')
PROVIDERS=('Otomatik','Claude','Codex','Gemini')
QUALITIES=('Ekonomik','Dengeli','En guclu')


@contextmanager
def _conn(path=None):
    target=Path(path) if path is not None else DATABASE
    target.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(str(target),timeout=12,isolation_level=None)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA busy_timeout=12000')
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,project TEXT NOT NULL,title TEXT NOT NULL,kind TEXT NOT NULL,
        provider_preference TEXT NOT NULL,quality TEXT NOT NULL,priority INTEGER NOT NULL,
        max_minutes INTEGER NOT NULL,status TEXT NOT NULL,
        created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
        approved_at TEXT,started_at TEXT,ended_at TEXT,provider_used TEXT,model_used TEXT,
        verified INTEGER,result_note TEXT NOT NULL DEFAULT '',attempts INTEGER NOT NULL DEFAULT 0)''')
    db.execute('''CREATE TABLE IF NOT EXISTS task_events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,task_id TEXT NOT NULL,time TEXT NOT NULL,
        action TEXT NOT NULL,note TEXT NOT NULL DEFAULT '')''')
    db.execute('CREATE INDEX IF NOT EXISTS task_status_priority ON tasks(status,priority DESC,created_at)')
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _event(db,ident,action,note=''):
    db.execute('INSERT INTO task_events(task_id,time,action,note) VALUES(?,?,?,?)',
               (ident,core.now(),action,core.redact_log_output(str(note))[:320]))


def _row(db,ident):
    result=db.execute('SELECT * FROM tasks WHERE id=?',(ident,)).fetchone()
    if result is None:raise ValueError('Gorev bulunamadi')
    return dict(result)


def add_task(project,title,kind='Yeni ozellik / Kod',provider='Otomatik',
             quality='Dengeli',priority=3,max_minutes=15,path=None):
    project=Path(project).expanduser().resolve()
    if not project.is_dir() or core.project_type(project)=='unknown':
        raise ValueError('Taninan bir proje gerekli')
    title=str(title).strip()
    if not 6<=len(title)<=1200:raise ValueError('Gorev 6-1200 karakter olmali')
    if kind not in KINDS or provider not in PROVIDERS or quality not in QUALITIES:
        raise ValueError('Bilinmeyen gorev/AI/kalite')
    if type(priority) is not int or not 1<=priority<=5:raise ValueError('Oncelik 1-5 olmali')
    if type(max_minutes) is not int or not 2<=max_minutes<=45:raise ValueError('Sure 2-45 dk olmali')
    ident='TASK-'+uuid.uuid4().hex[:12]
    with _conn(path) as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('''INSERT INTO tasks(id,project,title,kind,provider_preference,quality,priority,
             max_minutes,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
             (ident,str(project),core.redact_log_output(title),kind,provider,quality,priority,
              max_minutes,'pending-owner',core.now(),core.now()))
        _event(db,ident,'created','owner permission required')
        db.commit()
    return get_task(ident,path)


def get_task(ident,path=None):
    with _conn(path) as db:return _row(db,ident)


def list_tasks(path=None,limit=100):
    with _conn(path) as db:
        rows=db.execute('''SELECT * FROM tasks ORDER BY
            CASE status WHEN "ready" THEN 0 WHEN "running" THEN 1
                        WHEN "pending-owner" THEN 2 ELSE 3 END,
            priority DESC,created_at ASC LIMIT ?''',(max(1,min(int(limit),500)),))
        return [dict(x) for x in rows]


def events(ident,path=None):
    with _conn(path) as db:
        _row(db,ident)
        return [dict(x) for x in db.execute('SELECT * FROM task_events WHERE task_id=? ORDER BY id',(ident,))]


def _transition(ident,old,new,action,note='',path=None,fields=None):
    with _conn(path) as db:
        db.execute('BEGIN IMMEDIATE')
        row=_row(db,ident)
        if row['status'] not in old:raise ValueError('Gecersiz durum: '+row['status'])
        fields=fields or {}
        extra=(', '+', '.join(k+'=?' for k in fields)) if fields else ''
        db.execute('UPDATE tasks SET status=?,updated_at=?'+extra+' WHERE id=?',
                   (new,core.now(),*fields.values(),ident))
        _event(db,ident,action,note)
        db.commit()
        return _row(db,ident)


def approve(ident,path=None):
    """Only call after an actual owner UI interaction."""
    return _transition(ident,('pending-owner',),'ready','owner-approved',
                       path=path,fields={'approved_at':core.now()})


def cancel(ident,path=None):
    return _transition(ident,('pending-owner','ready','needs-attention'),
                       'cancelled','owner-cancel',path=path)


def accept(ident,path=None):
    return _transition(ident,('awaiting-acceptance',),'accepted','owner-accepted',
                       path=path,fields={'ended_at':core.now()})


def request_rework(ident,reason,path=None):
    reason=str(reason).strip()
    if len(reason)<4:raise ValueError('Gerekce gerekli')
    return _transition(ident,('awaiting-acceptance',),'needs-attention',
                       'owner-rejected',reason,path=path,
                       fields={'result_note':core.redact_log_output(reason)[:350]})


def reset_for_manual_retry(ident,path=None):
    return _transition(ident,('needs-attention',),'pending-owner','rework-requested',
                       path=path,fields={'approved_at':None,'started_at':None})


def preview_next(day_limit=8,path=None):
    """Zero AI call; a routing estimate, not a real subscription quota."""
    with _conn(path) as db:
        row=db.execute('SELECT * FROM tasks WHERE status="ready" ORDER BY priority DESC,rowid ASC LIMIT 1').fetchone()
        running=db.execute('SELECT count(*) FROM tasks WHERE status="running"').fetchone()[0]
    if not row:return {'ready':False,'message':'Onayli gorev yok'}
    item=dict(row)
    provider,model=core.route(item['kind'],item['provider_preference'],item['quality'])
    exe={'Claude':'claude','Codex':'codex','Gemini':'gemini'}[provider]
    return {'ready':True,'id':item['id'],'project':Path(item['project']).name,
            'provider_estimate':provider,'model_estimate':model,'max_minutes':item['max_minutes'],
            'estimated_cli_calls':1,'local_calls_today':core.usage_count(),
            'day_limit':day_limit,
            'blocked':bool(running or core.usage_count()>=day_limit or not core.which(exe)),
            'note':'Tahmin; gercek token bakiyesi bilinmiyor. Sahibin kabul testi gerekli.'}


def claim_next(day_limit=8,path=None):
    """Atomic single worker. A crashed task is never automatically retried."""
    if type(day_limit) is not int or not 1<=day_limit<=100:raise ValueError('Gunluk sinir 1-100')
    with _conn(path) as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT 1 FROM tasks WHERE status="running" LIMIT 1').fetchone():
            raise RuntimeError('Zaten bir AI gorevi calisiyor veya kurtarma bekliyor')
        row=db.execute('SELECT * FROM tasks WHERE status="ready" ORDER BY priority DESC,rowid ASC LIMIT 1').fetchone()
        if row is None:return None
        if core.usage_count()>=day_limit:raise RuntimeError('Gunluk AI cagri limiti doldu')
        row=dict(row)
        provider,_=core.route(row['kind'],row['provider_preference'],row['quality'])
        exe={'Claude':'claude','Codex':'codex','Gemini':'gemini'}[provider]
        if not core.which(exe):raise RuntimeError(provider+' kurulu degil')
        if core.project_type(row['project'])=='unknown':raise RuntimeError('Proje bulunamadi')
        db.execute('UPDATE tasks SET status="running",started_at=?,updated_at=?,attempts=attempts+1 WHERE id=?',
                   (core.now(),core.now(),row['id']))
        _event(db,row['id'],'claimed',provider+' | manually started')
        db.commit()
        return _row(db,row['id'])


def execute_one(day_limit=8,path=None,on_update=None):
    """Run only after explicit UI action. No daemon, auto-merge, deployment or auto retry."""
    item=claim_next(day_limit,path)
    if item is None:return None
    try:
        outcome=core.run_ai_task(item['project'],item['kind'],item['title'],
            item['provider_preference'],item['quality'],day_limit,item['max_minutes'],on_update=on_update)
        good=bool(outcome.get('ai_ok') and outcome.get('verified'))
        status='awaiting-acceptance' if good else 'needs-attention'
        note=('Test gecti; insanin oynanis/UI kabul testi bekleniyor' if good else
              'AI/test basarisiz veya motor test edilemedi; sahibi incelemeli')
        fields={'ended_at':core.now(),'result_note':note,
                'provider_used':str(outcome.get('provider',''))[:20],
                'model_used':str(outcome.get('model',''))[:60],
                'verified':int(bool(outcome.get('verified')))}
        return _transition(item['id'],('running',),status,'finished',note,path,fields=fields)
    except Exception as err:
        note='Gorev durdu: '+type(err).__name__+' — '+core.redact_log_output(str(err))[:220]
        return _transition(item['id'],('running',),'needs-attention','failed',note,path,
                           fields={'ended_at':core.now(),'result_note':note,'verified':0})


def recover_interrupted(ident,confirm=False,path=None):
    if confirm is not True:raise PermissionError('Sahip onayi gerekli')
    return _transition(ident,('running',),'needs-attention','owner-recovery',
        'Outcome unknown; inspect logs and files',path,
        fields={'ended_at':core.now(),'result_note':'Onceki calisma sonucu bilinmiyor'})


def statistics(path=None):
    with _conn(path) as db:
        statuses={r[0]:r[1] for r in db.execute('SELECT status,count(*) FROM tasks GROUP BY status')}
        providers={r[0]:r[1] for r in db.execute('SELECT provider_used,count(*) FROM tasks WHERE provider_used IS NOT NULL GROUP BY provider_used')}
    return {'status':statuses,'completed_by_provider':providers,'calls_today_local':core.usage_count(),
            'real_token_usage_known':False,'cloud_subscription_balance_known':False}
