"""Owner-triggered GitHub release workflow. No AI calls and no force-push/reset of user edits."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

REPO = 'SerkanAydin06/PARDEX_STUDIO'
URL = 'https://github.com/' + REPO + '.git'
REQUIRED = {'unit', 'hygiene', 'docs-and-safety', 'windows-update'}


def command(args, cwd, payload=None, timeout=60):
    env = os.environ.copy()
    env.update(GIT_TERMINAL_PROMPT='0', GH_PROMPT_DISABLED='1')
    r = subprocess.run(args, cwd=cwd, input=payload, text=True, encoding='utf-8',
                       errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       timeout=timeout, env=env, check=False)
    if r.returncode:
        import core
        raise RuntimeError(core.redact_log_output(r.stderr or r.stdout)[-1200:])
    return r.stdout.strip()


def git(root, *args):
    return command(['git', '-C', str(root), *args], root)


def api(root, endpoint, method='GET', data=None):
    args = ['gh', 'api', '--hostname', 'github.com', '-X', method, 'repos/' + REPO + '/' + endpoint]
    if data is not None:
        args += ['--input', '-']
    return json.loads(command(args, root, json.dumps(data) if data is not None else None) or '{}')


def clean_checkout(root):
    root = Path(root).resolve()
    if Path(git(root, 'rev-parse', '--show-toplevel')).resolve() != root:
        raise ValueError('Pardex klasörü bağımsız Git deposu olmalı. ZIP kurulumuna otomatik yazılmaz.')
    if git(root, 'status', '--porcelain', '--untracked-files=all'):
        raise ValueError('Pardex klasöründe kaydedilmemiş/izlenmeyen dosyalar var; üzerlerine yazılmadı.')
    if git(root, 'branch', '--show-current') != 'main':
        raise ValueError('Güncelleme için Pardex main dalında olmalı.')
    return git(root, 'rev-parse', 'HEAD')


def checked(root, sha):
    if not re.fullmatch('[0-9a-f]{40}', sha):
        raise ValueError('Geçersiz Git sürümü')
    result = api(root, f'commits/{sha}/check-runs?per_page=100')
    checks = result.get('check_runs', [])
    if result.get('total_count', len(checks)) > 100:
        raise ValueError('Kontrol listesi çok uzun; otomatik karar verilmedi.')
    trusted = [c for c in checks if c.get('app', {}).get('slug') == 'github-actions']
    names = {c.get('name') for c in trusted}
    if any(c.get('status') == 'completed' and c.get('conclusion') not in ('success',) for c in trusted):
        raise ValueError('GitHub kontrollerinden en az biri başarısız/atlanmış; sürüm kurulmadı.')
    return REQUIRED <= names and all(c.get('status') == 'completed' and c.get('conclusion') == 'success' for c in trusted)


def wait_checks(root, sha, progress, timeout=900):
    deadline = time.monotonic() + timeout
    progress('GitHub testleri bekleniyor…')
    while time.monotonic() < deadline:
        if checked(root, sha):
            return
        time.sleep(5)
    raise ValueError('GitHub testleri zamanında tamamlanmadı. PR korunuyor; kurulum yapılmadı.')


def publish(root, candidate, progress):
    import core
    import evolution
    from hq_maintenance import plain_chain
    root, candidate = Path(root).resolve(), Path(candidate).resolve()
    old = clean_checkout(root)
    manifest = evolution.info(candidate)
    if manifest.get('source_revision') != old:
        raise ValueError('Adayın kaynak sürümü güncel değil; yeni kopyada test ve inceleme gerekli.')
    if not evolution.ready_to_export(candidate):
        raise ValueError('Çekirdek adayı test ve iki bağımsız incelemeden geçmemiş veya değişmiş.')
    remote = api(root, 'git/ref/heads/main')['object']['sha']
    if old != remote:
        raise ValueError('Önce GitHub sürümünü güncelle; aday eski sürüm üzerine kurulamaz.')
    entries = []
    for item in evolution.changed_files(candidate):
        rel = item['path']
        if not rel.startswith('app/') or not rel.endswith('.py') or '..' in Path(rel).parts:
            raise ValueError('Yalnızca denetlenmiş app Python değişiklikleri yayınlanabilir.')
        f = candidate / rel
        plain_chain(f)
        raw = f.read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest['tests']['hashes'].get(rel):
            raise ValueError('Aday testten sonra değişmiş.')
        content = raw.decode('utf-8')
        if len(raw) > 1_000_000 or core.redact_log_output(content) != content:
            raise ValueError('Aday dosyası boyut/gizli veri kontrolünden geçemedi.')
        entries.append({'path': rel, 'mode': '100644', 'type': 'blob', 'content': content})
    if not entries:
        raise ValueError('Yayınlanacak değişiklik yok.')
    tree = api(root, 'git/commits/' + old)['tree']['sha']
    tree = api(root, 'git/trees', 'POST', {'base_tree': tree, 'tree': entries})['sha']
    sha = api(root, 'git/commits', 'POST', {'message': 'Pardex: tested core maintenance', 'tree': tree, 'parents': [old]})['sha']
    branch = 'pardex/maintenance-' + uuid.uuid4().hex[:12]
    api(root, 'git/refs', 'POST', {'ref': 'refs/heads/' + branch, 'sha': sha})
    pr = api(root, 'pulls', 'POST', {'title': 'Pardex: tested core maintenance', 'head': branch, 'base': 'main',
        'body': 'Owner-triggered core update. Isolated regression and two independent reviews passed for the uploaded file hashes. GitHub checks must pass before merge. Local install uses a backup and startup health check. No game files or local logs are included.'})
    progress('PR oluşturuldu: ' + pr['html_url'])
    wait_checks(root, sha, progress)
    if api(root, 'git/ref/heads/main')['object']['sha'] != old:
        raise ValueError('main değişti. PR korundu; yeniden tabanlama ve test gerekli.')
    result = api(root, f"pulls/{pr['number']}/merge", 'PUT', {'sha': sha, 'merge_method': 'squash'})
    if not result.get('merged'):
        raise ValueError('GitHub birleştirmeyi kabul etmedi; PR korundu.')
    progress('GitHub birleştirildi: ' + pr['html_url'])
    return result['sha']


def prepare(root, state, progress, candidate=None):
    root, state = Path(root).resolve(), Path(state).resolve()
    if not shutil.which('git') or not shutil.which('gh'):
        raise ValueError('Git ve GitHub CLI gerekli. Panelde GitHub CLI kur düğmesini kullanın.')
    old = clean_checkout(root)
    command(['gh', 'auth', 'status', '--hostname', 'github.com'], root)
    target = publish(root, candidate, progress) if candidate else api(root, 'git/ref/heads/main')['object']['sha']
    if target == old:
        return None
    wait_checks(root, target, progress)
    progress('Doğrulanmış sürüm indiriliyor…')
    git(root, 'fetch', '--no-tags', URL, 'main')
    if git(root, 'rev-parse', 'FETCH_HEAD') != target:
        raise ValueError('GitHub sürümü indirme sırasında değişti; tekrar kontrol gerekli.')
    git(root, 'merge-base', '--is-ancestor', old, target)
    if clean_checkout(root) != old:
        raise ValueError('Yerel sürüm hazırlık sırasında değişti.')
    state.mkdir(parents=True, exist_ok=True)
    job = state / ('release-' + uuid.uuid4().hex)
    job.mkdir()
    git(root, 'bundle', 'create', str(job / 'previous.bundle'), 'HEAD')
    return {'root': str(root), 'old': old, 'target': target, 'job': str(job), 'python': sys.executable}


def launch(plan, port, db_paths):
    """Copy supervisor out of the files it will update; wait for its handshake before exiting."""
    from hq_maintenance import plain_chain
    job = Path(plan['job'])
    plain_chain(job)
    script = job / 'supervisor.py'
    shutil.copyfile(Path(__file__).with_name('hq_update_supervisor.py'), script)
    plan = dict(plan, port=port, parent=os.getpid(), nonce=uuid.uuid4().hex,
                databases=[str(Path(p).resolve()) for p in db_paths])
    config = job / 'plan.json'
    config.write_text(json.dumps(plan), encoding='utf-8')
    opts = {'creationflags': subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}
    with (job / 'supervisor.log').open('ab') as log:
        proc = subprocess.Popen([sys.executable, '-B', str(script), str(config)], cwd=job,
            stdin=subprocess.DEVNULL, stdout=log, stderr=log, **opts)
    for _ in range(100):
        if (job / 'ready').is_file():
            return
        if proc.poll() is not None:
            raise RuntimeError('Güncelleme yardımcısı başlatılamadı; Pardex açık bırakıldı.')
        time.sleep(.1)
    proc.terminate()
    raise RuntimeError('Güncelleme yardımcısı yanıt vermedi; Pardex açık bırakıldı.')


class Controller:
    def __init__(self, root, home):
        import threading
        self.root = Path(root).resolve()
        self.state = Path(home) / 'updates' / hashlib.sha256(str(self.root).encode()).hexdigest()[:12]
        self.cancel = threading.Event()
        self.mutex = threading.Lock()
        self.phase = ''
        self.pr_url = ''

    def busy(self):
        lock = self.state / 'update.lock'
        if not lock.exists():
            return False
        try:
            from hq_update_supervisor import parent_alive
            if parent_alive(int(lock.read_text())):
                return True
            lock.unlink()
        except (OSError, ValueError):
            return True  # Unknown lock ownership: fail closed.
        return False

    def progress(self, message, phase='preparing'):
        from hq_maintenance import plain_chain
        plain_chain(self.state)
        self.phase = phase
        found = re.search(r'https://github\.com/SerkanAydin06/PARDEX_STUDIO/pull/[0-9]+', message)
        if found:
            self.pr_url = found.group(0)
        if self.pr_url and self.pr_url not in message:
            message += '\nPR: ' + self.pr_url
        target = self.state / 'status.json'
        if target.exists():
            plain_chain(target)
        tmp = self.state / ('status-' + uuid.uuid4().hex + '.tmp')
        tmp.write_text(json.dumps({'phase': phase, 'message': message}, ensure_ascii=False), encoding='utf-8')
        tmp.replace(target)

    def view(self):
        try:
            result = json.loads((self.state / 'status.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            result = {'phase': 'idle', 'message': 'GitHub sürümünü kontrol edip güncelleyebilirsiniz.'}
        return dict(result, running=self.busy(), git=bool(shutil.which('git')), gh=bool(shutil.which('gh')))

    def begin(self, busy, shutdown, port, databases, candidate=None):
        import threading
        from hq_maintenance import plain_chain
        with self.mutex:
            if self.busy():
                raise ValueError('Bir güncelleme zaten sürüyor.')
            if shutdown is None:
                raise ValueError('Yeniden başlatma bu çalışma ortamında bağlı değil.')
            self.state.mkdir(parents=True, exist_ok=True)
            plain_chain(self.state)
            with (self.state / 'update.lock').open('x') as f:
                f.write(str(os.getpid()))
            self.cancel.clear()
            self.pr_url = ''
            self.progress('Çalışan işler bitince güncelleme başlayacak.', 'waiting')

        def worker():
            handed_off = False
            try:
                deadline = time.monotonic() + 3600
                while busy():
                    if self.cancel.wait(.5) or time.monotonic() >= deadline:
                        raise ValueError('Güncelleme beklemesi iptal edildi veya süresi doldu; üretim korunuyor.')
                if self.cancel.is_set():
                    raise ValueError('Güncelleme iptal edildi.')
                self.progress('GitHub bağlantısı ve sürüm kontrol ediliyor…')
                plan = prepare(self.root, self.state, self.progress, candidate)
                if plan is None:
                    self.progress('Pardex zaten güncel.', 'success')
                    return
                self.progress('Yedek hazır. Pardex kapanıp yeniden açılacak.', 'restarting')
                launch(plan, port, databases)
                handed_off = True
                shutdown()
            except Exception as exc:
                import core
                self.progress(core.redact_log_output(str(exc))[:1200], 'error')
            finally:
                if not handed_off:
                    (self.state / 'update.lock').unlink(missing_ok=True)
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        return thread

    def cancel_wait(self):
        if self.phase != 'waiting':
            raise ValueError('Yalnızca işleri bekleyen güncelleme iptal edilebilir.')
        self.cancel.set()
