"""PARDEX 2F: bounded owner-started AI work shifts across projects.

No daemon, hidden approval, auto-retry, deploy, purchase or background polling.
The queue remains authoritative. A shift may only consume tasks individually
approved by the owner, and results always await separate owner acceptance.
Native CLI subprocesses are NOT a security sandbox; strict mode fails closed.
"""
from __future__ import annotations

from pathlib import Path
import time

import core
import task_queue as queue
import worker_guard

_MAX_CALLS = 3
_MAX_MINUTES = 90


def _limits(day_limit, max_cli_calls, max_total_minutes):
    for number, minimum, maximum, title in (
        (day_limit, 1, 100, 'daily calls'),
        (max_cli_calls, 1, _MAX_CALLS, 'shift calls'),
        (max_total_minutes, 2, _MAX_MINUTES, 'shift minutes'),
    ):
        if type(number) is not int or not minimum <= number <= maximum:
            raise ValueError(f'{title} must be {minimum}..{maximum}')


def _ready_rows(path):
    with queue._conn(path) as conn:
        running = conn.execute("SELECT count(*) FROM tasks WHERE status='running'").fetchone()[0]
        rows = conn.execute("SELECT * FROM tasks WHERE status='ready' "
                            "ORDER BY priority DESC,rowid ASC").fetchall()
        accepted = {x[0] for x in conn.execute(
            "SELECT id FROM tasks WHERE status='accepted'")}
        dependencies = {}
        for row in conn.execute('SELECT task_id,prerequisite_id FROM task_dependencies'):
            dependencies.setdefault(row[0], []).append(row[1])
    return running, [dict(x) for x in rows], accepted, dependencies


def preview_shift(*, path=None, day_limit=8, max_cli_calls=2, max_total_minutes=45):
    """Offline preflight. Never calls a model, records usage or writes SQLite."""
    _limits(day_limit, max_cli_calls, max_total_minutes)
    running, rows, accepted, deps = _ready_rows(path)
    calls_today = core.usage_count()
    available = max(0, min(max_cli_calls, day_limit - calls_today))
    selected, used_projects = [], set()
    minutes = 0
    reason = None
    strict = worker_guard.strict_worker_mode()
    if running:reason = 'another AI task is already running or awaits recovery'
    elif strict:reason = 'strict isolation blocks native CLI workers (no isolated credentialed agent is available)'
    elif available == 0:reason = 'daily call allowance exhausted'
    else:
        for row in rows:
            if len(selected) >= available:break
            if any(dep not in accepted for dep in deps.get(row['id'], ())):
                # Queue would not claim this task; it is safe to consider the next.
                continue
            if row['project'] in used_projects:
                # queue.execute_one selects the earliest eligible task, not a chosen ID.
                # Do NOT skip it or the shift might execute an unlisted task.
                reason = 'another task from the same project needs owner review first'
                break
            if minutes + row['max_minutes'] > max_total_minutes:
                reason = 'next task would exceed the shift minute ceiling'
                break
            provider, model = core.route(row['kind'], row['provider_preference'], row['quality'])
            command = {'Claude':'claude', 'Codex':'codex', 'Gemini':'gemini'}[provider]
            if not core.which(command):
                reason = f'{provider} CLI is not installed'
                break
            if core.project_type(row['project']) == 'unknown':
                reason = 'project directory or engine is missing'
                break
            selected.append({'id': row['id'], 'project': Path(row['project']).name,
                             'provider': provider, 'model_estimate': model,
                             'max_minutes': row['max_minutes'], 'priority': row['priority']})
            used_projects.add(row['project'])
            minutes += row['max_minutes']
    return {'tasks': selected, 'planned_calls': len(selected),
            'max_total_minutes': max_total_minutes, 'reserved_minutes': minutes,
            'calls_today': calls_today, 'day_limit': day_limit,
            'remaining_daily_before': max(0, day_limit - calls_today),
            'blocked_reason': reason, 'already_running': bool(running),
            'strict_mode': strict, 'requires_owner_start': True,
            'requires_individual_task_approval': True,
            'requires_separate_result_acceptance': True,
            'tokens_or_subscription_balance_known': False,
            'real_os_isolation_guaranteed': False,
            'no_model_calls_in_preview': True}


def run_shift(*, owner_confirms=False, authorized_task_ids=(), path=None, day_limit=8,
              max_cli_calls=2, max_total_minutes=45, on_update=None):
    """Runs only the exact preflight sequence after an explicit owner action.

    Stops on any change in the top queued task, failure, daily ceiling, timeout,
    or exception. Never accepts results, handles billing or creates fresh tasks.
    """
    if owner_confirms is not True:
        raise PermissionError('explicit owner start confirmation required')
    plan = preview_shift(path=path, day_limit=day_limit,
                         max_cli_calls=max_cli_calls,max_total_minutes=max_total_minutes)
    planned_ids=tuple(x['id'] for x in plan['tasks'])
    if type(authorized_task_ids) not in (tuple,list) or tuple(authorized_task_ids) != planned_ids:
        raise PermissionError('shift task list changed; preview and explicitly approve exact task IDs')
    if not plan['tasks']:
        return {'executed': [], 'stop_reason': plan['blocked_reason'] or 'no ready tasks',
                'requires_result_acceptance': False, 'owner_started': True}
    observed = []
    started = time.monotonic()
    stop_reason = 'planned tasks completed; owner must inspect results'
    for expected in plan['tasks']:
        elapsed = time.monotonic() - started
        if elapsed >= max_total_minutes * 60:
            stop_reason = 'shift elapsed time ceiling reached'
            break
        if core.usage_count() >= day_limit:
            stop_reason = 'daily AI call limit reached'
            break
        # Revalidate the exact task before executing; never run a newly arrived,
        # higher-priority task that the owner did not see in the shift preview.
        next_task = queue.preview_next(day_limit=day_limit, path=path)
        if not next_task.get('ready') or next_task.get('id') != expected['id']:
            stop_reason = 'queue order changed; new explicit owner review required'
            break
        if next_task.get('blocked'):
            stop_reason = 'worker/tool/call limit blocked execution'
            break
        if worker_guard.strict_worker_mode():
            stop_reason = 'strict worker mode blocks native agent execution'
            break
        try:
            result = queue.execute_one(day_limit=day_limit,path=path,on_update=on_update)
        except Exception as exc:
            # Do not retry. A claimed task may now be marked running; operator recovery is required.
            stop_reason = 'worker exception; inspect queue manually: ' + type(exc).__name__
            break
        if result is None or result['id'] != expected['id']:
            stop_reason = 'unexpected worker result; inspect queue manually'
            break
        observed.append({'id': result['id'], 'status': result['status'],
                         'provider': result.get('provider_used') or expected['provider']})
        if result['status'] != 'awaiting-acceptance':
            stop_reason = 'task failed or needs human attention; automatic retries disabled'
            break
    return {'executed': observed, 'stop_reason': stop_reason,
            'requires_result_acceptance': bool(observed), 'owner_started': True,
            'any_tasks_auto_accepted': False, 'automatic_retry': False,
            'actual_token_cost_known': False}


def board(*, path=None):
    """Private, deterministic company dashboard; no AI calls or task prompts."""
    with queue._conn(path) as conn:
        rows = [dict(x) for x in conn.execute(
            'SELECT project,status,priority,max_minutes FROM tasks ORDER BY rowid')]
    projects={}
    for task in rows:
        name=Path(task['project']).name
        item=projects.setdefault(task['project'], {'project_name':name, 'total':0,
            'owner_approval':0, 'awaiting_owner_review':0,
            'needs_attention':0,'ready':0,'running':0,'accepted':0})
        item['total'] += 1
        status=task['status']
        key={'pending-owner':'owner_approval','awaiting-acceptance':'awaiting_owner_review',
             'needs-attention':'needs_attention'}.get(status,status)
        if key in item:item[key] += 1
    return {'projects':sorted(projects.values(),key=lambda d:(-d['needs_attention'],
                   -d['awaiting_owner_review'],-d['ready'],d['project_name'])),
            'project_count':len(projects),'total_tasks':len(rows),
            'subscription_balance_known':False,'no_ai_called':True}
