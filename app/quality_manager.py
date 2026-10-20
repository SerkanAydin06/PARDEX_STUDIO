"""PARDEX independent QA and owner-approved fair comparison pilots.

No cloud calls, autonomous model selection, price claims or hidden approvals.
A model PASS is only an untrusted claim and never a security certificate.
"""
from __future__ import annotations

from pathlib import Path
from collections import defaultdict
import hashlib
import json
import uuid
import core
import task_queue as queue

PROVIDERS = ('Claude','Codex','Gemini')


def _schema(c):
    c.execute("""CREATE TABLE IF NOT EXISTS quality_reviews(
        review_task_id TEXT PRIMARY KEY, producer_task_id TEXT NOT NULL,
        created_at TEXT NOT NULL, verdict TEXT NOT NULL DEFAULT 'pending',
        finding_summary TEXT NOT NULL DEFAULT '', reviewer_provider TEXT NOT NULL DEFAULT '',
        producer_attempt INTEGER, review_attempt INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS quality_pilots(
        id TEXT PRIMARY KEY, task_kind TEXT NOT NULL, scenario_hash TEXT NOT NULL,
        engine TEXT NOT NULL, test_profile TEXT NOT NULL, providers TEXT NOT NULL,
        created_at TEXT NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS quality_trials(
        pilot_id TEXT NOT NULL,pair_number INTEGER NOT NULL,
        provider TEXT NOT NULL,task_id TEXT NOT NULL UNIQUE,
        project TEXT NOT NULL,verified INTEGER NOT NULL,
        owner_accepted INTEGER NOT NULL,seconds REAL,
        PRIMARY KEY(pilot_id,pair_number,provider))""")


def register_review(producer_id,review_id,path=None):
    with queue._conn(path) as c:
        c.execute('BEGIN IMMEDIATE')
        _schema(c)
        a=queue._row(c,producer_id)
        b=queue._row(c,review_id)
        if a['project']!=b['project'] or producer_id==review_id or b['kind']!='Inceleme / Analiz':
            raise ValueError('Same-project independent analysis task required')
        dep=c.execute('SELECT 1 FROM task_dependencies WHERE task_id=? AND prerequisite_id=?',
                      (review_id,producer_id)).fetchone()
        if not dep:raise ValueError('Review must depend on producer acceptance')
        pa=core.route(a['kind'],a['provider_preference'],a['quality'])[0]
        pb=core.route(b['kind'],b['provider_preference'],b['quality'])[0]
        if pa==pb:raise ValueError('Independent reviewer must use another provider')
        if b['attempts']:raise ValueError('Cannot register a review after execution started')
        c.execute('INSERT INTO quality_reviews(review_task_id,producer_task_id,created_at) VALUES(?,?,?)',
                  (review_id,producer_id,core.now()))
        c.commit()
    return review_status(review_id,path)


def review_status(review_id,path=None):
    with queue._conn(path) as c:
        _schema(c)
        rec=c.execute('SELECT * FROM quality_reviews WHERE review_task_id=?',(review_id,)).fetchone()
        if not rec:raise ValueError('Unregistered QA review')
        rec=dict(rec)
        producer=queue._row(c,rec['producer_task_id'])
        reviewer=queue._row(c,review_id)
    pa=producer['provider_used'] or core.route(producer['kind'],producer['provider_preference'],producer['quality'])[0]
    pb=reviewer['provider_used'] or core.route(reviewer['kind'],reviewer['provider_preference'],reviewer['quality'])[0]
    independent=pa!=pb
    return {
        'review_task_id':review_id,'producer_task_id':rec['producer_task_id'],
        'review_status':reviewer['status'],'producer_status':producer['status'],
        'verdict':rec['verdict'],'finding_summary':rec['finding_summary'],
        'independent_provider':independent,'local_engine_test_verified':bool(reviewer['verified']),
        'owner_accepted_review':reviewer['status']=='accepted',
        'quality_gate_passed':bool(rec['verdict']=='PASS' and independent
            and reviewer['status']=='accepted' and producer['status']=='accepted'
            and reviewer['verified'] and rec['producer_attempt']==producer['attempts']
            and rec['review_attempt']==reviewer['attempts']),
        'not_a_security_certification':True}


def _qa_result(output):
    if not isinstance(output,str):return None
    lines=output.strip().splitlines()
    marks=[(i,line.strip()) for i,line in enumerate(lines)
           if line.strip().startswith('PARDEX_QA_VERDICT=')]
    if len(marks)!=1:return None
    idx,mark=marks[0]
    if mark not in ('PARDEX_QA_VERDICT=PASS','PARDEX_QA_VERDICT=FAIL'):return None
    details=[x.strip() for x in lines[idx+1:] if x.strip()]
    if len(details)!=1 or not details[0].startswith('PARDEX_QA_FINDINGS='):return None
    finding=details[0].split('=',1)[1].strip()
    if not 10<=len(finding)<=240:return None
    return mark.split('=',1)[1],core.redact_log_output(finding)[:240]


def evaluate_review(review_id,outcome,path=None):
    """Read one structured claim, fail closed, require another provider."""
    with queue._conn(path) as c:
        c.execute('BEGIN IMMEDIATE')
        _schema(c)
        record=c.execute('SELECT * FROM quality_reviews WHERE review_task_id=?',(review_id,)).fetchone()
        if not record:return None
        producer=queue._row(c,record['producer_task_id'])
        reviewer=queue._row(c,review_id)
        if reviewer['status']!='running':raise ValueError('Review has not started')
        actual=outcome.get('provider')
        parsed=_qa_result(outcome.get('output',''))
        valid=(producer['status']=='accepted' and producer['provider_used'] in PROVIDERS
            and actual in PROVIDERS and actual!=producer['provider_used']
            and bool(outcome.get('ai_ok')) and bool(outcome.get('verified')) and parsed)
        verdict=parsed[0] if valid else 'INCONCLUSIVE'
        finding=parsed[1] if valid else 'Review evidence missing, provider reused or engine test failed'
        c.execute("""UPDATE quality_reviews
                     SET verdict=?,finding_summary=?,reviewer_provider=?,
                         producer_attempt=?,review_attempt=?
                     WHERE review_task_id=?""",
                  (verdict,finding,actual if actual in PROVIDERS else '',
                   producer['attempts'],reviewer['attempts'],review_id))
        c.commit()
    return {'passed':verdict=='PASS','verdict':verdict,'summary':finding,
            'requires_owner_acceptance':True,'ai_claim_not_guarantee':True}


def review_dashboard(path=None):
    with queue._conn(path) as c:
        _schema(c)
        ids=[r[0] for r in c.execute('SELECT review_task_id FROM quality_reviews ORDER BY rowid DESC LIMIT 100')]
    rows=[review_status(x,path) for x in ids]
    return {'registered':len(rows),'quality_gates_passed':sum(x['quality_gate_passed'] for x in rows),
            'reviews':rows,'claims_are_not_certificates':True,'cloud_costs_known':False}


def register_pilot(kind,scenario,engine,test_profile,providers=('Codex','Gemini'),path=None):
    """Persist an offline experimental plan. NO model runs."""
    scenario=str(scenario).strip()
    profile=str(test_profile).strip()
    if kind not in queue.KINDS or not 12<=len(scenario)<=700:
        raise ValueError('Comparable task description required')
    if engine not in ('godot','unity','unreal','flutter','android','web') or not 4<=len(profile)<=160:
        raise ValueError('Engine and identical test profile required')
    if not isinstance(providers,(tuple,list)) or len(providers)!=2 or len(set(providers))!=2 or any(x not in PROVIDERS for x in providers):
        raise ValueError('Two independent providers required')
    pid='PILOT-'+uuid.uuid4().hex[:12]
    with queue._conn(path) as c:
        _schema(c)
        c.execute('INSERT INTO quality_pilots VALUES(?,?,?,?,?,?,?)',
                  (pid,kind,hashlib.sha256(scenario.encode()).hexdigest(),
                   engine,profile,json.dumps(list(providers)),core.now()))
    return pilot_info(pid,path)


def pilot_info(pilot_id,path=None):
    with queue._conn(path) as c:
        _schema(c)
        pilot=c.execute('SELECT * FROM quality_pilots WHERE id=?',(pilot_id,)).fetchone()
        if not pilot:raise ValueError('Pilot not found')
        pilot=dict(pilot)
        trials=[dict(t) for t in c.execute(
            'SELECT * FROM quality_trials WHERE pilot_id=? ORDER BY pair_number,provider',(pilot_id,))]
    providers=json.loads(pilot['providers'])
    pairs=defaultdict(list)
    for t in trials:pairs[t['pair_number']].append(t)
    complete={n for n,rows in pairs.items() if len(rows)==2
              and {x['provider'] for x in rows}==set(providers)
              and rows[0]['project']!=rows[1]['project']}
    observations=[]
    for provider in providers:
        rows=[r for r in trials if r['provider']==provider and r['pair_number'] in complete]
        observations.append({'provider':provider,'pairs':len(rows),
            'locally_verified':sum(x['verified'] for x in rows),
            'owner_accepted':sum(x['owner_accepted'] for x in rows),
            'total_elapsed_seconds':round(sum(x['seconds'] or 0 for x in rows),2)})
    return {'id':pilot_id,'kind':pilot['task_kind'],'engine':pilot['engine'],
        'test_profile':pilot['test_profile'],'providers':providers,
        'paired_trials':len(complete),'minimum_paired_trials':3,
        'observations':observations,'fair_quality_comparison_ready':len(complete)>=3,
        'actual_tokens_known':False,'cost_savings_proven':False,
        'owner_approval_required':True,'automatic_model_switch':False,
        'note':'Owner-attested separate projects; matched task/test profile. No proven savings or model superiority.'}


def record_pilot_trial(pilot_id,pair_number,task_id,*,owner_confirms_isolation=False,path=None):
    """Register one real, owner-reviewed task attempt. No invented scores."""
    if owner_confirms_isolation is not True:
        raise PermissionError('Owner must attest isolated independent workspace')
    if isinstance(pair_number,bool) or not isinstance(pair_number,int) or not 1<=pair_number<=100:
        raise ValueError('Invalid pair number')
    with queue._conn(path) as c:
        c.execute('BEGIN IMMEDIATE')
        _schema(c)
        pilot=c.execute('SELECT * FROM quality_pilots WHERE id=?',(pilot_id,)).fetchone()
        if not pilot:raise ValueError('Pilot not found')
        task=queue._row(c,task_id)
        if task['status'] not in ('accepted','needs-attention'):
            raise ValueError('Owner-reviewed finished task required')
        if core.project_type(task['project'])!=pilot['engine'] or task['kind']!=pilot['task_kind']:
            raise ValueError('Engine/task kind mismatch')
        if hashlib.sha256(task['title'].strip().encode()).hexdigest()!=pilot['scenario_hash']:
            raise ValueError('Tasks must have identical scenario description')
        if task['provider_used'] not in json.loads(pilot['providers']):
            raise ValueError('Wrong actual provider')
        attempt=c.execute('SELECT * FROM task_attempt_metrics WHERE task_id=? ORDER BY attempt DESC LIMIT 1',
                          (task_id,)).fetchone()
        if not attempt or attempt['owner_review'] not in ('accepted','rejected') or attempt['provider']!=task['provider_used']:
            raise ValueError('Owner-reviewed measured attempt required')
        pair=c.execute('SELECT project FROM quality_trials WHERE pilot_id=? AND pair_number=?',
                       (pilot_id,pair_number)).fetchall()
        if any(x['project']==task['project'] for x in pair):
            raise ValueError('Different isolated project paths required per pair')
        c.execute("""INSERT INTO quality_trials(
            pilot_id,pair_number,provider,task_id,project,verified,owner_accepted,seconds)
            VALUES(?,?,?,?,?,?,?,?)""",
            (pilot_id,pair_number,task['provider_used'],task_id,task['project'],
             int(bool(attempt['verified'])),int(attempt['owner_review']=='accepted'),
             attempt['elapsed_seconds']))
        c.commit()
    return pilot_info(pilot_id,path)


def list_pilots(path=None,limit=20):
    with queue._conn(path) as c:
        _schema(c)
        ids=[x[0] for x in c.execute('SELECT id FROM quality_pilots ORDER BY rowid DESC LIMIT ?',
            (max(1,min(int(limit),100)),))]
    return [pilot_info(ident,path) for ident in ids]
