"""Owner-started, bounded AI worker sessions; NOT an OS sandbox or daemon."""
import json
import time
import uuid
import core
import operations
import task_queue as tasks


def _schema(db):
    db.execute("""CREATE TABLE IF NOT EXISTS worker_sessions (
      id TEXT PRIMARY KEY,started_at TEXT,state TEXT,ended_at TEXT,
      task_ids TEXT,processed TEXT DEFAULT '[]',stop_requested INTEGER DEFAULT 0,
      reason TEXT DEFAULT '')""")


def _get(db, sid):
    r=db.execute("SELECT * FROM worker_sessions WHERE id=?",(sid,)).fetchone()
    if not r:raise ValueError("Unknown worker session")
    d=dict(r)
    for k in ("task_ids","processed"):d[k]=json.loads(d[k])
    return d


def inspect(sid,path=None):
    with tasks._conn(path) as db:
        _schema(db)
        return _get(db,sid)


def recent(path=None,limit=10):
    if type(limit)!=int or not 1<=limit<=50:raise ValueError("Bad limit")
    with tasks._conn(path) as db:
        _schema(db)
        ids=[r[0] for r in db.execute(
            "SELECT id FROM worker_sessions ORDER BY rowid DESC LIMIT ?",(limit,))]
        return [_get(db,sid) for sid in ids]


def preview(path=None,day_limit=8,max_tasks=2,max_minutes=30):
    if type(max_tasks)!=int or not 1<=max_tasks<=2:raise ValueError("At most two tasks")
    if type(max_minutes)!=int or not 2<=max_minutes<=45:raise ValueError("2..45 minutes")
    p=operations.preview_shift(path=path,day_limit=day_limit,
        max_cli_calls=max_tasks,max_total_minutes=max_minutes)
    with tasks._conn(path) as db:
        _schema(db)
        active=db.execute("SELECT 1 FROM worker_sessions WHERE state='running' LIMIT 1").fetchone()
    if active:
        p=dict(p,tasks=[],planned_calls=0,blocked_reason="Previous worker needs owner review")
    return dict(p,active_session=bool(active),owner_start_required=True,
        no_ai_calls_in_preview=True,os_sandbox_provided=False,
        stop_between_tasks_only=True,automatic_retry=False)


def request_stop(sid,owner_confirms=False,path=None):
    if owner_confirms is not True:raise PermissionError("Owner approval required")
    with tasks._conn(path) as db:
        db.execute("BEGIN IMMEDIATE")
        _schema(db)
        if _get(db,sid)["state"]=="running":
            db.execute("UPDATE worker_sessions SET stop_requested=1 WHERE id=?",(sid,))
            db.commit()
    return inspect(sid,path)


def recover(sid,owner_confirms=False,path=None):
    """Does not auto-recover any underlying task still marked running."""
    if owner_confirms is not True:raise PermissionError("Owner review required")
    with tasks._conn(path) as db:
        db.execute("BEGIN IMMEDIATE")
        _schema(db)
        if _get(db,sid)["state"]!="running":raise ValueError("Not active")
        db.execute("""UPDATE worker_sessions SET state='interrupted',ended_at=?,
          reason='Owner recovery: inspect tasks before retry' WHERE id=?""",(core.now(),sid))
        db.commit()
    return inspect(sid,path)


def _finish(sid,state,reason,path):
    with tasks._conn(path) as db:
        db.execute("BEGIN IMMEDIATE")
        _schema(db)
        if _get(db,sid)["state"]=="running":
            db.execute("UPDATE worker_sessions SET state=?,ended_at=?,reason=? WHERE id=?",
                       (state,core.now(),reason[:160],sid))
            db.commit()
    return inspect(sid,path)


def run(expected_task_ids,owner_confirms=False,path=None,day_limit=8,
        max_tasks=2,max_minutes=30):
    """Synchronous shift; never accepts results, retries or charges automatically."""
    if owner_confirms is not True:raise PermissionError("Owner start required")
    if type(expected_task_ids) not in (list,tuple) or not expected_task_ids:
        raise PermissionError("Approve exact task IDs")
    ids=tuple(expected_task_ids)
    if len(ids)>2 or len(set(ids))!=len(ids) or not all(
            isinstance(i,str) and i.startswith("TASK-") for i in ids):
        raise PermissionError("Bad task authorization")
    p=preview(path,day_limit,max_tasks,max_minutes)
    if p.get("blocked_reason") or tuple(t["id"] for t in p["tasks"])!=ids:
        raise PermissionError("Preflight changed: review the plan again")
    sid="SHIFT-"+uuid.uuid4().hex[:16]
    with tasks._conn(path) as db:
        db.execute("BEGIN IMMEDIATE")
        _schema(db)
        if db.execute("SELECT 1 FROM worker_sessions WHERE state='running' LIMIT 1").fetchone():
            raise RuntimeError("Another worker holds the lease")
        ready={r[0] for r in db.execute("SELECT id FROM tasks WHERE status='ready'")}
        if not set(ids)<=ready:raise PermissionError("Task status changed")
        db.execute("""INSERT INTO worker_sessions
            (id,started_at,state,task_ids) VALUES(?,?,'running',?)""",
            (sid,core.now(),json.dumps(ids)))
        db.commit()
    start=time.monotonic()
    state="completed"
    reason="Finished; owner acceptance still required"
    try:
        for task_id in ids:
            r=inspect(sid,path)
            if r["state"]!="running":state="interrupted";reason="Owner interrupted";break
            if r["stop_requested"]:state="stopped";reason="Owner requested stop";break
            remaining=int((max_minutes*60-(time.monotonic()-start))//60)
            if remaining<2:state="stopped";reason="Shift time budget reached";break
            ceiling=min(45,remaining)
            next_plan=operations.preview_shift(path=path,day_limit=day_limit,
                max_cli_calls=1,max_total_minutes=ceiling)
            if (next_plan.get("blocked_reason") or not next_plan["tasks"] or
                    next_plan["tasks"][0]["id"]!=task_id):
                state="stopped";reason="Queue changed; owner review required";break
            outcome=operations.run_shift(owner_confirms=True,
                authorized_task_ids=(task_id,),path=path,day_limit=day_limit,
                max_cli_calls=1,max_total_minutes=ceiling)
            results=outcome.get("executed",[])
            if len(results)!=1 or results[0].get("id")!=task_id:
                state="stopped";reason="Unexpected task outcome";break
            minimal={"task_id":task_id,"status":str(results[0]["status"])[:40]}
            with tasks._conn(path) as db:
                db.execute("BEGIN IMMEDIATE")
                _schema(db)
                current=_get(db,sid)
                if current["state"]!="running":raise RuntimeError("Lease interrupted")
                db.execute("UPDATE worker_sessions SET processed=? WHERE id=?",
                    (json.dumps(current["processed"]+[minimal]),sid))
                db.commit()
            if minimal["status"]!="awaiting-acceptance":
                state="stopped";reason="Failed task; manual review required";break
    except Exception as error:
        state="interrupted"
        reason="Worker error "+type(error).__name__+"; manual inspection required"
    return _finish(sid,state,reason,path)
