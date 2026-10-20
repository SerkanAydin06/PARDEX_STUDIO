"""PARDEX 2H: single-use, preapproved AI shifts. Not a daemon or sandbox."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import json
import os
import uuid
import task_queue as queue
import worker_supervisor as supervisor
import worker_guard

def utc(value):
    if isinstance(value,str):
        try: value=datetime.fromisoformat(value.replace('Z','+00:00'))
        except ValueError as e: raise ValueError('Invalid ISO time') from e
    if not isinstance(value,datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('Timezone-aware datetime is required')
    return value.astimezone(timezone.utc).replace(microsecond=0)

def clock(now=None):
    return utc(now if now is not None else datetime.now(timezone.utc))

def schema(db):
    db.execute("""CREATE TABLE IF NOT EXISTS scheduled_shifts(
        id TEXT PRIMARY KEY,task_ids TEXT NOT NULL,run_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,created_at TEXT NOT NULL,finished_at TEXT,
        state TEXT NOT NULL,native_opt_in INTEGER NOT NULL,
        max_minutes INTEGER NOT NULL,worker_id TEXT,result_code TEXT NOT NULL DEFAULT '')""")
    db.execute("CREATE INDEX IF NOT EXISTS scheduled_shifts_state_idx ON scheduled_shifts(state,run_at)")

def record(db,ident):
    row=db.execute('SELECT * FROM scheduled_shifts WHERE id=?',(ident,)).fetchone()
    if row is None:raise ValueError('Schedule not found')
    out=dict(row);out['task_ids']=json.loads(out['task_ids'])
    out['native_opt_in']=bool(out['native_opt_in'])
    return out

def get(ident,path=None):
    with queue._conn(path) as db:
        schema(db)
        return record(db,ident)

def all_schedules(path=None,limit=20):
    if type(limit) is not int or not 1<=limit<=100:raise ValueError('Invalid limit')
    with queue._conn(path) as db:
        schema(db)
        ids=[r[0] for r in db.execute('SELECT id FROM scheduled_shifts ORDER BY rowid DESC LIMIT ?',(limit,))]
        return [record(db,ident) for ident in ids]

def plan(task_ids,run_at,expires_at,*,path=None,now=None,owner_confirms=False,
         allow_native_unisolated=False,max_minutes=30):
    if owner_confirms is not True:raise PermissionError('Owner approval required')
    if type(allow_native_unisolated) is not bool:raise ValueError('Native approval must be boolean')
    if type(task_ids) not in (list,tuple):raise ValueError('Exact task IDs required')
    ids=tuple(task_ids)
    if not 1<=len(ids)<=2 or len(set(ids))!=len(ids) or not all(
        isinstance(x,str) and x.startswith('TASK-') and len(x)==17 for x in ids):
        raise ValueError('One or two distinct real task IDs required')
    if type(max_minutes) is not int or not 2<=max_minutes<=30:
        raise ValueError('Scheduled shift limit is 2 to 30 minutes')
    moment,start,end=clock(now),utc(run_at),utc(expires_at)
    if not moment+timedelta(minutes=1)<=start<=moment+timedelta(days=7):
        raise ValueError('Start must be 1 minute to 7 days in the future')
    if not start+timedelta(minutes=1)<=end<=start+timedelta(minutes=60):
        raise ValueError('Schedule validity must be 1 to 60 minutes')
    preview=supervisor.preview(path=path,max_tasks=len(ids),max_minutes=max_minutes)
    if preview.get('blocked_reason') or tuple(x['id'] for x in preview['tasks'])!=ids:
        raise PermissionError('Queue changed or blocked; review exact task IDs')
    ident='SCHED-'+uuid.uuid4().hex[:16]
    with queue._conn(path) as db:
        db.execute('BEGIN IMMEDIATE');schema(db)
        count=db.execute("SELECT count(*) FROM scheduled_shifts WHERE state IN ('armed','running')").fetchone()[0]
        if count>=3:raise RuntimeError('Schedule capacity exceeded')
        db.execute("""INSERT INTO scheduled_shifts
            (id,task_ids,run_at,expires_at,created_at,state,native_opt_in,max_minutes)
            VALUES(?,?,?,?,?,'armed',?,?)""",
            (ident,json.dumps(ids),start.isoformat(),end.isoformat(),moment.isoformat(),
             int(allow_native_unisolated),max_minutes))
        db.commit()
    return get(ident,path)

def cancel(ident,*,path=None,owner_confirms=False,now=None):
    if owner_confirms is not True:raise PermissionError('Owner cancellation required')
    with queue._conn(path) as db:
        db.execute('BEGIN IMMEDIATE');schema(db)
        row=record(db,ident)
        if row['state']!='armed':raise ValueError('Only unstarted schedules may be cancelled')
        db.execute("UPDATE scheduled_shifts SET state='cancelled',result_code='cancelled',finished_at=? WHERE id=?",
                   (clock(now).isoformat(),ident))
        db.commit()
    return get(ident,path)

def preview_due(*,path=None,now=None):
    moment=clock(now)
    with queue._conn(path) as db:
        schema(db)
        rows=[record(db,r[0]) for r in db.execute(
            "SELECT id FROM scheduled_shifts WHERE state='armed' ORDER BY run_at,rowid")]
    return {'due':[r for r in rows if utc(r['run_at'])<=moment<=utc(r['expires_at'])],
            'expired_ids':[r['id'] for r in rows if utc(r['expires_at'])<moment],
            'armed_total':len(rows),'no_model_calls':True,
            'native_os_isolation_proven':False,'auto_retry':False}

def dispatch_due(*,path=None,now=None,execute=False,env=None):
    if execute is not True:return dict(preview_due(path=path,now=now),dry_run=True)
    env=os.environ if env is None else env
    if worker_guard.strict_worker_mode() or worker_guard.strict_worker_mode(env):
        return {'executed':False,'blocked':'strict-mode-requires-real-isolated-agent'}
    if env.get('PARDEX_ALLOW_SCHEDULED_NATIVE_AI')!='1':
        return {'executed':False,'blocked':'explicit-runtime-opt-in-required'}
    moment=clock(now)
    with queue._conn(path) as db:
        db.execute('BEGIN IMMEDIATE');schema(db)
        if db.execute("SELECT 1 FROM scheduled_shifts WHERE state='running' LIMIT 1").fetchone():
            return {'executed':False,'blocked':'another-schedule-is-running'}
        ids=[r[0] for r in db.execute("SELECT id FROM scheduled_shifts WHERE state='armed' ORDER BY run_at,rowid")]
        selected=None
        for ident in ids:
            rec=record(db,ident)
            if utc(rec['expires_at'])<moment:
                db.execute("UPDATE scheduled_shifts SET state='expired',finished_at=?,result_code='missed-window' WHERE id=?",
                           (moment.isoformat(),ident))
            elif selected is None and utc(rec['run_at'])<=moment and rec['native_opt_in']:
                selected=rec
        if selected is None:
            db.commit();return {'executed':False,'blocked':'no-opted-in-due-schedule'}
        db.execute("UPDATE scheduled_shifts SET state='running' WHERE id=? AND state='armed'",(selected['id'],))
        db.commit()
    state='interrupted';worker_id=None
    try:
        # Rechecks exact IDs, live queue ordering, previous approval and budgets.
        worker=supervisor.run(path=path,expected_task_ids=tuple(selected['task_ids']),
            owner_confirms=True,max_tasks=len(selected['task_ids']),max_minutes=selected['max_minutes'])
        worker_id=worker['id']
        state='completed' if worker['state']=='completed' else 'needs-attention'
    except Exception:
        # Never store private exceptions, code or CLI transcripts in schedule DB.
        state='interrupted'
    with queue._conn(path) as db:
        db.execute('BEGIN IMMEDIATE');schema(db)
        db.execute("""UPDATE scheduled_shifts SET state=?,result_code=?,worker_id=?,
            finished_at=? WHERE id=? AND state='running'""",
            (state,state,worker_id,clock(now).isoformat(),selected['id']))
        db.commit()
    return {'executed':True,'schedule_id':selected['id'],'status':state,
            'worker_id':worker_id,'auto_retry':False,
            'owner_result_acceptance_required':True}
