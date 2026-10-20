"""Phase 4 — Ar-Ge: owner-requested, source-backed research. One AI call with web search.

An idea is kept only if it cites at least two reachable sources on different websites.
Paid tools/memberships are only *recommended* to the owner with a source and a price note — never bought.
"""
import json
import re
import urllib.parse
import urllib.request

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


def reachable(url, timeout=7):
    """K0 check that a cited page exists (HEAD, then a tiny GET)."""
    if not re.fullmatch(r'https?://[^\s<>"]{4,300}', url or ''):
        return False
    for method in ('HEAD', 'GET'):
        try:
            req = urllib.request.Request(url, method=method, headers={'User-Agent': 'PARDEX-ArGe/1.0'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                if r.status < 400:
                    return True
        except Exception:
            continue
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
