# Şirket Merkezi — Veri kaybı olmadan proje başlatma

Bu düzeltme, "Bunu yap" sırasında üç hata yolunu kapatır:

1. **Eski klasörleri silme kaldırıldı.** `_reclaim` artık yoktur. Boş ya da dolu, işaretli ya da işaretsiz mevcut hiçbir çalışma klasörü otomatik olarak silinmez. İsim kullanımdaysa yeni bir `-deneme-N` klasörü atomik olarak ayrılır. Eski işleri kullanıcı manuel olarak değerlendirebilir.
2. **Yeni proje için doğru hata temizliği.** Klasör `mkdir(exist_ok=False)` ile işlemden önce ayrılır; Godot/web/Flutter projesi oluşturulurken yazma/disk hatası oluşursa yalnızca o denemede oluşturulan klasör temizlenir. Önceden var olan hiçbir klasöre dokunulmaz. Klasör adı core.safe_name 50 karakter sınırına uyar.
3. **Motor eşleşmesi.** Mevcut projeyi bağlarken seçilen Godot/web/Flutter/Unity/Unreal/Android motoru ile gerçek kaynak motoru aynı değilse, hiçbir klasör oluşturmadan kullanıcıya hata gösterilir.

Otomatik testler kaynak klasörün değişmeden kaldığını, eski işaretli/işaretsiz klasörün korunduğunu, uzun adların doğru hedefe gittiğini ve core.create_project içindeki yarım hata yolunun temizlendiğini kontrol eder.

**Sınır:** Gerçek Windows/Godot ve Claude/Codex/Gemini CLI hesapları ile uçtan uca test CI kapsamında yapılmadı. Native AI çağrıları tam sandbox değildir.
