"""Phase 4 — Ar-Ge: owner-requested, source-backed research. One AI call with web search.

An idea is kept only if it cites at least two reachable sources on different websites.
Paid tools/memberships are only *recommended* to the owner with a source and a price note — never bought.
"""
import http.client
import ipaddress
import json
import re
import socket
import ssl
import urllib.parse

import core
import hq_router as router
import hq_store as store

FOCUS = {
    'oyun': 'kârlı olabilecek, küçük ekiple yapılabilir oyun fikirleri (mağaza verisi, trend, boşluk)',
    'uygulama': 'gerçek bir ihtiyaca cevap veren, para kazanabilecek uygulama veya araç fikirleri',
    'sirket': 'PARDEX şirketinin üretim kalitesini artıracak, token/kota tasarrufu sağlayacak araç ve yöntemler',
    'uyelik': 'şirketin gerçekten ihtiyaç duyabileceği ücretli/ücretsiz AI araçları ve üyelikler (net fayda gerekçesiyle)',
}
KIND_PREFIX = {'urun': '', 'sirket': '[Şirket gelişimi] ', 'uyelik': '[Üyelik önerisi] '}


def _domain(url):
    try:
        host = urllib.parse.urlparse(url).hostname or ''
    except ValueError:
        return ''
    parts = host.lower().split('.')
    return '.'.join(parts[-2:]) if len(parts) >= 2 else host


def _public_ips(host):
    """Resolve every address and fail closed on any private/local result."""
    try:
        answers = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        ips = list(dict.fromkeys(item[4][0] for item in answers))
        if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
            return []
        return ips
    except (OSError, ValueError):
        return []


MAX_REDIRECTS = 3


def _target(url):
    """Validate one URL. Returns (host, route) for a public HTTPS target, else None."""
    try:
        if not isinstance(url, str) or len(url) > 300:
            return None
        u = urllib.parse.urlsplit(url)
        if (u.scheme != 'https' or not u.hostname or u.username is not None or
                u.password is not None or u.port not in (None, 443) or
                u.hostname.endswith(('.local', '.internal', '.localhost'))):
            return None
        host = u.hostname.encode('idna').decode('ascii')
        if not re.fullmatch(r'[a-zA-Z0-9.-]{4,253}', host) or '.' not in host:
            return None
        return host, urllib.parse.urlunsplit(('', '', u.path or '/', u.query, ''))
    except (ValueError, UnicodeError, AttributeError):
        return None


def _probe(host, route, timeout):
    """One pinned request. Returns ('ok'|'redirect'|'fail', location)."""
    ips = _public_ips(host)
    for ip in ips[:2]:
        for method in ('HEAD', 'GET'):
            raw = tls = conn = None
            try:
                raw = socket.create_connection((ip, 443), timeout=timeout)
                tls = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
                conn = http.client.HTTPConnection(host, 443, timeout=timeout)
                conn.sock = tls  # validated public address, no second DNS lookup
                conn.request(method, route, headers={'Host': host, 'User-Agent': 'PARDEX-ArGe/1.0'})
                response = conn.getresponse()
                if 200 <= response.status < 300:
                    return 'ok', ''
                if response.status in (301, 302, 303, 307, 308):
                    loc = response.getheader('Location')
                    return ('redirect', loc) if isinstance(loc, str) and loc else ('fail', '')
                if response.status not in (405, 501):
                    break
            except (OSError, ValueError, ssl.SSLError, http.client.HTTPException):
                break
            finally:
                if conn is not None:
                    conn.close()
                elif tls is not None:
                    tls.close()
                elif raw is not None:
                    raw.close()
    return 'fail', ''


def reachable(url, timeout=7):
    """Does a cited page exist? Pinned public HTTPS only.

    Redirects are followed at most MAX_REDIRECTS times and every hop is validated from scratch
    (https:443, no credentials, public IPs only, fresh DNS pinned to the dialed address), so a
    redirect can never lead into a local/private network. TLS certificates are verified.
    """
    if isinstance(url, str) and urllib.parse.urlsplit(url).fragment:
        return False
    current = url
    for _hop in range(MAX_REDIRECTS + 1):
        target = _target(current)
        if not target:
            return False
        state, loc = _probe(*target, timeout)
        if state == 'ok':
            return True
        if state != 'redirect':
            return False
        current = urllib.parse.urljoin(current, loc)
    return False


def prompt_for(focus, topic, known):
    return ('Sen PARDEX yazılım şirketinin Ar-Ge analistisin. WEB ARAMASI YAP; bilgiyi gerçek, güncel sayfalardan al. '
            'Kafadan fikir, uydurma istatistik veya var olmayan kaynak YASAK. Kaynağı olmayan maddeyi hiç yazma. '
            f'Odak: {FOCUS[focus]}. Patronun konusu: {topic[:300] or "serbest"}. '
            f'Zaten bilinen fikirleri tekrar etme: {"; ".join(known)[:800]}. '
            'Her madde için en az 2 farklı siteden doğrudan sayfa adresi ver. Hile, kural ihlali, sahte hesap içeren fikir verme. '
            'YALNIZCA JSON döndür: {"ideas":[{"title":"en fazla 90 karakter","type":"urun|sirket|uyelik",'
            '"why_now":"neden şimdi, kanıtla","evidence":"kaynaklardaki somut bulgu","sources":["https://..."],'
            '"revenue":1-5,"effort":1-5,"cost":1-5,"fit":1-5,"first_step":"ilk somut adım","price":"üyelikse fiyat ve tarih, yoksa boş"}]} '
            'En fazla 5 madde; az ama sağlam madde tercih et.')


def _int(v, d=3):
    return v if type(v) is int and 1 <= v <= 5 else d


def research(focus, topic='', path=None, ai=None, check=None):
    if focus not in FOCUS:
        raise ValueError('Odak oyun/uygulama/sirket/uyelik olmalı')
    known = [i['title'] for i in store.ideas(path)][:30]
    import hq_projects
    res = (ai or router.call)('research', prompt_for(focus, str(topic), known), hq_projects._scratch(), 'arge', path=path)
    if not res['ok']:
        raise RuntimeError('Ar-Ge araştırması yapılamadı: ' + res['output'][-200:])
    data = hq_projects._json(res['output']) or {}
    check = check or reachable
    seen = {store._norm(re.sub(r'^\[[^\]]+\]\s*', '', t)) for t in known}
    accepted, rejected = [], []
    for it in (data.get('ideas') or [])[:6]:
        if not isinstance(it, dict):
            continue
        title = core.redact_log_output(str(it.get('title', ''))).strip()[:90]
        urls = [u.strip() for u in it.get('sources') or [] if isinstance(u, str)][:6]
        if len(title) < 4:
            continue
        if store._norm(title) in seen:
            rejected.append((title, 'zaten listede'))
            continue
        live = [u for u in urls if check(u)]
        if len({_domain(u) for u in live}) < 2:
            rejected.append((title, f'en az 2 farklı siteden doğrulanabilir kaynak yok ({len(live)}/{len(urls)})'))
            continue
        kind = it.get('type') if it.get('type') in KIND_PREFIX else ('uyelik' if focus == 'uyelik' else 'sirket' if focus == 'sirket' else 'urun')
        note = ' · '.join(x for x in (
            'Neden şimdi: ' + str(it.get('why_now', ''))[:300],
            'Kanıt: ' + str(it.get('evidence', ''))[:300],
            'İlk adım: ' + str(it.get('first_step', ''))[:200],
            ('Fiyat (doğrula): ' + str(it.get('price', ''))[:120]) if kind == 'uyelik' else '') if x)
        ident = store.add_idea(KIND_PREFIX[kind] + title, _int(it.get('revenue')), _int(it.get('effort')),
                               _int(it.get('cost')), _int(it.get('fit')), 'arge', note, path, sources=live)
        if kind == 'uyelik':
            store.move_idea(ident, 'onay', path)  # owner decides; nothing is purchased
        seen.add(store._norm(title))
        accepted.append({'id': ident, 'title': KIND_PREFIX[kind] + title, 'sources': live})
    store.event('arge', 'research', focus, f'{len(accepted)} kabul, {len(rejected)} elendi ({res["provider"]})', path)
    return {'accepted': accepted, 'rejected': [{'title': t, 'reason': r} for t, r in rejected],
            'provider': res['provider'], 'model': res['model']}
