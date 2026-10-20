# Katkı ve AI Kod İnceleme Düzeni

1. `AGENTS.md` oku. `docs/ROADMAP.md` içinden tek bir küçük hedef seç.
2. `feature/<konu>` veya `fix/<konu>` dalı oluştur. Mevcut kodu koru, kopya bir 'yeni çekirdek' yazma.
3. Kod/ test / belgeyi aynı PR'da güncelle. Uygunysa `python -m unittest discover -s tests -p 'test_*.py' -v` çalıştır.
4. PR taslağına problem, test kanıtı, motor/işletim sistemi koşulları, risk, kota etkisi, rollback ve manuel kontrol notu ekle.
5. Çekirdek yönergeleri, AI routing veya güvenlik değişikliğinde ikinci bağımsız inceleme iste. Önemsiz raporlar bile dış servis secret'ı taşımamalı.
6. Gözden geçirilmemiş AI kodlarını otomatik birleştirme. Depo sahibinin onayı son karardır.

GitHub Actions yalnızca çekirdek testlerini gerçek olarak doğrular. Oyuna özgü motor CI ayrı depoda kurulur.
