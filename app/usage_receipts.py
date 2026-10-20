"""Opt-in Codex JSONL usage import. Reported tokens are NOT invoice data."""
import json
from pathlib import Path
import task_queue
import core

def parse_codex_jsonl(raw):
    if not isinstance(raw,str) or len(raw)>1000000:raise ValueError('Input too large')
    total={'input_tokens':0,'cached_input_tokens':0,'output_tokens':0}
    count=0
    for line in raw.splitlines():
        if not line.strip():continue
        try:event=json.loads(line)
        except ValueError:raise ValueError('Malformed JSONL') from None
        if not isinstance(event,dict):raise ValueError('Invalid event')
        if event.get('type')!='turn.completed' or not isinstance(event.get('usage'),dict):continue
        usage=event['usage']
        if any(type(usage.get(k)) is not int or not 0<=usage[k]<=10000000000 for k in total):
            raise ValueError('Invalid token counts')
        if usage['cached_input_tokens']>usage['input_tokens']:raise ValueError('Invalid cache count')
        for k in total:total[k]+=usage[k]
        count+=1
    if not count:raise ValueError('No token usage events')
    return total

def import_codex_usage(task_id,attempt,raw,path=None,owner_confirms_source=False):
    if owner_confirms_source is not True:raise PermissionError('Owner confirmation required')
    if type(attempt) is not int or attempt<1:raise ValueError('Invalid attempt')
    tokens=parse_codex_jsonl(raw)
    with task_queue._conn(path) as db:
        db.execute('BEGIN IMMEDIATE')
        task_queue._row(db,task_id)
        rec=db.execute('SELECT provider,result_code FROM task_attempt_metrics WHERE task_id=? AND attempt=?',
                       (task_id,attempt)).fetchone()
        if not rec or rec['provider']!='Codex' or rec['result_code']=='running':
            raise ValueError('Matching finished Codex attempt required')
        db.execute('''CREATE TABLE IF NOT EXISTS provider_usage_receipts(
            task_id TEXT,attempt INTEGER,provider TEXT,input_tokens INTEGER,
            cached_input_tokens INTEGER,output_tokens INTEGER,source TEXT,
            PRIMARY KEY(task_id,attempt))''')
        db.execute('INSERT INTO provider_usage_receipts VALUES(?,?,?,?,?,?,?)',
                   (task_id,attempt,'Codex',tokens['input_tokens'],
                    tokens['cached_input_tokens'],tokens['output_tokens'],'operator-supplied-unverified-CLI'))
        db.commit()
    return {'reported_tokens':tokens,'verified_billing':False,'subscription_balance_known':False}

def summary(path=None,project=None):
    with task_queue._conn(path) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='provider_usage_receipts'").fetchone():
            return {'attempts':0,'tokens':None,'verified_billing':False}
        q=('SELECT count(*),sum(u.input_tokens),sum(u.cached_input_tokens),sum(u.output_tokens) '
           'FROM provider_usage_receipts u JOIN tasks t ON t.id=u.task_id')
        params=()
        if project is not None:
            q+=' WHERE t.project=?'
            params=(str(Path(project).expanduser().resolve()),)
        row=db.execute(q,params).fetchone()
    return {'attempts':row[0],
            'tokens':{'input':row[1],'cached_input':row[2],'output':row[3]} if row[0] else None,
            'verified_billing':False,'provenance':'operator-supplied-unverified-CLI'}
