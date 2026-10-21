# HQ Safety: mevcut projeler, Git, QA ve Ar-Ge

- Mevcut proje artık doğrudan AI çalışma klasörü değildir. İzinli dosyalar, özel klasörler ve gizli bilgiler hariç, ayrı çalışma kopyasına alınır.
- Kod commit işlemi yalnızca açıkça listelenen dosyaları sahneler. Yalnızca gerçek gizli konumlar reddedilir: `.env*`, `.npmrc`, `.pypirc`, `.netrc`, anahtar/sertifika dosyaları (`.pem`, `.key`, `.jks`, `.p12`…), `secrets/`, `.ssh/`, `key.properties`, `google-services.json` vb. Oyun kelimeleri (`token_pickup.gd`, `secret_level.gd`) ve araç dosyaları (`.metadata`, `.editorconfig`) engellenmez. AI talimat/politika dosyaları commit dışıdır.
- Engellenen dosya üretimi kilitlemez: paket "Kayıt bekliyor" olur, patrona soru gelir ("Git dışında bırak ve devam et" / "paketi atla"). Dosya silinmez, yalnızca ürünün `.gitignore` dosyasına eklenir. Yarım kalan kayıt bir sonraki çalıştırmada 0 token ile tamamlanır.
- Veri kaybettirebilen otomatik git reset --hard ve git clean -fd kaldırıldı. Eski ekranda kalmış seçenekler dahi reddedilir.
- Kod yazan AI ve bağımsız denetçi aynı sağlayıcı olamaz. Üretim başlamadan, 0 token ile yeterli sayıda farklı AI kurulu olup olmadığı kontrol edilir (1 denetçi = 2 AI, 2 denetçi = 3 AI); eksikse hiç çağrı harcanmadan patrona sorulur.
- Korsan gemisi oyunları serbesttir; yazılım korsanlığı/crack yasaktır.
- Ar-Ge URL kontrolü HTTPS 443, doğrulanmış TLS ve kamuya açık, sabitlenmiş IP gerektirir. Yönlendirmeler en fazla 3 kez izlenir ve her adım sıfırdan doğrulanır (https, kimlik bilgisi yok, yeni DNS çözümü, yalnızca kamuya açık IP). Özel ağa veya http'ye yönlendirme reddedilir.
- Mevcut proje kopyasına motorun ihtiyaç duyduğu 3D model, ses, doku ve motor kaynak dosyaları da alınır (`.glb`, `.gltf`, `.fbx`, `.mp3`, `.exr`, Unity `.meta`/`.prefab`, Unreal `.uasset` vb.). Çalıştırılabilir dosyalar alınmaz. Sınır 20.000 dosya / 2 GB; büyük dosyalar belleğe yüklenmeden kopyalanır.
- Mevcut oyun orijinali değişmeden kalır. Üretim sonucu asıl projeye otomatik uygulanmaz; gerektiğinde değişiklik inceleme merkezi kullanılır.
- Gerçek Windows, Godot ve Claude/Codex/Gemini CLI hesapları bu CI ortamında uçtan uca denenemez.
