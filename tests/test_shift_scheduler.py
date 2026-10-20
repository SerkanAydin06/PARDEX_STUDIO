"""2H: offline tests, no AI calls, network or billing."""
import sys
from pathlib import Path
from datetime import datetime,timedelta,timezone
import tempfile
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import shift_scheduler as s
import worker_supervisor as worker

A='TASK-aaaaaaaaaaaa'
B='TASK-bbbbbbbbbbbb'
T=datetime(2026,10,21,10,0,tzinfo=timezone.utc)
NOW=T-timedelta(minutes=10)

class ScheduledTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.db=Path(tmp.name)/'private'/'tasks.db'
        p=mock.patch.object(worker,'preview',return_value={
            'tasks':[{'id':A},{'id':B}],'blocked_reason':None})
        p.start();self.addCleanup(p.stop)
    def plan(self,native=True):
        return s.plan((A,B),T,T+timedelta(minutes=20),path=self.db,now=NOW,
               owner_confirms=True,allow_native_unisolated=native)
    def test_owner_approval_required(self):
        with self.assertRaises(PermissionError):
            s.plan((A,B),T,T+timedelta(minutes=20),path=self.db,now=NOW)
    def test_preview_calls_no_worker(self):
        self.plan()
        with mock.patch.object(worker,'run') as run:
            self.assertTrue(s.dispatch_due(path=self.db,now=T)['dry_run'])
            run.assert_not_called()
    def test_double_native_optin(self):
        self.plan(native=False)
        with mock.patch.object(worker,'run') as run:
            self.assertFalse(s.dispatch_due(path=self.db,execute=True,now=T,
                env={'PARDEX_ALLOW_SCHEDULED_NATIVE_AI':'1'})['executed'])
            run.assert_not_called()
    def test_strict_guard_blocks(self):
        self.plan()
        with mock.patch.object(worker,'run') as run:
            self.assertFalse(s.dispatch_due(path=self.db,execute=True,now=T,
                env={'PARDEX_ALLOW_SCHEDULED_NATIVE_AI':'1','PARDEX_REQUIRE_ISOLATED_AI':'1'})['executed'])
            run.assert_not_called()
    def test_single_use_when_opted_in(self):
        job=self.plan()
        with mock.patch.object(worker,'run',return_value={'id':'SHIFT-test','state':'completed'}) as run:
            a=s.dispatch_due(path=self.db,execute=True,now=T,env={'PARDEX_ALLOW_SCHEDULED_NATIVE_AI':'1'})
            b=s.dispatch_due(path=self.db,execute=True,now=T,env={'PARDEX_ALLOW_SCHEDULED_NATIVE_AI':'1'})
            self.assertEqual(a['status'],'completed');self.assertFalse(b['executed'])
            self.assertEqual(run.call_count,1)
            run.assert_called_once_with(path=self.db,expected_task_ids=(A,B),
                owner_confirms=True,max_tasks=2,max_minutes=30)
        self.assertEqual(s.get(job['id'],path=self.db)['state'],'completed')
    def test_failure_no_retry_and_no_secret_recorded(self):
        job=self.plan()
        with mock.patch.object(worker,'run',side_effect=RuntimeError('secret-token')) as run:
            self.assertEqual(s.dispatch_due(path=self.db,execute=True,now=T,
                env={'PARDEX_ALLOW_SCHEDULED_NATIVE_AI':'1'})['status'],'interrupted')
            s.dispatch_due(path=self.db,execute=True,now=T,env={'PARDEX_ALLOW_SCHEDULED_NATIVE_AI':'1'})
            run.assert_called_once()
        self.assertNotIn('secret',str(s.get(job['id'],path=self.db)))
    def test_cancellation_and_expiry(self):
        item=self.plan()
        with self.assertRaises(PermissionError):s.cancel(item['id'],path=self.db)
        self.assertEqual(s.cancel(item['id'],path=self.db,owner_confirms=True)['state'],'cancelled')
        next_job=self.plan()
        r=s.dispatch_due(path=self.db,execute=True,now=T+timedelta(hours=2),
                         env={'PARDEX_ALLOW_SCHEDULED_NATIVE_AI':'1'})
        self.assertFalse(r['executed'])
        self.assertEqual(s.get(next_job['id'],path=self.db)['state'],'expired')
    def test_preflight_change_blocks(self):
        with mock.patch.object(worker,'preview',return_value={
                'tasks':[{'id':B},{'id':A}],'blocked_reason':None}):
            with self.assertRaises(PermissionError):self.plan()
    def test_window_validation(self):
        with self.assertRaises(ValueError):
            s.plan((A,B),T.replace(tzinfo=None),T+timedelta(minutes=15),
                   path=self.db,now=NOW,owner_confirms=True)
        with self.assertRaises(ValueError):
            s.plan((A,B),T,T+timedelta(minutes=90),path=self.db,now=NOW,owner_confirms=True)
    def test_maximum_armed(self):
        for i in range(3):self.plan()
        with self.assertRaises(RuntimeError):self.plan()

if __name__=='__main__':unittest.main()
