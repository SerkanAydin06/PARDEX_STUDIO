# Aşama 4 — Proje Hattı: gerçek yazılım şirketi akışı

Panel: `09_SIRKET_PANELI.cmd` → **Projeler** sekmesi.

## Akış

1. **Planlama (Ürün Müdürü):** Patron yeni proje açar ve ana hatları sohbetle anlatır. Ürün Müdürü en fazla 3 soru sorar ve tarifi (özet, motor, özellikler, kabul ölçütleri, kapsam dışı, varsayımlar) canlı günceller.
2. **"Bunu yap":** Tarif dondurulur. Ürün, **şirket deposunun dışında** kendi klasöründe ve kendi git deposunda açılır (`Ayarlar → Ürün klasörü`, varsayılan `~/PardexProjeler`). Şirket deposuna ürüne özel hiçbir dosya yazılmaz; şirket deposunun içi ürün klasörü olarak seçilemez.
3. **İş paylaşımı (CEO):** Tarif en fazla 8 test edilebilir pakete bölünür. Yüksek karmaşıklıkta güçlü mimari modeli kullanılır. AI cevabı bozuksa K0 yedek plan devreye girer.
4. **Üretim:** Her paket sırayla departmanına (Oyun Stüdyosu / Uygulama) gider.
5. **Kontrol:** Önce K0 motor testi (0 token) çalışır. Ardından **yazan sağlayıcıdan farklı bir sağlayıcı**, değişiklik farkını salt-okunur inceler ve `PARDEX_QA_VERDICT=PASS|FAIL` verir.
6. **Düzeltme:** FAIL olursa bulgularla en fazla 2 düzeltme turu yapılır. İkinci turda başka bir ekip üyesi (farklı sağlayıcı) dener. Geçen paket ürün deposunda yerel commit olur.
7. **Teslim:** Teslim raporu (nasıl çalıştırılır, test sonucu, paketler, eksikler, patronun kontrol listesi) patrona gelir. Patron **kabul eder** ya da **değişiklik ister**; değişiklik yeni paket olur ve hat yeniden çalışır.

## Patrona yalnızca önemli sorular gelir

| Durum | Seçenekler |
| --- | --- |
| Motor testi bu bilgisayarda çalışmıyor (üretimden önce, 0 token) | Testsiz devam / durdur |
| Onaylanan çağrı bütçesi doldu | Bütçeyi artır / burada durdur ve teslim et |
| Paket 3 denemede kontrolden geçmedi | Güçlü modelle bir kez daha / atla / değişiklikleri geri al ve atla |
| AI patron kararı gerektiren bir engel buldu (`PARDEX_QUESTION=`) | Serbest cevap; pakete patron notu olarak eklenir |

Cevaptan sonra üretim kendiliğinden devam eder.

## Model yönlendirme (Claude Pro · ChatGPT Pro/Codex · Google AI Pro/Gemini)

Sürüm numarası sabitlenmez. Takma adlar her zaman aboneliğin sunduğu en güncel modele gider. Codex'te hesabın varsayılan modeli kullanılır, yalnızca reasoning effort ayarlanır.

| Görev | 1. tercih | Yedek | Neden |
| --- | --- | --- | --- |
| Plan sohbeti | Claude `sonnet`, effort low | Gemini `pro` | İyi Türkçe soru-cevap, düşük maliyet |
| İş paylaşımı | Claude `sonnet`, medium | Gemini `pro` | Yapılandırılmış plan |
| Zor mimari | Claude `opus`, medium | Gemini `pro` | Yalnızca karmaşıklık "Yüksek" ise |
| Kod yazımı | Codex (varsayılan model), medium | Claude `sonnet` | ChatGPT Pro kotası kod için geniş |
| Düzeltme | Codex, high | Claude `sonnet`, high | 2. turda farklı sağlayıcı |
| Güçlü düzeltme | Claude `opus`, high | Codex high | Yalnızca patron seçerse |
| Bağımsız inceleme | Gemini `flash` | Claude `haiku` | Ucuz; yazandan farklı sağlayıcı |
| Ar-Ge web araştırması | Gemini `pro` | Claude `sonnet` + WebSearch | Arama yerleşik |
| Kısa metin | Claude `haiku` | Gemini `flash-lite` | En ucuz |

- **Öğrenme:** Her çağrının sonucu rol/sağlayıcı bazında kaydedilir. Bir sağlayıcı en az 5 denemede alternatifinden 20 puan kötüyse yönlendirici alternatife geçer.
- **Patron ayarı:** `Ayarlar → Model yönlendirme` ile her rol sabitlenebilir.

**İzinler (gerçek Claude CLI ile doğrulandı):**
- Yazma rolleri yalnızca `Read, Edit, Write, Glob, Grep` kullanır; komut çalıştırma (Bash) yoktur.
- Okuma rolleri `dontAsk` modunda çalışır; yazma denemesi engellendi.
- Codex okuma rollerinde `read-only` sandbox kullanır.
- Gemini yazmada `auto_edit` kullanır, `yolo` asla kullanılmaz.

## Token tasarrufu

- Plan sohbetine yalnızca son 10 mesaj ve tarif JSON'u gider.
- Paket istemine tarifin kısa özeti, paket ayrıntısı, biten paketlerin tek satırlık özetleri ve departmanın en fazla 4 dersi gider.
- İncelemeye yalnızca değişiklik farkı gider (en fazla ~6.500 karakter).
- Test her zaman K0'dır (motor komutu).
- Tahmini bütçe = paket × 2 + düzeltme payı. Bütçe aşılırsa hat durur ve sorar; sessiz tekrar yoktur.

## Departmanların kendini geliştirmesi

- Kontrolde kalıp düzeltilen her hata, ilgili departmana kısa bir **ders** olarak kaydedilir. Aynı ders tekrar ederse sayacı artar; departman başına en fazla 40 ders tutulur.
- Patronun değişiklik istekleri de ders olur.
- Dersler o departmanın sonraki istemlerine eklenir (0 ek çağrı).
- `Departmanlar → Rapor iste` (0 token) dersleri, bütçeyi ve son hareketleri gösterir.

## Ar-Ge

- `Fikirler & Ar-Ge → Araştır`: odak (oyun, uygulama, şirket gelişimi, araç/üyelik) seçilir ve 1 çağrı yapılır.
- Her fikir, **en az 2 farklı siteden, bu bilgisayardan erişilebildiği doğrulanan** kaynakla gelmek zorundadır. Kaynaksız veya ulaşılamayan kaynaklı fikir elenir; mükerrerler de elenir.
- Ücretli üyelik önerileri "Patron onayı" aşamasına düşer; satın alma yapılmaz.

## Sınırlar

- Codex ve Gemini CLI bayrakları resmî belgelere göre yazıldı; bu ortamda yalnızca Claude Code gerçek olarak denendi.
- Gemini'nin başsız modda web aramasını kullanması CLI sürümüne bağlıdır.
- Unity, Unreal ve Android projeleri resmi editörde açılıp klasörü bağlanmalıdır. Godot, web ve Flutter otomatik oluşturulur (Flutter için SDK gerekir).
- Görsel/oynanış kabulü patrondadır; AI incelemesi kalite sertifikası değildir.
- Gerçek Windows kurulumu henüz denenmedi.
