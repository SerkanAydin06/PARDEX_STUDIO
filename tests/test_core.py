import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
import core


class StudioTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.state_patch=mock.patch.object(core,'STATE',self.root/'config'/'state.json')
        self.state_patch.start();self.addCleanup(self.state_patch.stop)

    def mk(self,name='TestOyun',engine='godot'):
        return core.create_project(self.root,name,engine,'Turkce oyun fikri')

    def test_engine_list_contains_6(self):
        self.assertEqual(set(core.ENGINE_LABELS),{'godot','unity','unreal','flutter','android','web'})
    def test_creates_godot(self):
        p=self.mk()
        self.assertEqual(core.project_type(p),'godot')
        self.assertIn('main.tscn',(p/'project.godot').read_text())
        self.assertTrue((p/'scenes/main.tscn').is_file())
    def test_creates_web(self):
        p=self.mk(engine='web')
        self.assertEqual(core.project_type(p),'web')
        self.assertIn('lang="tr"',(p/'index.html').read_text())
    def test_refuses_fake_unreal(self):
        with self.assertRaises(RuntimeError):self.mk(engine='unreal')
    def test_refuses_fake_unity(self):
        with self.assertRaises(RuntimeError):self.mk(engine='unity')
    def test_refuses_fake_android(self):
        with self.assertRaises(RuntimeError):self.mk(engine='android')
    def test_refuses_flutter_missing_sdk(self):
        with mock.patch.object(core,'which',return_value=None):
            with self.assertRaises(RuntimeError):self.mk(engine='flutter')
    def test_preserves_existing_project_files(self):
        p=self.mk()
        (p/'AGENTS.md').write_text('Personal rules',encoding='utf-8')
        core.attach_project(p)
        self.assertEqual((p/'AGENTS.md').read_text(encoding='utf-8'),'Personal rules')
    def test_detect_flutter(self):
        p=self.root/'f';p.mkdir();(p/'pubspec.yaml').write_text('name: app')
        self.assertEqual(core.project_type(p),'flutter')
    def test_detect_unreal(self):
        p=self.root/'u';p.mkdir();(p/'Demo.uproject').write_text('{}')
        self.assertEqual(core.project_type(p),'unreal')
    def test_detect_unity(self):
        p=self.root/'u';(p/'ProjectSettings').mkdir(parents=True);(p/'ProjectSettings/ProjectVersion.txt').write_text('v')
        self.assertEqual(core.project_type(p),'unity')
    def test_detect_android(self):
        p=self.root/'a';p.mkdir();(p/'settings.gradle.kts').write_text('')
        self.assertEqual(core.project_type(p),'android')
    def test_unknown_rejected(self):
        p=self.root/'x';p.mkdir()
        with self.assertRaises(ValueError):core.attach_project(p)
    def test_auto_route_code_codex(self):
        self.assertEqual(core.route('Yeni ozellik / Kod'),('Codex','cli-varsayilan'))
    def test_auto_route_plan_sonnet(self):
        self.assertEqual(core.route('Mimari / Plan'),('Claude','sonnet'))
    def test_auto_route_review_gemini_auto(self):
        self.assertEqual(core.route('Inceleme / Analiz'),('Gemini','auto'))
    def test_strong_claude_opus(self):
        self.assertEqual(core.route('Mimari / Plan','Claude','En guclu'),('Claude','opus'))
    def test_strong_gemini_pro(self):
        self.assertEqual(core.route('Inceleme / Analiz','Gemini','En guclu'),('Gemini','pro'))
    def test_safe_env_clears_keys(self):
        with mock.patch.dict(os.environ,{'OPENAI_API_KEY':'abc','ANTHROPIC_API_KEY':'abc','GEMINI_API_KEY':'123','GOOGLE_API_KEY':'abc'}):
            env=core.safe_env()
            for s in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','GEMINI_API_KEY','GOOGLE_API_KEY'):
                self.assertNotIn(s,env)
    def test_usage_counter_per_day(self):
        core.record_usage('Codex');core.record_usage('Gemini')
        self.assertEqual(core.usage_count(),2)
        self.assertEqual(core.usage_count('Gemini'),1)
    def test_reject_empty_task_before_ai(self):
        p=self.mk()
        with self.assertRaises(RuntimeError):core.run_ai_task(p,'Yeni ozellik / Kod','')
        self.assertEqual(core.usage_count(),0)
    def test_respects_local_task_cap(self):
        p=self.mk();core.record_usage('Codex')
        with self.assertRaises(RuntimeError):core.run_ai_task(p,'Yeni ozellik / Kod','Add a button',day_limit=1)
    def test_asset_prompt_2d(self):
        s=core.create_asset_prompt('godot','korsan kilici','2D')
        self.assertIn('ChatGPT',s);self.assertNotIn('Meshy.ai',s)
    def test_asset_prompt_3d(self):
        s=core.create_asset_prompt('unity','korsan kilici','3D')
        self.assertIn('Meshy.ai',s)
    def test_lessons_are_deduplicated(self):
        p=self.mk()
        self.assertTrue(core.learn(p,'test','task',False,'test failed'))
        self.assertFalse(core.learn(p,'test','task',False,'test failed'))
        self.assertEqual((p/'.studio/LESSONS.md').read_text(encoding='utf-8').count('test failed'),1)
    def test_add_ci_no_overwrite(self):
        p=self.mk()
        dest=p/'.github/workflows';dest.mkdir(parents=True)
        (dest/'ci-ultra-pro.yml').write_text('user-owned')
        response=core.add_ci(p)
        self.assertIn('degismedi',response)
        self.assertEqual((dest/'ci-ultra-pro.yml').read_text(),'user-owned')
        self.assertTrue((dest/'weekly-health.yml').exists())
        self.assertTrue((p/'.github/dependabot.yml').exists())
    def test_ci_script_godot_project(self):
        p=self.mk()
        core.add_ci(p)
        r=subprocess.run([sys.executable,str(p/'.studio/ci_check.py')],cwd=p,capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
    def test_validate_unreal_does_not_lie(self):
        p=self.root/'Unreal';p.mkdir();(p/'game.uproject').write_text('{}')
        passed,report=core.validate(p)
        self.assertFalse(passed);self.assertIn('YAPILMADI',report)
    def test_validate_unity_does_not_lie(self):
        p=self.root/'Unity';(p/'ProjectSettings').mkdir(parents=True);(p/'ProjectSettings/ProjectVersion.txt').write_text('v')
        passed,report=core.validate(p)
        self.assertFalse(passed);self.assertIn('YAPILMADI',report)
    def test_ai_task_mock_no_real_network_or_cli(self):
        p=self.mk(engine='web')
        def fake_run(args, cwd, **kwargs):
            self.assertEqual(args[:3],['/tmp/codex','exec','--sandbox'])
            self.assertEqual(kwargs.get('env',{}).get('OPENAI_API_KEY'),None)
            return subprocess.CompletedProcess(args,0,'Yapildi')
        with mock.patch.object(core,'which',return_value='/tmp/codex'),mock.patch.object(core,'run',side_effect=fake_run):
            result=core.run_ai_task(p,'Yeni ozellik / Kod','Giris butonu ekle')
        self.assertFalse(result['success'])  # AI tamam, fakat Web icin gercek test yapilmadi
        self.assertEqual(core.usage_count(),1)
        self.assertTrue((p/'.studio/PROGRESS.md').is_file())
    def test_runtime_for_godot_missing_not_success(self):
        p=self.mk()
        with mock.patch.object(core,'find_godot',return_value=None):
            passed,report=core.validate(p)
        self.assertFalse(passed);self.assertIn('bulunur degil',report)
    def test_runtime_for_web_basic_is_not_build(self):
        p=self.mk(engine='web')
        passed,report=core.validate(p)
        self.assertFalse(passed);self.assertIn('test/build YAPILMADI',report)
    def test_project_state_active(self):
        p=self.mk();core.set_active(p)
        self.assertEqual(core.active_project(),p.resolve())

if __name__=='__main__': unittest.main()

class Extras(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
        self.p=Path(self.t.name)
        self.pstate=mock.patch.object(core,'STATE',self.p/'state.json');self.pstate.start();self.addCleanup(self.pstate.stop)
    def test_backup_does_not_include_secrets(self):
        p=core.create_project(self.p,'Test','web','fikir')
        (p/'.env').write_text('SUPERSECRET')
        (p/'main.js').write_text('let x=3')
        import zipfile
        arc=core.backup_code(p)
        with zipfile.ZipFile(arc) as z:
            self.assertIn('main.js',z.namelist())
            self.assertNotIn('.env',z.namelist())
        self.assertIn('backups/',(p/'.studio/.gitignore').read_text())
    def test_guided_limit_enforced_no_calls(self):
        p=core.create_project(self.p,'Test','web','fikir')
        with self.assertRaises(RuntimeError):core.guided_workflow(p,'new feature','En guclu',day_limit=2)
        self.assertEqual(core.usage_count(),0)
    def test_economy_models(self):
        self.assertEqual(core.route('Mimari / Plan','Claude','Ekonomik')[1],'haiku')
        self.assertEqual(core.route('Inceleme / Analiz','Gemini','Ekonomik')[1],'flash')

class ManualCheckTests(unittest.TestCase):
    def test_user_checks_gate_next_steps(self):
        with tempfile.TemporaryDirectory() as t:
            p=core.create_project(t,'StepGame','godot','a')
            first=core.next_step(p)
            self.assertEqual(first[0],1)
            second=core.approve_step(p,'Ben oynadim')
            self.assertEqual(second[0],2)
            self.assertEqual(len(core.step_status(p)),1)
