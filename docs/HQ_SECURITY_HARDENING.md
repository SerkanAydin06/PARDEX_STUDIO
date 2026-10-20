# HQ Safety: mevcut projeler, Git, QA ve Ar-Ge

- Mevcut proje artık doğrudan AI çalışma klasörü değildir. İzinli dosyalar, özel klasörler ve gizli bilgiler hariç, ayrı çalışma kopyasına alınır.
- Kod commit işlemi yalnızca açıkça listelenen dosyaları sahneler; .env, .npmrc, secrets ve diğer gizli dosyalar reddedilir. AI talimat/politika dosyaları commit dışıdır.
- Veri kaybettirebilen otomatik git reset --hard ve git clean -fd kaldırıldı. Eski ekranda kalmış seçenekler dahi reddedilir.
- Kod yazan AI ve bağımsız denetçi aynı sağlayıcı olamaz. Alternatif yoksa inceleme durur.
- Korsan gemisi oyunları serbesttir; yazılım korsanlığı/crack yasaktır.
- Ar-Ge URL kontrolü HTTPS 443, doğrulanmış TLS ve kamuya açık, sabitlenmiş IP gerektirir. Yönlendirme ve özel IP reddedilir.
- Mevcut oyun orijinali değişmeden kalır. Üretim sonucu asıl projeye otomatik uygulanmaz; gerektiğinde değişiklik inceleme merkezi kullanılır.
- Gerçek Windows, Godot ve Claude/Codex/Gemini CLI hesapları bu CI ortamında uçtan uca denenemez.
