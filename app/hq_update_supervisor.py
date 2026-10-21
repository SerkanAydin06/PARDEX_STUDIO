"""Standalone update supervisor, copied outside the checkout before the panel exits."""
import json
from contextlib import closing
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
import webbrowser


def run(root, *args):
    r = subprocess.run(['git', '-C', str(root), *args], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', timeout=90)
    if r.returncode:
        raise RuntimeError('Git işlemi başarısız: ' + ' '.join(args[:2]))
    return r.stdout.strip()


def clean(root, sha):
    if run(root, 'rev-parse', 'HEAD') != sha or run(root, 'status', '--porcelain', '--untracked-files=all'):
        raise RuntimeError('Yerel dosyalar/sürüm değişti; güncelleme veya geri alma durduruldu.')


def status(plan, phase, message):
    dest = Path(plan['job']).parent / 'status.json'
    tmp = dest.with_suffix('.tmp')
    tmp.write_text(json.dumps({'phase': phase, 'message': message, 'backup': plan['job']}, ensure_ascii=False), encoding='utf-8')
    tmp.replace(dest)


def parent_alive(pid):
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        k = ctypes.WinDLL('kernel32', use_last_error=True)
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.OpenProcess.restype = wintypes.HANDLE
        k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = k.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE only; never terminate the parent.
        if not handle:
            if ctypes.get_last_error() == 87:
                return False
            raise RuntimeError('Üst süreç durumu okunamadı.')
        try:
            result = k.WaitForSingleObject(handle, 0)
            if result not in (0, 0x102):
                raise RuntimeError('Üst süreç bekleme sonucu okunamadı.')
            return result == 0x102
        finally:
            k.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def backup_databases(plan):
    result = []
    for i, path in enumerate(plan['databases']):
        source = Path(path)
        if source.is_symlink():
            raise RuntimeError('Veritabanı bağlantı olamaz.')
        target = Path(plan['job']) / f'database-{i}.sqlite3'
        existed = source.is_file()
        if existed:
            with closing(sqlite3.connect(str(source))) as db, closing(sqlite3.connect(str(target))) as backup:
                db.backup(backup)
        result.append({'source': str(source), 'backup': str(target), 'existed': existed})
    (Path(plan['job']) / 'databases.json').write_text(json.dumps(result), encoding='utf-8')
    return result


def restore_databases(backups):
    for item in backups:
        dest = Path(item['source'])
        for suffix in ('-wal', '-shm'):
            Path(str(dest) + suffix).unlink(missing_ok=True)
        if item['existed']:
            tmp = dest.with_name(dest.name + '.update-restore')
            shutil.copyfile(item['backup'], tmp)
            tmp.replace(dest)
        else:
            dest.unlink(missing_ok=True)


def start(plan, health=True):
    env = os.environ.copy()
    env['PYTHONPYCACHEPREFIX'] = str(Path(plan['job']) / ('pycache-new' if health else 'pycache-old'))
    env.pop('PARDEX_UPDATE_HEALTH', None)
    env.pop('PARDEX_UPDATE_NONCE', None)
    if health:
        env['PARDEX_UPDATE_HEALTH'] = str(Path(plan['job']) / 'healthy.json')
        env['PARDEX_UPDATE_NONCE'] = plan['nonce']
    opts = {'creationflags': subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}
    with (Path(plan['job']) / 'panel.log').open('ab') as log:
        return subprocess.Popen([plan['python'], '-B', str(Path(plan['root']) / 'app/hq_server.py'),
            '--port', str(plan['port']), '--no-browser'], cwd=plan['root'], env=env,
            stdin=subprocess.DEVNULL, stdout=log, stderr=log, **opts)


def healthy(plan, child, timeout=45):
    receipt = Path(plan['job']) / 'healthy.json'
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if child.poll() is not None:
            return False
        try:
            data = json.loads(receipt.read_text(encoding='utf-8'))
            if data == {'nonce': plan['nonce'], 'pid': child.pid}:
                with urllib.request.urlopen(f"http://127.0.0.1:{plan['port']}/", timeout=2) as r:
                    if r.status == 200:
                        time.sleep(2)
                        return child.poll() is None
        except (OSError, ValueError):
            pass
        time.sleep(.2)
    return False


def install(plan, starter=start, checker=healthy):
    root = Path(plan['root'])
    child, backups, merged = None, [], False
    try:
        clean(root, plan['old'])
        backups = backup_databases(plan)
        status(plan, 'installing', 'Yedek alındı; doğrulanmış sürüm kuruluyor.')
        run(root, 'merge', '--ff-only', plan['target'])
        merged = True
        clean(root, plan['target'])
        # A fresh external cache prefix prevents loading stale bytecode after replacement.
        child = starter(plan)
        if not checker(plan, child):
            raise RuntimeError('Yeni sürüm açılış kontrolünden geçemedi.')
        status(plan, 'success', 'Güncellendi; Pardex yeniden açıldı.')
        return True
    except Exception as exc:
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=10)
        if merged:
            # Only reset the exact clean version installed by this helper; never discard edits.
            clean(root, plan['target'])
            run(root, 'reset', '--hard', plan['old'])
            restore_databases(backups)
        status(plan, 'rolled_back' if merged else 'error', str(exc)[:300] + (' Eski sürüm geri yüklendi.' if merged else ''))
        starter(plan, health=False)
        return False


def main():
    plan = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    job = Path(plan['job'])
    try:
        (job.parent / 'update.lock').write_text(str(os.getpid()))
        (job / 'ready').write_text('ready', encoding='utf-8')
        deadline = time.monotonic() + 60
        while parent_alive(plan['parent']):
            if time.monotonic() >= deadline:
                status(plan, 'error', 'Pardex kapanmadı; güncelleme yapılmadı.')
                return
            time.sleep(.2)
        install(plan)
        webbrowser.open(f"http://127.0.0.1:{plan['port']}/")
    except Exception as exc:
        status(plan, 'error', 'Güncelleme/geri alma tamamlanamadı: ' + type(exc).__name__ + '. Yedek korundu.')
        raise
    finally:
        (job.parent / 'update.lock').unlink(missing_ok=True)


if __name__ == '__main__':
    main()
