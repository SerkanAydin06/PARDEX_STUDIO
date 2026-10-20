# Katkı ve denetim düzeni

1. `AGENTS.md` ve `docs/ROADMAP.md` oku.
2. Tek görev için `feature/<konu>` veya `fix/<konu>` dalı aç.
3. Kod+test+belgeyi uyumlu şekilde düzenle. `python -m unittest discover -s tests -p 'test_*.py' -v`.
4. PR'da amaç, kapsam, test kanıtı, AI kotası/maliyet etkisi, risk ve geri alma planı belirt.
5. Güvenlik, çekirdek ve ajan talimatı değişikliği için bağımsız ikinci AI incelemesi iste.
6. Sahibin onayı olmadan üretim dağıtımı, ödeme, hesap oluşturma ve çekirdek sürümüne terfi yok.
