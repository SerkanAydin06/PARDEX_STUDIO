"""One concrete, owner-started AI delivery: COPY -> CLI -> VERIFY -> REVIEW.

Never hands the live project directory to an AI CLI. The CLI itself is a NATIVE
HOST PROCESS, not an OS sandbox; an authorized local user must trust it.
No automatic publishing, application, spending or retry occurs here.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import tempfile

import change_review
import core
import worker_guard

MAX_SOURCE_FILES = 3000
MAX_SOURCE_BYTES = 100_000_000
SKIP_DIRS = frozenset({'.git', '.studio', '.godot', '.dart_tool', '.gradle', '.idea',
    '.vscode', 'node_modules', 'Library', 'Temp', 'Saved', 'build', 'dist',
    '__pycache__', '.venv', 'venv', 'secrets', '.next', '.cache'})
SKIP_FILES = frozenset({'AGENTS.md', 'CLAUDE.md', 'GEMINI.md', 'SECURITY.md'})
# Project files and local assets needed for Godot to validate the copy.
COPY_EXTENSIONS = frozenset(change_review.EXTENSIONS | {
    '.tscn', '.tres', '.godot', '.gdshader', '.cfg', '.ini', '.toml', '.xml',
    '.png', '.jpg', '.jpeg', '.webp', '.svg', '.ogg', '.wav', '.ttf', '.otf',
    '.import', '.lock', '.properties', '.gradle', '.kts', '.sh'})


def _private(name: str) -> bool:
    low = name.casefold()
    return (name.startswith('.') and name not in {'.gitignore'} or
            low in {s.casefold() for s in SKIP_FILES} or
            low in {s.casefold() for s in SKIP_DIRS} or
            low in {'.env', '.npmrc', '.pypirc', '.netrc'} or
            low.startswith('.env.') or
            ('token' in low) or ('password' in low) or
            ('credential' in low) or low.startswith('secret') or low.endswith(('.pem', '.key', '.p12', '.pfx')))


def _snapshot(project: Path, *, target: Path | None = None):
    """Copy allowlisted sources; reject symlinks; hash text files for exact change detection."""
    hashes = {}
    total = 0
    files = 0
    for folder, dirs, names in os.walk(project, followlinks=False):
        current = Path(folder)
        rel_dir = current.relative_to(project)
        for dirname in list(dirs):
            child = current / dirname
            if child.is_symlink():
                raise ValueError('Symlink directory refused: ' + str(child))
            if _private(dirname):
                dirs.remove(dirname)
        for name in names:
            src = current / name
            if src.is_symlink():
                raise ValueError('Symlink file refused: ' + str(src))
            if _private(name) or src.suffix.lower() not in COPY_EXTENSIONS:
                continue
            if not src.is_file():
                raise ValueError('Unexpected project file type')
            relative = (rel_dir / name).as_posix()
            size = src.stat().st_size
            files += 1
            total += size
            if files > MAX_SOURCE_FILES or total > MAX_SOURCE_BYTES:
                raise ValueError('Project too large for bounded delivery copy')
            blob = src.read_bytes()
            # Only text source changes are applied by change_review.
            if src.suffix.lower() in change_review.EXTENSIONS:
                hashes[relative] = hashlib.sha256(blob).hexdigest()
            if target is not None:
                out = target / relative
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(blob)
    return hashes


def preview(project, goal, relative_paths, *, provider='Codex'):
    """Free validation, without AI invocation, filesystem writes or quota use."""
    raw = Path(project).expanduser()
    if raw.is_symlink():
        raise ValueError('Symlink project root refused')
    source = raw.resolve(strict=True)
    if not source.is_dir() or core.project_type(source) == 'unknown':
        raise ValueError('Recognized game/app project required')
    if type(goal) is not str or not 8 <= len(goal.strip()) <= 1000:
        raise ValueError('Goal must be 8–1000 characters')
    if provider not in ('Codex', 'Claude', 'Gemini'):
        raise ValueError('Unknown CLI provider')
    if not isinstance(relative_paths, (list, tuple)) or not 1 <= len(relative_paths) <= change_review.MAX_FILES:
        raise ValueError('Choose 1–12 expected source files')
    files = tuple(change_review._name(p) for p in relative_paths)
    if len(set(files)) != len(files):
        raise ValueError('Duplicate proposed files')
    # These entries can be new; they must not traverse symlink parents.
    for rel in files:
        change_review._contained(source, rel)
    return {'project': str(source), 'engine': core.project_type(source),
            'goal': core.redact_log_output(goal.strip()), 'provider': provider,
            'expected_files': list(files), 'invokes_ai': False,
            'native_cli_not_sandboxed': True, 'separate_acceptance_required': True}


def deliver(project, goal, relative_paths, *, provider='Codex', owner_confirms=False,
            allow_native_cli=False, max_minutes=15, day_limit=8,
            home=None, runner=None, on_update=None):
    """Owner-triggered single CLI call on disposable *copy*, then stage changed files.

    `runner` is injectable ONLY for offline integration tests. Production calls
    core.run_ai_task; the model may use the network and local credentials because
    it remains a native process. If strict isolation is required it fails closed.
    """
    plan = preview(project, goal, relative_paths, provider=provider)
    if owner_confirms is not True or allow_native_cli is not True:
        raise PermissionError('Explicit approval of native CLI risks and exact files required')
    worker_guard.guard_native_agent()  # Must happen before any CLI or cost.
    if type(max_minutes) is not int or not 2 <= max_minutes <= 30:
        raise ValueError('Max minutes must be 2..30')
    if type(day_limit) is not int or not 1 <= day_limit <= 100:
        raise ValueError('Daily invocation cap must be 1..100')
    if runner is None and not core.which(provider.lower()):
        raise RuntimeError('AI CLI unavailable; no fake implementation or success')
    source = Path(plan['project'])
    store = Path(home).expanduser().resolve() if home is not None else (core.HOME / 'delivery_reviews').resolve()
    if store.is_relative_to(source) or source.is_relative_to(store):
        raise ValueError('Private review location must not overlap the project')
    store.mkdir(parents=True, exist_ok=True)
    if os.name != 'nt':
        store.chmod(0o700)
    callback = on_update or (lambda message: None)
    with tempfile.TemporaryDirectory(prefix='pardex-delivery-', dir=store) as temp:
        copy = Path(temp) / 'project'
        copy.mkdir(mode=0o700)
        before = _snapshot(source, target=copy)
        if core.project_type(copy) != plan['engine']:
            raise RuntimeError('Project marker missing in disposable copy')
        # Locally controlled instructions. Deliberately do not copy the project's
        # AI policy files or private .studio data into the work directory.
        marker = copy / 'AGENTS.md'
        marker.write_text('PARDEX one-task work copy. Change ONLY the explicitly named files. '
                          'No publishing, new dependencies, credentials or external commands. '\
                          'Never edit the original project.\n', encoding='utf-8')
        callback('Ayrı çalışma kopyası hazır; gerçek projeye AI erişim yolu verilmedi.')
        allowed = ', '.join(plan['expected_files'])
        task = (goal.strip() + '\nYalnızca şu dosyaları değiştir/oluştur: ' + allowed +
                '. Başka dosya ekleme veya değiştirme. Projeyi yayınlama.')
        if len(task) > 1200:
            raise ValueError('Goal plus paths exceed CLI task length')
        executor = runner or core.run_ai_task
        result = executor(copy, 'Yeni ozellik / Kod', task,
                          provider_pref=provider, quality='Dengeli',
                          day_limit=day_limit, max_minutes=max_minutes)
        if not isinstance(result, dict):
            raise RuntimeError('AI runner returned no structured result')
        if result.get('ai_ok') is not True:
            raise RuntimeError('AI command did not succeed; no proposal staged or applied')
        after = _snapshot(copy)
        changes = {name for name in set(before) | set(after) if before.get(name) != after.get(name)}
        # Missing source files and deletion are not supported by the approval tool.
        expected = set(plan['expected_files'])
        unexpected = sorted(changes - expected)
        if unexpected:
            raise RuntimeError('AI modified unapproved files: ' + ', '.join(unexpected[:8]))
        changed = sorted(changes & expected)
        if not changed:
            raise RuntimeError('AI produced no authorized source changes')
        for rel in changed:
            proposed = change_review._contained(copy, rel)
            if not proposed.is_file():
                raise RuntimeError('AI deleted a source file: ' + rel)
        # If the owner edits ANY source while AI is working, do not stage stale patches.
        # Native CLI is not OS-sandboxed; this detects, but cannot prevent, host edits.
        original_now = _snapshot(source)
        if original_now != before:
            drift = sorted(k for k in set(before) | set(original_now)
                           if original_now.get(k) != before.get(k))
            raise RuntimeError('Live project changed while AI worked: ' + ', '.join(drift[:5]))
        review = change_review.stage(source, copy, changed, home=store / 'reviews')
        callback('Kod önerisi oluşturuldu. Gerçek proje değiştirilmedi.')
        return {'state': 'awaiting-owner-review', 'review_id': review['review_id'],
                'digest': review['digest'], 'files': changed,
                'ai_ok': bool(result.get('ai_ok')), 'test_passed': bool(result.get('verified')),
                'provider': str(result.get('provider') or provider),
                'test_report': core.redact_log_output(str(result.get('test_report', '')))[:1400],
                'project_unchanged': True, 'native_cli_isolated': False,
                'requires_owner_approval_to_apply': True}
