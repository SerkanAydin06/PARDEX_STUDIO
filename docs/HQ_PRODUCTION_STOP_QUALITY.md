# Üretimde İptal / Acil Durdurma ve Son Kalite Kapısı

Bu düzeltme iki üretim engelini giderir.

**Durdurma:** “Projeyi iptal et” bir ürünü iptal eder; global acil durdurma, çalışan üretimi `durdu` durumuna getirir. Üretim döngüsü paket başlangıcında, AI dönüşlerinde, testler ve kalite denetimi sonrasında, Git kaydından ve teslimattan önce durma durumunu denetler. Gerçek CLI üretiminde `core.run` ek bir iptal kontrolü alır: çalışan alt süreç periyodik olarak kontrol edilir; durdurma talebinde süreç ve alt süreç ağacı sonlandırılır. Linux/macOS'ta ayrı süreç grubu, Windows'ta `taskkill /T /F` kullanılır. Yarım kalan kod değişiklikleri **silinmez**; tekrar üretimde incelenebilir.

**Teslim:** Hiç tamamlanmış paket yoksa teslim engellenmeye devam eder. Son otomatik motor testi **gerçekten başarısızsa** ürün `durdu` durumuna alınır ve “Değişiklik iste” yoluyla düzeltme bekler; `TESLIM.md` oluşturulmaz. Kullanıcı daha önce açıkça “Testsiz devam et” seçmişse yalnızca motorun **bulunmaması / testin yapılamaması** geçici olarak teslim raporunda belirtilerek kabul edilebilir; başarısız çalışan test buna dahil değildir. Oyunun görsel oynanışı, kaynak tüketimi ve gerçek cihaz testi ayrıca kullanıcı tarafından yapılmalıdır.

## Test sınırları

Bu paketin çevrimdışı regresyonları iptal, duraklatıp devam, gerçek alt süreç sonlandırma, son test hatası ve testin atlanması senaryolarını kapsar. GitHub Actions testleri Linux'ta; gerçek Windows, Godot ve giriş yapılmış Claude/Codex/Gemini CLI entegrasyonu ayrıca doğrulanmalıdır.
## İptal kesindir

- İptal edilen proje hiçbir yoldan yeniden canlanmaz: veritabanı katmanında `iptal` aşaması başka bir aşamaya çevrilemez.
- İptal, projenin açık sorularını kapatır; Ofis ekranında görünmezler ve cevaplanamazlar. İptal edilmiş projeye yeni soru oluşturulmaz.
- "Bunu yap" sırasında CEO iş planı ve plan sonrası departman çağrıları da iptal edilebilir: çalışan AI CLI bir saniye içinde durdurulur ve proje üretime geçmez.
