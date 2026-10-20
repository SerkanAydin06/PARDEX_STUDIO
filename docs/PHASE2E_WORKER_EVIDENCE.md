# 2E — Worker güvenliği, A/B kanıtı ve raporlu token verisi

## Durum
İnceleme PR'si. Yerel regresyon testleri vardır; gerçek Windows, Docker daemon, abonelik CLI ve gerçek model A/B sonuçları **henüz** uçtan uca doğrulanmadı.

## Yürütme güvenliği
- `app/worker_guard.py` ile `PARDEX_REQUIRE_ISOLATED_AI=1` veya AI Genel Müdür GUI'deki **Sıkı izolasyon** seçeneği, yerel Claude/Codex/Gemini CLI işlerini durdurur. Bu özellik **sandbox değildir**; hazır olmayan güvenli çalıştırıcı için *fail closed* kapısıdır.
- Görev Merkezi, doğrudan AI görevi, Çekirdek Konseyi, aday kod inceleme, şirket toplantısı ve Ollama çağrılarındaki ilgili çıkışlar guard kontrolünden geçirilir. AI çağrı bütçesi engellenen işte harcanmamalıdır.
- Eski, açıkça kullanıcı tarafından başlatılan native CLI akışları sıkı mod kapalıyken mevcut izin sınırlarıyla sürer. Bu varsayılan akışta işletim sistemi seviyesinde izolasyon garanti edilemez.
- `app/evolution.py` içindeki Docker regresyon kontrolü ayrı ve kısmi bir düzenektir; Docker daemon/host, imajın digest pinlenmesi ve gerçek Windows/WSL doğrulaması gerekiyor. **AI worker sandbox'ı tamamlandı iddiası yoktur.**

## Deney ve kaynak
- `app/benchmark_lab.py` aynı kod başlangıcını SHA256 dosya parmak iziyle, aynı görev, motor, test profili ve araç sürümü eşleşmesiyle kontrol eder. Gizli `.studio` ve geçici derleme dosyaları bu imzaya eklenmez. İmza model kodu değiştirmeden **önce** alınmalıdır.
- `app/usage_receipts.py` yalnızca kullanıcı tarafından açıkça onaylanmış, daha önceden üretilmiş **Codex CLI JSONL** `turn.completed.usage` sayıları içe aktarabilir. Transkript ve prompt kayıt edilmez. Sayılar *CLI raporlu, fatura ile doğrulanmamış* veri olarak saklanır.
- Şu an PARDEX native CLI akışı kendi başına JSONL dışa aktarımı üretmiyor. Diğer modellerin token bakiyesi ve abonelik ücreti bilinmiyor. Para veya tasarruf yüzdesi **hesaplanmaz**.
- Karşılaştırmalar kalite sertifikası veya sağlayıcı üstünlüğü değildir; kullanıcının onayıyla pilot hipotez sağlar.

## Kullanım
AI Genel Müdür: sıkı izolasyonu isteğe bağlı aç; proje parmak izi al; varsa Codex JSONL raporunu tamamlanan görevle ilişkilendir. Hiçbiri kendiliğinden AI, ağ, satın alma veya yayınlama çağrısı oluşturmaz.

## Test / rollback
`python -m unittest discover -s tests -p 'test_*.py' -q`, `python -m compileall -q app tests`. PR geri alınabilir; isteğe bağlı yerel kullanım sayıları mevcut özel SQLite veritabanında tutulur. Gerçek Docker/Windows ve canlı AI testi ayrıca gereklidir.
