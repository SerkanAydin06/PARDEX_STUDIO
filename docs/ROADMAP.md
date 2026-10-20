# Ürün Yol Haritası (2026-10-20)

## Çalışan başlangıç kabiliyetleri
- [x] Türkçe masaüstü prototipi, yerel proje yönetimi, temel Godot/Web/Flutter akışları.
- [x] Codex/Claude/Gemini CLI görev sarmalayıcıları ve kısıtlı yerel test komutları.
- [x] Çekirdek testleri, basit motor CI şablonları, GitHub Actions.
- [x] Hata hafızası, onay kuyruğu, AI şirket gündemi, sürüm metaverisi radarı.

## Öncelikli doğrulama/geliştirme (bitmiş diye sunma)
- [ ] **P0 — Windows uçtan uca kurulum:** temiz Windows'ta Python, Git, AI CLI kurulum; WinGet bozuksa akış; hesap girişleri ve GUI kullanılabilirliği.
- [ ] **P0 — Güvenlik denetimi:** subprocess allowlist, shell arg güvenliği, path traversal, prompt injection, kimlik bilgisi/log temizliği, güncelleme rollback.
- [ ] **P0 — Gerçek motor testleri:** Godot/Unity/Unreal/Flutter/Kotlin/Web için kendi resmi SDK veya CI doğrulaması; başarısızlıklarda açık durum.
- [ ] **P0 — Veri güvenliği:** public repo için secret taraması, repo-safety ve test fixture sınırları; kişisel `.studio` dışlama.
- [ ] **P1 — Orkestrasyon:** görev grafiği, bağımlılık, güvenilir retry bütçesi, bağımsız QA kanıtı, kullanıcı kabul ekranı.
- [ ] **P1 — Benchmark:** model başına başarı oranı, gecikme, toplam işlem/süre, manuel denetim sıklığı (abonelik kotası API'den okunamayabilir).
- [ ] **P1 — AI PR önerisi:** kendi çekirdeğini geliştirmek için draft PR, yeniden test, review, geri alma, sahibin son onayı.
- [ ] **P1 — IDE/motor entegrasyon:** Godot MCP'nin doğrulanması, Unity Editor/Unreal Editor bağlantılarının kontrollü testleri.
- [ ] **P1 — Görsel döngüsü:** ChatGPT/Gemini 2D brief'i, Meshy 3D asset katalogu, lisans/optimizasyon ve manuel oyun içi kabul testi.
- [ ] **P2 — Teknoloji radarı:** resmî kaynak karşılaştırması, lisans/güvenlik, test önerileri; kazancı ölçmeden otomatik yükseltme yok.
- [ ] **P2 — Finans paneli:** doğrulanmış fiyat ve tarih, aylık gider uyarısı, başabaş analizi; harcama otomatik değil.
- [ ] **P2 — Yayın/ürün analitiği:** kullanıcı onaylı mağaza dağıtımı, telif ve gizlilik kontrolleri, geri bildirim toplama.

## Kabul ölçütü
Bir özelliği 'bitti' işaretlemek için kod + güncel test + örnek çıktı + kılavuz + rollback gerekli. CI yeşil tek başına gerçek Unity/Unreal/Android testinin kanıtı değildir.


## P0 güvenlik ilerlemesi — inceleme PR'ı
- [x] Yeni projelerin özel .studio/ hafızasını Git dışına al; CI yardımcılarını .github/scripts/ içinde takip et.
- [x] Staged özel dosyaları masaüstü uygulamasının GitHub ilk yayın akışında kontrol et.
- [x] Yapay zekâ konseyi, eski ayar açık olsa bile onay olmadan çekirdek talimatı etkinleştiremez.
- [x] Kod etkinleştirmesi GUI sahibinin açık onay bayrağını ister.
- [x] AI tarafından değiştirilen çekirdek testleri, Docker ön yüklemesi yoksa durur; host'ta çalışmaz.
- [ ] Docker/Windows/WSL entegrasyon testi, imaj digest sabitleme ve daha güçlü VM izolasyonu.
- [ ] AI kodlayıcı CLI'nın yetkilerini ayrıca sınırla; sandbox yalnızca aday regresyon testini kapsıyor.
- [ ] Geçmiş commit'lerde sızmış özel verileri/anahtarları ayrıca denetle ve gerekiyorsa sırları döndür.
