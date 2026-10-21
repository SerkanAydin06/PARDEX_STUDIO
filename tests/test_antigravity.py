"""Google consumer CLI migration: no live calls."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import core
import hq_setup as setup
import hq_router as router

class AntigravityTests(unittest.TestCase):
    def test_old_binary_is_never_selected(self):
        with patch.object(core.shutil, 'which', side_effect=lambda x: '/bin/agy' if x == 'agy' else None):
            self.assertEqual(core.which('gemini'), '/bin/agy')
        with patch.object(core.shutil, 'which', return_value=None), patch.object(core.Path, 'is_file', return_value=False):
            self.assertIsNone(core.which('gemini'))

    def test_legacy_models_and_flags(self):
        args, stdin = core.normalize_google_args(['/bin/agy', '--model', 'flash', '--prompt', 'hello'], None)
        self.assertEqual(args, ['/bin/agy', '--prompt', 'hello'])
        with self.assertRaises(ValueError):
            core.normalize_google_args(['agy', '--approval-mode', 'auto_edit'])
        self.assertIn('custom-model', core.google_command('agy', 'hello', 'custom-model'))

    def test_hq_stdin_is_explicit_prompt(self):
        args = router.build_cmd('Gemini', 'agy', 'pro', '', 'read')
        args, stdin = core.normalize_google_args(args, 'review this')
        self.assertEqual(args, ['agy', '--prompt', 'review this'])
        self.assertIsNone(stdin)
        self.assertNotIn('--dangerously-skip-permissions', args)

    def test_windows_installer_and_login(self):
        base = Path(__file__).resolve().parents[1]
        with patch.object(setup.os, 'name', 'nt'):
            # Path creation must remain POSIX in a Linux test, so use a prebuilt path.
            with patch.object(setup.core, 'BASE', base):
                self.assertIn('antigravity-kur.ps1', setup.install_command('gemini')[-1])
        with patch.object(core, 'which', return_value='/bin/agy'):
            self.assertEqual(setup.login_command('gemini'), ['/bin/agy'])

if __name__ == '__main__':
    unittest.main()
