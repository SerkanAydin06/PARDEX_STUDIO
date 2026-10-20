"""Owner-approved multi-project General Manager: planning without background AI calls."""
from __future__ import annotations
from pathlib import Path
import json
import uuid
import core
import task_queue as q
import performance

RISKS=('Basit','Normal','Kritik')
TEMPLATES={
 'Basit':(('Muhendislik','Yeni ozellik / Kod','Codex','Dengeli',12),),
 'Normal':(('Muhendislik','Yeni ozellik / Kod','Codex','Dengeli',18),
           ('Kalite Guvence','Inceleme / Analiz','Gemini','Ekonomik',8)),
 'Kritik':(('AI Genel Mudur','Mimari / Plan','Claude','Dengeli',8),
           ('Muhendislik','Yeni ozellik / Kod','Codex','Dengeli',20),
           ('Kalite Guvence','Inceleme / Analiz','Gemini','Dengeli',10))
}

def _setup(db):
    db.execute("""CREATE TABLE IF NOT EXISTS manager_plans(
        id TEXT PRIMARY KEY, project TEXT NOT NULL, goal TEXT NOT NULL,
        risk TEXT NOT NULL, created_at TEXT NOT NULL, task_ids TEXT NOT NULL,
        call_ceiling INTEGER NOT NULL, minute_ceiling INTEGER NOT NULL)""")

def preview(project,goal,risk='Normal'):
    project=Path(project).expanduser().resolve()
    goal=str(goal).strip()
    if core.project_type(project)=='unknown':raise ValueError('Once taninan bir proje bagla')
    if not 8<=len(goal)<=300:raise ValueError('Hedef 8-300 karakter olmali')
    if risk not in RISKS:raise ValueError('Gecersiz risk seviyesi')
    steps=TEMPLATES[risk]
    return {'project':str(project),'goal':core.redact_log_output(goal),'risk':risk,
        'steps':[{'department':d,'kind':k,'provider':p,'quality':z,'max_minutes':m}
                 for d,k,p,z,m in steps],
        'max_cli_calls':len(steps),'max_total_minutes':sum(x[4] for x in steps),
        'real_token_cost_known':False,'requires_owner_start':True,'requires_owner_acceptance':True}

def create(project,goal,risk='Normal',priority=3,path=None):
    """Create only pending-owner tasks. No AI requests, auto-approval or background work."""
    planned=preview(project,goal,risk)
    if type(priority) is not int or not 1<=priority<=5:raise ValueError('Oncelik 1-5 olmali')
    task_ids=[]
    for stage in planned['steps']:
        if stage['kind']=='Mimari / Plan':
            detail='Ilgili dosyalari, testleri ve riskleri kisa planla; kod degistirme.'
        elif stage['kind']=='Inceleme / Analiz':
            detail='Onceki kod farkini ve testleri bagimsiz denetle; kod degistirme.'
        else:
            detail='Kucuk degisikliklerle uygula ve test et; push, yayin ve satin alma yapma.'
        title=planned['goal'][:180]+' | '+stage['department']+': '+detail
        task=q.add_task(planned['project'],title,kind=stage['kind'],provider=stage['provider'],
                        quality=stage['quality'],priority=priority,max_minutes=stage['max_minutes'],
                        path=path,depends_on=task_ids[-1:] if task_ids else ())
        task_ids.append(task['id'])
    ident='PLAN-'+uuid.uuid4().hex[:12]
    with q._conn(path) as db:
        db.execute('BEGIN IMMEDIATE')
        _setup(db)
        db.execute('''INSERT INTO manager_plans(id,project,goal,risk,created_at,task_ids,call_ceiling,minute_ceiling)
                      VALUES(?,?,?,?,?,?,?,?)''',
                   (ident,planned['project'],planned['goal'],risk,core.now(),
                    json.dumps(task_ids),planned['max_cli_calls'],planned['max_total_minutes']))
        db.commit()
    return get(ident,path)

def get(ident,path=None):
    with q._conn(path) as db:
        _setup(db)
        row=db.execute('SELECT * FROM manager_plans WHERE id=?',(ident,)).fetchone()
        if row is None:raise ValueError('Plan bulunamadi')
        item=dict(row)
    tasks=[q.get_task(t,path) for t in json.loads(item['task_ids'])]
    for task in tasks:
        task['waiting_for']=[d['id'] for d in q.dependencies(task['id'],path) if d['status']!='accepted']
    item['tasks']=tasks
    item['invocations_observed']=sum(t['attempts'] for t in tasks)
    item['model_spend_known']=False
    item['status']=('accepted' if all(t['status']=='accepted' for t in tasks)
        else 'needs-attention' if any(t['status'] in ('needs-attention','cancelled') for t in tasks)
        else 'in-progress' if any(t['status']!='pending-owner' for t in tasks)
        else 'pending-owner')
    return item

def list_plans(path=None,limit=50):
    with q._conn(path) as db:
        _setup(db)
        rows=db.execute('SELECT id FROM manager_plans ORDER BY rowid DESC LIMIT ?',
                        (max(1,min(int(limit),100)),)).fetchall()
    return [get(row['id'],path) for row in rows]

def dashboard(path=None):
    plans=list_plans(path)
    observed=performance.report(path)
    return {'plans_total':len(plans),
        'by_status':{s:sum(p['status']==s for p in plans)
                     for s in ('pending-owner','in-progress','needs-attention','accepted')},
        'estimated_max_cli_calls':sum(p['call_ceiling'] for p in plans),
        'observed_attempts':sum(p['invocations_observed'] for p in plans),
        'subscription_remaining_tokens_known':False,'paid_provider_api_needed':False,
        'observed_execution_metrics':observed,'advisory_experiments':performance.recommendations(path)}
