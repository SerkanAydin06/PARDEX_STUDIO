# CEO planlama ve boş teslimat güvenilirliği

İş planını çıkaran AI hata verirse PARDEX artık `üretim` aşamasına geçmez. Çalışma klasörü bir kez oluşturulur ve `planlama` durumunda, aynı proje kimliğiyle saklanır. "Bunu yap" tekrar seçildiğinde güvenli yerel işaret, motor ve ürünler kökü kontrol edilip aynı kopyada planlama yeniden denenir. Planı henüz tamamlanmamış eski `üretim` kayıtları da aynı kontrolle kurtarılır; eski klasörler silinmez.

Gerçek AI CLI kurulu değilse, şirket iş planı başlamadan bilgilendirir ve proje kopyası yaratmaz. Başlatma sırasında AI hata döndürürse sessizce "hazır" sayılmaz. Planlama başarısız olduysa tarif, oluşturulmuş proje kopyasıyla tutarsızlaşmasın diye sohbetle değiştirilemez.

Sıfır iş paketi bulunan üretim çalıştırılmaz. İş paketlerinin hiçbiri tamamlanmadıysa proje teslim edilmez; tümü atlandıysa durum `durdu` olur. Bu önlem, teslim öncesi ek AI çağrılarının boşa yapılmasını da engeller.

Tarayıcıda "Bunu yap" ve yarım kalmış eski kayıtlarda "İş planını yeniden dene" düğmeleri başarısız HTTP isteği sonrası tekrar etkinleşir; üretim yalnızca başarılı başlatmadan sonra tetiklenir.

Sekiz yeni çevrimdışı regresyon testi eklendi. GitHub CI'da gerçek Claude/Codex/Gemini aboneliği ve Windows/Godot kurulumu test edilemez.