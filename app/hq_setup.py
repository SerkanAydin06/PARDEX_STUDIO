"""Phase 6 — Kurulum: one screen that shows what is installed and logged in, and fixes it.

Zero token: status checks never send a prompt to any AI. Installs and logins happen only when the
owner presses a button. Installs run fixed, allow-listed commands (no user text reaches a shell).
Logins open the provider's own sign-in in a visible window; PARDEX never sees or stores credentials.
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import core

NODE_MIN = 20
CLIS = {
    'claude': {'name': 'Claude Code', 'plan': 'Claude Pro', 'npm': '@anthropic-ai/claude-code',
               'login': ['claude', 'auth', 'login'], 'role': 'Plan sohbeti, iş paylaşımı, zor mimari'},
    'codex': {'name': 'Codex CLI', 'plan': 'ChatGPT Pro', 'npm': '@openai/codex',
              'login': ['codex', 'login'], 'role': 'Kod yazımı ve düzeltme'},
    'gemini': {'name': 'Gemini CLI', 'plan': 'Google AI Pro', 'npm': '@google/gemini-cli',
               'login': ['gemini'], 'role': 'Bağımsız kod denetimi ve Ar-Ge'},
}
BASE_TOOLS = {
    'git': {'name': 'Git', 'winget': 'Git.Git', 'url': 'https://git-scm.com/downloads/win',
            'why': 'Her ürün kendi Git deposunda tutulur'},
    'node': {'name': 'Node.js', 'winget': 'OpenJS.NodeJS.LTS', 'url': 'https://nodejs.org/en/download',
             'why': 'Üç AI programı Node.js ile kurulur ve çalışır'},
}
JOBS = {}
_LOCK = threading.Lock()
_CACHE = {'at': 0.0, 'data': None}


def _run(argv, timeout=20):
    try:
        r = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                           encoding='utf-8', errors='replace', timeout=timeout, env=core.safe_env(), check=False)
        return r.returncode, (r.stdout or '').strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, type(exc).__name__


def _version(text):
    m = re.search(r'(\d+)\.(\d+)(?:\.(\d+))?', text or '')
    return m.group(0) if m else ''


# ---------------- login checks (0 token) ----------------
def _claude_login(exe):
    code, out = _run([exe, 'auth', 'status', '--json'], 20)
    try:
        data = json.loads(out[out.index('{'):]) if '{' in out else {}
    except ValueError:
        data = {}
    if data.get('loggedIn') is True:
        return 'yes', 'Giriş yapılmış' + (f" ({data['subscriptionType']})" if data.get('subscriptionType') else '')
    if data.get('loggedIn') is False:
        return 'no', 'Giriş yapılmamış'
    return 'unknown', 'Durum okunamadı; gerekirse "Giriş yap"a bas'


def _codex_login(exe):
    code, out = _run([exe, 'login', 'status'], 20)
    low = out.casefold()
    if code == 0 and not re.search(r'not logged in|authenticated: no|not authenticated', low):
        return 'yes', 'Giriş yapılmış'
    if re.search(r'not logged in|authenticated: no|not authenticated', low) or code == 1:
        return 'no', 'Giriş yapılmamış'
    return 'unknown', 'Durum okunamadı; gerekirse "Giriş yap"a bas'


def _verified():
    return core.load_json(core.HOME / 'hq' / 'setup_verified.json', {})


def _gemini_login(_exe, home=None):
    """Gemini CLI has no status command. Without a chosen auth method it cannot run at all (no), a cached
    Google login file or a successful "Test et" means yes; a chosen method with credentials in the system
    keychain cannot be seen from here (unknown). Never a false 'yes'."""
    v = _verified().get('gemini')
    if v and v.get('ok'):
        return 'yes', 'Giriş doğrulandı (Test et)'
    base = Path(home or Path.home()) / '.gemini'
    if (base / 'oauth_creds.json').is_file():
        return 'yes', 'Google hesabıyla giriş yapılmış'
    try:
        conf = json.loads((base / 'settings.json').read_text(encoding='utf-8'))
        selected = ((conf.get('security') or {}).get('auth') or {}).get('selectedType') or conf.get('selectedAuthType')
    except (OSError, ValueError, AttributeError):
        selected = None
    if not selected:
        return 'no', 'Giriş yapılmamış'
    return 'unknown', 'Giriş yapılmış görünüyor ama doğrulanamadı; "Test et"e bas'


LOGIN_CHECK = {'claude': _claude_login, 'codex': _codex_login, 'gemini': _gemini_login}


# ---------------- status ----------------
def status(force=False):
    if not force and _CACHE['data'] and time.monotonic() - _CACHE['at'] < 15:
        return _CACHE['data']
    items = [{'key': 'python', 'name': 'Python', 'ok': True, 'version': '.'.join(map(str, sys.version_info[:3])),
              'detail': 'Panel çalıştığına göre kurulu', 'why': 'Şirket paneli Python ile çalışır', 'actions': []}]
    git = core.which('git')
    gv = _version(_run([git, '--version'])[1]) if git else ''
    items.append({'key': 'git', 'name': 'Git', 'ok': bool(git), 'version': gv,
                  'detail': 'Kurulu' if git else 'Kurulu değil', 'why': BASE_TOOLS['git']['why'],
                  'actions': [] if git else ['install']})
    node = core.which('node')
    nv = _version(_run([node, '--version'])[1]) if node else ''
    major = int(nv.split('.')[0]) if nv else 0
    node_ok = bool(node) and major >= NODE_MIN
    items.append({'key': 'node', 'name': 'Node.js', 'ok': node_ok, 'version': nv,
                  'detail': ('Kurulu' if node_ok else f'Sürüm {nv} eski; en az {NODE_MIN} gerekli') if node else 'Kurulu değil',
                  'why': BASE_TOOLS['node']['why'], 'actions': [] if node_ok else ['install']})
    npm = core.which('npm')
    logged = 0
    for key, spec in CLIS.items():
        exe = core.which(key)
        row = {'key': key, 'name': spec['name'], 'plan': spec['plan'], 'why': spec['role'], 'version': '',
               'installed': bool(exe), 'login': 'no', 'ok': False, 'actions': []}
        if not exe:
            row['detail'] = 'Kurulu değil'
            row['actions'] = ['install'] if npm else []
            if not npm:
                row['detail'] += ' (önce Node.js kur)'
        else:
            row['version'] = _version(_run([exe, '--version'])[1])
            state, detail = LOGIN_CHECK[key](exe)
            row.update(login=state, detail=detail, ok=state == 'yes')
            row['actions'] = (['update'] if state == 'yes' else
                              ['verify', 'login', 'update'] if state == 'unknown' else ['login', 'update'])
            logged += state == 'yes'
        if key in JOBS and JOBS[key]['state'] == 'running':
            row['actions'] = []
            row['detail'] = 'Kuruluyor…'
        items.append(row)
    usable = sum(1 for i in items if i['key'] in CLIS and i['login'] == 'yes')  # only confirmed logins count
    ready = items[1]['ok'] and items[2]['ok'] and usable >= 2
    data = {'items': items, 'ready': ready, 'logged_in': logged, 'usable_ai': usable,
            'next': _next_step(items, usable), 'windows': os.name == 'nt', 'jobs': jobs()}
    _CACHE.update(at=time.monotonic(), data=data)
    return data


def _next_step(items, usable):
    by = {i['key']: i for i in items}
    if not by['git']['ok']:
        return 'Git’i kur.'
    if not by['node']['ok']:
        return 'Node.js’i kur; bitince paneli kapatıp yeniden aç.'
    nologin = [i['name'] for i in items if i['key'] in CLIS and i['installed'] and i['login'] == 'no']
    if usable < 2 and nologin:  # already installed: a login is the quickest way to a second AI
        return f"Giriş yap: {', '.join(nologin)}."
    missing = [i['name'] for i in items if i['key'] in CLIS and not i['installed']]
    unsure = [i['name'] for i in items if i['key'] in CLIS and i['login'] == 'unknown']
    if usable < 2 and unsure:
        return f"Girişini doğrula: {', '.join(unsure)} için \"Test et\"e bas (giriş yoksa hiç kota harcanmaz)."
    if usable < 2 and missing:
        return f"AI programlarını kur: {', '.join(missing)}."
    if usable < 2:
        return 'En az iki farklı AI’nın kurulu ve girişli olması gerekiyor.'
    rest = [i['name'] for i in items if i['key'] in CLIS and not i['ok']]
    if rest:
        return f"Hazırsın. İstersen {', '.join(rest)} için de kurulum/girişi tamamla; iş daha dengeli dağılır."
    return 'Her şey hazır. Projeler sekmesinden ilk projeni başlat.'


# ---------------- actions (owner-triggered) ----------------
def install_command(key):
    """Fixed, allow-listed install command for a tool, or None if it cannot be automated here."""
    if key in CLIS:
        npm = core.which('npm')
        return [npm, 'install', '-g', CLIS[key]['npm'] + '@latest'] if npm else None
    if key in BASE_TOOLS and os.name == 'nt' and core.which('winget'):
        return [core.which('winget'), 'install', '--id', BASE_TOOLS[key]['winget'], '-e', '--source', 'winget',
                '--accept-package-agreements', '--accept-source-agreements']
    return None


def install(key):
    if key not in CLIS and key not in BASE_TOOLS:
        raise ValueError('Bilinmeyen araç')
    cmd = install_command(key)
    if cmd is None:
        if key in BASE_TOOLS:
            return {'manual': True, 'url': BASE_TOOLS[key]['url'],
                    'message': f"{BASE_TOOLS[key]['name']} otomatik kurulamadı (winget yok). İndirme sayfasından kur, "
                               'sonra paneli yeniden aç.'}
        raise ValueError('Önce Node.js kurulmalı (npm bulunamadı)')
    with _LOCK:
        if any(j['state'] == 'running' for j in JOBS.values()):
            raise ValueError('Başka bir kurulum sürüyor; bitmesini bekle')
        JOBS[key] = {'state': 'running', 'started': core.now(), 'output': '', 'tool': key}

    def work():
        code, out = _run(cmd, 900)
        JOBS[key].update(state='ok' if code == 0 else 'failed', output=core.redact_log_output(out)[-1500:],
                         ended=core.now())
        _CACHE['data'] = None
    threading.Thread(target=work, daemon=True).start()
    restart = key in BASE_TOOLS
    return {'started': key, 'restart_needed': restart,
            'message': ('Kurulum başladı. Bitince paneli kapatıp yeniden aç (yeni program yolu ancak öyle görünür).'
                        if restart else 'Kurulum başladı; birkaç dakika sürebilir.')}


def jobs():
    return {k: {kk: v for kk, v in j.items() if kk != 'output'} | {'tail': j['output'][-400:]}
            for k, j in JOBS.items()}


def login_command(key):
    if key not in CLIS:
        raise ValueError('Bilinmeyen AI programı')
    if not core.which(key):
        raise ValueError(f"{CLIS[key]['name']} kurulu değil; önce kur")
    return list(CLIS[key]['login'])  # bare name: the console resolves it via PATH (no quoting pitfalls)


def login(key, opener=None):
    """Open the provider's own sign-in in a visible console window (the owner types nothing into PARDEX)."""
    argv = login_command(key)
    title = f"PARDEX - {CLIS[key]['name']} girisi"
    hint = {'claude': 'Tarayıcıda Claude hesabınla giriş yap, sonra bu pencereyi kapat.',
            'codex': 'Tarayıcıda ChatGPT hesabınla giriş yap, sonra bu pencereyi kapat.',
            'gemini': '"Login with Google" seç, tarayıcıda giriş yap; açılan sohbette /quit yazıp çık.'}[key]
    if os.name == 'nt':
        cmd = ['cmd.exe', '/c', 'start', title, 'cmd.exe', '/k', *argv]
        (opener or subprocess.Popen)(cmd, env=core.safe_env())
        _CACHE['data'] = None
        return {'opened': True, 'message': 'Yeni bir pencere açıldı. ' + hint +
                ' Ardından burada "Yeniden kontrol et"e bas.'}
    return {'opened': False, 'command': ' '.join(argv),
            'message': f"Bir terminal aç ve şunu çalıştır: {' '.join(argv)} — {hint}"}


VERIFY = {'gemini': lambda exe: [exe, '-p', 'Sadece OK yaz. Başka hiçbir şey yazma.']}


def verify(key):
    """Owner-triggered login check for a CLI without a status command. Not logged in: fails before any
    request (0 quota). Logged in: exactly one tiny prompt."""
    if key not in VERIFY:
        raise ValueError('Bu program için test gerekmiyor; durumu otomatik okunuyor')
    exe = core.which(key)
    if not exe:
        raise ValueError(f"{CLIS[key]['name']} kurulu değil; önce kur")
    code, out = _run(VERIFY[key](exe), 120)
    ok = code == 0 and 'OK' in out.upper()
    data = _verified()
    data[key] = {'ok': ok, 'at': core.now()}
    core.save_json(core.HOME / 'hq' / 'setup_verified.json', data)
    _CACHE['data'] = None
    if ok:
        return {'ok': True, 'message': f"{CLIS[key]['name']} girişi doğrulandı (1 küçük çağrı kullanıldı)."}
    reason = 'Giriş yapılmamış' if re.search(r'auth', out, re.I) else 'Test başarısız'
    return {'ok': False, 'message': f"{reason}: \"Giriş yap\" ile hesabınla giriş yap, sonra tekrar test et.",
            'detail': core.redact_log_output(out)[-300:]}
