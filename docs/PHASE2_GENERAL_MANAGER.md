# Aşama 2B — AI Genel Müdür

Bu sürüm çoklu proje için **onaylı, bağımlılık kontrollü** iş planları üretir. Offline planlama AI kotası harcamaz; gerçek CLI çağrıları sahip onayından sonra Görev Merkezi üzerinden başlar.

## İş akışı
1. Proje seç. **AI Genel Müdür** sekmesinde hedef, risk ve öncelik yaz.
2. Ücretsiz önizlemede adımları, en fazla CLI çağrısı ve dakika toplamını gör.
3. Onayınla görevleri oluştur; **hiçbir AI kendiliğinden çalışmaz**.
4. Görev Merkezi'nde ilk görevi onayla ve başlat. Gözle ve sonuçları kabul et. Önceki kabul olmadan sonraki AI çalışmaz.
5. Bağımsız QA görevi çıktısını incele. Oyun görsel/oynanış kabulü senindir.

| Risk | Sıra | AI çağrı üst limiti | Toplam görev dakikası |
|---|---|---:|---:|
| Basit | Codex kod ve sahibin testi | 1 | 12 |
| Normal | Codex kod → Gemini QA | 2 | 26 |
| Kritik | Claude plan → Codex kod → Gemini QA | 3 | 38 |

Bu limitler birer görev planıdır; gerçek token, abonelik bakiyesi veya fatura ölçümü değildir. Bir AI erişilemezse iş hazırda kalır. Başarısız işler otomatik tekrarlanmaz, bağımlı işler kilitlenir. Şimdilik otomatik PR açma, zamanlanmış AI worker veya gerçek modelden otonom görev planı üretme yoktur.

## Teknik
- `app/general_manager.py`: plan kayıtları (aynı yerel SQLite), görev listesi ve yerel/ücretsiz risk planları.
- `app/task_queue.py`: SQL bağımlılık kapısı ve SQLite göçü; AI çıktı devir notu yalnızca kabul edilmiş önceki görevden; yeni yetki doğurmaz.
- `app/gui.py`: Türkçe yönetici plan arayüzü.
- `app/core.py`: Önceki AI çıktısını güvenilmeyen veri olarak belirtir.

Sistemin kendi güvenlik sınırlamaları sürer. Görevleri çalıştırabilen yerel CLI araçları gerçek OS sandbox ile sınırlandırılmış değildir; dış işlemler (para, yayın, kod aktivasyonu, hesap ve altyapı) için ayrı insan onayı gerekir. Ticari ROI/gerçek token tasarrufu kanıtlanmamıştır.

## Doğrulama
`python -m unittest discover -s tests -p 'test_*.py' -q`; GitHub CI ile tekrar kontrol edilmeli. Gerçek Windows ve gerçek abonelik CLI hesaplarıyla entegrasyon ayrıca test edilmelidir.
