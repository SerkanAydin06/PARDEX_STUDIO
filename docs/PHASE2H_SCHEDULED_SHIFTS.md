# 2H — Zamanlanmış AI vardiya altyapısı

Bu PR henüz 7/24 servis veya gerçek credentialed OS sandbox sağlamaz.

- Önce her görev Görev Merkezi'nde sahibi tarafından tek tek onaylanır. Daha sonra \`shift_scheduler.plan((id1,id2),start,end,owner_confirms=True)\` ile 1–2 tam görev kimliği için 1–7 gün ileri ve 1–60 dakikalık pencere oluşturulur.
- Planlama / listeleme / \`preview_due()\` ve varsayılan \`python app/scheduler_cli.py\` **AI çağrısı yapmaz**; planın oluşturulması daemon kurmaz.
- Gerçek zamanlanmış native CLI için aynı planı kaydederken açık \`allow_native_unisolated=True\`, ayrıca \`--execute\` ve çalıştırıcı ortamında \`PARDEX_ALLOW_SCHEDULED_NATIVE_AI=1\` birlikte gerekir. \`PARDEX_REQUIRE_ISOLATED_AI=1\` ise native çalıştırmayı her durumda engeller.
- SQLite claim kilidi; tek kullanımlık plan; tekrar deneme, otomatik görev kabulü veya otomatik yayınlama yok. Yarım kalan oturum elle incelenir.
- Kurulmuş Windows Görev Zamanlayıcı tetikleyicisi yoktur; \`scheduler_cli.py --execute\` ancak sahip ayrıca böyle bir tetikleyici kurarsa o saatte çağrılır.
- Mevcut \`worker_supervisor.run\` ayrıca tam görev sırasını, kotayı, onayı ve çalışan kilidini doğrular. Başlamış CLI işleminin anında sonlandırılması bu PR'da desteklenmez.
- Gerçek token, bakiye veya para tasarrufu uydurulmaz. Özel prompt ve çıktı plan veritabanına konulmaz.

Test: \`python -m unittest discover -s tests -p 'test_*.py' -q\`. Gerçek Windows/CLI uçtan uca doğrulaması ayrıca gereklidir.
