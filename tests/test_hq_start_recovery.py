"""'Bunu yap' must never leave a half-made folder that blocks a retry; Git is checked before anything
is created; the owner is told what the safe copy left out. Offline, fake AI."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
sys.path.insert(0, str(ROOT))
import core  # noqa: E402
import hq_projects as hp  # noqa: E402
import hq_store as store  # noqa: E402
from tests.test_hq_projects import FakeAI  # noqa: E402

REAL_WHICH = core.which
NO_GIT = lambda n: None if n == 'git' else REAL_WHICH(n)  # noqa: E731


@unittest.skipUnless(shutil.which('git'), 'git not installed')
class StartRecoveryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.db = self.root / 'hq.sqlite3'
        self.work = self.root / 'urunler'
        for p in (mock.patch.object(core, 'STATE', self.root / 'state.json'),
                  mock.patch.object(hp, '_scratch', lambda: str(self.root))):
            p.start()
            self.addCleanup(p.stop)
        store.update_settings({'projects_root': str(self.work)}, self.db)
        self.original = core.create_project(self.root, 'Vadi', 'godot', 'x')

    def product(self, name='Vadi', engine='godot'):
        p = hp.new_product(name, 'oyun', self.db)
        hp._set(p['id'], self.db, spec=json.dumps({'name': name, 'engine': engine, 'summary': 'x',
                                                   'features': ['a', 'b']}))
        return p['id']

    def folders(self):
        return sorted(x.name for x in self.work.iterdir()) if self.work.exists() else []

    def test_missing_git_creates_nothing_and_retry_works_after_install(self):
        pid = self.product()
        with mock.patch.object(core, 'which', NO_GIT):
            for _ in range(2):
                with self.assertRaisesRegex(ValueError, 'Git kurulu değil'):
                    hp.start(pid, self.db, ai=FakeAI(), existing_folder=str(self.original))
        self.assertEqual(self.folders(), [])
        self.assertEqual(hp.get(pid, self.db)['stage'], 'planlama')
        p = hp.start(pid, self.db, ai=FakeAI(), existing_folder=str(self.original))
        self.assertEqual(p['stage'], 'uretim')

    def test_any_failure_after_creation_removes_only_the_new_folder(self):
        for existing in (str(self.original), ''):
            pid = self.product('Kopya' if existing else 'Yeni', 'godot' if existing else 'web')
            with mock.patch.object(hp, '_commit', side_effect=RuntimeError('disk dolu')):
                with self.assertRaises(RuntimeError):
                    hp.start(pid, self.db, ai=FakeAI(), existing_folder=existing)
            self.assertEqual(self.folders(), [], existing)
            self.assertTrue((self.original / 'project.godot').is_file())  # original untouched
            self.assertEqual(hp.start(pid, self.db, ai=FakeAI(), existing_folder=existing)['stage'], 'uretim')
            shutil.rmtree(self.work)

    def test_legacy_leftover_copy_is_preserved(self):
        pid = self.product()
        leftover = self.work / ('Vadi-kopya-' + pid[2:])
        (leftover / '.studio').mkdir(parents=True)
        (leftover / 'project.godot').write_text('x')  # old version, no ownership marker
        (leftover / 'valuable.gd').write_text('user changes', encoding='utf-8')
        p = hp.start(pid, self.db, ai=FakeAI(), existing_folder=str(self.original))
        self.assertNotEqual(Path(p['folder']), leftover.resolve())
        self.assertTrue((Path(p['folder']) / '.git').is_dir())
        self.assertEqual((leftover / 'valuable.gd').read_text(), 'user changes')

    def test_other_products_folders_are_never_deleted(self):
        a = self.product('Vadi', 'web')
        pa = hp.start(a, self.db, ai=FakeAI())
        work_a = Path(pa['folder'])
        (work_a / 'emek.js').write_text('// A projesinin işi')
        b = self.product('Vadi', 'web')
        stray = self.work / ('Vadi-' + b[-4:])
        stray.mkdir()
        (stray / 'index.html').write_text('başka bir işin')  # not ours: no marker
        pb = hp.start(b, self.db, ai=FakeAI())
        self.assertTrue((work_a / 'emek.js').is_file())
        self.assertTrue((stray / 'index.html').is_file())
        self.assertNotIn(Path(pb['folder']), (work_a, stray))

    def test_owner_is_told_what_the_copy_left_out(self):
        (self.original / 'client_token.json').write_text('{"t":"x"}')
        (self.original / 'secrets').mkdir()
        (self.original / 'secrets' / 'k.txt').write_text('x')
        (self.original / 'tool.exe').write_bytes(b'MZ')
        (self.original / 'oyun_verisi.json').write_text('{}')
        pid = self.product()
        ai = FakeAI(('PASS',) * 6)
        p = hp.start(pid, self.db, ai=ai, existing_folder=str(self.original))
        chat = p['chat'][-1]['text']
        self.assertIn('client_token.json', chat)
        self.assertIn('secrets', chat)
        self.assertIn('.exe', chat)
        self.assertNotIn('oyun_verisi', chat)
        self.assertTrue((Path(p['folder']) / 'oyun_verisi.json').is_file())
        p = hp.run_production(pid, self.db, ai=ai, tester=lambda f: (True, 'OK'))
        self.assertIn('client_token.json', p['report'])


if __name__ == '__main__':
    unittest.main()
