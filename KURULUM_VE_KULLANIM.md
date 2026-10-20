# Ultra Pro AI Studio v5 — Kod bilmeyenler için kullanım

## 1 — Önce programı aç

1. ZIP'i Masaüstünde **yeni bir klasöre** çıkar. Eski v4 klasörünün üzerine yazma.
2. `01_ULTRA_PRO_STUDIO_AC.cmd` dosyasına çift tıkla. Python/Tkinter eksikse Windows dijital imza kontrolü yapılan resmî Python kurulumuna **ayrıca onay vermen** istenir. Bozuk `winget` gerekli değildir.
3. Program açılmazsa hata penceresinin görüntüsünü paylaş; şifre veya token gönderme.
4. `Sistem` bölümünde hangi motor ve CLI araçlarının bulunduğunu gör.

## 2 — AI ekibine giriş

1. `02_AI_CLI_KUR.cmd` ile CLI araçlarının kurulmasını başlat (Node.js gerekebilir).
2. `Sistem` içinde **Claude giriş**, **Codex giriş**, **Gemini giriş** düğmelerini kullan.
3. Mevcut üyelik hesaplarını seç; API anahtarı üzerinden ayrıca ücretli kullanım açma. Servislerin kendi kotası geçerlidir.
4. Bir tek görevi önce `Codex` ile dene. Sonra istersen `Claude planı → Codex kodlama → test → Gemini kontrolü` akışını kullan.

## 3 — Şirket merkezini işlet

1. **AI Şirketi** sekmesini aç.
2. `Şirket hedefin veya yeni fikrin` kutusuna örneğin şunu yaz: *"Önce 2D mobil bulmaca oyunu yapalım. 14 günde oynanabilir MVP; reklam mı tek seferlik satış mı daha uygun?"*
3. **Toplantı gündemi oluştur (0 AI)** düğmesi yerel rapor ve gündem çıkarır; kota kullanmaz.
4. **Claude + Gemini kurul görüşü (2 AI)** için onay verirsen en fazla iki ayrı görüş alır. Günlük AI toplantı sınırı vardır. Bir hesabın kotası dolmuşsa rapor başarısızlığı açıkça belirtir.
5. Ücretsiz yerel model kullanmak istiyorsan [Ollama resmi sayfasından](https://ollama.com/download/windows) Ollama kur, terminalde `ollama pull qwen3:4b` gibi uygun bir model seç. Model boyutu bilgisayarının belleğine uymalıdır. Model hazırsa `Yerel ücretsiz modelden görüş al` kullanılabilir; sistem otomatik model indirmez.
6. Bir oyun sunucusu / uygulama backend'i araştıracaksan `web`, `mobile`, `game`, `realtime` türünü seçip **Sunucu seçenekleri için öneri üret**. Resmî fiyat sayfası, tarih ve gereksinim kontrol listesini aç. Bu yalnızca öneridir; gerçek teklif gereklidir.
7. Yeni abonelik için adını, USD/ay ücretini ve **senin varsaydığın** saat tasarrufunu gir. ROI düğmesi hesap yapar ve sahibin onay kuyruğuna ekler. Saatlik değer gerçek gelir anlamına gelmez.
8. Bir satır seçip **Öneriyi onayla** veya **Reddet**. Onay, satın alma/deploy işlemi gerçekleştirmez.

## 4 — Proje oluştur, yazılım geliştir, sonra sen dene

- `Projeler` → yeni Godot/Web projesi; Flutter SDK kuruluysa Flutter. Unity/Unreal/Kotlin için önce motorun kendi uygulamasında proje oluştur, sonra bağla.
- `AI Ekibi` → hedefi yaz, `Otomatik` ve `Dengeli` ile başla. Gereksiz yere paralel ajan çağırma.
- `Test & Öğrenme` → testleri kontrol et. Unity/Unreal için **tam motor derleme/test entegrasyonu yok**; sonuç 'test edilmedi' yazmalıdır.
- Oyunu çalıştır, görsel/oynanış kontrolünü bizzat yap, onayı ver.
- `Görsel Atölyesi`: 2D brief'ini ChatGPT/Gemini, 3D brief'ini Meshy arayüzüne taşı. Aboneliklerin görsel API'leri sessizce kullanılmaz.

## 5 — GitHub üzerinde sürekli toplantılar

1. `Git` ve `GitHub CLI` kurulu olmalı; `gh auth login` ile kendi hesabına giriş yap.
2. **Çekirdek stüdyoyu** ayrı bir GitHub **özel** deposuna göndermek için `03_CEKIRDEGI_GITHUBA_YUKLE.cmd` çalıştır. Önce adını ve yayınlama onayını sorar.
3. GitHub deponun **Settings → Actions** kısmında izinleri incele. Issue (sorun) oluşturma özelliği açık olmalı. `.github/workflows/company-board.yml` haftalık, `monthly-strategy.yml` aylık rapor/karar gündemi açacaktır.
4. **İsteğe bağlı** OpenRouter Free: [openrouter.ai](https://openrouter.ai) üzerinden kendi hesabını kendin aç; API anahtarını GitHub **Settings → Secrets and variables → Actions → New repository secret** alanına `OPENROUTER_API_KEY` adıyla gir. Sohbete veya kod dosyalarına yapıştırma. Haftalık GitHub akışı `openrouter/free` modeline yalnızca *sabit, kamuya açık* bir gündem gönderir; özel oyun kodlarını göndermez. Ücretsiz model limitleri vardır; model seçimi değişebilir. Kullanmayacaksan hiç ekleme.
5. GitHub Actions'da çalışma gerçekleştiğinde **Issues** sekmesinde haftalık toplantı notlarını gör. Bu GitHub işleri Claude/ChatGPT Pro girişini kullanmaz. Bilgisayar kapalıyken oyun kodu kendi kendine geliştirilmez.
6. Her oyun deposu için oyunun `GitHub` sekmesinden o motorun test şablonunu ayrıca ekleyebilirsin.

## 6 — Çekirdek kendi nasıl öğrenir?

- Her oyun kendi `.studio` klasöründe görevler ve hatalar biriktirir.
- İki **ayrı oyunda aynı kanıtlı hata türü** görülürse `Çekirdek Konseyi` kodlama talimatının değişmesini önerebilir.
- Codex önerir, Claude/Gemini değerlendirir. Düşük riskli metin kuralları, konsey ayarında önceden izin verilmişse otomatik sürümlenir ve yedeklenir.
- Python çekirdek kodu için daima ayrı deneme kopyası, test, iki AI incelemesi ve **senin 'onaylı kodu uygula' düğmesiyle açık onayın** gerekir.
- İnternet Radarı yeni model/motor sürümü olduğunda **resmî GitHub release bilgilerini** gösterir. Değişiklik doğrudan kurulmaz.
- Aynı motor için yeterli doğrulanmış Codex/Gemini geçmişi varsa otomatik görev rotası ayarlanabilir. Gerçek token sayısı ve başarının nedeni bilinmiyorsa güçlü verim artışı iddia edilmez.

## 7 — Ne otomatik DEĞİL?

Hesap açma ve doğrulama, özel oyun varlıklarının 2D/3D üretilmesi, tam Unity/Unreal derleme, fiziksel Android cihaz testi, oyun içi görsel/oynanış kabulü, gerçek mağaza yayımı, ücretli sunucu ve üyelik satın alma, müşteri destek operasyonları. Bunlar ayrı, açık yetkilendirilmiş entegrasyonlar ve canlı testler gerektirir. Aynı şekilde 'sürekli kendini eğitme' model ağırlıklarını eğitmek değildir: kanıtlı deneyimler ve rol kuralları sürümlenir.

## 8 — İlk plan

Büyük ekip kurmadan **tek bir gelir denemesi** yap: 14 gün içinde minimal prototip, ardından oynanış/görsel senin onayın, test ve yayın maliyet listesi. Gelir garantisi yok; fikri küçük maliyetle doğrula. Tüm projeleri değiştirecek kararı ilk oyun için alma.
