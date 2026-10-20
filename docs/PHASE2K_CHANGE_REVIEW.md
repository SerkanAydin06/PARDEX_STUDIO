# 2K — AI önerilerini güvenli inceleme ve kontrollü uygulama

Bu bir **insan onaylı kod değişikliği inceleme aracı**dır, otonom AI worker veya Docker/VM sandbox'u değildir. Varsayılan olarak AI çağrısı yapmaz ve token tüketmez.

## Kullanım (Windows)

`07_AI_DEGISIKLIK_INCELE.cmd` dosyasını aç. Gerçek oyun/uygulama klasörünü, AI'nın değişiklik hazırladığı **ayrı** öneri klasörünü ve incelenecek kaynak dosyalarını (virgülle) belirt. "Öneriyi incelemeye al" ile salt verilerden bir inceleme oluştur. SHA256 parmak izini ve farkları incele, daha sonra "ONAYLA ve uygula" ile açıkça izin ver. Geri alma düğmesi bu incelemenin daha önce değiştirdiği dosyaları eski içeriklerine döndürür.

Teknik konsol kullanımı: `python app/change_review_cli.py stage --project ... --proposal ... --files scripts/player.gd`, ardından `summary`, `diff` ve açıkça `apply --review-id REV-... --digest ... --confirm`. Onay bayrağı kimlik doğrulama değildir; işletim sistemi kullanıcı yetkileri geçerlidir.

## Koruma sınırları

- Gerçek proje klasörü, AI'nın öneri klasörü ve yerel inceleme kayıt deposu birbirinden ayrı olmak zorunda.
- Yalnızca listesi açıkça verilmiş en fazla 12 metin/kod dosyası; en fazla 128 KB/dosya ve toplam 512 KB. `.studio`, `.env`, `.git`, `.github`, AI politika dosyaları, symlink ve `..` gibi yollar engellenir.
- Öneriyle özgün dosyanın SHA256 değeri kaydedilir. İncelemeden sonra özgün kaynak, öneri veya yedek değişirse uygulama başlamaz.
- Sahip onayı ve birebir eşleşen inceleme SHA256 parmak izi gereklidir. Tekrar uygulama engellenir.
- Dosyalar aynı dizinde geçici dosya üzerinden tek tek atomik değiştirilir; hata durumunda eski kopyalar geri konulur. İşlem ortasında sistem kapanması çok dosyalı atomiklik sağlamaz: inceleme "applying" kalabilir; elle müdahale gerekir. Kod çalıştırılmaz ve otomatik yayın yapılmaz.
- Geri alma, uygulamadan sonra insan tarafından değiştirilmiş dosyaları ezmez; bütün dosyalar önce denetlenir.

## Bilerek eklenmeyenler

Bu sürüm Claude/Codex/Gemini'ye komut vermez, Docker izolasyonu sağlamaz, testleri otomatik geçirmez, yeni paketi `main` dalına veya ticari mağazaya göndermez. İzole AI çalıştırıcısı hâlâ ayrı bir aşamadır. Bir AI aynı yerel kullanıcı hesabının bütün haklarıyla zaten çalışabiliyorsa Python'daki onay bayrağı onun kötü niyetli davranışını teknik olarak engelleyemez; **gerçek erişim kontrolü işletim sisteminde veya bir sandbox'ta kurulmalıdır.**

## Test

`python -m unittest discover -s tests -p 'test_*.py' -q`, `python -m compileall -q app tests`, Windows GUI ve Windows/Docker uçtan uca testleri ayrı değerlendir.
