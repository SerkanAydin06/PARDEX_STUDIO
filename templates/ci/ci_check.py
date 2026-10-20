"""Safe structural repository validator - intentionally no AI, network or secrets."""
from pathlib import Path
import argparse
import sys

root=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--report',action='store_true');a=p.parse_args()
problems=[];notes=[]
# CI checks repository-visible files only; .studio is deliberately private.
recognized=((root/'project.godot').exists() or bool(list(root.glob('*.uproject')))
    or (root/'ProjectSettings'/'ProjectVersion.txt').exists() or (root/'pubspec.yaml').exists()
    or (root/'settings.gradle').exists() or (root/'settings.gradle.kts').exists()
    or (root/'package.json').exists() or (root/'index.html').exists())
if not recognized:problems.append('Taninmis proje dosyasi bulunamadi')
if (root/'project.godot').exists():
    notes.append('Godot algilandi; ayrica GitHub Actions headless Godot testi calistirilir.')
    if not (root/'scenes').is_dir():notes.append('scenes/ yok (bazı Godot projeleri için normal)')
if list(root.glob('*.uproject')):notes.append('Unreal algilandi. Runnerda Unreal Editor kurulmadigindan GERCEK Unreal test yapilmiyor.')
if (root/'ProjectSettings'/'ProjectVersion.txt').exists():notes.append('Unity algilandi. Runnerda Unity Editor kurulmadigindan GERCEK Unity test yapilmiyor.')
if (root/'pubspec.yaml').exists():notes.append('Flutter algilandi; Flutter CI jobu ayrica analyze calistirir.')
if (root/'settings.gradle').exists() or (root/'settings.gradle.kts').exists():notes.append('Android Native algilandi. gradlew varsa CI test jobu calisir.')
if (root/'package.json').exists():notes.append('Web paketi algilandi. package-lock.json varsa npm jobu calisir.')
if not notes:notes.append('Proje motoru dosyalardan algilanamadi')
print('# Ultra Pro Studio denetim raporu')
for n in notes:print('- '+n)
for e in problems:print('HATA: '+e)
print('Yapisal denetim:', 'BASARISIZ' if problems else 'BASARILI')
print('Not: yapisal denetim, motor testleri veya oyun icinde kullanici testi demek degildir.')
sys.exit(1 if problems else 0)
