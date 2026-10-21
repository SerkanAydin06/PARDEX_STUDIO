"""Bounded, local engine maintenance. Never changes ACLs, source code or credentials."""
import os
from pathlib import Path
import stat
import uuid

EDITOR_DIRS = ('export_templates', 'feature_profiles', 'script_templates', 'text_editor_themes')


def linked(path):
    """Also reject Windows junctions/reparse points on Python versions without is_junction."""
    s = path.lstat()
    return stat.S_ISLNK(s.st_mode) or bool(getattr(s, 'st_file_attributes', 0) & 0x400)


def plain_chain(path):
    for p in (path, *path.parents):
        if linked(p):
            raise OSError('Bağlantı/reparse noktası üzerinden bakım yapılmaz: ' + str(p))


def state_dir(folder):
    plain_chain(folder)
    for p in (folder / '.studio', folder / '.studio' / 'maintenance'):
        if p.exists() or p.is_symlink():
            plain_chain(p)
        else:
            p.mkdir()
    return folder / '.studio' / 'maintenance'


def probe(folder):
    """Exercise the actual create/rename/delete operation used by safe save."""
    plain_chain(folder)
    a = folder / ('.pardex-probe-' + uuid.uuid4().hex)
    b = a.with_name(a.name + '-renamed')
    try:
        with a.open('x', encoding='utf-8') as f:
            f.write('Pardex local write probe\n')
        a.rename(b)
        b.unlink()
    finally:
        for p in (a, b):
            if p.exists() and not p.is_symlink():
                p.unlink()


def referenced(folder, name):
    """Fail closed if a bounded source scan cannot rule out a reference."""
    size = count = 0
    for root, dirs, files in os.walk(folder, followlinks=False, onerror=lambda e: (_ for _ in ()).throw(e)):
        dirs[:] = [d for d in dirs if not d.startswith('.') ]
        for d in dirs:
            if linked(Path(root) / d):
                return True
        for filename in files:
            p = Path(root) / filename
            if filename.startswith('.'):
                continue
            count += 1
            if count > 2000 or linked(p):
                return True
            # Resource/code/config files; unknown/binary files cannot prove a reference.
            if p.suffix.lower() not in ('.gd', '.tscn', '.tres', '.godot', '.cs', '.json', '.cfg', '.ini', '.txt', '.md', '.py', '.gdshader'):
                continue
            size += p.stat().st_size
            if size > 8_000_000 or p.stat().st_size > 1_000_000:
                return True
            if name.casefold() in p.read_text(encoding='utf-8').casefold():
                return True
    return False


def repair(folder, output):
    """One repair batch per unresolved incident; returns (changed, diagnostic).

    Backups remain inside hidden .studio, outside Godot's resource scan and Git.
    A failed retest leaves the claim in place, avoiding cache rotation loops.
    """
    folder = Path(folder).absolute()
    notes, changed = [], False
    try:
        plain_chain(folder)
        if not (folder / 'project.godot').is_file():
            return False, 'Bakım: bu motor için otomatik onarım kuralı yok.'
        if linked(folder / 'project.godot'):
            return False, 'Bakım: project.godot bağlantı; otomatik işlem yapılmadı.'
        probe(folder)
        notes.append('Proje kökü oluşturma/yeniden adlandırma/silme testi geçti.')
        state = state_dir(folder)
        claim = state / 'attempted'
        try:
            with claim.open('x', encoding='utf-8') as f:
                f.write('Tek otomatik bakım denemesi; başarılı motor testiyle sıfırlanır.\n')
        except FileExistsError:
            return False, 'Bakım daha önce denendi; tekrar yedekleme döngüsü engellendi. Önceki rapor: ' + str(state / 'REPORT.txt')
        backup = state / ('backup-' + uuid.uuid4().hex)
        backup.mkdir()
        for name in EDITOR_DIRS:
            if "Cannot go into subdir '" + name + "'" not in str(output):
                continue
            source = folder / name
            try:
                plain_chain(source)
                if not source.is_dir() or any(source.iterdir()):
                    notes.append(name + ': boş klasör değil; korundu.')
                    continue
                if referenced(folder, name):
                    notes.append(name + ': referans olmadığı doğrulanamadı; korundu.')
                    continue
                source.rename(backup / name)
                changed = True
                notes.append(name + ': yedeklendi → ' + str(backup / name))
            except (OSError, UnicodeError) as exc:
                notes.append(name + ': işlem yapılamadı (' + str(exc) + ').')
        # Only generated editor state, not the resource UID/import cache or game files.
        editor = folder / '.godot' / 'editor'
        if editor.exists() or editor.is_symlink():
            try:
                plain_chain(editor)
                if not editor.is_dir():
                    raise OSError('Editör önbelleği klasör değil')
                editor.rename(backup / 'godot-editor')
                changed = True
                notes.append('Godot editör önbelleği yedeklendi → ' + str(backup / 'godot-editor'))
            except OSError as exc:
                notes.append('Editör önbelleği korundu: ' + str(exc))
        if not changed:
            notes.append('Güvenli otomatik onarım uygulanamadı; dosya izinleri değiştirilmedi.')
        report = '\n'.join(notes)
        # Per-attempt unique backup also contains the recovery record.
        with (backup / 'RESTORE.txt').open('x', encoding='utf-8') as f:
            f.write('Godot kapalıyken yedekleri eski yollarına taşıyın. Mevcut dosyaların üzerine yazmayın.\n' + report)
        target = state / 'REPORT.txt'
        if target.exists() or target.is_symlink():
            if linked(target):
                raise OSError('Bakım raporu bağlantı; yazılmadı')
        target.write_text(report, encoding='utf-8')
        return changed, report
    except (OSError, UnicodeError) as exc:
        return changed, '\n'.join(notes + ['Bakım erişim kontrolü başarısız: ' + str(exc)])


def resolved(folder):
    """Allow a future incident only after an actually successful engine test."""
    try:
        claim = Path(folder).absolute() / '.studio' / 'maintenance' / 'attempted'
        if claim.exists():
            plain_chain(claim)
            claim.unlink()
    except OSError:
        pass  # Diagnostics must not turn a successful engine test into a failure.


def report_core_fault(exc, path=None):
    """Route internal Python defects to the board; no source/log/secret payloads."""
    import hashlib
    import traceback
    import core
    import hq_board as board
    if not isinstance(exc, (AttributeError, TypeError, NameError, AssertionError)):
        return None
    frames = traceback.extract_tb(exc.__traceback__)
    if not frames:
        return None
    last = frames[-1]
    file = Path(last.filename).resolve()
    if file.parent != (core.BASE / 'app').resolve():
        return None  # Not a confirmed studio frame (e.g. a custom tester).
    signature = f'{type(exc).__name__}: app/{file.name}:{last.lineno} ({last.name})'
    source = 'maintenance-' + hashlib.sha256(signature.encode()).hexdigest()[:16]
    with board._Tx(path) as db:
        old = db.execute('SELECT id FROM board_proposals WHERE source=?', (source,)).fetchone()
    if old:
        return old['id']
    request = board.propose([], 'Teknik bakım: çekirdek hatası ' + signature,
        source=source, impact='Otomatik hata kaydı 0 AI çağrısı. Kod değişikliği ayrı test/inceleme hattında.',
        code_request='Üretim sırasında Pardex çekirdeğinde yakalanan hata: ' + signature +
        '. Ayrı çekirdek kopyasında yeniden üret, regresyon testi ekle ve düzelt. '
        'Oyun dosyalarını veya işletim sistemi izinlerini değiştirme. Test ve bağımsız inceleme olmadan kurma.',
        path=path)
    return request['id']
