# Ürün Yol Haritası (2026-10-20)

## Çalışan başlangıç kabiliyetleri
- [x] Türkçe masaüstü prototipi, yerel proje yönetimi, temel Godot/Web/Flutter akışları.
- [x] Codex/Claude/Gemini CLI görev sarmalayıcıları ve kısıtlı yerel test komutları.
- [x] Çekirdek testleri, basit motor CI şablonları, GitHub Actions.
- [x] Hata hafızası, onay kuyruğu, AI şirket gündemi, sürüm metaverisi radarı.

## Tamamlanan 2A: AI Görev Merkezi
- [x] Yerel SQLite kalıcı iş kuyruğu; öncelik ve tek kuyruk çalışanı; sahip onayı, görsel/oynanış kabulü, açık manuel kurtarma.
- [x] AI çağrısı harcamayan önizleme ve mevcut günlük yerel kullanım sınırı.
- [ ] Gerçek AI CEO, görev grafiği, otomatik bağımsız QA, iş başına gerçek token/fiyat ölçümü, arka plan işçileri ve gelir takibi henüz YOK.

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

## Aşama 2B — Yapılan ilk paket
- [x] Basit/Normal/Kritik planlar, kalıcı görev bağımlılıkları ve sahibin aşama bazlı kabulü.
- [ ] Gerçek otomatik AI CEO planlaması, bağımsız entegrasyon testleri, gerçek maliyet ölçümü, daemon ve PR işçisi daha sonra. Mevcut uygulama onaylı yerel prototiptir.

## Phase 2C — AI performans telemetrisi
- Yerel, özel SQLite'da deneme geçmişi ve süre.
- Teknik test ile insan onayını ayıran metrikler.
- Pilot önerisi için yeterli örnek şartı ve kullanıcı onayı.
- Gelecek: gerçek ölçülebilir kredi/token adaptörleri, bağımsız QA ve A/B testleri.


### Aşama 2D — Bağımsız AI Kalite Müdürü
- [x] Ayrı AI sağlayıcısı kullanarak sahip onaylı QA sözleşmesi
- [x] PASS/FAIL delil biçimi; başarısız veya kanıtsız inceleme geçersiz
- [x] Offline Codex/Gemini karşılaştırma pilotu, aynı senaryo/test profili ve gözlenen sonuçlar
- [x] Türkçe AI Genel Müdür arayüzünden QA raporu ve pilot yönetimi
- [ ] Gerçek VM/read-only denetçi sandbox'u ve sabitlenmiş tekrar üretilebilir deneyler (2E)
- [ ] Sağlayıcı desteklerse doğrulanabilir gerçek token/kredi raporu; otomatik model geçişi yok (2E)


## Aşama 2E — ölçüm ve güvenlik kontrolü (PR aşamasında)
- [x] Sıkı opt-in mod, native AI CLI işlerini ortak girişlerde durdurur.
- [x] Özel proje hafızası dışarıda kalacak biçimde kaynak kod parmak izi.
- [x] Kullanıcı onaylı Codex CLI JSONL token metaverisi içe aktarımı; ücret doğrulaması yok.
- [x] Türkçe AI Genel Müdür güvenlik ve metaveri kontrolü.
- [ ] İzole AI worker/container/VM, imaj digest güveni, gerçek Windows/WSL deneyi.
- [ ] Sağlayıcıların güvenilir maliyet verileri, otomatik JSONL toplayıcı, gerçek A/B pilotu.


## Aşama 3 — PARDEX Şirket Merkezi (yerel web paneli)
- [x] 11 departman, haftalık çağrı bütçeleri, K0/K1/K2 kademeleri, acil durdur.
- [x] CEO K0 planlayıcı (0 token) ve isteğe bağlı tek çağrılık AI planı; kural ihlali hedeflerini engeller.
- [x] Onay → çalıştır → teslim → kabul döngüsü; kod işleri mevcut Görev Merkezi kuyruğundan geçer.
- [x] Fikir puanlama ve aşama tahtası, finans defteri, olay günlüğü, 0 token sabah brifingi.
- [x] Yerel güvenli HTTP sunucu (127.0.0.1, oturum anahtarı, Host/Origin kontrolü, CSP) ve mobil uyumlu arayüz.
- [ ] Gerçek Windows uçtan uca denemesi, video render/ses hattı, zamanlanmış haftalık departman raporları, kaynaklı web araştırması.

## Aşama 4 — Proje Hattı
- [x] Plan sohbeti → "Bunu yap" → CEO iş paylaşımı → üretim → K0 test + farklı sağlayıcıyla bağımsız inceleme → en fazla 2 düzeltme → teslim/kabul/değişiklik.
- [x] Ürünler şirket deposu dışında, kendi git deposunda; paket başına yerel commit.
- [x] Abonelik tabanlı model yönlendirme (takma adlar, effort), başarı istatistiğiyle öğrenme, patron sabitlemesi.
- [x] Departman dersleri (K0), 0 token departman raporu, yalnızca önemli kararlar için patron soruları.
- [x] Kaynaklı Ar-Ge (en az 2 farklı ve erişilebilir kaynak), üyelik önerileri yalnızca patrona.
- [ ] Codex ve Gemini CLI ile gerçek uçtan uca deneme; Windows'ta deneme; Unity/Unreal test hattı.
