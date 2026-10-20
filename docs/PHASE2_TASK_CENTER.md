# Aşama 2A — Kalıcı, Kullanıcı Onaylı AI Görev Merkezi

- SQLite veritabanı kullanıcı bilgisayarında tutulur: Windows \`%LOCALAPPDATA%/UltraProStudio/task_queue.sqlite3\`; proje GitHub deposuna yüklenmez.
- \`AI Ekibi\` metnini gir, \`Gorev Merkezi\`ne ekle; durum önce \`pending-owner\`. Açıkça onayla -> \`ready\`; sonra \`tek görevi çalıştır\` -> \`running\`; başarılı AI + gerçek motor testinden sonra \`awaiting-acceptance\`; oynanış/UI kontrolünü **kullanıcı** kabul edince \`accepted\`.
- Hata ve test eksikliği \`needs-attention\`; yeni deneme için ayrı onay gerekir. Çalışma yarıda kesilirse, otomatik yeniden başlamaz; kullanıcının kurtarma onayı gerekir.
- Öncelik 1-5; aynı anda yalnızca **bir kuyruk görevi**. Yerel günlük AI çağrı limiti ve dakika üst sınırı; bekleyen ve önizlenen görevler ücretsiz yerel işlemdir.
- Gerçek abonelik token/kota bakiyesi mevcut API'lerle okunmuyor; kullanıcı arayüzü varsayım yapmaz.
- **Sınır:** Bu bir OS sandbox, sürekli CEO/otonom çalışan ekip, otomatik ücretli API, anlık çoklu ajan toplantısı veya otomatik deployment değildir. Kodlayan CLI'nın izni ayrıca gözden geçirilmelidir.
- **Geri alma:** PR'ı revert etmek yeterli; yerel SQLite kullanıcının verisi olarak yerinde kalır. Şifre/oturum içeriği kaydedilmez.
- Testler: mock AI CLI, kalıcılık, onay, tek yürütücü, bütçe, hata, kurtarma, gizli veri maskeleme. Windows ve gerçek abonelikle uçtan uca test ayrıca gereklidir.

Sıradaki faz: bağımlılık grafiği, kanıta dayalı AI CEO görev ataması, modeller arası QA ve gerçek kalite/süre/kullanım maliyeti ölçümü.
