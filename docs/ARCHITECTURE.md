# Mimari / Modül Sınırları

```
Sahip (onay / oynanış / görsel test)
     │
Tkinter UI (`app/gui.py`)
     │
├── İş akışı / çok motor: `app/core.py`
├── AI şirketi ve öneriler: `app/company.py`, `app/company_cli.py`
├── Test hafızası ve konsey: `app/brain.py`, `app/brain_cli.py`
└── Çekirdek iyileştirme / sandbox denemesi: `app/evolution.py`
     │
├── Oyun özel hafıza: projede `.studio/` (Git'e gitmez)
└── Ortak öğrenme: `%LOCALAPPDATA%/UltraProStudio/` (Git'e gitmez)

GitHub Actions: `.github/workflows/` çekirdeği test eder, sürüm raporu çıkarır. Oyun projelerine `templates/ci` içinden ayrı motor bazlı iş akışları kurulur.
```

**Çekirdek ≠ oyun:** Oyun kodu değişikliği çekirdeği kendiliğinden değiştirmez. Oyun projeleri ve ortak hafızalar birbirinden ayrılır. Ortak kural güncellemesi en az iki farklı projeden kanıt + bağımsız inceleme ile önerilir. Çekirdek kodunun etkinleştirilmesi sahibin onayını gerektirir.

**Yetki modeli:** AI kod yazar, rapor hazırlar, dar kapsamlı test yapar. Satın alma, hesap oluşturma, prod dağıtımı, ücretli sunucu açma, koruma mekanizması değiştirme ve çekirdek sürümüne terfi ayrı onay gerektirir. AI konseyinin iki oyu sahibin onayı yerine geçmez.

**Model seçim:** Sabit Claude Sonnet 3.5 gibi tarihsel model adları yerine resmi CLI'ın erişilebilir model seçeneği; başarısız görevi tekrar tekrar çalıştırmak yerine test/denetim.

**Güncellik:** Fiyat ve model limitleri dinamik. Geçerli kaynak/tarih yoksa öneriyi 'araştırılacak' olarak kaydet.
