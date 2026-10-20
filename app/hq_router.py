"""Phase 4 — model router for the owner's subscriptions (Claude Pro, ChatGPT Pro/Codex, Google AI Pro/Gemini).

Picks the cheapest provider/model/effort that is good enough for each company role, using only the
CLIs that are installed and logged in. Version numbers are never hard-coded: Claude Code aliases
(haiku/sonnet/opus) and Gemini aliases (flash-lite/flash/pro) always resolve to the latest model the
subscription offers. Codex uses the account default model; only reasoning effort is set.

Learning (K0): every call records success per role/provider; once a provider has >= 5 results and
does >= 20 points worse than an alternative with >= 5 results, the router switches to the alternative.
"""
import functools
import time
from pathlib import Path

import core
import hq_store as store

# role -> ordered candidates (provider, model alias, effort). First installed one wins.
ROLES = {
    'plan_chat': (('Claude', 'sonnet', 'low'), ('Gemini', 'pro', ''), ('Codex', '', 'low')),
    'breakdown': (('Claude', 'sonnet', 'medium'), ('Gemini', 'pro', ''), ('Codex', '', 'medium')),
    'architect': (('Claude', 'opus', 'medium'), ('Gemini', 'pro', ''), ('Codex', '', 'high')),
    'implement': (('Codex', '', 'medium'), ('Claude', 'sonnet', 'medium'), ('Gemini', 'pro', '')),
    'fix':       (('Codex', '', 'high'), ('Claude', 'sonnet', 'high'), ('Gemini', 'pro', '')),
    'fix_strong': (('Claude', 'opus', 'high'), ('Codex', '', 'high'), ('Gemini', 'pro', '')),
    'review':    (('Gemini', 'flash', ''), ('Claude', 'haiku', 'low'), ('Codex', '', 'low')),
    'research':  (('Gemini', 'pro', ''), ('Claude', 'sonnet', 'medium')),
    'text':      (('Claude', 'haiku', 'low'), ('Gemini', 'flash-lite', ''), ('Codex', '', 'low')),
}
ROLE_LABELS = {
    'plan_chat': 'Plan sohbeti (Ürün Müdürü)', 'breakdown': 'İş paylaşımı (CEO)',
    'architect': 'Zor mimari (yalnızca yüksek karmaşıklık)', 'implement': 'Kod yazımı',
    'fix': 'Düzeltme', 'fix_strong': 'Güçlü düzeltme (yalnızca patron isterse)', 'review': 'Bağımsız kod incelemesi', 'research': 'Ar-Ge web araştırması',
    'text': 'Kısa metin / özet',
}
# What a role may touch: write = edit files in the product folder only; web = search/fetch only.
MODES = {'implement': 'write', 'fix': 'write', 'fix_strong': 'write', 'research': 'web'}
BINARIES = {'Claude': 'claude', 'Codex': 'codex', 'Gemini': 'gemini'}


def installed():
    return {p: core.which(b) for p, b in BINARIES.items() if core.which(b)}


@functools.lru_cache(maxsize=8)
def _help(exe):
    try:
        r = core.run([exe, '--help'], Path.home(), timeout=20)
        return r.stdout or ''
    except Exception:
        return ''


def _supports(exe, flag):
    return flag in _help(exe)


def _rate(stats, role, provider):
    row = stats.get((role, provider))
    return (row['ok'] / row['n'], row['n']) if row and row['n'] else (None, 0)


def choose(role, avoid=(), path=None, have=None):
    """Return (provider, model, effort, reason). Raises if no usable provider."""
    if role not in ROLES:
        raise ValueError('Bilinmeyen rol')
    have = installed() if have is None else have
    s = store.settings(path)
    override = (s.get('routing') or {}).get(role)
    if override and override['provider'] in have and override['provider'] not in avoid:
        return override['provider'], override['model'], override['effort'], 'Patronun yönlendirme ayarı'
    cands = [c for c in ROLES[role] if c[0] in have and c[0] not in avoid]
    if not cands:
        if role == 'review' and avoid:
            raise RuntimeError('Bağımsız kalite denetçisi yok; farklı bir AI sağlayıcısı kurulmalı')
        cands = [c for c in ROLES[role] if c[0] in have]
        if not cands:
            raise RuntimeError('Kullanılabilir AI CLI yok (Claude Code, Codex veya Gemini CLI kur ve giriş yap)')
        if avoid:
            first = cands[0]
            return first[0], first[1], first[2], 'Farklı sağlayıcı kurulu değil; bağımsızlık sınırlı'
    stats = {(r['role'], r['provider']): r for r in store.route_stats(path)}
    first = cands[0]
    r0, n0 = _rate(stats, role, first[0])
    if n0 >= 5:
        for alt in cands[1:]:
            ra, na = _rate(stats, role, alt[0])
            if na >= 5 and ra - r0 >= 0.2:
                return alt[0], alt[1], alt[2], f'Öğrenme: {alt[0]} bu işte daha başarılı (%{round(ra*100)} / %{round(r0*100)})'
    return first[0], first[1], first[2], 'Varsayılan en ekonomik uygun model'


def build_cmd(provider, exe, model, effort, mode):
    """Command line; the prompt always goes through stdin (no shell, no length limits)."""
    if provider == 'Claude':
        cmd = [exe, '-p', '--model', model or 'sonnet']
        if effort and _supports(exe, '--effort'):
            cmd += ['--effort', effort]
        if mode == 'write':
            cmd += ['--permission-mode', 'acceptEdits', '--allowedTools', 'Read,Edit,Write,Glob,Grep']
        elif mode == 'web':
            cmd += ['--permission-mode', 'dontAsk', '--allowedTools', 'WebSearch,WebFetch']
        else:
            cmd += ['--permission-mode', 'dontAsk', '--allowedTools', 'Read,Glob,Grep']
        return cmd
    if provider == 'Codex':
        cmd = [exe, 'exec', '--sandbox', 'workspace-write' if mode == 'write' else 'read-only']
        if model:
            cmd += ['-m', model]
        if effort:
            cmd += ['-c', 'model_reasoning_effort=' + effort]
        return cmd + ['-']
    cmd = [exe, '--model', model or 'auto']
    if mode == 'write':
        cmd += ['--approval-mode', 'auto_edit']
    return cmd


def call(role, prompt, cwd, dept, *, avoid=(), timeout=900, path=None, runner=None, have=None, job_id=''):
    """One budgeted AI call. Returns dict(ok, output, provider, model, effort, reason, seconds)."""
    ok, why = store.budget_check(dept, 1, path)
    if not ok:
        raise BudgetStop(why)
    have = installed() if have is None else have
    provider, model, effort, reason = choose(role, avoid, path, have)
    import worker_guard
    worker_guard.guard_native_agent()
    cmd = build_cmd(provider, have[provider], model, effort, MODES.get(role, 'read'))
    core.record_usage(provider)
    store.record(dept, 'ai_call', 1, provider, job_id=job_id, note=f'{role} · {model or "varsayılan"} {effort}'.strip(), path=path)
    t0 = time.monotonic()
    run = runner or core.run
    r = run(cmd, Path(cwd), timeout=timeout, input_data=prompt, env=core.safe_env())
    good = r.returncode == 0 and bool((r.stdout or '').strip())
    store.route_result(role, provider, good, path)
    return {'ok': good, 'output': core.redact_log_output(r.stdout or '')[-9000:], 'provider': provider,
            'model': model or 'hesap varsayılanı', 'effort': effort, 'reason': reason,
            'seconds': round(time.monotonic() - t0, 1)}


class BudgetStop(RuntimeError):
    """Budget or pause stop — becomes an owner question, never a silent retry."""


def routing_table(path=None):
    have = installed()
    rows = []
    for role in ROLES:
        try:
            p, m, e, why = choose(role, path=path, have=have)
        except RuntimeError as exc:
            p, m, e, why = '-', '-', '-', str(exc)
        rows.append({'role': role, 'label': ROLE_LABELS[role], 'provider': p, 'model': m or 'hesap varsayılanı',
                     'effort': e, 'reason': why})
    return {'installed': sorted(have), 'rows': rows, 'stats': store.route_stats(path)}
