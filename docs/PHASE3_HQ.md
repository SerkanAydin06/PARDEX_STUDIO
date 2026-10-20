# Aşama 3 — PARDEX Şirket Merkezi (yerel web paneli)

Çalıştır: `09_SIRKET_PANELI.cmd` (Windows) veya `python app/hq_server.py`. Tarayıcıda `http://127.0.0.1:8765/` açılır.

## Ne yapar

| Bölüm | İşlev |
| --- | --- |
| **Ofis** | Bekleyen onaylar, haftalık AI bütçesi, aylık net, CEO brifingi (0 token), departman durumları, fikirden gelire hat |
| **İşler** | Bütün işler; Onayla → Şimdi çalıştır → Teslimi gör → Kabul et / Geri çevir |
| **Fikirler** | Gelir, uygunluk, emek ve maliyet puanıyla 0-100 kâr puanı; aşama tahtası; "Üretime al" CEO’ya iş böldürür |
| **Departmanlar** | 11 departman, görevleri, haftalık çağrı bütçesi; departmana doğrudan iş önerme |
| **Finans** | Senin girdiğin gelir/gider ve AI çağrı defteri |
| **Ayarlar** | Varsayılan proje, yerel Ollama modeli, haftalık sınır, departman bütçeleri, olay günlüğü |
| **Acil durdur** | Tek tuşla yeni işlerin başlatılmasını engeller |

## İş akışı

1. Patron hedef yazar. **CEO K0** kurallarla (0 token) işleri departmanlara böler. İstersen **AI ile planla** tek K1 çağrısı yapar.
2. Her iş `proposed` (onay bekliyor) başlar. Hile, anti-cheat aşma, sahte hesap, spam içeren hedefler `blocked` olur.
3. Patron onaylar. Kod işleri mevcut **Görev Merkezi** kuyruğuna onaylı görev olarak girer; testler ve bağımsız QA kuralları aynen geçerlidir.
4. Patron **Şimdi çalıştır** der. Çalıştırmadan önce departman bütçesi, şirket haftalık sınırı, yerel günlük sınır (8) ve acil durdur kontrol edilir.
5. Sonuç `delivered` olur; patron kabul eder veya gerekçeyle geri çevirir. Gerekçeler Gelişim Konseyi raporunun girdisidir.

## Token kademeleri

- **K0 (0 token):** fikir puanlama, testler, resmî sürüm radarı, finans raporu, CEO brifingi, K0 planlama.
- **K1:** önce Ayarlar’daki yerel Ollama modeli (ücretsiz); yoksa Claude Code `haiku` veya Gemini `flash`, salt-okunur, tek tur.
- **K2:** yalnızca kod; mevcut `task_queue` + `core.run_ai_task` yolu.

Bir iş en fazla 3 çağrı planlayabilir; başarısız iş kendiliğinden tekrar edilmez.

## Güvenlik

- Sunucu yalnızca `127.0.0.1` dinler. Her başlatmada yeni oturum anahtarı üretilir; API anahtarsız veya yabancı `Host`/`Origin` ile çağrılamaz (CSRF ve DNS rebinding koruması).
- CSP dış kaynak yüklemez; panel internet bağlantısı olmadan çalışır.
- Veriler `UltraProStudio/hq/` altında, Git dışında tutulur. Teslim metinleri `hq/deliverables/*.md`.
- Sistem hesap açmaz, ödeme yapmaz, mağazaya yayın yapmaz. "Yayın" aşaması yalnızca patronun kararını kaydeder.

## Sınırlar (bitmiş diye sunma)

- Arka planda 7/24 çalışan servis değildir; her iş patronun düğmesiyle tek tek çalışır.
- İnternet araştırması: K0 radar yalnızca resmî sürüm meta verisi okur. K1 Ar-Ge raporunun web erişimi kullanılan CLI’a bağlıdır; doğrulanmamış iddialar "doğrulanmalı" olarak işaretlenir.
- Video için metin paketi (senaryo, sahne listesi, altyazı, kapak brief’i) üretilir. Video render ve ses üretimi henüz yok.
- Gerçek abonelik kotası ve token fiyatı okunmaz; defter çağrı sayısı tutar.
- Gerçek Windows kurulumu doğrulanmadı; Linux’ta tarayıcıyla ve gerçek bir K1 Claude çağrısıyla uçtan uca denendi.

## Geri alma

Panel eklentidir: `app/hq_*.py`, `app/hq_static/`, `09_SIRKET_PANELI.cmd` silinirse eski masaüstü uygulaması aynen çalışır. Veriler `UltraProStudio/hq/` klasöründedir.
