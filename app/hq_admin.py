"""Owner-only local administration. No AI calls and no provider account changes."""
import json
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path

import core
import hq_maintenance as maintenance
import hq_projects as projects
import hq_store as store
import task_queue


def _plain(path):
    # Validate existing ancestors even when the final destination does not exist.
    for p in (path, *path.parents):
        if p.exists() or p.is_symlink():
            if maintenance.linked(p):
                raise ValueError('Bağlantı/reparse noktası üzerinden veri yönetimi yapılmaz.')


def _schema(db):
    db.execute('CREATE TABLE IF NOT EXISTS admin_trash(id TEXT PRIMARY KEY, name TEXT, data TEXT, original TEXT, moved TEXT, at TEXT)')


def trash(path=None):
    with store._conn(path) as db:
        _schema(db)
        return [dict(r) for r in db.execute('SELECT id,name,original,moved,at FROM admin_trash ORDER BY at DESC')]


def remove(pid, confirmation, files=False, path=None, queue_path=None):
    p = projects.get(pid, path)
    if confirmation != p['name']:
        raise ValueError('Onay için proje adını aynen yazın.')
    original = moved = None
    if files and p['folder']:
        original = Path(p['folder']).expanduser().absolute()
        _plain(original)
        original = original.resolve()
        root = Path(store.settings(path)['projects_root']).expanduser().resolve()
        marker = original / '.studio' / projects.MARKER
        _plain(marker)
        if (original.parent != root or projects._inside_company(original) or
                original == core.HOME or original in core.HOME.parents or original in core.BASE.parents or
                not marker.is_file() or marker.stat().st_size > 200 or
                marker.read_text(encoding='utf-8').strip() != pid):
            raise ValueError('Klasör sahipliği doğrulanamadı. Yalnızca listeden kaldırabilirsiniz.')
        for other in projects.products(path):
            if other['id'] != pid and other['folder']:
                f = Path(other['folder']).resolve()
                if f == original or original in f.parents or f in original.parents:
                    raise ValueError('Klasör başka bir projeyle paylaşılıyor; dosyalar taşınamaz.')
        dest = root / '.pardex-trash'
        _plain(dest)
        dest.mkdir(exist_ok=True)
        moved = dest / (pid + '-' + uuid.uuid4().hex)
    queue = Path(queue_path or task_queue.DATABASE)
    with task_queue._conn(queue):
        pass
    with projects._Tx(path) as db:
        _schema(db)
        db.execute('ATTACH DATABASE ? AS queue', (str(queue),))
        db.execute('BEGIN IMMEDIATE')
        if db.execute("SELECT 1 FROM queue.tasks WHERE status='running'").fetchone():
            raise ValueError('Görev kuyruğu çalışıyor; önce bitmesini bekleyin.')
        if p['folder']:
            folder = Path(p['folder']).resolve()
            for job in db.execute("SELECT id,project,status FROM jobs WHERE status IN ('proposed','approved','running','blocked','failed')").fetchall():
                if job['project'] and Path(job['project']).resolve() == folder:
                    if job['status'] == 'running':
                        raise ValueError('Bu projede çalışan bir şirket görevi var.')
                    db.execute("UPDATE jobs SET status='rejected',note=?,updated_at=? WHERE id=?",
                               ('Proje kaldırıldı', core.now(), job['id']))
            for task in db.execute("SELECT id,project FROM queue.tasks WHERE status IN ('pending-owner','ready','needs-attention')").fetchall():
                if Path(task['project']).resolve() == folder:
                    db.execute("UPDATE queue.tasks SET status='cancelled',updated_at=? WHERE id=?", (core.now(), task['id']))
                    db.execute('INSERT INTO queue.task_events(task_id,time,action,note) VALUES(?,?,?,?)',
                               (task['id'], core.now(), 'owner-cancel', 'Proje kaldırıldı'))
        data = {'products': [dict(db.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone())]}
        for table in ('chat', 'packages', 'questions'):
            data[table] = [dict(r) for r in db.execute(f'SELECT * FROM {table} WHERE product_id=?', (pid,))]
        db.execute('INSERT INTO admin_trash VALUES(?,?,?,?,?,?)',
                   (pid, p['name'], json.dumps(data), str(original or ''), str(moved or ''), core.now()))
        if moved:
            # Durable recovery note covers a power loss between rename and DB commit.
            core.save_json(moved.with_suffix('.json'), {'id': pid, 'original': str(original), 'moved': str(moved), 'data': data})
            original.rename(moved)
        try:
            for table in ('chat', 'packages', 'questions'):
                db.execute(f'DELETE FROM {table} WHERE product_id=?', (pid,))
            db.execute('DELETE FROM products WHERE id=?', (pid,))
            db.commit()
        except Exception:
            if moved:
                moved.rename(original)
            raise
    return {'removed': pid, 'files': bool(moved)}


def restore(pid, path=None):
    with projects._Tx(path) as db:
        _schema(db)
        row = db.execute('SELECT * FROM admin_trash WHERE id=?', (pid,)).fetchone()
        if not row:
            raise ValueError('Çöp kutusunda proje bulunamadı.')
        data = json.loads(row['data'])
        original, moved = Path(row['original']), Path(row['moved'])
        if row['moved']:
            _plain(original)
            _plain(moved)
            if original.exists() or not moved.is_dir():
                raise ValueError('Hedef klasör dolu veya çöp kutusundaki dosyalar taşınmış; geri yüklenmedi.')
        # Restored projects never resume AI automatically.
        for p in data['products']:
            if p['stage'] not in ('planlama', 'tamamlandi', 'iptal'):
                p['stage'] = 'durdu'
        for table, rows in data.items():
            for r in rows:
                cols = ','.join('"' + k + '"' for k in r)
                db.execute(f'INSERT INTO {table} ({cols}) VALUES ({",".join("?" for _ in r)})', tuple(r.values()))
        if row['moved']:
            moved.rename(original)
        try:
            db.execute('DELETE FROM admin_trash WHERE id=?', (pid,))
            db.commit()
        except Exception:
            if row['moved']:
                original.rename(moved)
            raise
    return {'restored': pid}


def reset_company(confirmation, path=None, queue_path=None):
    if confirmation != 'SIFIRLA':
        raise ValueError('Onay için SIFIRLA yazın.')
    target = Path(path or store.DATABASE)
    queue = Path(queue_path or task_queue.DATABASE)
    settings = store.settings(path)
    backup = target.parent / 'admin-backups' / uuid.uuid4().hex
    _plain(backup)
    backup.mkdir(parents=True)
    # SQLite backup includes WAL contents; credentials and product files are not copied.
    with task_queue._conn(queue) as q:
        if q.execute("SELECT 1 FROM tasks WHERE status='running'").fetchone():
            raise ValueError('Görev kuyruğu çalışıyor; önce durmasını bekleyin.')
        with closing(sqlite3.connect(backup / 'task_queue.sqlite3')) as out:
            q.backup(out)
    with store._conn(path) as db:
        with closing(sqlite3.connect(backup / 'company.sqlite3')) as out:
            db.backup(out)
        db.execute('ATTACH DATABASE ? AS queue', (str(queue),))
        db.execute('BEGIN IMMEDIATE')
        if db.execute("SELECT 1 FROM queue.tasks WHERE status='running'").fetchone():
            raise ValueError('Görev kuyruğu çalışıyor; sıfırlanmadı.')
        for schema in ('main', 'queue'):
            tables = [r[0] for r in db.execute(f"SELECT name FROM {schema}.sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            for table in tables:
                if schema == 'main' and table == 'admin_trash':
                    continue
                db.execute(f'DELETE FROM {schema}."{table.replace(chr(34), chr(34)*2)}"')
        for key in ('godot_path', 'projects_root'):
            if key in settings:
                db.execute('INSERT INTO settings VALUES(?,?)', (key, json.dumps(settings[key])))
        db.execute('INSERT INTO settings VALUES(?,?)', ('paused', 'true'))
    store.event('patron', 'company-reset', '', str(backup), path)
    return {'backup': str(backup), 'message': 'Şirket sıfırlandı ve duraklatıldı. Proje dosyaları, çöp kutusu, günlük sayaç ve AI girişleri korundu.'}
