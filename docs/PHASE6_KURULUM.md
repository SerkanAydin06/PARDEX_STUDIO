# Aşama 6 — Kolay kurulum

## `00_KUR.cmd` (tek tık)
PowerShell ile çalışır, Python gerektirmez.
1. Python 3.12, Git ve Node.js LTS (en az 20) eksikse listeler ve onayınla `winget` ile kurar. Microsoft Store'un sahte `python` kısayolu "kurulu" sayılmaz. winget yoksa indirme sayfalarını açar ve yeniden çalıştırmanı ister.
2. Eksik AI programlarını resmî npm paketlerinden kurar: `@anthropic-ai/claude-code`, `@openai/codex`, `@google/gemini-cli`.
3. Şirket panelini açar.

Hiçbir hesap bilgisi ya da API anahtarı istenmez veya kaydedilmez.

## Panelde Kurulum ekranı
- Python, Git, Node.js ve üç AI programı için kurulu mu, sürüm, giriş durumu gösterilir. "Sıradaki adım" tek cümleyle söylenir. Kurulum eksikse panel bu ekranla açılır.
- **Kur:** AI programları için npm, Git/Node.js için winget kullanılır. Komutlar sabittir; kullanıcı metni komuta girmez. Git/Node.js kurulduktan sonra panel yeniden açılmalı.
- **Giriş yap:** Programın kendi giriş akışını görünür bir pencerede açar (`claude auth login`, `codex login`, `gemini`). Giriş bilgisi PARDEX'e yazılmaz.
- **Giriş kontrolü (0 token):**
  - Claude: `claude auth status`
  - Codex: `codex login status`
  - Gemini: durum komutu olmadığı için önce ayar ve giriş dosyalarının varlığına bakılır; bu yalnızca giriş ihtimalidir. Emin olunamazsa "doğrulanamadı" gösterilir ve **Test et** düğmesi çıkar. Giriş yoksa Gemini istek göndermeden hata verir (0 kota); giriş varsa tek küçük çağrı yapılır.
- **GitHub Copilot CLI (isteğe bağlı):** Kur (`@github/copilot`), Giriş yap (`copilot login`), Test et. Girişi sistemin kimlik deposunda tutulduğu için yalnızca test sonucuna güvenilir. Girişsizken CLI hiçbir şey göndermeden reddeder (0 kota); girişliyse test 1 küçük istek kullanır (Copilot Pro kredisi). Kurulu değilse "sıradaki adım"da önerilmez.
- Testlerde ve girişlerde `GH_TOKEN`, `COPILOT_GITHUB_TOKEN` gibi token değişkenleri kaldırılır; abonelik girişi kullanılır.
- "Giriş yap"a basınca eski test sonucu silinir; "Test et" her zaman yeniden denenebilir.
- Yalnızca **doğrulanmış** girişler "hazır" sayılır. Şirket, en az iki farklı AI doğrulanınca hazırdır.

## Doğrulama
- PowerShell 7.4 ayrıştırıcısıyla betikte 0 hata. Sahte programlarla dört senaryo çalıştırıldı: boş makine, eski Node.js, eksik AI programları, winget yok.
- Gerçek ortamda:
  - Panelden **Kur** ile Codex 18 saniyede kuruldu.
  - Gerçek `claude auth status` / `codex login status` doğru okundu.
  - Gerçek Gemini testi girişsiz durumda 2 saniyede, kota harcamadan "giriş yapılmamış" dedi.
- Gerçek Windows'ta (winget, UAC, yeni pencerede giriş) henüz denenmedi.

## Giriş testi korumaları
- Test et, acil durdurma ve günlük/haftalık/CEO departmanı çağrı sınırlarına uyar; sıkı izolasyonda native CLI testi engellenir.
- Her başlatılan test denemesi, başarısız olsa da, günlük kullanım ve şirket defterine 1 çağrı olarak yazılır. Bu yerel deneme sayısıdır; gerçek sağlayıcı token tüketimi değildir.
- Yalnızca başarılı çıkış koduyla tam `OK` yanıtı doğrulamadır; hata metnindeki harfler başarı sayılmaz.
- Gemini giriş dosyasının varlığı tek başına doğrulanmış giriş değildir. Başarılı test kanıtı 15 dakika geçerlidir; eski kayıtlar tekrar doğrulama ister.
