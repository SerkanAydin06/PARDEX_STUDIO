# Tek Görev → Çalışma Kopyası → Test → İnceleme → Sahip Onayı

**Bu, PARDEX'in ilk uçtan uca üretim akışıdır.** Yeni bir yönetim bölümü değildir; `core.run_ai_task()` ve `change_review` modüllerini birbirine bağlar. Bir somut hedef için bir AI çağrısı yapar. AI yalnızca ayrı proje **kopyasının yolu** ile başlatılır; gerçek oyun klasörüne otomatik uygulama yapılmaz.

## Windows'ta kullanma

1. Repoyu güncelle ve `08_TEK_GOREV_TESLIM.cmd` dosyasını aç (Python 3 ve seçtiğin Claude/Codex/Gemini CLI kurulmuş ve oturum açılmış olmalı).
2. Godot, Unity, Flutter, Android veya web proje klasörünü seç, somut tek görev yaz, **değişmesine izin verdiğin** kaynak dosyaları virgülle listele (örn. `scripts/player.gd, scenes/main.tscn`).
3. **Ücretsiz kontrol** ile proje/izin dosyalarını gör. Bu aşama AI çağrısı yapmaz.
4. Native CLI'nin sandbox olmadığını anlayıp risk kutucuğunu işaretle; tek AI çağrısını ayrıca onayla. CLI özel aboneliğindeki kullanım haklarını tüketebilir, kalan kredi sayısını PARDEX bilmiyor.
5. Sistem proje içindeki **yalnızca izin verilen türdeki** dosyalardan geçici bir kopya çıkarır; `.studio`, `.env`, AI politika dosyaları ve gizli anahtarlar kopyalanmaz. AI işi o kopyada yapar. Motorun mevcut yerel doğrulayıcısı çalışır: motor yoksa sonuç `test_passed=false` olur, başarı uydurulmaz.
6. AI'nın değiştirdiği dosyalar yalnızca senin izin verdiğin listedeyse, `change_review.stage` ile SHA256 kimlikli incelemeye alınır. **Kod farkını incele**; istersen **İncelenen kodu uygula** ile bir kez daha onay ver.
7. Eski önerinin senin yeni değişikliğini ezmesi engellenir. İstersen `07_AI_DEGISIKLIK_INCELE.cmd` ile daha sonra değişikliği geri alabilirsin.

## Komut satırı (isteğe bağlı)

```sh
python app/project_delivery_cli.py --preview --project /path/to/game --goal 'Oyuncu yönünü değiştir' --files scripts/player.gd
python app/project_delivery_cli.py --project /path/to/game --goal 'Oyuncu yönünü değiştir' --files scripts/player.gd --provider Codex --confirm --allow-native
```

İkinci komut *gerçek* yerel AI çağrısı yapar. Verdiği `review_id` ve `digest` ile `app/change_review_cli.py` üzerinde ayrıca açıkça uygulama onayı gerekir. Çalışma alanı iş bitince silinir, onay bekleyen değişiklikler yerel özel `delivery_reviews/reviews` klasöründe tutulur. CLI'dan gelen prompt/transkript burada saklanmaz.

## Kesin sınırlar

- **Gerçek bir OS/VM sandbox değil.** Yerel Codex/Claude/Gemini CLI, aynı Windows hesabının yetkileriyle çalışır. Proje klasörü ayrı olsa da kötü niyetli CLI host üzerindeki diğer dosyalara erişebilir. `PARDEX_REQUIRE_ISOLATED_AI=1` seçildiyse sistem çağrıyı *durdurur*. İzole ve kimlik bilgileri ayrı worker henüz desteklenmiyor.
- Gerçek Godot/Windows/abonelik CLI deneyimi CI'da doğrulanmadı. Bu iş akışının otomasyon testinde dış AI yerine deterministik sahte runner kullanılır: dosya değişir → öneri hazırlanır → canlı proje değişmez → sahip onayıyla uygulanır → geri alınır.
- Motor doğrulaması gerçek kodu yerel bilgisayarda çalıştırabilir; **yalnızca güvendiğin projelerde kullan**. Docker ile OS seviyesinde izole Godot/Flutter testi bu sürümde yok.
- Bu akış *tek çağrılık*: bağımsız AI kalite müdürü ve çok aşamalı kuyruk **otomatik tetiklenmez**. Gizli harcama, otomatik yayın, otomatik retry, onaysız güncelleme yoktur.
- İnceleme en fazla 12 dosya, 128 KB/dosya ve toplam 512 KB değişiklik destekler. Çok büyük veya silinen dosyalar için otomatik uygulama yapılmaz. AI izin verilmemiş kaynak dosyalarını değiştirirse teslimat reddedilir.
- `change_review` tarafından bilinmeyen/binary dosya değişiklikleri uygulanmaz. Godot `.gd`, `.tscn`, `.tres`, `.godot`, `.gdshader` metinleri desteklenir.

## Test

```
python -m unittest discover -s tests -p "test_*.py" -q
python -m compileall -q app tests
```

`tests/test_project_delivery.py` gerçek geçici Godot dosyaları kullanır; sadece AI çağrısı sahte olup güvenlik, kopya, onay, çakışma, diff, rollback akışları gerçek çalışır.


## Hızlı deneme ve kesin kalite kapısı

Ana PARDEX ekranındaki **AI ile tek görev teslimi** düğmesi aynı aracı ayrı pencerede açar. **AI ve Godot kontrolü** kurulum durumunu ücret/AI çağrısı yapmadan gösterir. İstenirse yeni ve mevcut dosyaların üzerine yazılmayan bir Godot 4 gemi-hareket örneği hazırlanır (sabit şablon, AI üretimi değildir). Demo sahnesi Godot 4.2+ ile oynanabilir olacak şekilde oluşturulmuştur; gerçek motor başlatma testi yalnızca motor kuruluysa yapılabilir.

Artık AI komutu başarısızsa hiçbir değişiklik incelemeye alınmaz. Çalışma sırasında **herhangi bir** izinli kaynak dosyası değişmişse stale öneri reddedilir. Native CLI yine işletim sistemi izolasyonu değildir; bu kural yalnızca değişiklik tespiti ve onay kapısıdır. Gerçek Windows ve CLI hesaplarıyla uçtan uca test beklemektedir.
