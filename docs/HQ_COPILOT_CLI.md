# GitHub Copilot Pro — isteğe bağlı dördüncü AI çalışanı

PARDEX Şirket Merkezi, hesabının mevcut GitHub Copilot Pro aboneliğini **Copilot CLI** üzerinden kullanabilir. Bu sağlayıcı isteğe bağlıdır; Claude, Codex ve Gemini'nin varsayılan rol önceliklerini değiştirmez.

## Kurulum (Windows)

- Node.js 22+ ve PowerShell 6+ kurulu olmalı.
- `02_AI_CLI_KUR.cmd` → ilk üç aracı tekrar kurmak istemiyorsan ilk soruda **HAYIR**, Copilot sorusunda **EVET** yaz.
- Alternatif: `npm install -g @github/copilot` (veya `winget install GitHub.Copilot`).
- PowerShell'de **`copilot login`** komutunu çalıştır; GitHub Copilot Pro hesabınla OAuth girişini tamamla.
- `09_SIRKET_PANELI.cmd` ile şirketi aç → **Model yönlendirme** ekranında **Copilot** görünüyor mu kontrol et. Kod yazma/inceleme veya planlama rolüne istersen elle ata.

## Nasıl çalışır?

- Copilot otomatik sıralamada **yedek sağlayıcıdır**; diğer üç sağlayıcı kuruluysa mevcut varsayılanları değiştirmez. İstersen belirli role Copilot'u seçebilirsin.
- Kodlama görevlerinde sadece `view,glob,grep,edit,create,apply_patch` dosya araçlarını; salt okunur işlerde sadece `view,glob,grep` araçlarını kullanabilir. Terminal komutları, web erişimi, MCP araçları, alt ajanlar ve güvensiz toplu izin bayrakları verilmez. Kod dışındaki testleri PARDEX'in kendi test çalıştırıcısı denetler.
- İstemler standart girdiden (stdin) iletilir. `--model` yalnızca kullanıcı açıkça belirlediğinde eklenir; normal durumda Copilot CLI'ın seçili/hesap varsayılan modeli geçerlidir.
- AI çağrıları PARDEX günlük/haftalık/departman çağrı bütçelerine dahil olur. GitHub Copilot Pro'nun **AI credits / premium requests** kullanımını abonelik panelinden ayrıca takip et; PARDEX gerçek kredi miktarını veya kalan kotayı ölçmez.
- Kod yazan sağlayıcı, aynı paketin bağımsız incelemesini yapamaz; en az iki **farklı sağlayıcı** kurulu olmalı. İki bağımsız denetçi ayarlıysa en az üç ayrı sağlayıcı gerekir.
- **Ar-Ge web rolüne Copilot atanmaz**; güvenlik politikası internet araçlarını engeller. Ar-Ge için Claude veya Gemini gerekir.
- Native CLI işletim sistemi sandbox'ı değildir. Copilot dosya izinlerini sınırlasak da sistemi yalnızca ayrı çalışma kopyası ve güvenilir hesap ortamında dene.
- PARDEX, Copilot CLI çağrısına dışarıdan verilmiş GitHub PAT veya BYOK sağlayıcı ortam değişkenlerini taşımamaya çalışır; yerel Copilot OAuth hesabı kullanılmalıdır.

## Kaynaklar

- GitHub CLI kurulum: https://docs.github.com/en/copilot/get-started/cli-quickstart
- Programatik kullanım ve stdin: https://docs.github.com/en/copilot/how-tos/copilot-cli/automate-copilot-cli/run-cli-programmatically
- İzinler ve araç kısıtları: https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli/allowing-tools
- Kimlik doğrulama: https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/authenticate-copilot-cli

**Doğrulama sınırı:** GitHub Actions Linux testleri, gerçek Windows + Copilot Pro OAuth oturumunda uçtan uca testi yerine geçmez.