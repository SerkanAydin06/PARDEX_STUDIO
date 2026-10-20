"""2J: deterministic security properties; Docker/AI/network never launched."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import isolated_worker as iso
import worker_guard

DIGEST = 'local-python@sha256:' + 'e'*64


class IsolatedWorkerTests(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.home = Path(root.name)
        self.project = self.home / 'project'
        (self.project / 'tests').mkdir(parents=True)
        (self.project / 'app').mkdir()
        (self.project / 'tests' / 'test_ok.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_ok(self):self.assertTrue(True)\n')
        (self.project / 'app' / 'api.py').write_text('ANSWER=42\n')
        (self.project / '.studio').mkdir()
        (self.project / '.studio' / 'BRIEF.md').write_text('PRIVATE PLAN')
        (self.project / '.env').write_text('API_KEY=SECRET')
        self.calls = []
        self.env = {'PATH':os.environ.get('PATH','/usr/bin'),
                    'OPENAI_API_KEY':'DO-NOT-PASS','GITHUB_TOKEN':'SECRET'}

    def runner(self,args,cwd,timeout=0,env=None):
        self.calls.append((args,Path(cwd),timeout,env))
        if args[1]=='run':
            mount=args[args.index('--mount')+1]
            src=Path(mount.split('src=')[1].split(',dst=')[0])
            self.assertTrue(src.is_dir())
            self.assertTrue((src/'tests'/'test_ok.py').exists())
            self.assertFalse((src/'.studio').exists())
            self.assertFalse((src/'.env').exists())
            self.assertFalse((src/'.git').exists())
        return subprocess.CompletedProcess(args,0,'ok\nBearer SK-SECRET12345678910')

    def test_no_execution_without_explicit_owner_approval(self):
        with self.assertRaises(PermissionError):
            iso.run_python_regression(self.project,DIGEST,runner=self.runner,docker='docker',env=self.env)
        self.assertEqual(self.calls,[])

    def test_repo_tag_not_accepted(self):
        for x in ('python:3.12','python:latest','sha256:'+'e'*64,'bad image@sha256:'+'e'*64):
            with self.assertRaises(ValueError):iso.preflight(self.project,x,env=self.env)

    def test_preflight_is_free_and_does_not_invoke_docker(self):
        out=iso.preflight(self.project,DIGEST,env=self.env)
        self.assertFalse(out['docker_execution_verified'])
        self.assertTrue(out['no_ai_call'])

    def test_offline_security_flags_privacy_and_env_redaction(self):
        r=iso.run_python_regression(self.project,DIGEST,runner=self.runner,
            docker='docker',owner_confirms=True,env=self.env)
        self.assertTrue(r['passed'])
        self.assertEqual(len(self.calls),2)
        cmd,cwd,timeout,env=self.calls[-1]
        self.assertEqual(cmd[1],'run')
        for flag in ('--network','none','--read-only','--cap-drop=ALL',
                     '--security-opt=no-new-privileges','--pull=never',
                     '--pids-limit=64','--memory=512m','--cpus=1'):
            self.assertIn(flag,cmd)
        self.assertNotIn('OPENAI_API_KEY',env)
        self.assertNotIn('GITHUB_TOKEN',env)
        self.assertIn('--cidfile',cmd)
        self.assertEqual(r['staged']['files'],2)
        self.assertNotIn('SK-SECRET',r['output_tail'])
        self.assertTrue(r['no_model_or_subscription_calls'])

    def test_evolution_gate_uses_staged_worker_not_old_mount(self):
        import evolution
        with mock.patch.object(iso,'run_python_regression',return_value={
            'exit_code':0,'output_tail':'passed'}) as guarded:
            result=evolution.run_isolated_regression(self.project,owner_confirms=True)
        # no pinned image configured => safe runner rejects before any native code;
        # mock only checks that the integration uses the new narrow API.
        self.assertEqual(result.returncode,0)
        guarded.assert_called_once()
        self.assertEqual(guarded.call_args.kwargs['owner_confirms'],True)

    def test_evolution_gate_denies_without_owner_permission(self):
        import evolution
        with mock.patch.object(iso,'run_python_regression') as guarded:
            result=evolution.run_isolated_regression(self.project)
        self.assertEqual(result.returncode,126)
        guarded.assert_not_called()

    def test_strict_mode_still_blocks_cloud_cli(self):
        with self.assertRaises(RuntimeError):
            worker_guard.guard_native_agent(env={'PARDEX_REQUIRE_ISOLATED_AI':'1'})

    def test_old_worker_requires_approval_too(self):
        with self.assertRaises(PermissionError):
            worker_guard.offline_python_tests(self.project,DIGEST,docker='docker',runner=self.runner)

    def test_missing_docker_never_launches_host_python(self):
        with self.assertRaises(RuntimeError):
            iso.run_python_regression(self.project,DIGEST,docker='',runner=self.runner,
                owner_confirms=True,env=self.env)
        self.assertEqual(self.calls,[])

    def test_missing_local_image_never_runs(self):
        def absent(args,cwd,timeout=0,env=None):
            self.calls.append(args)
            return subprocess.CompletedProcess(args,1,'')
        with self.assertRaises(RuntimeError):
            iso.run_python_regression(self.project,DIGEST,docker='docker',runner=absent,
                owner_confirms=True,env=self.env)
        self.assertEqual(len(self.calls),1)

    def test_symlinks_refused(self):
        try:(self.project/'tests'/'linked.py').symlink_to(self.project/'app'/'api.py')
        except (OSError,NotImplementedError):self.skipTest('No symlink support')
        with self.assertRaises(ValueError):
            iso.run_python_regression(self.project,DIGEST,owner_confirms=True,
                                      docker='docker',runner=self.runner,env=self.env)
        self.assertEqual(self.calls,[])

    def test_private_folder_large_data_not_included(self):
        (self.project/'.studio'/'huge_secret.txt').write_text('x'*200_000)
        result=iso.run_python_regression(self.project,DIGEST,owner_confirms=True,
                                         docker='docker',runner=self.runner,env=self.env)
        self.assertEqual(result['staged']['files'],2)

    def test_file_size_limit_blocks_before_docker(self):
        (self.project/'app'/'large.py').write_bytes(b'a'*1_000_001)
        with self.assertRaises(ValueError):
            iso.run_python_regression(self.project,DIGEST,owner_confirms=True,
                                      docker='docker',runner=self.runner,env=self.env)
        self.assertEqual(self.calls,[])

    def test_remote_docker_env_rejected(self):
        with self.assertRaises(RuntimeError):
            iso.preflight(self.project,DIGEST,env={'DOCKER_HOST':'tcp://remote:2375'})

    def test_timeout_no_bool_allowed(self):
        with self.assertRaises(ValueError):
            iso.run_python_regression(self.project,DIGEST,owner_confirms=True,timeout=True,
                docker='docker',runner=self.runner,env=self.env)

    def test_known_container_id_force_cleanup(self):
        def timed(args,cwd,timeout=0,env=None):
            self.calls.append(args)
            if args[1]=='run':
                Path(args[args.index('--cidfile')+1]).write_text('abcdef0123456789')
                return subprocess.CompletedProcess(args,124,'timeout')
            return subprocess.CompletedProcess(args,0,'')
        r=iso.run_python_regression(self.project,DIGEST,owner_confirms=True,
               docker='docker',runner=timed,env=self.env)
        self.assertFalse(r['passed'])
        self.assertEqual(self.calls[-1][1:3],['rm','-f'])
        self.assertEqual(self.calls[-1][3],'abcdef0123456789')

    def test_no_cleanup_using_untrusted_cid(self):
        def fail(args,cwd,timeout=0,env=None):
            self.calls.append(args)
            if args[1]=='run':
                Path(args[args.index('--cidfile')+1]).write_text('not-a-container; rm -rf /')
                return subprocess.CompletedProcess(args,124,'timeout')
            return subprocess.CompletedProcess(args,0,'')
        iso.run_python_regression(self.project,DIGEST,owner_confirms=True,
               docker='docker',runner=fail,env=self.env)
        self.assertEqual(len(self.calls),2)


if __name__=='__main__':unittest.main()
