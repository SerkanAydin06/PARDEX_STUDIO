"""Daily limit defaults and one-time migration; no AI calls."""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import hq_store as store

class DailyLimitTests(unittest.TestCase):
    def test_default_and_later_owner_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'hq.db'
            self.assertEqual(store.settings(path)['day_call_limit'], 100)
            store.update_settings({'day_call_limit': 40}, path)
            self.assertEqual(store.settings(path)['day_call_limit'], 40)

    def test_migrate_legacy_default_but_preserve_custom_limit(self):
        for old, expected in [(40, 100), (25, 25), (150, 150)]:
            with self.subTest(old=old), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'hq.db'
                with sqlite3.connect(path) as db:
                    db.execute('CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
                    db.execute('INSERT INTO settings VALUES(?,?)', ('day_call_limit', json.dumps(old)))
                self.assertEqual(store.settings(path)['day_call_limit'], expected)
                self.assertEqual(store.settings(path)['day_call_limit'], expected)
