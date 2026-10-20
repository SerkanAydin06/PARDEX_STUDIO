"""2I Windows Task Scheduler: safe preview and no implicit execution tests."""
import base64
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import windows_trigger as w
import windows_trigger_cli as cli


class FakeResult:
    def __init__(self,stdout='PARDEX_TASK_REGISTERED',code=0):
        self.stdout=stdout
        self.stderr='CONFIDENTIAL-SECRETS'
        self.returncode=code


class WindowsTriggerTests(unittest.TestCase):
    def setUp(self):
        td=tempfile.TemporaryDirectory();self.addCleanup(td.cleanup)
        base=Path(td.name)/'PARDEX dir'/'app';base.mkdir(parents=True)
        self.cli=base/'scheduler_cli.py';self.cli.write_text('print(1)')
        self.py=base/'python.exe';self.py.write_text('fake')
        self.calls=[]
        def run(cmd,**kwargs):
            self.calls.append((cmd,kwargs))
            return FakeResult()
        self.run=run
        self.options=dict(python=self.py,cli=self.cli,platform='nt',which=lambda name:'powershell.exe',runner=self.run)

    def plan(self,**kw):
        return w.preview(python=self.py,cli=self.cli,**kw)

    def payload(self):
        return base64.b64decode(self.calls[-1][0][-1]).decode('utf-16-le')

    def test_preview_never_runs_windows_or_ai_and_defaults_free(self):
        with mock.patch.object(w,'_powershell') as ps:
            p=self.plan()
            self.assertEqual(p['tick_mode'],'preview_only')
            self.assertTrue(p['owner_task_approvals_required'])
            self.assertEqual(p['expires_after_days'],7)
            self.assertFalse(p['real_ai_sandbox_provided'])
            self.assertTrue(p['run_only_when_logged_on'])
            ps.assert_not_called()

    def test_validation_hard_limits(self):
        for minutes in (0,4,61,True,'5'):
            with self.subTest(minutes=minutes),self.assertRaises(ValueError):self.plan(every_minutes=minutes)
        for days in (0,8,True,7.1):
            with self.subTest(days=days),self.assertRaises(ValueError):self.plan(for_days=days)
        with self.assertRaises(ValueError):self.plan(execute='yes')
        with self.assertRaises(ValueError):w.preview(python=self.py,cli=self.cli.parent/'other.py')

    def test_install_refuses_without_owner_and_without_native_risk_ack(self):
        with self.assertRaises(PermissionError):w.install(**self.options)
        with self.assertRaises(PermissionError):w.install(owner_confirms=True,execute=True,**self.options)
        self.assertEqual(self.calls,[])

    def test_install_preview_only_current_user_least_privilege(self):
        p=w.install(owner_confirms=True,**self.options)
        self.assertTrue(p['registered'])
        self.assertEqual(p['tick_mode'],'preview_only')
        decoded=self.payload()
        self.assertIn('-LogonType Interactive',decoded)
        self.assertIn('-RunLevel Limited',decoded)
        self.assertIn('-MultipleInstances IgnoreNew',decoded)
        self.assertIn('-RepetitionInterval (New-TimeSpan -Minutes 5)',decoded)
        self.assertIn("-B \"",decoded)
        self.assertNotIn('--execute',decoded)
        self.assertNotIn('PARDEX_ALLOW_SCHEDULED_NATIVE_AI=1',decoded)
        self.assertNotIn('CONFIDENTIAL-SECRETS',str(p))

    def test_install_execution_requires_second_confirmation(self):
        p=w.install(owner_confirms=True,acknowledges_native_risk=True,execute=True,**self.options)
        self.assertEqual(p['tick_mode'],'dispatch_once')
        self.assertIn('--execute',self.payload())
        self.assertTrue(p['runtime_native_opt_in_required'])

    def test_remove_requires_confirmation_status_is_read_only(self):
        with self.assertRaises(PermissionError):w.remove(runner=self.run,platform='nt',which=lambda _: 'powershell.exe')
        with mock.patch.object(w,'_powershell',return_value='INSTALLED') as p:
            self.assertTrue(w.status()['installed']);p.assert_called_once()
        self.calls.clear()
        self.run=lambda cmd,**kw:FakeResult('PARDEX_TASK_REMOVED')
        self.assertTrue(w.remove(owner_confirms=True,runner=self.run,platform='nt',which=lambda _: 'powershell.exe')['removed'])

    def test_no_nonwindows_run_or_fallback(self):
        with self.assertRaises(RuntimeError):w.install(owner_confirms=True,platform='posix',
            python=self.py,cli=self.cli,runner=self.run,which=lambda _:'powershell.exe')
        self.assertEqual(self.calls,[])
        with self.assertRaises(RuntimeError):w._powershell('x',platform='nt',which=lambda _:None)

    def test_errors_redacted_and_no_shell(self):
        def failure(cmd,**kwargs):
            self.assertEqual(kwargs['timeout'],35)
            self.assertEqual(cmd[1:4],['-NoLogo','-NoProfile','-NonInteractive'])
            self.assertNotIsInstance(cmd,str)
            return FakeResult(code=1)
        with self.assertRaises(RuntimeError) as x:
            w.install(owner_confirms=True,python=self.py,cli=self.cli,platform='nt',which=lambda _:'powershell.exe',runner=failure)
        self.assertNotIn('CONFIDENTIAL',str(x.exception))

    def test_ps_literal_quotes_escaped(self):
        self.assertEqual(w._ps("C:/owner's app"),"'C:/owner''s app'")
        with self.assertRaises(ValueError):w._ps('abc\n');

    def test_cli_preview_no_windows_operations(self):
        with mock.patch.object(cli.windows_trigger,'preview',return_value={'tick_mode':'preview_only'}) as p:
            self.assertEqual(cli.main(['--preview']),0)
            p.assert_called_once()
        with mock.patch.object(cli.windows_trigger,'install',return_value={'registered':True}) as ins:
            self.assertEqual(cli.main(['--install']),0)  # mocked, real install requires confirmation
            ins.assert_called_once()


if __name__=='__main__':unittest.main()
