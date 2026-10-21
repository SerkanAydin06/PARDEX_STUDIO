# CEO planlama ve boş teslimat güvenilirliği

İş planını çıkaran AI hata verirse PARDEX artık `üretim` aşamasına geçmez. Çalışma klasörü bir kez oluşturulur ve `planlama` durumunda, aynı proje kimliğiyle saklanır. "Bunu yap" tekrar seçildiğinde güvenli yerel işaret, motor ve ürünler kökü kontrol edilip aynı kopyada planlama yeniden denenir. Planı henüz tamamlanmamış eski `üretim` kayıtları da aynı kontrolle kurtarılır; eski klasörler silinmez.

Gerçek AI CLI kurulu değilse, şirket iş planı başlamadan bilgilendirir ve proje kopyası yaratmaz. Başlatma sırasında AI hata döndürürse sessizce "hazır" sayılmaz. Planlama başarısız olduysa tarif, oluşturulmuş proje kopyasıyla tutarsızlaşmasın diye sohbetle değiştirilemez.

Sıfır iş paketi bulunan üretim çalıştırılmaz. İş paketlerinin hiçbiri tamamlanmadıysa proje teslim edilmez; tümü atlandıysa durum `durdu` olur. Bu önlem, teslim öncesi ek AI çağrılarının boşa yapılmasını da engeller.

Tarayıcıda "Bunu yap" ve yarım kalmış eski kayıtlarda "İş planını yeniden dene" düğmeleri başarısız HTTP isteği sonrası tekrar etkinleşir; üretim yalnızca başarılı başlatmadan sonra tetiklenir.

Sekiz yeni çevrimdışı regresyon testi eklendi. GitHub CI'da gerçek Claude/Codex/Gemini aboneliği ve Windows/Godot kurulumu test edilemez.
## Durdurulmuş projeden devam

- **Motor için durdurma:** "Durdur, motoru kurup sonra devam edeceğim" denen proje, motor kurulduktan sonra **Üretime devam et** ile kaldığı yerden sürer. Motor hâlâ yoksa soru 0 token ile yeniden sorulur.
- **Bütün paketleri atlanan proje:** Teslim yapılmaz, proje `durdu` olur ve Ürün Müdürü nedenini sohbette söyler. **Değişiklik iste** ile yeni bir paket eklenir ve üretim yeniden başlar. İşe yaramayan "devam" düğmesi gösterilmez.
- **"Bunu yap" ön kontrolü:** Bağımsız kontrol için gereken sayıda farklı AI kurulu değilse (1 denetçi = 2 AI, 2 denetçi = 3 AI) proje kopyalanmadan ve hiç çağrı harcanmadan durulur.
