import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import core
import hq_store as store

class GodotPathTests(unittest.TestCase):
    def test_configured_executable_with_spaces_and_quotes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / 'OneDrive Desktop' / 'Godot_v4.7.1-stable_win64.exe'
            binary.parent.mkdir()
            binary.touch()
            with patch.object(store, 'DATABASE', root / 'company.db'), patch.object(core, 'which', return_value=None):
                store.update_settings({'godot_path': '"' + str(binary) + '"'})
                self.assertEqual(core.find_godot(), str(binary))
                binary.unlink()
                self.assertIsNone(core.find_godot())
                with self.assertRaises(ValueError):
                    store.update_settings({'godot_path': str(binary)})
                store.update_settings({'godot_path': ''})
                with patch.object(core, 'which', return_value='/bin/godot'):
                    self.assertEqual(core.find_godot(), '/bin/godot')

    def test_relative_paths_and_other_programs_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(store, 'DATABASE', Path(tmp) / 'hq.db'):
            with self.assertRaises(ValueError):
                store.update_settings({'godot_path': 'Godot.exe'})
            other = Path(tmp) / 'other.exe'
            other.touch()
            with self.assertRaises(ValueError):
                store.update_settings({'godot_path': str(other)})

if __name__ == '__main__':
    unittest.main()
