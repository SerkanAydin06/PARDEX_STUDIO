# Aşama 5 — Yönetim Kurulu: şirketi büyütmek ve yeniden yapılandırmak

Panel → **Yönetim** sekmesi.

## Genel Müdür Yardımcısı (GMY)

Patron talimatını düz Türkçe yazar. Örnekler:
- "Tasarım departmanı kur, her projede önce o çalışsın."
- "Kod incelemesini iki denetçili yap."
- "Ar-Ge bütçesini artır."

GMY tek çağrıyla (Claude `sonnet`, effort low; CEO bütçesinden) talimatı **izinli işlemlerden** oluşan bir öneriye çevirir ve kota etkisini söyler. Öneri:
1. Önce doğrulanır. Geçersiz veya güvensiz öneri hiç oluşmaz.
2. Patron **Onayla ve uygula** derse hepsi birlikte uygulanır (ya hepsi ya hiçbiri).
3. Sürüm olarak kaydedilir (V1, V2…). **Değişiklik geçmişi**nden herhangi bir sürümün öncesine tek tuşla dönülür.

İzinli işlemler: departman ekle/güncelle/kapat/aç, bütçe, iş akışı, model yönlendirme, haftalık/günlük sınır. Çekirdek departmanlar (CEO, Ürün, Oyun, Uygulama, Kalite, Ar-Ge, Finans) düzenlenebilir ama kapatılamaz. "Onaysız", "push et", "satın al", ".env" gibi kuralları aşmaya çalışan talimatlar reddedilir.

## Veriye dayalı organizasyon

Departmanlar artık kodda değil veritabanında tutulur: ad, görev, talimat (AI rolü), kademe (K0/K1/K2), bütçe, aktiflik.

Yeni departmanlar proje hattına üç noktadan bağlanabilir:

| Kanca | Mod | Ne olur |
| --- | --- | --- |
| Plan sonrası | Rapor | Tarif donunca, iş paylaşımından önce rapor yazar (örn. Tasarım). Rapor CEO'ya ve kodu yazan ekibe verilir. |
| Paket sonrası | Denetim | Her paket kontrolden geçtikten sonra kendi alanında ek PASS/FAIL verir (örn. Güvenlik). FAIL düzeltme turu açar. |
| Teslim öncesi | Rapor / Kod | Teslimden önce son adımı yapar (örn. Dokümantasyon kılavuz yazar). |

Kancalı departmanın model rolü kademesinden seçilir:
- **K1 rapor:** en ucuz metin modeli
- **K1 denetim:** ucuz inceleme modeli
- **K2:** güçlü plan modeli
- **Kod modu:** her zaman kod yazım modeli

**İş akışı ayarları:**
- Düzeltme hakkı (0–3)
- Proje başına en fazla paket (2–12)
- Bağımsız denetçi sayısı (1–2; 2'de ikinci denetçi hem yazandan hem ilk denetçiden farklı sağlayıcıdır)
- İsteme eklenen ders sayısı (0–8)
- Oyunları ve uygulamaları hangi departmanın üreteceği (örn. yeni bir "Mobil Ekip")

Tahmini proje bütçesi bu ayarlara ve kancalara göre otomatik hesaplanır.

## Şirket sağlığı (0 token)

Departman başına şunlar gösterilir:
- Bu haftanın çağrıları / bütçesi
- İlk denemede geçen paket oranı
- Takılan paketler
- Ders sayısı

Kurallardan gelen **optimizasyon önerileri** tek tuşla Onay Masasına öneri olarak düşer:
- Bütçenin %90'ı kullanıldıysa artır.
- Şirket en az 4 haftalıksa ve departman 4 haftadır çağrı kullanmadıysa kotayı düşür.
- İlk deneme başarısı %50'nin altındaysa talimatı güçlendir.
- Paketler sık takılıyorsa düzeltme hakkını artır.

Tek AI kurulu olduğunda bağımsızlık uyarısı verilir.

## Çekirdek yazılım değişikliği

Ayarla yapılamayan istekler (yeni ekran, yeni özellik, yeni entegrasyon) mevcut Çekirdek Konseyi hattından geçer. GMY bunları `code_request` olarak işaretler; patron isterse talep açılır:

1. **Kodu yazdır:** Codex, şirket yazılımının kopyasında yalnızca `app/*.py` dosyalarını değiştirir.
2. **Test et:** Orijinal testler, izole Docker imajında çalışır (`PARDEX_TEST_IMAGE`). AI tarafından değiştirilmiş test kabul edilmez.
3. **İki AI denetimi:** Claude ve Gemini ayrı ayrı onaylamalıdır.
4. **Kur:** Yalnızca patron yapar; önce yedek alınır. **Son çekirdek kurulumunu geri al** ile eski hâle dönülür.

Gereksinimler panelde işaretli gösterilir: Codex, Claude, Gemini, Docker, test imajı. Bunlar yoksa çekirdek değişikliğini Claude Code ile PR olarak yaptırmak en pratik yoldur.

## Doğrulama

- 295 unit test.
- Tarayıcıda sahte GMY ile: öneri → onay → departman açıldı → V1 → sağlık önerisi → departman düzenleme penceresi.
- Gerçek Claude ile: "Tasarım departmanı kur + iki denetçi" talimatı doğrulamadan geçen 2 işleme çevrildi; kota etkisi ve tek AI uyarısı da verildi.
