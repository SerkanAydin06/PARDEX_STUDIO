# PARDEX 2J: Çevrimdışı, sınırlı Docker test çalışanı

Bu aşama **gerçek Codex/Claude/Gemini üretim çalışanını kapsamaz**. Yalnızca daha önce üretilmiş Python kodunu, özel çalışma alanını dışarı aktarmadan, çevrimdışı ve sınırlı bir Docker konteynerinde test eden bir çalıştırıcı getirir. `PARDEX_REQUIRE_ISOLATED_AI=1` bulut CLI'larını bloke etmeye devam eder.

## Kullanım

1. Güvenilir, sürümü/digest'i doğrulanmış Python test imajını **kullanıcı kendi Docker kurulumuna önceden yükler**. PARDEX imaj indirmez.
2. İmajın `repository@sha256:<64 hex>` referansını kullanır. Örnekteki `<digest>` gerçek değeri temsil etmez.
3. `python app/isolated_worker_cli.py preview <proje> --image <repository@sha256:digest>` ücretsiz ön kontroldür.
4. `python app/isolated_worker_cli.py run <proje> --image <repository@sha256:digest> --confirm` tek seferlik kullanıcı onaylı testtir. Yapılandırılmış kısa çıktı verir.

## Güvenlik sınırları

- Yalnızca `app/`, `tests/`, `templates/`, `scripts/` altındaki izinli uzantıları geçici alana kopyalar; `.studio`, `.env`, `.git` ve gizli klasörleri **kopyalamaz**. Sembolik bağlantıları reddeder. Dosya/boyut sınırları vardır.
- `docker run --pull=never --network none --read-only --cap-drop ALL --security-opt no-new-privileges` ve işlem/bellek/CPU kısıtlarını uygular. Kendi anahtarlarını ve kullanıcının ev klasörünü container'a bağlamaz. Ortam değişkenlerini beyaz listeyle sınırlar.
- İmaj tag'i değil SHA256 referansı gereklidir. Yerel Docker imajı yoksa durur. Zaman aşımında yalnızca kendi oluşturduğu konteyner kimliği doğrulanırsa `docker rm -f` denenir.
- Docker daemon'u, ana makine çekirdeği, kötü niyetli önceden yüklenmiş imaj ve kaynak dosyasına gömülü gizli bilgiler bağımsız güvenlik sınırlarıdır. Bu **VM düzeyinde güvenlik sertifikası değildir**. İmajın imzasını ve daemon'u bu kod doğrulamıyor.
- Python dışı motorların tam build/test zinciri, Docker Desktop/Windows/WSL gerçek testi, bulut AI CLI kimlik bilgilerini güvenli aracı üzerinden sunma, zamanlanmış güvenli model çağrıları hâlâ yapılacak.

## Onay, maliyet ve geri alma

`preview` AI çağrısı yapmaz. Test işlemi yalnızca `--confirm` ile başlar ve model kullanımı/fatura oluşturmaz; yerel Docker kaynakları tüketir. Ana çekirdek, kullanıcı onayı olmadan güncellenmez. Bu değişiklik PR revert edilerek geri alınabilir; özel görev veritabanına migration yapılmaz.
