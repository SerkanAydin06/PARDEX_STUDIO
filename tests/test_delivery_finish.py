"""Last-mile offline product checks: readiness, demo, error paths and live data protection."""
import sys
from pathlib import Path
import tempfile
import unittest
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import core
import quick_demo
import project_delivery


class ReadyForUserTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root=Path(folder.name)
        self.store=self.root/'private'
        self.project=Path(quick_demo.create(self.root,owner_confirms=True))

    def test_demo_is_recognized_godot_and_has_real_player_source(self):
        self.assertEqual(core.project_type(self.project),'godot')
        self.assertIn('run/main_scene=',(self.project/'project.godot').read_text())
        self.assertIn('Input.get_vector',(self.project/'scripts/player.gd').read_text())
        self.assertIn('ExtResource',(self.project/'main.tscn').read_text())

    def test_demo_never_overwrites_existing_project(self):
        before=(self.project/'scripts/player.gd').read_bytes()
        with self.assertRaises(FileExistsError):quick_demo.create(self.root,owner_confirms=True)
        self.assertEqual(before,(self.project/'scripts/player.gd').read_bytes())

    def test_demo_owner_approval_is_mandatory(self):
        with self.assertRaises(PermissionError):quick_demo.create(self.root)

    def test_offline_end_to_end_flow_stages_and_requires_owner_to_apply(self):
        original=(self.project/'scripts/player.gd').read_text()
        def fake(project,kind,goal,**kwargs):
            file=Path(project)/'scripts/player.gd'
            file.write_text(file.read_text().replace('260.0','520.0'))
            return {'ai_ok':True,'verified':False,'test_report':'Godot local simulator not installed'}
        with mock.patch.object(core,'run_ai_task'):
            record=project_delivery.deliver(self.project,'Geminin hizini iki katina cikar',
                ['scripts/player.gd'],owner_confirms=True,allow_native_cli=True,
                runner=fake,home=self.store)
        self.assertTrue(record['requires_owner_approval_to_apply'])
        self.assertEqual(original,(self.project/'scripts/player.gd').read_text())
        import change_review
        change_review.apply(record['review_id'],record['digest'],owner_confirms=True,home=self.store/'reviews')
        self.assertIn('520.0',(self.project/'scripts/player.gd').read_text())

    def test_unsuccessful_ai_cannot_stage_code(self):
        def fake(project,kind,goal,**kwargs):
            (Path(project)/'scripts/player.gd').write_text('extends Node\n')
            return {'ai_ok':False,'verified':False}
        with self.assertRaisesRegex(RuntimeError,'did not succeed'):
            project_delivery.deliver(self.project,'Geminin hizini iki katina cikar',
                ['scripts/player.gd'],owner_confirms=True,allow_native_cli=True,
                runner=fake,home=self.store)
        self.assertFalse((self.store/'reviews').exists())

    def test_unrelated_owner_edit_blocks_stale_proposal(self):
        def fake(project,kind,goal,**kwargs):
            (Path(project)/'scripts/player.gd').write_text('extends Node2D\n')
            (self.project/'main.tscn').write_text('[gd_scene format=3]\n')
            return {'ai_ok':True,'verified':False}
        with self.assertRaisesRegex(RuntimeError,'Live project changed'):
            project_delivery.deliver(self.project,'Geminin hizini iki katina cikar',
                ['scripts/player.gd'],owner_confirms=True,allow_native_cli=True,
                runner=fake,home=self.store)
        self.assertFalse((self.store/'reviews').exists())

if __name__=='__main__':unittest.main()
