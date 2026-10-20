# Stüdyo mimarisi

- **Sahip:** Fikir, bütçe, görsel/oynanış kabulü, yayın/harcama/çekirdek son onayı.
- **GUI:** `app/gui.py` — kod bilmeyen kullanıcı için masaüstü kontrol merkezi.
- **İş akışı:** `app/core.py` — motor seçimi, AI görevleri, yerel testler.
- **AI şirketi:** `app/company.py` — gündem, araştırma, öneri/onay.
- **Hata hafızası/konsey:** `app/brain.py`, `app/evolution.py` — birden fazla projede doğrulanan hatalar, kontrollü iyileştirme.
- **CLI köprüleri:** Claude Code, Codex, Gemini CLI; isteğe bağlı yerel/ücretsiz modeller.
- **CI:** GitHub Actions çekirdek testleri, haftalık araştırma/kurul ve aylık strateji gündemi. Oyun depoları için ayrı CI şablonları.
- **Görseller:** ChatGPT/Gemini 2D, Meshy yalnızca 3D.

Her oyun ayrı GitHub deposunda kalır. Oyun projesinin `.studio/` hafızası, ortak çekirdek kodu veya kamuya açık GitHub depolarına otomatik taşınmaz. Paylaşılan çekirdek deneyimi test kanıtına ve bağımsız incelemeye bağlıdır.

**Gerçek durum:** v5.0 yerel prototip için 106 Python testi geçmişti; Windows ve gerçek oyun motorlarında uçtan uca entegrasyon henüz doğrulanmadı. GitHub'a yüklenmiş dokümantasyon, kaynak kodun yüklenip test edilmesi anlamına gelmez.
