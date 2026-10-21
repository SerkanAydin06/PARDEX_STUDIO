# Otomatik teknik bakım

Üretimdeki motor erişim hataları artık doğrudan patron sorusuna dönüşmez.
Pardex, AI çağrısı yapmadan aşağıdaki sınırlı bakım akışını çalıştırır:

1. Godot proje kökünde benzersiz geçici dosya oluşturma, yeniden adlandırma ve silmeyi dener.
2. Godot raporunda adı geçen `export_templates`, `feature_profiles`, `script_templates`, `text_editor_themes` klasörlerini kontrol eder. Yalnızca boş, bağlantısız, sınırlandırılmış kaynak taramasında referansı bulunmayan klasörleri yedekleyerek ayırır. Okunamayan, referansı bulunan veya dolu klasörlere dokunmaz.
3. `.godot/editor` editör önbelleğini yedekler. Kaynak dosyalarını, kaynak UID önbelleğini ve içe aktarılmış varlıkları değiştirmez.
4. Değişiklik yaptıysa gerçek motor testini bir kez yeniden çalıştırır. Test geçerse üretim devam eder; geçmezse sonuç ve yapılan işlemler proje sohbetinde gösterilir. Motorun başarı durumu onarım yapılmış olmasına bakılarak varsayılmaz.

Yedekler projenin gizli ve Git dışında tutulan `.studio/maintenance/backup-*` klasöründedir; Godot bunları kaynak olarak taramaz. Proje dışına yazma yetkisi gerekmez. `RESTORE.txt` geri alma kaydıdır. Geri almak için motor kapalıyken yedeklenen klasörü kayıtlı eski yerine taşıyın; yeni oluşmuş dosyaların üzerine yazmayın, önce onları ayrıca yedekleyin.

Bir çözülmemiş olayda en fazla bir bakım denemesi yapılır. Kullanıcı tekrar denese bile önbellek yedekleme döngüsü oluşmaz. Başarılı motor testi sonraki olay için bakım hakkını sıfırlar. Bakım, AI çağrısı veya kod düzeltme hakkı tüketmez; yalnızca bir ek yerel motor testi çalışabilir.

Windows ACL, antivirüs, yönetici yetkisi, bağlantılar/junction/reparse noktaları otomatik değiştirilmez. Bu sınıra gelindiğinde veya güvenli kural bulunamadığında kullanıcıya somut bakım raporuyla dönülür. Gerçek Windows koruma engeli ayrıca kullanıcı müdahalesi gerektirebilir.

## Pardex'in kendi kod hataları

Üretimde Pardex'in `app/` kodunda oluşan Python `TypeError`, `AttributeError`, `NameError`, `AssertionError` hataları dosya/satır ve hata türüyle Yönetim Kurulu'na otomatik düzeltme önerisi olarak kaydedilir. Aynı kayıt yinelenmez. Özel oyun kaynakları, hata mesajındaki olası sırlar ve yerel değişkenler öneriye eklenmez. Orijinal hata görünür kalır.

Bu kayıt, otomatik canlı yazılım güncellemesi değildir. Kod değişikliğinin mevcut ayrı kopya → regresyon → bağımsız denetim → kurulum hattından geçmesi gerekir. Bu sürüm o hattı kendiliğinden çalıştırmaz; Docker/test imajı ve CLI gereksinimlerini de kurmaz. İşletim sistemi erişim hataları çekirdek kod hatası gibi bu kuyruğa gönderilmez.

Doğrulama: Python regresyon testleriyle onarım, yeniden test, tekrar sınırı ve bağlantı koruması sınanır. Windows ACL/Defender davranışı için gerçek Windows uçtan uca doğrulaması gerekir.
