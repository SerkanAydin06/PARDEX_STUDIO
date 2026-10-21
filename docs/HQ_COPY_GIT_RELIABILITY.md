# Şirket Merkezi — Dosya kopyası ve Git güvenilirlik düzeltmeleri

Bu güncelleme, 4 hata sınıfını ele alır:

1. **Birleşik gizli dosya politikası:** Oyun dosyaları \`token_pickup.gd\`, \`secret_level.gd\`, \`password_screen.gd\` kopyalanır ve normal kod gibi Git'e eklenebilir. \`client_token.json\`, \`.env*\`, servis hesabı JSON'u, özel anahtarlar, kimlik bilgisi içerebilen yapılandırmalar ve \`secrets/\` dışarıda tutulur. \`.editorconfig\`, \`.metadata\`, \`.gitattributes\` gibi araç dosyaları proje kopyasına alınır. Politika, ilgili isimlerden hassas içerik çıkıp çıkmadığını **içerik okuyarak anlayamaz**; gerçek anahtarları oyun kaynaklarına koymayın.
2. **Git sonucu doğru raporlanır:** Git başlatılamazsa, stage/diff başarısız olursa veya commit hata döndürürse paket başarılı sayılmaz; kullanıcıya soru sorulur. Önceden kaydedilmiş temiz çalışma ağacında commit gerekmiyorsa no-op başarılı kabul edilir.
3. **Tam dosya listesi:** Kaydedilecek Git dosya listesi artık genel \`core.run\` işlevinin 10.000 karakterlik günlük sınırından geçirilmez; \`git -z\` çıktısı bağımsız ve 4 MB üst sınır ile doğrulanır. Liste bu sınırı aşarsa **güvenli biçimde durur**, sessiz kesilmez.
4. **Yarım kopya temizliği:** Geçici ürün kopyası doğrulanırken disk dolması, izin, doğrulama veya proje bağlama hatasında oluşturulan *yeni* kopya kaldırılır. Orijinal oyun klasörüne dokunulmaz.

Test kapsamı: 8 yeni çevrimdışı regresyon testi + mevcut çekirdek testleri.

Bu CI, gerçek Windows/Godot/Claude/Codex/Gemini entegrasyon testi yerine geçmez. Bu akışta yerel AI CLI hâlâ işletim sistemi sandbox'ı değildir.
