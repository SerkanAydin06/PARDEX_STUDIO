> **AI katkı rehberi:** [AGENTS.md](AGENTS.md) · [CLAUDE.md](CLAUDE.md) · [GEMINI.md](GEMINI.md) · [Mimari](docs/ARCHITECTURE.md) · [Öncelikler](docs/ROADMAP.md) · [AI görevleri](docs/AI_TASKS.md) · [PR rehberi](CONTRIBUTING.md).

> Bu depo herkese açıktır. Özel oyun kaynaklarını ve hesap bilgilerini bu depoya yüklemeyin.

# Ultra Pro AI Studio v5.1 — AI Şirket Merkezi + Kalıcı Görev Kuyruğu (Windows)

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

Ayrıntılar: [KURULUM_VE_KULLANIM.md](KURULUM_VE_KULLANIM.md), [TEST_RAPORU.md](TEST_RAPORU.md).

## Aşama 2A: Kalıcı Görev Merkezi

Görevler yerel SQLite veritabanına kaydedilir. Sahip onayı olmadan AI çağrısı başlamaz; biten iş kullanıcı görsel/oynanış kabulü bekler. Başarısız işler kendiliğinden tekrar edilmez. Gerçek kalan abonelik kotası **bilinmez**. Ayrıntılar: [Aşama 2A](docs/PHASE2_TASK_CENTER.md).
