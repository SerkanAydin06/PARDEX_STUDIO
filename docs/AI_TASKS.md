# AI ekipleri için ilk görev dağılımı

Birden fazla ajan aynı dosyayı birbirinden bağımsız olarak eşzamanlı değiştirmesin. Her küçük görev ayrı branch/PR.

1. **Codex:** Windows kurulum ve `app/core.py` komut çağırma güvenliği incelemesi; test ekleyerek düzelt.
2. **Claude:** Proje/çekirdek sınırları, hata hafızası ve yetki/onay modelinin mimari analizi.
3. **Gemini:** Önceki iki ajan çıktılarında bağımsız QA; sahte başarılı test ve performans iddialarını tespit.
4. **Codex veya diğer güvenilir ajan:** Teknik olmayan kullanıcı için arayüz kullanılabilirliği düzeltmeleri.
5. **Bağımsız güvenlik denetçisi:** Actions izinleri, dış API/secret/log sızıntısı ve otomatik güncelleme kontrolleri.
6. **İki ajan:** Model yönlendirme benchmark tasarımı; ölçüm olmadan 'daha ucuz' iddiası yok.

PR açıklaması: problem, dosyalar, çalışan test komutu/çıktısı, risk, geri alma, maliyet/AI kotası, kullanıcı kabul maddesi. Ödeme, yeni hesap ve prod dağıtımı otomatik değil.
