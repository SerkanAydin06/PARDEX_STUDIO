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
import hq_store as store
import worker_guard

NODE_MIN = 20
CLIS = {
    'claude': {'name': 'Claude Code', 'plan': 'Claude Pro', 'npm': '@anthropic-ai/claude-code',
               'login': ['claude', 'auth', 'login'], 'role': 'Plan sohbeti, iş paylaşımı, zor mimari'},
    'codex': {'name': 'Codex CLI', 'plan': 'ChatGPT Pro', 'npm': '@openai/codex',
              'login': ['codex', 'login'], 'role': 'Kod yazımı ve düzeltme'},
    'gemini': {'name': 'Google Antigravity CLI', 'plan': 'Google AI Pro', 'npm': None,
               'url': 'https://antigravity.google/docs/getting-started/?tab=cli',
               'login': ['agy'], 'role': 'Bağımsız kod denetimi ve Ar-Ge'},
    'copilot': {'name': 'GitHub Copilot CLI', 'plan': 'Copilot Pro · isteğe bağlı', 'npm': '@github/copilot',
                'login': ['copilot', 'login'], 'optional': True,
                'role': 'Yedek çalışan: kod, inceleme, plan (Ar-Ge yapamaz)'},
}
# Variables that would make a CLI use a token/API key instead of the owner's subscription login.
NOT_SUBSCRIPTION = ('COPILOT_GITHUB_TOKEN', 'GH_TOKEN', 'GITHUB_TOKEN', 'COPILOT_PROVIDER_API_KEY',
                    'COPILOT_PROVIDER_BASE_URL', 'COPILOT_OFFLINE')
BASE_TOOLS = {
    'git': {'name': 'Git', 'winget': 'Git.Git', 'url': 'https://git-scm.com/downloads/win',
            'why': 'Her ürün kendi Git deposunda tutulur'},
    'node': {'name': 'Node.js', 'winget': 'OpenJS.NodeJS.LTS', 'url': 'https://nodejs.org/en/download',
             'why': 'Üç AI programı Node.js ile kurulur ve çalışır'},
}
JOBS = {}
_LOCK = threading.Lock()
_VERIFY_LOCK = threading.Lock()
VERIFY_MAX_AGE = 15 * 60
_CACHE = {'at': 0.0, 'data': None}


def _env():
    env = core.safe_env()
    for key in NOT_SUBSCRIPTION:
        env.pop(key, None)
    return env


def _run(argv, timeout=20):
    try:
        r = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, stdin=subprocess.DEVNULL,
                           encoding='utf-8', errors='replace', timeout=timeout, env=_env(), check=False)
        return r.returncode, (r.stdout or '').strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, core.redact_log_output(type(exc).__name__ + ': ' + str(exc))[-1500:]


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


def _recent_verification(key):
    v = _verified().get(key)
    if not v:
        return None
    # An old successful test is historical evidence, not a logout event.
    if v.get('ok') and time.time() - v.get('checked_at', 0) > VERIFY_MAX_AGE:
        return 'cached', 'Son bağlantı testi başarılı; güncel oturum kontrol edilmedi. Yeniden giriş zorunlu değil.'
    return ('yes', 'Giriş doğrulandı (Test et)') if v.get('ok') else ('unknown', 'Bağlantı doğrulanamadı; test ayrıntısını kontrol et')


def _gemini_login(_exe, home=None):
    """Gemini CLI has no status command. Without a chosen auth method it cannot run at all (no), only a recent successful "Test et" means yes; a cached
    Google login file is unconfirmed; a chosen method with credentials in the system
    keychain cannot be seen from here (unknown). Never a false 'yes'."""
    v = _recent_verification('antigravity')
    return v or ('unknown', 'Antigravity hesabını Giriş yap ile aç, ardından Test et')


def _copilot_login(_exe):
    """Copilot keeps its login in the system credential store and has no status command: only a
    "Test et" result is trusted (when logged out the CLI refuses before sending anything)."""
    v = _recent_verification('copilot')
    if v:
        return v
    return 'unknown', 'Giriş durumu dışarıdan okunamıyor; giriş yaptıysan "Test et"e bas'


LOGIN_CHECK = {'claude': _claude_login, 'codex': _codex_login, 'gemini': _gemini_login, 'copilot': _copilot_login}


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
        row['optional'] = bool(spec.get('optional'))
        if not exe:
            row['detail'] = 'Kurulu değil' + (' (isteğe bağlı)' if spec.get('optional') else '')
            row['actions'] = ['install'] if npm or key == 'gemini' else []
            if not npm and key != 'gemini':
                row['detail'] += ' (önce Node.js kur)'
        else:
            row['version'] = _version(_run([exe, '--version'])[1])
            state, detail = LOGIN_CHECK[key](exe)
            row.update(login=state, detail=detail, ok=state in ('yes', 'cached'))
            testable = key in VERIFY
            row['actions'] = (['verify', 'login', 'update'] if state == 'cached' else ['update'] if state == 'yes' else
                              ['verify', 'login', 'update'] if state == 'unknown' else
                              ['login', 'verify', 'update'] if testable else ['login', 'update'])
            logged += state in ('yes', 'cached')
        if key in JOBS and JOBS[key]['state'] == 'running':
            row['actions'] = []
            row['detail'] = 'Kuruluyor…'
        items.append(row)
    usable = sum(1 for i in items if i['key'] in CLIS and i['login'] in ('yes', 'cached'))  # only confirmed logins count
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
    missing = [i['name'] for i in items if i['key'] in CLIS and not i['installed'] and not i.get('optional')]
    unsure = [i['name'] for i in items if i['key'] in CLIS and i['login'] == 'unknown']
    if usable < 2 and unsure:
        return f"Girişini doğrula: {', '.join(unsure)} için \"Test et\"e bas (giriş yoksa hiç kota harcanmaz)."
    if usable < 2 and missing:
        return f"AI programlarını kur: {', '.join(missing)}."
    if usable < 2:
        return 'En az iki farklı AI’nın kurulu ve girişli olması gerekiyor.'
    rest = [i['name'] for i in items if i['key'] in CLIS and not i['ok'] and (i['installed'] or not i.get('optional'))]
    if rest:
        return f"Hazırsın. İstersen {', '.join(rest)} için de kurulum/girişi tamamla; iş daha dengeli dağılır."
    return 'Her şey hazır. Projeler sekmesinden ilk projeni başlat.'


# ---------------- actions (owner-triggered) ----------------
def install_command(key):
    """Fixed, allow-listed install command for a tool, or None if it cannot be automated here."""
    if key == 'gemini':
        if os.name == 'nt':
            return ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                    str(core.BASE / 'scripts' / 'antigravity-kur.ps1')]
        return None
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
        if key in BASE_TOOLS or key == 'gemini':
            spec = CLIS[key] if key == 'gemini' else BASE_TOOLS[key]
            return {'manual': True, 'url': spec['url'],
                    'message': f"{spec['name']} için resmî kurulum sayfasını aç. Kurduktan sonra "
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
    restart = key in BASE_TOOLS or key == 'gemini'
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
    if key == 'gemini':
        return [core.which('gemini')]
    return list(CLIS[key]['login'])  # bare name: the console resolves it via PATH (no quoting pitfalls)


def login(key, opener=None):
    """Open the provider's own sign-in in a visible console window (the owner types nothing into PARDEX)."""
    argv = login_command(key)
    data = _verified()
    if data.pop('antigravity' if key == 'gemini' else key, None) is not None:  # a new login makes an old "Test et" result stale
        core.save_json(core.HOME / 'hq' / 'setup_verified.json', data)
    title = f"PARDEX - {CLIS[key]['name']} girisi"
    hint = {'copilot': 'Tarayıcıda GitHub hesabınla (Copilot Pro) giriş yap, sonra bu pencereyi kapat ve "Test et"e bas.',
            'claude': 'Tarayıcıda Claude hesabınla giriş yap, sonra bu pencereyi kapat.',
            'codex': 'Tarayıcıda ChatGPT hesabınla giriş yap, sonra bu pencereyi kapat.',
            'gemini': 'Antigravity ilk açılışını tamamla, Google hesabınla giriş yap; /quit ile çıkıp Test et’e bas.'}[key]
    if os.name == 'nt':
        cmd = ['cmd.exe', '/c', 'start', title, 'cmd.exe', '/k', *argv]
        (opener or subprocess.Popen)(cmd, env=core.safe_env())
        _CACHE['data'] = None
        return {'opened': True, 'message': 'Yeni bir pencere açıldı. ' + hint +
                ' Ardından burada "Yeniden kontrol et"e bas.'}
    return {'opened': False, 'command': ' '.join(argv),
            'message': f"Bir terminal aç ve şunu çalıştır: {' '.join(argv)} — {hint}"}


VERIFY = {'gemini': lambda exe: [exe, '-p', 'Sadece OK yaz. Başka hiçbir şey yazma.'],
          'copilot': lambda exe: [exe, '--silent', '--no-ask-user', '-p', 'Sadece OK yaz. Başka hiçbir şey yazma.']}


def verify(key, path=None):
    if not _VERIFY_LOCK.acquire(blocking=False):
        raise ValueError('Başka bir giriş testi sürüyor; bitmesini bekle')
    try:
        return _verify(key, path)
    finally:
        _VERIFY_LOCK.release()


def _verify(key, path=None):
    """One budgeted owner-triggered prompt; reserve one attempt before dispatch."""
    if key not in VERIFY:
        raise ValueError('Bu program için test gerekmiyor; durumu otomatik okunuyor')
    exe = core.which(key)
    if not exe:
        raise ValueError(f"{CLIS[key]['name']} kurulu değil; önce kur")
    worker_guard.guard_native_agent()
    allowed, reason = store.budget_check('kalite', 1, path)
    if not allowed:
        raise ValueError(reason)
    provider = {'gemini': 'Gemini', 'copilot': 'Copilot'}[key]
    # Reserve before dispatch, including failed attempts; no automatic retries.
    core.record_usage(provider)
    store.record('kalite', 'ai_call', 1, provider, note='Kurulum giriş testi', path=path)
    code, out = _run(VERIFY[key](exe), 120)
    ok = code == 0 and out.strip() == 'OK'
    data = _verified()
    auth_missing = bool(re.search(r"not logged in|not signed in|authentication required|login required|run.*(?:/login|copilot login)|set an auth method", out, re.I))
    record_key = 'antigravity' if key == 'gemini' else key
    previous = data.get(record_key, {})
    if ok or auth_missing or not previous.get('ok'):
        data[record_key] = {'ok': ok, 'at': core.now(), 'checked_at': time.time()}
    core.save_json(core.HOME / 'hq' / 'setup_verified.json', data)
    _CACHE['data'] = None
    if ok:
        return {'ok': True, 'message': f"{CLIS[key]['name']} girişi doğrulandı (1 küçük çağrı kullanıldı)."}
    auth_missing = bool(re.search(r"not logged in|not signed in|authentication required|login required|run.*(?:/login|copilot login)|set an auth method", out, re.I))
    if auth_missing:
        message = 'Giriş doğrulanamadı. Giriş yap ile hesabına bağlan, sonra tekrar test et.'
    elif code == 0:
        message = 'Komut tamamlandı ancak beklenen test yanıtı alınamadı. Ayrıntıyı incele; yeniden giriş gerekmeyebilir.'
    else:
        message = 'Test komutu başarısız. Ayrıntıyı incele; bu sonuç tek başına giriş yapılmadığı anlamına gelmez.'
    return {'ok': False, 'message': message, 'exit_code': code,
            'detail': core.redact_log_output(out)[-1500:] or 'CLI çıktı vermedi.'}
