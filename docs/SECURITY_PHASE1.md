# PARDEX — Güvenli Çekirdek İlk Aşama

Bu PR, farklı oyunları ve uygulamaları kullanan ortak çekirdeği değiştirmeden önce temel güvenlik kapılarını ekler.

## Özel proje hafızası
- Yeni ve mevcut projelerde .studio/ varsayılan olarak Git'e eklenmez.
- Mevcut .gitignore korunur, gerekli ignore kuralı eklenir.
- GitHub Actions için gerekli yardımcı Python dosyaları .github/scripts/ klasörüne alınır.
- Daha önceden Git tarafından takip edilen özel dosyalar bu değişiklikle geçmişten silinmez. Bunun için ayrıca denetim gerekir.
- Var olan workflow dosyaları otomatik düzenlenmez; eski .studio yolu tespit edilirse uyarı gösterilir.

## Kullanıcı onayı
- Claude ve Gemini'nin olumlu incelemesi bir politika veya kod yükseltmesini otomatik başlatamaz.
- Uygulamada görünen onay penceresinden sonra ayrı owner_approved parametresi aktarılır.
- Bu, kriptografik bir yetkilendirme sistemi değildir. Çekirdek dosyalarını değiştirebilen kötü niyetli bir süreç bu parametreyi taklit edebilir. Bu nedenle otonom ajanlara main dalına erişim verilmemelidir.

## Aday AI kodunun testi
- Daha önce aday kod Python host sürecinde test ediliyordu; bu yol kaldırıldı.
- Artık yalnızca önceden indirilmiş yerel Docker imajı kullanılır; Docker yoksa test fail-closed olur.
- Docker komutu ağsız, salt okunur kaynak bağlama, yetkisiz kullanıcı, yetenekleri kaldırma ve kaynak limitleriyle çalışır.
- Varsayılan örnek imaj pardex-core-tests:3.12 (Dockerfile: docker/Dockerfile.tests); üretimde doğrulanmış SHA256 digest ile sabitlenmelidir.
- Bu ortamda gerçek Docker ve Windows+WSL entegrasyonu doğrulanmadı. Docker tek başına kesin bir saldırgan-kod izolasyonu sağlamaz; güçlü düşmanca koda karşı ayrı VM/uzak worker gerekir.
- Kod üreten Codex/Claude/Gemini CLI'ların kendi sandbox özellikleri bu testle aynı değildir. CLI'ların üretim yetkileri henüz ayrıca sertleştirilmelidir.

## Sınırlar
- GitHub ilk yayın ön kontrolü, uygulamanın başlattığı git sürecini korur; kullanıcı başka terminalden elle git push yaparsa bu kontrol çalışmaz.
- AI günlük sınırı gerçek sağlayıcı kotasının ölçümü değildir.
- 2D/3D asset, Unity, Unreal ve video üretim hatları bu güvenlik PR'ında tamamlanmış sayılmaz.
- Çekirdek PR'ı ve CI testleri kullanıcı onayından önce main ile birleştirilmez.

## Test
\`python -m unittest discover -s tests -p 'test_*.py' -q\`
\`python -m compileall -q app tests\`


Güvenli aday testi için ayrı çalışan Docker imajı sahibi tarafından hazırlanır:

docker build -t pardex-core-tests:3.12 -f docker/Dockerfile.tests .

Bu komut ağ kullanabilir, fakat otonom işçi tarafından otomatik çalıştırılmaz. Windows Docker Desktop/WSL ve digest pinleme ayrıca doğrulanmalıdır.
