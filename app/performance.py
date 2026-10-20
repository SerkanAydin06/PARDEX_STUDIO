"""PARDEX Studio's offline, privacy-respecting AI evaluation data.

Observational data is only advisory. Subscription balances, model token
consumption and prices cannot be inferred from elapsed time.
"""
from __future__ import annotations
from collections import defaultdict
from pathlib import Path
from statistics import median

def report(path=None,project=None):
    import task_queue
    with task_queue._conn(path) as db:
        if project is None:
            rows=[dict(r) for r in db.execute('SELECT * FROM task_attempt_metrics ORDER BY started_at DESC LIMIT 3000')]
        else:
            target=str(Path(project).expanduser().resolve())
            rows=[dict(r) for r in db.execute(
                'SELECT * FROM task_attempt_metrics WHERE project=? ORDER BY started_at DESC LIMIT 3000',(target,))]
    groups=defaultdict(list)
    for r in rows:groups[(r['provider'],r['kind'])].append(r)
    out=[]
    for (provider,kind),items in sorted(groups.items()):
        done=[r for r in items if r['result_code']!='running']
        reviewed=[r for r in done if r['owner_review'] in ('accepted','rejected')]
        durations=[float(r['elapsed_seconds']) for r in done if r['elapsed_seconds'] is not None]
        accepted=sum(r['owner_review']=='accepted' for r in reviewed)
        out.append({'provider':provider,'kind':kind,'attempts':len(items),
                    'completed':len(done),'verified':sum(r['verified']==1 for r in done),
                    'owner_accepted':accepted,'owner_rejected':len(reviewed)-accepted,
                    'reviewed_samples':len(reviewed),
                    'awaiting_review':sum(r['result_code']=='verified' and r['owner_review']=='pending' for r in done),
                    'failed':sum(r['result_code'] in ('ai_failed','test_failed','exception','interrupted') for r in done),
                    'median_elapsed_seconds':round(median(durations),2) if durations else None,
                    'acceptance_rate_reviewed':round(accepted/len(reviewed),3) if reviewed else None})
    return {'total_attempts':len(rows),
            'completed_attempts':sum(r['result_code']!='running' for r in rows),
            'total_recorded_seconds':round(sum(float(r['elapsed_seconds']) for r in rows
                                                if r['elapsed_seconds'] is not None),2),
            'by_provider_and_kind':out,
            'actual_cloud_token_usage_known':False,'subscription_balance_known':False,
            'provider_prices_known':False,'unmeasured_historical_attempts_possible':True,
            'note':'Sadece yerel sure, test sonucu ve sahip kabul sonucu olculur; gercek token/kredi maliyeti bilinmiyor.'}

def recommendations(path=None,project=None,minimum_reviewed=5):
    """Pilot hints only, NEVER autonomous provider switching or spending."""
    if type(minimum_reviewed) is not int or minimum_reviewed<5:
        raise ValueError('En az 5 sahip incelemeli ornek gerekli')
    grouped=defaultdict(list)
    for r in report(path,project)['by_provider_and_kind']:
        if r['reviewed_samples']>=minimum_reviewed:grouped[r['kind']].append(r)
    suggestions=[]
    for kind,options in sorted(grouped.items()):
        if len(options)<2:continue
        best=max(options,key=lambda x:x['acceptance_rate_reviewed'])
        second=max((r for r in options if r is not best),key=lambda x:x['acceptance_rate_reviewed'])
        gap=best['acceptance_rate_reviewed']-second['acceptance_rate_reviewed']
        if gap>=0.20:
            suggestions.append({'kind':kind,'candidate_provider':best['provider'],
                                'other_provider':second['provider'],
                                'accepted_rate_difference':round(gap,3),
                                'requires_owner_approval':True,
                                'actual_cost_saving_proven':False,
                                'recommendation':'Kontrollu kucuk A/B denemesi; otomatik model degisikligi yok.'})
    return suggestions
