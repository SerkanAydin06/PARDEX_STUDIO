# AI Ekiplerine İlk Görevler

Birden fazla model aynı commit'i bağımsız değiştirmesin. Her görev ayrı dal ve PR olsun.

| Sıra | Rol | Görev | Çıktı |
|---|---|---|---|
| 1 | Codex / kod | `app/core.py` ve PowerShell kurulumuna güvenlik + Windows sağlamlık denetimi | Kanıtlı küçük PR ve test |
| 2 | Claude / mimari | Çekirdek/game hafıza izolasyonu ve sınırlı token kullanımı raporu | Mimari risk listesi; kod değişiyorsa ayrı PR |
| 3 | Gemini / bağımsız QA | Gerçek ve simüle test iddialarını gözden geçir; sahte başarı durumlarını ara | Ayrıntılı QA raporu ve test önerileri |
| 4 | Codex / GUI | Teknik olmayan kullanıcı için üç adımlı ekran: Başlat → Üret → Onayla | Kullanılabilirlik PR'ı |
| 5 | Farklı ajan / güvenlik | Agent yetkileri, otomatik güncelleme, GitHub secret/permissions denetimi | Check-list, riskli yerler, önerilen güvenli değişiklikler |
| 6 | İki bağımsız ajan / karar | Kısa görevler için model yönlendirme benchmark planı | Karşılaştırma yöntemi; gerçek veri gelince politika değişimi |

**PR biçimi:** amaç, sınırlı dosyalar, değişen davranış, test komutları ve sonuçlar, risk/geri alma, abonelik-kota tahmini, manuel kabul gereksinimi.

**Onaysız yapılmayanlar:** ücretli servis, model/API faturası, otomatik canlı kod kurulumu, hesap yaratma, lisans değişimi, PR merge ve oyun yayınlama.
