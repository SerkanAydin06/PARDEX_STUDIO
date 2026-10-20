"""PARDEX 2J: offline, least-privilege Python regression worker.

This is NOT an authenticated Claude/Codex/Gemini worker. Those CLIs remain
blocked by strict mode. A Docker daemon is a privileged trust dependency;
Docker flags alone cannot make a hostile host or kernel trustworthy.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import shutil
import tempfile

import core

IMAGE = re.compile(r'^[a-z0-9][a-z0-9._/-]*@sha256:[0-9a-f]{64}$')
CID = re.compile(r'^[0-9a-f]{12,64}$')
ALLOWED_TOP = {'app', 'tests', 'templates', 'scripts'}
ALLOWED_EXT = {'.py', '.json', '.md', '.yaml', '.yml', '.txt', '.cmd', '.ps1', '.gd', '.cs'}
SKIP = {'__pycache__', '.git', '.studio', 'node_modules', '.venv', 'venv', 'build', 'dist',
        '.pytest_cache', '.mypy_cache', '.cache'}
MAX_FILES = 1500
MAX_BYTES = 12_000_000


def _validate_image(image):
    if not isinstance(image, str) or not IMAGE.fullmatch(image):
        raise ValueError('Local image must use repository@sha256:<64 lowercase hex>, never a mutable tag')
    return image


def _host_environment(env=None):
    """Avoid passing AI/Cloud/GitHub credentials to the Docker client process."""
    env = os.environ if env is None else env
    if env.get('DOCKER_HOST') or env.get('DOCKER_CONTEXT') or env.get('DOCKER_TLS_VERIFY'):
        raise RuntimeError('Explicit/remote Docker daemon context not approved')
    keep = ('PATH', 'SystemRoot', 'SYSTEMROOT', 'WINDIR', 'PATHEXT', 'COMSPEC', 'TMP', 'TEMP')
    return {key: env[key] for key in keep if key in env}


def _stage_sources(source, destination):
    """No symlinks or hidden/private data. Only allowlisted source and tests."""
    source = Path(source).resolve(strict=True)
    if not source.is_dir() or not (source / 'tests').is_dir():
        raise ValueError('Source directory with tests/ required')
    if source.is_symlink():
        raise ValueError('Symlink source forbidden')
    # Reject symlinks anywhere, including directories a glob would otherwise skip.
    for item in source.rglob('*'):
        if item.is_symlink():
            raise ValueError('Symlink source forbidden')
    fingerprints = []
    total = 0
    count = 0
    test_count = 0
    for top in sorted(ALLOWED_TOP):
        folder = source / top
        if not folder.exists():
            continue
        if not folder.is_dir():
            raise ValueError('Invalid source subtree')
        for item in sorted(folder.rglob('*')):
            rel = item.relative_to(source)
            if not item.is_file() or any(x.startswith('.') or x in SKIP for x in rel.parts):
                continue
            if item.suffix.lower() not in ALLOWED_EXT:
                continue
            if top in ('app', 'tests') and item.suffix.lower() != '.py':
                continue
            if item.stat().st_size > 1_000_000:
                raise ValueError('Single source file exceeds 1MB')
            total += item.stat().st_size
            count += 1
            if total > MAX_BYTES or count > MAX_FILES:
                raise ValueError('Source exceeds offline worker limits')
            if top == 'tests' and item.name.startswith('test_') and item.suffix == '.py':
                test_count += 1
            target = destination / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(item, target, follow_symlinks=False)
            # File is read-only inside Docker; nobody must be able to traverse dirs.
            target.chmod(0o644)
            target.parent.chmod(0o755)
            fingerprints.append((rel.as_posix(), hashlib.sha256(target.read_bytes()).hexdigest()))
    if not test_count:
        raise ValueError('At least one test_*.py must be staged')
    return {'files': count, 'bytes': total, 'sha256': hashlib.sha256(
        repr(fingerprints).encode('utf-8')).hexdigest()}


def preflight(source, image, *, env=None):
    """Dry validation of configuration; no Docker execution, AI call or spend."""
    _validate_image(image)
    _host_environment(env)
    path = Path(source).expanduser().resolve(strict=True)
    if not path.is_dir() or not (path / 'tests').is_dir():
        raise ValueError('Tests directory required')
    return {'image_digest_pinned': True, 'source': str(path), 'no_ai_call': True,
            'owner_execution_approval_required': True, 'docker_execution_verified': False,
            'cloud_model_isolation_supported': False}


def run_python_regression(source, image, *, owner_confirms=False, timeout=120,
                          docker=None, runner=None, env=None):
    """Offline Docker regression with staging, read-only mount and forced cleanup.

    runner is injectable for deterministic unit tests; production defaults to
    core.run. Missing image, Docker, permission or failed staging all fail closed.
    Docker may be inaccessible or unsafe on a given host; this is not a VM.
    """
    if owner_confirms is not True:
        raise PermissionError('Owner must explicitly authorize this local Docker regression')
    image = _validate_image(image)
    if type(timeout) is not int or not 20 <= timeout <= 300:
        raise ValueError('Timeout must be between 20 and 300 seconds')
    host_env = _host_environment(env)
    binary = docker if docker is not None else core.which('docker')
    if not binary or not isinstance(binary, str):
        raise RuntimeError('Docker unavailable: no host-code fallback')
    runner = runner or core.run
    source = Path(source).expanduser().resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix='pardex-2j-') as scratch:
        scratch_path = Path(scratch)
        staging = scratch_path / 'source'
        staging.mkdir(mode=0o755)
        scratch_path.chmod(0o755)
        evidence = _stage_sources(source, staging)
        check = runner([binary, 'image', 'inspect', image], scratch_path,
                       timeout=20, env=host_env)
        if check.returncode:
            raise RuntimeError('Pinned image not found locally: no pull or host fallback')
        cidfile = scratch_path / 'container.cid'
        cmd = [binary, 'run', '--rm', '--pull=never', '--network', 'none',
               '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges',
               '--pids-limit=64', '--cpus=1', '--memory=512m', '--memory-swap=512m',
               '--user=65534:65534', '--tmpfs=/tmp:rw,nosuid,nodev,noexec,size=64m',
               '--cidfile', str(cidfile),
               '--mount', f'type=bind,src={staging},dst=/workspace,readonly',
               '--workdir=/workspace', '--env=HOME=/tmp',
               '--env=PYTHONDONTWRITEBYTECODE=1', '--env=PYTHONPATH=/workspace/app',
               image, 'python', '-B', '-m', 'unittest', 'discover',
               '-s', 'tests', '-p', 'test_*.py', '-q']
        try:
            result = runner(cmd, scratch_path, timeout=timeout, env=host_env)
        finally:
            # core.run returns 124 on timeout and kills the Docker CLI, not
            # necessarily the container; cleanup by *validated* container id.
            if cidfile.is_file():
                cid = cidfile.read_text(encoding='ascii', errors='ignore').strip()
                if CID.fullmatch(cid):
                    runner([binary, 'rm', '-f', cid], scratch_path, timeout=20, env=host_env)
        output = core.redact_log_output(getattr(result, 'stdout', '') or '')[-1200:]
        return {'passed': result.returncode == 0, 'exit_code': result.returncode,
                'output_tail': output, 'staged': evidence,
                'isolated_checks_requested': True, 'network_off': True,
                'readonly_project': True, 'image': image,
                'docker_engine_trust_assumed': True,
                'not_a_vm_security_certificate': True,
                'no_model_or_subscription_calls': True}
