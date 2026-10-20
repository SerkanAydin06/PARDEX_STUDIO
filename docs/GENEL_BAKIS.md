# PARDEX — ayrıntılı genel bakış

> Eski ana sayfa metni. Kısa giriş için [README](../README.md).

> **AI katkı rehberi:** [AGENTS.md](../AGENTS.md) · [CLAUDE.md](../CLAUDE.md) · [GEMINI.md](../GEMINI.md) · [Mimari](ARCHITECTURE.md) · [Öncelikler](ROADMAP.md) · [AI görevleri](AI_TASKS.md) · [PR rehberi](../CONTRIBUTING.md).

> Bu depo herkese açıktır. Özel oyun kaynaklarını ve hesap bilgilerini bu depoya yüklemeyin.

# Ultra Pro AI Studio v5.1 — AI Şirket Merkezi + Kalıcı Görev Kuyruğu (Windows)

## ⭐ Yeni: PARDEX Şirket Merkezi (yerel web paneli)

`09_SIRKET_PANELI.cmd` dosyasına çift tıkla. Tarayıcıda sade bir **Patron Ofisi** açılır. Hedef yazarsın; CEO işleri 11 departmana böler. Her işi sen onaylar, çalıştırır ve kabul edersin. Departmanların haftalık AI çağrı bütçesi, 0 token K0 / ucuz K1 / kod için K2 kademeleri, fikir puanlama, finans defteri ve acil durdur bulunur. Telefon tarayıcısında da çalışır; yalnızca bu bilgisayardan erişilir. Ayrıntılar: [Aşama 3](PHASE3_HQ.md).

**Proje Hattı (Aşama 4):** `Projeler` sekmesinde Ürün Müdürüyle oyun/uygulamanın ana hatlarını konuşursun. "Bunu yap" dediğinde CEO işi paketlere böler. Ekip yazar, farklı bir AI denetler, gerekirse düzeltir ve hazır hâlini sana teslim eder. Ürünler şirket deposunun dışında, kendi git deposunda tutulur. Modeller Claude/Codex/Gemini aboneliklerine göre en ekonomik uygun şekilde seçilir; sana yalnızca önemli kararlar sorulur. Ayrıntılar: [Aşama 4](PHASE4_PROJE_HATTI.md).


> **Çalışan, test edilmiş prototip; bitmiş, sınırsız, tamamen otonom bir şirket değil.**

Bu proje birden fazla Godot, Unity, Unreal, Flutter, Android/Kotlin ve Web projesi için ortak çekirdeğe sahip, Türkçe Tkinter masaüstü kontrol merkezidir. Ana amacı **yüksek doğrulama oranı / az ve kısa AI çağrısı**dır. Token tüketimini veya aboneliklerin gerçek kalan kotasını otomatik okuyamaz.

## İş bölümü

| Departman | Yapabildiği | Sınır |
| --- | --- | --- |
| AI yönetim kurulu | Proje hedefinden gündem ve Claude/Gemini raporu çıkarır | Önermeler otomatik işleme dönüşmez |
| Oyun/uygulama ekibi | Küçük kod görevleri, plan, kısıtlı motor kontrolleri | Motor SDK ve gerçek test ortamı gerekli |
| QA ve güvenlik | Test sonuçları, bağımsız inceleme, hata hafızası | Kullanıcı görsel/oynanış kontrolü yapar |
| Ar-Ge | Resmî sürüm radarı, ücretsiz araç listesi | İnternette bulduğu yeni kodu indirmez/çalıştırmaz |
| Finans ve sunucu | Resmî fiyat kaynakları, tarihlenmiş örnekler, senaryo ROI | Gerçek fatura/kota ve yerel vergiler doğrulanmalı |
| Ürün ve büyüme | MVP, mağaza/gelir gündemi, aylık toplantı | Pazarlama ve yayınlama otomatik değil |
| Çekirdek denetimi | Ayrı kopyada kod değişimi/test/iki AI inceleme; rol kuralları | Canlı çekirdek koduna kurulum sahibin açık onayına bağlı |

**Kalıcı izolasyon:** Her projenin `.studio/` hafızası ayrı; küresel olay ve rol hafızası `%LOCALAPPDATA%\UltraProStudio\brain` içinde. Şirket toplantı/karar kayıtları `%LOCALAPPDATA%\UltraProStudio\company` içinde tutulur. Tek oyun ortak çekirdek kodunu değiştiremez.

## İlk kullanım

1. ZIP'i bir klasöre tamamen çıkar. `01_ULTRA_PRO_STUDIO_AC.cmd` dosyasına çift tıkla. `winget` gerekli değil.
2. `02_AI_CLI_KUR.cmd` ile ihtiyaç duyduğun CLI araçlarını yükle. Her hesap için giriş adımlarını kendi uygulamasında tamamla.
3. `Projeler` bölümünde yeni bir Godot/Web projesi oluştur veya mevcut Unity/Unreal/Android/Flutter/Godot projesini bağla.
4. `AI Şirketi` bölümüne şirket hedefini yaz; önce **0 AI** gündemiyle başla. Gerekirse **Claude + Gemini** toplantısına onay ver.
5. `AI Ekibi` bölümünde görev oluşturabilir, `Gorev Merkezi` sekmesinden onaylayıp tek tek çalıştırabilirsin. Biten görevin oynanışını/görüntüsünü ayrıca sen kabul edersin.\n6. `AI Ekibi` bölümünden doğrudan görev de başlatabilir; `Test & Öğrenme` sonuçlarını incele. Oyun içi/görsel denemeyi sen yapıp onayla.
7. GitHub deposu açmak istiyorsan `03_CEKIRDEGI_GITHUBA_YUKLE.cmd` kullan; hesabında gerçek yayın yapmadan açık onay sorar.

## Ücretsiz / mevcut üyelik araçları

- Mevcut **Claude Pro → Claude Code**, **ChatGPT Pro → Codex**, **Google AI Pro → Gemini CLI**: kendi giriş akışları; sınırlı abonelik kullanımı.
- **Ollama:** Yerelde (RAM/VRAM uygunsa) küçük işleri ücretsiz modellerle çalıştırma. İstediğin modeli önce kendin kur; uygulama model indirmez.
- **OpenRouter / Free Models Router:** İsteğe bağlı ücretsiz bulut modeli. Ayrı hesap ve API anahtarı gerekir; ücretsiz limit ve servis koşulları vardır. Sadece GitHub haftalık kamuya açık gündemini incelemesi için kullanılabilir. **Başlangıçta kapalıdır.**
- **2D:** ChatGPT/Gemini görsel üretim arayüzlerinde üretim brief'i. **3D:** yalnızca Meshy. Bu aboneliklerin görsel üretim API'si otomatik çağrılmaz.

## GitHub otomasyonu

Çekirdeğin GitHub deposuna dosyaları yükleyince, `.github/workflows/` içinde:

- **kernel-tests.yml:** push/PR'da mevcut çekirdek unit testleri; ücretli AI yok.
- **kernel-radar.yml:** haftalık resmî GitHub sürüm meta verisi raporu; yeni kod yüklemez.
- **company-board.yml:** haftalık kurul gündemi ve resmi sürüm bilgileri için GitHub Issue oluşturur. `OPENROUTER_API_KEY` secret'ını **sen istersen** eklersen, kamuya açık ve sabit bir gündem için en fazla **1 ücretsiz model isteği** yapar.
- **monthly-strategy.yml:** aylık ürün/gelir kontrol listesi issue'su oluşturur; harcama/yayın yapmaz.
- **Dependabot:** Action güncellemelerini PR olarak sunar.

Bu dosyalar **stüdyonun çekirdek deposu** içindir. Oyun depoları için `GitHub` sekmesinden oyuna özel CI eklenir. İş akışlarını kullanmak için dosyaların GitHub varsayılan dalına yüklenmesi, Actions izninin ve Issue açmanın etkin olması gerekir. Zamanlanmış işler bazen gecikebilir.

## Kendini iyileştirme: Gerçek kapsam

- Test olaylarını ve tekrar eden hata sınıflarını kaydeder.
- Ortak rol talimatını değiştirmek için iki **farklı projede aynı doğrulanmış hata sınıfı**, iki AI onayı ve düşük risk gerekir. Rol metni sürümlenebilir ve geri alınabilir.
- Çekirdek kod önerileri orijinalin dışında test edilir. İki AI incelemesi ve mevcut testler geçerse **sen** bir düğmeyle uygularsın; her zaman yedek ve geri alma yolu bulunur.
- Görev yönlendirmesinde, **aynı motor için Codex ve Gemini'nin en az 10'ar doğrulanmış görevi** ve anlamlı başarı farkı varsa otomatik geçiş önerilebilir. Bu gerçek token maliyeti ölçümü değildir.
- İnternet radarı yalnızca resmi sürüm meta verilerini araştırır. Bir yazılımın gerçekten daha iyi olduğunu söylemek için A/B test ve bağımsız kontrol gereklidir.

## Önemli güvenlik ve ticaret notları

Sistem **kendiliğinden hesap açmaz, bedelsiz kotayı aşmak için sahte/çoklu hesap üretmez, ödeme yapmaz, sunucu açmaz, çekirdek kodunu onaysız etkinleştirmez, mağazada yayınlamaz**. Onay kuyruğundaki onay, dış dünyada bir işlem yapılmış anlamına gelmez. Dış servislerle gerçek işlemler ancak resmi yetkilendirme akışı eklenirse mümkün olur.

Oyunlarda makro/otomasyon yalnızca kendi oyunların, izin verilen modlama/erişilebilirlik veya platform kurallarına uygun senaryolar için tasarlanmalı; başka oyunlarda hile, anti-cheat aşma veya hizmet şartı ihlali ticari risk oluşturur.

**Doğrulama:** Python testleri ve sanal Linux GUI açılışı geçti. Gerçek Windows, güncel CLI hesapları, GitHub Actions koşusu, masaüstü oyun motorları, gerçek Android cihaz, satın alma ve dağıtım uçtan uca denenmedi. Bu alanlar 'tam otomatik hazır' diye sunulmaz.

Ayrıntılar: [KURULUM_VE_KULLANIM.md](../KURULUM_VE_KULLANIM.md), [TEST_RAPORU.md](../TEST_RAPORU.md).

## Aşama 2A: Kalıcı Görev Merkezi

Görevler yerel SQLite veritabanına kaydedilir. Sahip onayı olmadan AI çağrısı başlamaz; biten iş kullanıcı görsel/oynanış kabulü bekler. Başarısız işler kendiliğinden tekrar edilmez. Gerçek kalan abonelik kotası **bilinmez**. Ayrıntılar: [Aşama 2A](PHASE2_TASK_CENTER.md).

## Aşama 2B — AI Genel Müdür

Yerel risk temelli görev planları ve kullanıcı kabulüyle bağımlılık kontrolü eklendi. Basit işte 1, orta riskte 2, kritik işte en fazla 3 AI çağrısı için görev hazırlanır; gerçek kalan token kotası bilinmez. [Nasıl çalışıyor?](PHASE2_GENERAL_MANAGER.md)

## Aşama 2C — AI performans kanıtı (deneysel)

**AI Genel Müdür → AI performans raporu (ücretsiz)** ile görev türüne göre gerçek yerel AI çalışma süreleri, teknik test geçişleri, senin kabul/red kararların ve başarısız tekrarlar ayrı ölçülür. Yeterli kanıt oluşmadan model değiştirilmez; yalnızca kullanıcı onaylı küçük pilot önerilir. Gerçek token, abonelikte kalan kota veya para tasarrufu bilinmiyor. [Teknik ayrıntı](PHASE2C_MEASURED_AI.md).


## 2D — Bağımsız AI Kalite Müdürü
AI Genel Müdür, Normal/Kritik planlarda farklı sağlayıcıdan bir bağımsız inceleme görevi oluşturur. İnceleme sonucu yapılandırılmış PASS/FAIL ve kısa bulgular ile kaydedilir. Bu **bir AI iddiasıdır**; gerçek doğrulama ve sahibin kabulü ayrıca gerekir. Sahibi onaylamadan model değiştirilmez veya kod yayınlanmaz. Aynı iş/test profilini ayrı proje kopyalarında sınayan, AI çağrısı yapmayan A/B pilot kayıtları da arayüze eklendi. Ayrıntılar: [2D kalite ve A/B sınırlamaları](PHASE2D_INDEPENDENT_QA.md).


## 2E — Ölçüm ve güvenlik laboratuvarı (inceleme dalında)
Sıkı izolasyon, native abonelik CLI'larını **durduran** güvenlik kapısıdır; gerçek izole AI worker değildir. Başlangıç kod parmak izi ve kullanıcı onaylı Codex CLI JSONL token aktarımı bulunur. Veriler fatura/kota veya ölçülmüş tasarruf değildir. Ayrıntılar: [2E belgesi](PHASE2E_WORKER_EVIDENCE.md).

## Phase 2F — AI Operasyon Müdürü

`app/operations.py` çok projeli ücretsiz operasyon raporu ve **önceden tek tek onaylanmış** görevler için en fazla 2 çağrılık (teknik üst sınır 3), 45 dakikalık sınırlı çalışma vardiyası sunar. Onaylı görev kimlikleri sabitlenir; kuyruk değişirse, hata veya kota sınırı oluşursa durur. Sonuçların sahibi tarafından ayrıca kabul edilmesi gerekir. Native CLI için OS sandbox izolasyonu garanti edilmez. Ayrıntılar: `docs/PHASE2F_OPERATIONS.md`.


## 2H — Tek seferlik, önceden onaylı AI vardiya planlama

Bir veya iki ayrı ayrı onaylı işi belirli bir zaman aralığına kaydeden çevrimdışı `app/shift_scheduler.py` ve varsayılan kuru-çalıştırmalı `app/scheduler_cli.py` eklendi. **Kendiliğinden 7/24 çalışmaz, OS seviyesinde izole değildir.** Riskli native yürütme ayrıca iki açık izin gerektirir ve sıkı modda yasaktır. [Ayrıntılar](PHASE2H_SCHEDULED_SHIFTS.md).

Windows'ta **`05_AI_VARDIYA_PLANLAYICI.cmd`** Türkçe plan oluşturma, listeleme ve ücretsiz vade kontrolü ekranını açar. Bu pencere kendi başına bir zamanlayıcı servisi başlatmaz.


## Hızlı başlangıç — Tek görevle gerçek teslim

1. Python 3.10+ ve Godot 4.2+ kurun; bilgisayarınızda en az bir oturumu açık Codex, Claude Code veya Gemini CLI bulunmalı. Bunlar bu depo tarafından kurulmaz ve aboneliğe erişim garanti edilmez.
2. \`08_TEK_GOREV_TESLIM.cmd\` ile **Tek Görev Teslimi** ekranını açın. Alternatif: PARDEX ana ekranı > **AI ile tek görev teslimi**.
3. **AI ve Godot kontrolü** ile eksik programları görün. Henüz projeniz yoksa **Deneme Godot oyunu oluştur** düğmesi açık onayınızla yeni ve üzerine yazılmayan bir Godot 4 projesi oluşturur. Bu örnek sabit şablondur; AI çıktısı değildir.
4. Bir görev yazın ve değiştirilmesine izin verdiğiniz kod dosyalarını belirtin. Örneğin: \`Geminin hareket hızını iki katına çıkar\`; dosya \`scripts/player.gd\`.
5. Önizleme ücretsizdir. Native CLI izolasyon sınırını ve olası abonelik kullanımını onayladıktan sonra tek çağrı yapılır. AI komutu hata verirse değişiklik paketi oluşturulmaz.
6. Dosya farkını ve test raporunu inceleyin. Son onaydan sonra proje dosyaları değiştirilir; geri alma \`07_AI_DEGISIKLIK_INCELE.cmd\` aracındadır.

**Kanıt sınırı:** Çevrimdışı entegrasyon testinde AI çağrısı taklit edilir. Gerçek Windows/Godot ve üç sağlayıcı CLI kombinasyonu bu CI ortamında doğrulanmış değildir. Yerel CLI tam işletim sistemi sandbox'ı değildir; sıkı izolasyon modu onu engeller. Gerçek token bakiyesi, API faturası ve tasarruf ölçülmez.
