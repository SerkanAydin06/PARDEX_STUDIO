"""User-requested, offline Godot 4 proof-of-work project; never runs AI or overwrites."""
from __future__ import annotations
from pathlib import Path
import os
import shutil
import tempfile

FILES = {
    'project.godot': '''config_version=5

[application]
config/name="PARDEX Deneme Oyunu"
run/main_scene="res://main.tscn"
config/features=PackedStringArray("4.2", "GL Compatibility")

[display]
window/size/viewport_width=960
window/size/viewport_height=600

[rendering]
renderer/rendering_method="gl_compatibility"
renderer/rendering_method.mobile="gl_compatibility"
''',
    'main.tscn': '''[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://scripts/player.gd" id="1_player"]

[node name="Main" type="Node2D"]

[node name="Sea" type="ColorRect" parent="."]
offset_right = 960.0
offset_bottom = 600.0
color = Color(0.065, 0.19, 0.31, 1)

[node name="Player" type="CharacterBody2D" parent="."]
position = Vector2(480, 300)
script = ExtResource("1_player")

[node name="Ship" type="Polygon2D" parent="Player"]
color = Color(0.96, 0.78, 0.28, 1)
polygon = PackedVector2Array(-22, -14, 22, -14, 13, 18, -13, 18)
''',
    'scripts/player.gd': '''extends CharacterBody2D

const SPEED: float = 260.0

func _physics_process(_delta: float) -> void:
    var move_direction: Vector2 = Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
    velocity = move_direction * SPEED
    move_and_slide()
''',
    'BENI_OKU.md': '''# PARDEX Godot Deneme Oyunu

Godot 4.2+ ile `project.godot` dosyasini ac ve F6/F5 ile calistir.
Ok tuslari gemiyi hareket ettirir. Bu kaynak kod, AI ile degil, yerel sabit sablonla olusturulmustur.

PARDEX Tek Gorev Teslimi'nde ornek hedef: `Geminin hizini iki katina cikar`.
Dosya: `scripts/player.gd`. Gercek AI komutu icin CLI kurulu ve acik onay gereklidir.
'''
}

def create(parent, *, owner_confirms=False, folder_name='PARDEX_Deneme_Oyunu'):
    """Create one new project with atomic rename; cannot replace existing data."""
    if owner_confirms is not True:
        raise PermissionError('Proje olusturmak icin acik onay gerekli')
    if folder_name != 'PARDEX_Deneme_Oyunu':
        raise ValueError('Unexpected demo name')
    root = Path(parent).expanduser()
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Valid parent directory required')
    root = root.resolve(strict=True)
    dest = root / folder_name
    if dest.exists() or dest.is_symlink():
        raise FileExistsError('Deneme klasoru zaten var; uzerine yazilmadi')
    temp = Path(tempfile.mkdtemp(prefix='.pardex-new-', dir=root))
    try:
        for rel, content in FILES.items():
            dst = temp / rel
            dst.parent.mkdir(parents=True,exist_ok=True)
            dst.write_text(content, encoding='utf-8')
        if dest.exists() or dest.is_symlink():
            raise FileExistsError('Folder appeared during creation')
        # Atomic directory rename on the same volume.
        temp.rename(dest)
        return str(dest)
    finally:
        if temp.exists():
            shutil.rmtree(temp)
