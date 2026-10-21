# GitHub güncellemesi ve otomatik yeniden başlatma

Yönetim Kurulu ekranındaki **Güncelle ve yeniden başlat** düğmesi, kullanıcı tarafından başlatılan uçtan uca bir işlemdir. Arka planda habersiz sürüm arayan bir servis değildir. Çalışan üretim/kod işleri tamamlanana kadar bekler; yeni yazma işlemlerini engeller, acil durdurma/iptal kullanılabilir. Bekleme aşaması iptal edilebilir; bir saat sonunda bekleme sonlanır. Proje ilerlemesi SQLite'da korunur, yarıda kesilip yeniden AI çağrısı yapılmaz.

## Bir defalık gereksinimler

- Pardex **main dalında, temiz bir Git çalışma kopyası** olmalı. ZIP olarak açılmış veya yerel değişiklikler içeren klasöre otomatik yazılmaz. Kullanıcı dosyaları silinmez/stash yapılmaz. ZIP kurulumları için bu sürüm otomatik dönüşüm yapmaz.
- Git ve **GitHub CLI (`gh`)** gerekir. Yönetim Kurulu'nda GitHub CLI kurulum ve resmî tarayıcı giriş düğmeleri bulunur. Kurulum sonrası yeni PATH için paneli yeniden açmak gerekebilir.
- GitHub hesabının `SerkanAydin06/PARDEX_STUDIO` deposunda ilgili yetkileri gerekir; okuma güncelleme için, yazma/PR birleştirme ise yayınlama için. Copilot girişi `gh` yetkilendirmesinin yerine geçmez. Pardex şifre/token istemez veya saklamaz; resmî CLI oturumu kullanılır.
- Aynı çalışma kopyasını ve veritabanını kullanan diğer masaüstü Pardex/CLI örneklerini kapalı tutun. Bu özellik kendi panelindeki işleri koordine eder; haricî süreçleri kapatmaz.

## GitHub'dan kurulum

1. Sabit şirket deposunun `main` SHA'sı alınır. GitHub Actions `unit`, `hygiene`, `docs-and-safety`, `windows-update` kontrolleri ve dönen diğer Actions kontrolleri başarılı olmalıdır. Eksik/başarısız/atlanmış kontrollerle kurulum yapılmaz; en fazla 15 dakika beklenir.
2. Sürüm sabit URL'den indirilir, SHA yeniden doğrulanır. Yalnızca mevcut sürümün devamı olan fast-forward güncellemesi kabul edilir.
3. Uygulama klasörü dışında önceki sürümün Git bundle yedeği alınır. Güncelleme yardımcısının çalışan sürümü de buraya kopyalanır.
4. Yardımcı hazır olduğunu bildirdikten sonra panel kapanır. Yardımcı **eski sürecin gerçekten çıkmasını** bekler. Sonra çalışma kopyasının değişmediğini doğrular; şirket ve görev kuyruğu veritabanlarının tutarlı SQLite yedeklerini alır.
5. Yeni sürüm uygulanıp aynı Python ve portla açılır. Başlangıçta veritabanı şeması ve arayüz dosyaları açılmalı; doğru yeni süreç/nonce ile hazır sinyali ve HTTP yanıtı alınmalıdır.
6. Kontrol başarısızsa yalnızca yardımcının kurduğu sürüm temiz kaldıysa eski commit'e dönülür, veritabanları geri yüklenir, eski panel açılır. Bu sırada dışarıdan dosya düzenlenmişse üzerine yazılmaz; hata ve yedek korunur. İşletim sistemi geri almayı da engellerse otomatik kurtarma garanti edilmez.

Yedekler `%LOCALAPPDATA%\UltraProStudio\updates\<kurulum-kimliği>\release-*` altındadır (Linux: `~/.ultra-pro-studio/updates/…`). `status.json`, `supervisor.log`, `panel.log`, `previous.bundle` ve SQLite yedekleri burada kalır; GitHub'a yüklenmez. Diskteki eski yedekler bu sürümde otomatik silinmez. Güncelleme yarıda kesilirse kilit canlı süreç kimliğiyle kontrol edilir; yedekler saklanır.

## Kendi düzeltmesini GitHub'a gönderme

Çekirdek adayının mevcut kopyada kod yazma → izole test → iki bağımsız AI denetimi adımlarını tamamladıktan sonra **GitHub’a birleştir ve yeniden başlat** düğmesini kullanın. Sonraki adımlar tek işlem olarak yürür:

- Adayın kaynak commit'i hem yerel sürüm hem GitHub main ile eşleşmelidir. Eski aday yeniden hazırlanıp doğrulanmalıdır.
- Test edilmiş hash'lere sahip, izinli `app/*.py` dosyalarıyla ayrı dal/PR oluşturulur. Ürünler, oturumlar, yerel günlükler gönderilmez.
- Tam PR commit'inin GitHub kontrolleri beklenir. main bu sırada değişirse birleştirme yapılmaz; PR korunur.
- Başarılı PR beklenen head SHA ile squash birleştirilir. Birleşmiş sürümün kontrolleri de geçince yukarıdaki yerel kurulum/yeniden açma akışı çalışır. Depo koruma kuralları aşılmaz.

Bu özellik AI'nın kendiliğinden tüm hatalara kod yazmasını sağlamaz; mevcut denetlenmiş adayı GitHub'a yayınlama ve kurulum adımlarını otomatikleştirir. GitHub'da birleştirilmiş sürüm yerelde açılmazsa yerel geri alma yapılır; GitHub commit'i sessizce geri alınmaz. PR ve testler inceleme için korunur.

Güncelleme/PR işlemi ek AI çağrısı tüketmez. Öncesindeki aday kodlama ve bağımsız incelemeler kendi mevcut kotalarını kullanır. Python/regresyon ve yerel süreç testleri yapılmıştır; gerçek Windows Defender, GitHub hesabı izinleri ve platforma özel süreç davranışları için kullanıcı bilgisayarında uçtan uca doğrulama gerekir.
