# Phase 2C — Gözlenen AI performansı

AI çalışanlarının yerel CLI denemeleri tekil olarak kaydedilir: süre, görev türü, sağlayıcı, model, yerel test sonucu ve sahip kabul/red durumu.

- Model komutunun bitmesi, teknik testin geçmesi ve ürün sahibinin kabul etmesi ayrı olaylardır.
- Başarısız denemeler elle yeniden çalıştırılsa bile geçmişten silinmez.
- Oyun fikirleri, promptlar, raw AI yanıtları veya API anahtarları metrik tablosuna yazılmaz.
- AI Genel Müdür ekranında ücretsiz performans raporu vardır.
- Aynı görev türünde iki sağlayıcıda en az beşer sahip tarafından değerlendirilmiş deneme ve en az yirmi yüzde puan kabul farkı oluşursa kontrollü bir pilot önerilebilir.
- Model değişikliği, harcama, otomatik retry ve çekirdek güncellemesi kendiliğinden gerçekleşmez.

## Sınırlar

Abonelikte kalan kota, gerçek bulut token maliyeti ve parasal tasarruf bilinmez. Zaman, para/tokens anlamına gelmez. Karşılaştırmalar farklı görev zorluğundan etkilenebilir. Eski işler geriye dönük uydurulmaz. Bu sürüm ölçülen verileri yerel özel SQLite veritabanında tutar.

## Sıradaki adım

Bağımsız AI kalite denetimi, deterministik kıyaslama görevleri, kullanılabiliyorsa sağlayıcı bazında gerçek token sayıları ve kontrollü A/B testleri. Her etkinleştirme için kullanıcı onayı gerekir.
