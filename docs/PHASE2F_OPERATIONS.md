# PARDEX 2F — AI Operasyon Müdürü: sınırlı çalışma vardiyası

Yeni `app/operations.py` yerel ve çok projeli bir operasyon raporu üretir, **önceden ayrı ayrı onaylanmış** görevler için en fazla 3 çağrılık, 90 dakikalık bir *üst sınır* koyabilir. Normal önizleme 2 AI çağrısı ve 45 dakika ile sınırlandırılır; yeni görevlerin onayını vermez.

## Kullanım ve güvenlik
- `board()` proje başına hazır, onay bekleyen, kabul bekleyen ve sorunlu görevleri sayar. Özel brief/metin veya kullanıcı gizli bilgilerini başka servise aktarmaz.
- `preview_shift()` **AI çağrısı yapmadan** mevcut hazır görevleri sıralar. Bağımlılığı henüz kabul edilmemiş işleri atlar, her projeden en fazla bir görev içerir; sıra değişirse `run_shift()` durur.
- `run_shift(owner_confirms=True, ...)` yalnızca kullanıcının açık başlangıç onayından sonra çalışır. Yalnızca daha önce tek tek onaylanmış görevleri çalıştırır, her sonucu `awaiting-acceptance` statüsünde bırakır. Kritik hata, kota bitişi veya sıra değişiminde devam etmez; tekrar deneme ve otomatik kabul yoktur.
- Bu tasarımda **AI ajanlarının işletim sistemi izolasyonu garanti edilmez**. `PARDEX_REQUIRE_ISOLATED_AI=1` etkinse native CLI çalıştırılmaz. Docker içindeki Python testleri ile abonelik girişli AI CLI yürütmesi aynı şey değildir.
- Gerçek token tüketimi veya maliyet bilinmiyorsa raporlanmaz. Girilmiş aboneliklerin otomatik kullanılabilmesi ilgili CLI kurallarına ve kullanıcının giriş yapmasına bağlıdır.

## Kabul testleri
`python -m unittest discover -s tests -p 'test_*.py' -q` ve `python -m compileall -q app tests`.

## Sonraki gerçek dünya kontrolü
Windows'ta kullanıcıya ait test reposunda 2 farklı bağımsız görev için manuel yetkilendirilmiş vardiya denemesi; WSL/Docker için gerçek ortam kontrolü; CLI oturumu ve gizli dosyalara erişim sınırlarının ek denetimi.
