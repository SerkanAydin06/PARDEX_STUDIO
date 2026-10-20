"""Offline, owner-approved staged code edits for PARDEX product projects.

Untrusted proposals are DATA, never run here. A proposal cannot directly edit
live source through this module. This is file-integrity control, NOT a sandbox.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import uuid

import core

MAX_FILES = 12
MAX_FILE_BYTES = 128_000
MAX_TOTAL_BYTES = 512_000
EXTENSIONS = frozenset({'.py', '.gd', '.cs', '.dart', '.js', '.jsx', '.ts', '.tsx',
    '.kt', '.html', '.css', '.scss', '.json', '.yml', '.yaml', '.md', '.txt', '.shader'})
SKIP_PARTS = frozenset({'.git', '.studio', '.github', '.env', '.vscode', '.idea',
    'node_modules', 'Library', 'Temp', 'Saved', 'build', 'dist', 'secrets', '__pycache__'})
SKIP_BASENAMES = frozenset({'AGENTS.md', 'CLAUDE.md', 'GEMINI.md', 'SECURITY.md'})
REVIEW_ID = re.compile(r'^REV-[0-9a-f]{20}$')
HEX64 = re.compile(r'^[0-9a-f]{64}$')
WINDOWS_RESERVED = re.compile(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', re.I)


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _paths(*, home=None):
    root = Path(home) if home is not None else core.HOME / 'change_reviews'
    root = root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    if os.name != 'nt':
        root.chmod(0o700)
    return root


def _name(raw):
    if not isinstance(raw, str) or len(raw) > 180 or not raw or '\\' in raw or '\x00' in raw:
        raise ValueError('Invalid relative file path')
    if raw.startswith('/') or raw.endswith('/') or '//' in raw:
        raise ValueError('Only relative file names are allowed')
    parts = PurePosixPath(raw).parts
    if not parts or any(p in ('.', '..') or p.startswith('.') or p.lower() in {s.lower() for s in SKIP_PARTS} or
                        p.endswith('.') or WINDOWS_RESERVED.match(p) for p in parts):
        raise ValueError('Private, reserved or traversal path rejected')
    if any(not re.fullmatch(r'[\w .@+\-]+', p, re.UNICODE) for p in parts):
        raise ValueError('Unexpected filename characters')
    if parts[-1].lower() in {s.lower() for s in SKIP_BASENAMES} or PurePosixPath(raw).suffix.lower() not in EXTENSIONS:
        raise ValueError('AI policy, credentials or unsupported file type cannot be staged')
    return raw


def _contained(root: Path, relative: str) -> Path:
    """Reject symlink ancestors and destination symlinks before any file access."""
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Untrusted project folder')
    current = root
    for part in PurePosixPath(relative).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('Symlink source/destination refused')
    if not current.resolve().is_relative_to(root.resolve()):
        raise ValueError('Out-of-tree file')
    return current


def _manifest_path(review_id, *, home=None):
    if not REVIEW_ID.fullmatch(review_id):
        raise ValueError('Invalid review identifier')
    folder = _paths(home=home) / review_id
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError('Review not found')
    return folder, folder / 'review.json'


def _save(folder, record):
    tmp = folder / ('manifest-' + uuid.uuid4().hex + '.tmp')
    try:
        with tmp.open('x', encoding='utf-8') as stream:
            os.chmod(tmp, 0o600)
            json.dump(record, stream, sort_keys=True, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        tmp.replace(folder / 'review.json')
    finally:
        tmp.unlink(missing_ok=True)


def _load(review_id, *, home=None):
    folder, file = _manifest_path(review_id, home=home)
    record = json.loads(file.read_text(encoding='utf-8'))
    if record.get('id') != review_id or record.get('schema') != 1:
        raise ValueError('Review manifest invalid')
    project = Path(record['project']).resolve(strict=True)
    if project.is_symlink() or not project.is_dir() or core.project_type(project) == 'unknown':
        raise ValueError('Reviewed project is missing or invalid')
    if folder.resolve().is_relative_to(project):
        raise ValueError('Review directory cannot live inside project')
    entries = record['files']
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_FILES:
        raise ValueError('Manifest file limit exceeded')
    names = [_name(item['path']) for item in entries]
    if len(set(names)) != len(names):
        raise ValueError('Duplicate paths in manifest')
    if any(not HEX64.fullmatch(item['after']) or
           (item['before'] is not None and not HEX64.fullmatch(item['before'])) for item in entries):
        raise ValueError('Malformed digest')
    if _fingerprint(record['project'], entries) != record['digest']:
        raise ValueError('Review checksum invalid')
    return folder, record, project


def _fingerprint(project, entries):
    data = [{'path': e['path'], 'before': e['before'], 'after': e['after']}
            for e in entries]
    return _hash(json.dumps({'project': project, 'files': data},
                            ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode())


def stage(project, proposal, relative_paths, *, home=None):
    """Create private immutable snapshots; no writes to the product project."""
    project = Path(project).expanduser().resolve(strict=True)
    proposal = Path(proposal).expanduser().resolve(strict=True)
    if not project.is_dir() or core.project_type(project) == 'unknown':
        raise ValueError('Recognized Godot/Unity/Unreal/Flutter/Android/Web project required')
    if not proposal.is_dir() or proposal == project or proposal.is_relative_to(project) or project.is_relative_to(proposal):
        raise ValueError('AI proposal must be in a separate directory')
    if not isinstance(relative_paths, (list, tuple)) or not 1 <= len(relative_paths) <= MAX_FILES:
        raise ValueError('Select 1–12 specific source files')
    names = [_name(p) for p in relative_paths]
    if len(set(names)) != len(names):
        raise ValueError('Duplicate proposal paths')
    root = _paths(home=home)
    if (root.is_relative_to(project) or project.is_relative_to(root)
            or root.is_relative_to(proposal) or proposal.is_relative_to(root)):
        raise ValueError('Private review store must be separate from project and AI proposal')
    ident = 'REV-' + uuid.uuid4().hex[:20]
    folder = root / ident
    folder.mkdir(mode=0o700)
    entries = []
    total = 0
    try:
        (folder / 'before').mkdir()
        (folder / 'after').mkdir()
        for name in names:
            old = _contained(project, name)
            new = _contained(proposal, name)
            if not new.is_file() or (old.exists() and not old.is_file()):
                raise ValueError('Proposed path not a regular file')
            if new.stat().st_size > MAX_FILE_BYTES or (old.exists() and old.stat().st_size > MAX_FILE_BYTES):
                raise ValueError('One source file exceeds review limit')
            data = new.read_bytes()
            previous = old.read_bytes() if old.exists() else None
            total += len(data) + (len(previous) if previous is not None else 0)
            if total > MAX_TOTAL_BYTES:
                raise ValueError('Total source exceeds review limit')
            if b'\x00' in data or (previous is not None and b'\x00' in previous):
                raise ValueError('Only text source changes supported')
            if previous == data:
                raise ValueError('Unchanged source must not be staged')
            target = folder / 'after' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            if previous is not None:
                backup = folder / 'before' / name
                backup.parent.mkdir(parents=True, exist_ok=True)
                backup.write_bytes(previous)
            entries.append({'path': name, 'before': _hash(previous) if previous is not None else None,
                            'after': _hash(data), 'bytes': len(data)})
        record = {'schema': 1, 'id': ident, 'project': str(project), 'state': 'staged',
                  'files': entries, 'requires_owner_approval': True,
                  'no_ai_run': True, 'no_auto_deploy': True}
        record['digest'] = _fingerprint(record['project'], entries)
        _save(folder, record)
        return summary(ident, home=home)
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)
        raise


def summary(review_id, *, home=None):
    _, item, _ = _load(review_id, home=home)
    return {'review_id': item['id'], 'project': item['project'], 'state': item['state'],
            'digest': item['digest'], 'changes': [dict(e) for e in item['files']],
            'owner_approval_required': True, 'AI_execution': False}


def diff(review_id, *, home=None, max_chars=9000):
    folder, record, _ = _load(review_id, home=home)
    if type(max_chars) is not int or not 100 <= max_chars <= 20000:
        raise ValueError('Invalid diff length')
    chunks = []
    for e in record['files']:
        before = (folder / 'before' / e['path']).read_bytes() if e['before'] else b''
        after = (folder / 'after' / e['path']).read_bytes()
        if _hash(after) != e['after'] or (e['before'] and _hash(before) != e['before']):
            raise ValueError('Snapshot edited after staging')
        a = before.decode('utf-8', 'replace').splitlines()
        b = after.decode('utf-8', 'replace').splitlines()
        chunks.extend(difflib.unified_diff(a, b, fromfile='before/' + e['path'],
                                          tofile='after/' + e['path'], lineterm=''))
    return core.redact_log_output('\n'.join(chunks))[:max_chars]


def _lock(folder):
    handle = folder / 'busy.lock'
    with handle.open('x', encoding='utf-8') as out:
        out.write('Exclusive review operation; stale lock requires manual inspection.\n')
    return handle


def _check_snapshots(folder, record, project):
    for e in record['files']:
        old, new = _contained(project, e['path']), folder / 'after' / e['path']
        if not new.is_file() or _hash(new.read_bytes()) != e['after']:
            raise ValueError('Staged proposal changed')
        if old.exists():
            if e['before'] is None or not old.is_file() or _hash(old.read_bytes()) != e['before']:
                raise ValueError('Project changed after review: create a new proposal')
        elif e['before'] is not None:
            raise ValueError('Original project source disappeared')
        if e['before'] is not None:
            backup = folder / 'before' / e['path']
            if not backup.is_file() or _hash(backup.read_bytes()) != e['before']:
                raise ValueError('Original snapshot invalid')


def _write_atomic(target, data):
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix='.pardex-review-', dir=target.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp_name, target)
    finally:
        Path(tmp_name).unlink(missing_ok=True)


def _restore(folder, record, project):
    """Precheck *all* touched files before reverting any, preserving user edits."""
    restore = []
    for e in reversed(record['files']):
        live = _contained(project, e['path'])
        current = _hash(live.read_bytes()) if live.exists() and live.is_file() else None
        if current not in (e['before'], e['after']):
            raise RuntimeError('File modified outside review; manual recovery required: ' + e['path'])
        if current == e['before']:
            continue
        if e['before'] is None:
            restore.append((live, None))
        else:
            original = (folder / 'before' / e['path']).read_bytes()
            if _hash(original) != e['before']:
                raise RuntimeError('Backup checksum mismatch')
            restore.append((live, original))
    for live, original in restore:
        if original is None:
            live.unlink()
        else:
            _write_atomic(live, original)


def apply(review_id, digest, *, owner_confirms=False, home=None):
    if owner_confirms is not True:
        raise PermissionError('Human approval is mandatory')
    folder, record, project = _load(review_id, home=home)
    if not isinstance(digest, str) or digest != record['digest']:
        raise PermissionError('Owner must approve exact review fingerprint')
    lock = _lock(folder)
    try:
        if record['state'] != 'staged':
            raise RuntimeError('Review already processed; no automatic retry')
        _check_snapshots(folder, record, project)
        record['state'] = 'applying'
        _save(folder, record)
        try:
            for e in record['files']:
                target = _contained(project, e['path'])
                live = _hash(target.read_bytes()) if target.is_file() else None
                if live != e['before']:
                    raise RuntimeError('Concurrent project edit detected')
                proposal = (folder / 'after' / e['path']).read_bytes()
                if _hash(proposal) != e['after']:
                    raise RuntimeError('Proposed snapshot changed')
                _write_atomic(target, proposal)
        except Exception:
            record['state'] = 'attention'
            _save(folder, record)
            _restore(folder, record, project)
            record['state'] = 'rolled_back'
            _save(folder, record)
            raise
        record['state'] = 'applied'
        _save(folder, record)
        return summary(review_id, home=home)
    finally:
        lock.unlink(missing_ok=True)


def rollback(review_id, digest, *, owner_confirms=False, home=None):
    if owner_confirms is not True:
        raise PermissionError('Owner rollback approval required')
    folder, record, project = _load(review_id, home=home)
    if digest != record['digest']:
        raise PermissionError('Review fingerprint does not match')
    lock = _lock(folder)
    try:
        if record['state'] not in ('applied', 'attention', 'applying'):
            raise RuntimeError('No applied change to roll back')
        _restore(folder, record, project)
        record['state'] = 'rolled_back'
        _save(folder, record)
        return summary(review_id, home=home)
    finally:
        lock.unlink(missing_ok=True)
