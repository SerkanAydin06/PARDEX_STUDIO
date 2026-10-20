# PARDEX_STUDIO — Ultra Pro AI Studio

Türkçe, çok projeli **AI oyun ve uygulama geliştirme stüdyosu** için ortak GitHub deposu. Hedef: Godot, Unity, Unreal, Flutter, Android/Kotlin ve web projelerini ortak stüdyo çekirdeğiyle yönetmek; Claude Code, Codex, Gemini CLI ve isteğe bağlı ücretsiz modellerle kontrollü geliştirme yapmak.

**Durum:** v5.0 yerel prototip, Windows/gerçek motor entegrasyonu henüz uçtan uca doğrulanmadı. Bu depo şu an AI katkı protokolünün ilk kurulum aşamasında. **Tam uygulama kaynak kodu henüz yüklenmedi**; mevcut v5.0 kaynaklarının yerel ZIP paketinden senkronize edilmesi gerekecek.

## AI katkıları

- [AGENTS.md](AGENTS.md): Bütün AI araçları için ortak kurallar.
- [CLAUDE.md](CLAUDE.md) ve [GEMINI.md](GEMINI.md): Sağlayıcıya özgü talimatlar.
- [docs/ROADMAP.md](docs/ROADMAP.md): Doğrulanması gereken işler.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): Ortak çekirdeğin sınırları.
- [CONTRIBUTING.md](CONTRIBUTING.md): AI ve insan PR süreci.

## Temel ilkeler

1. Her oyun ayrı GitHub deposu ve proje hafızasıyla yönetilir; stüdyo çekirdeği bir oyuna göre bozulmaz.
2. Bir AI değişiklik önerir; bağımsız AI inceler; testlerden sonra **depo sahibi son onayı** verir.
3. Satın alma, hesap açma, sunucu başlatma, yayınlama veya canlı çekirdek güncellemesi izinsiz yapılmaz.
4. GitHub Actions test ve rapor üretir; abonelikle girilen AI CLI oturumları GitHub sunucusuna kopyalanmaz.
5. Kısa ve hedefli görevler, yerel testler, somut ölçüm ve kontrollü kota tüketimi tercih edilir.
6. Model ağırlıkları kendi kendine eğitilmez; sistem testlerden ve geri bildirimlerden kuralları/iş akışlarını sürümleyerek öğrenir.

**Güvenlik:** Depo herkese açıktır. API anahtarı, giriş oturumu, kişisel hafıza veya özel oyun kaynaklarını yüklemeyin.
