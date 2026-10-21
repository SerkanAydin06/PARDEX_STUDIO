# Proje kaldırma ve şirket sıfırlama

Proje ayrıntısındaki **Projeyi kaldır** iki seçenek sunar:

- **Yalnızca listeden kaldır:** proje kaydı, sohbet ve paketler Pardex çöp kutusunda saklanır; klasör yerinde kalır.
- **Dosyaları da taşı:** yalnızca yapılandırılmış proje ana klasörünün doğrudan altındaki, o ürüne ait PARDEX_PRODUCT işareti doğrulanmış klasör taşınır. Başka projeyle paylaşılan, bağlantı/junction içeren veya çekirdeğe ait yollar reddedilir. Kalıcı dosya silme yapılmaz.

Proje adıyla onay gerekir. Bekleyen kuyruk görevleri iptal edilir; çalışmakta olan iş varken işlem engellenir. Önce üretimi durdurup çalışanın bitmesini bekleyin.

**Ayarlar → Veri yönetimi → Pardex çöp kutusu → Geri al** kaydı ve taşındıysa dosyaları geri getirir. Üretim ve iptal edilen kuyruk görevleri otomatik başlamaz. Hedef klasörde başka dosyalar varsa üzerine yazılmaz. Bu, Windows çöp kutusu değildir; dosyalar proje ana klasöründeki `.pardex-trash` içinde tutulur. Elektrik kesintisi sırasında taşıma/veritabanı kaydı ayrışırsa aynı dizindeki JSON kurtarma kaydı özgün yolu ve kayıtları korur. Bu özel yerel dosyaları GitHub'a yüklemeyin.

**Bugünkü çağrı sayacını sıfırla** `SIFIRLA` onayıyla yerel günlük bütçe sayacına yeni başlangıç koyar. Gerçek kullanım sayıları ve sıfırlama geçmişi korunur. Sağlayıcı abonelik kotası, haftalık/departman/proje bütçeleri değişmez. İşlem AI çağrısı harcamaz.

**Şirketi sıfırla** `SIFIRLA` onayıyla şirket veritabanını ve görev kuyruğunu önce SQLite yedeğine alır. Şirket proje kayıtları, sohbetleri, paketleri, finans/çağrı defteri, öğrenilen notlar, kurul ve organizasyon ayarları temizlenir. Yeni şirket varsayılan organizasyonla ve duraklatılmış olarak açılır. Üretilmiş proje klasörleri, Pardex çöp kutusu, Godot yolu, proje ana klasörü, günlük kullanım geçmişi ve dış CLI hesap girişleri korunur. Bu işlem sağlayıcı kotasını sıfırlamaz.

Yedek yolu sonuç ekranında ve olay günlüğünde gösterilir: şirket veritabanının yanındaki `admin-backups/<işlem-kimliği>/`. `company.sqlite3` ve `task_queue.sqlite3` birlikte saklanır. Şirket yedeği için tek tık geri yükleme yoktur. Geri dönüşte Pardex ve kuyruk kullanan tüm süreçler kapatılmalı, mevcut veritabanları da yedeklenmeli ve iki yedek SQLite backup API ile karşılık gelen veritabanlarına birlikte geri alınmalıdır; açık veritabanı veya eski WAL dosyaları üzerine dosya kopyalamayın. Ayrı veritabanlarının WAL işlemleri elektrik kesintisinde birlikte atomik değildir; tam geri dönüş için iki yedeği beraber kullanın. Sonraki üretimde oluşan proje dosyaları bu veritabanı geri dönüşüyle silinmez.

İşlemler yalnızca oturum belirteci doğrulanmış yerel panelden yapılır. Güncelleme, üretim, çekirdek çalışması, kurulum veya çalışan kuyruk varken sıfırlama engellenir. Ayrı bir Pardex/CLI örneğinden aynı veriler üzerinde eşzamanlı işlem başlatmayın.
