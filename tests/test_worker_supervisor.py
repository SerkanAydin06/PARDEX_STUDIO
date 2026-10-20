"""2G offline worker lifecycle and owner-approval tests; no paid model calls."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import worker_supervisor as w
import operations
import task_queue as q

A="TASK-aaaaaaaaaaaa"
B="TASK-bbbbbbbbbbbb"


class WorkerTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db=Path(tmp.name)/"queue.sqlite3"
        with q._conn(self.db) as d:
            for task,prio in ((A,5),(B,4)):
                d.execute("""INSERT INTO tasks
                (id,project,title,kind,provider_preference,quality,priority,
                 max_minutes,status,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (task,tmp.name,"Do task "+task,"Yeni ozellik / Kod",
                 "Codex","Dengeli",prio,8,"ready","2026","2026"))

    def plan(self):
        calls=[0]
        def p(**kwargs):
            ids=(A,B)
            if kwargs.get("max_cli_calls")==1:
                i=min(calls[0],1)
                calls[0]+=1
                ids=(ids[i],)
            return {"tasks":[{"id":x,"max_minutes":8} for x in ids],
                    "planned_calls":len(ids),"blocked_reason":None}
        return mock.patch.object(operations,"preview_shift",side_effect=p)

    def test_free_preview_no_ai(self):
        with self.plan(),mock.patch.object(operations,"run_shift") as run:
            info=w.preview(path=self.db)
        self.assertEqual(info["planned_calls"],2)
        self.assertFalse(info["os_sandbox_provided"])
        self.assertTrue(info["owner_start_required"])
        self.assertFalse(w.recent(path=self.db))
        run.assert_not_called()

    def test_owner_approval_and_changed_order(self):
        with self.assertRaises(PermissionError):
            w.run((A,B),path=self.db)
        with self.assertRaises(PermissionError):
            w.run((A,A),path=self.db,owner_confirms=True)
        with self.plan(),mock.patch.object(operations,"run_shift") as run:
            with self.assertRaises(PermissionError):
                w.run((B,A),path=self.db,owner_confirms=True)
            run.assert_not_called()

    def test_two_tasks_and_private_receipt(self):
        def fake(**kwargs):
            return {"executed":[{"id":kwargs["authorized_task_ids"][0],
                     "status":"awaiting-acceptance","secret_content":"secret"}]}
        with self.plan(),mock.patch.object(operations,"run_shift",side_effect=fake) as run:
            out=w.run((A,B),path=self.db,owner_confirms=True)
        self.assertEqual(out["state"],"completed")
        self.assertEqual(len(out["processed"]),2)
        self.assertNotIn("secret",str(out))
        self.assertEqual(run.call_count,2)
        with q._conn(self.db) as d:
            self.assertEqual(d.execute("SELECT count(*) FROM tasks WHERE status='accepted'").fetchone()[0],0)

    def test_cooperative_stop(self):
        def fake(**kwargs):
            current=w.recent(path=self.db)[0]
            w.request_stop(current["id"],path=self.db,owner_confirms=True)
            return {"executed":[{"id":kwargs["authorized_task_ids"][0],
                                 "status":"awaiting-acceptance"}]}
        with self.plan(),mock.patch.object(operations,"run_shift",side_effect=fake) as run:
            out=w.run((A,B),path=self.db,owner_confirms=True)
        self.assertEqual(out["state"],"stopped")
        self.assertEqual(len(out["processed"]),1)
        run.assert_called_once()

    def test_failure_never_retries(self):
        with self.plan(),mock.patch.object(operations,"run_shift",return_value={
                "executed":[{"id":A,"status":"needs-attention"}]}) as run:
            out=w.run((A,B),path=self.db,owner_confirms=True)
        self.assertEqual(out["state"],"stopped")
        run.assert_called_once()

    def test_error_cannot_disclose_log_and_manual_recovery(self):
        with self.plan(),mock.patch.object(operations,"run_shift",side_effect=ValueError("private-data")):
            out=w.run((A,B),path=self.db,owner_confirms=True)
        self.assertEqual(out["state"],"interrupted")
        self.assertNotIn("private-data",str(out))
        with self.assertRaises(PermissionError):
            w.recover(out["id"],path=self.db)
        with self.assertRaises(ValueError):
            w.recover(out["id"],path=self.db,owner_confirms=True)

    def test_orphaned_shift_blocks_new_shift(self):
        with q._conn(self.db) as d:
            w._schema(d)
            d.execute("""INSERT INTO worker_sessions
            (id,started_at,state,task_ids) VALUES('SHIFT-old','2026','running','[]')""")
        with self.plan():
            self.assertEqual(w.preview(path=self.db)["planned_calls"],0)
            with self.assertRaises(PermissionError):
                w.run((A,B),path=self.db,owner_confirms=True)
        with self.assertRaises(PermissionError):
            w.recover("SHIFT-old",path=self.db)
        self.assertEqual(w.recover("SHIFT-old",path=self.db,owner_confirms=True)["state"],"interrupted")

    def test_limits(self):
        for options in ({"max_tasks":3},{"max_tasks":0},{"max_minutes":1},{"max_minutes":99}):
            with self.assertRaises(ValueError):
                w.preview(path=self.db,**options)
        with self.assertRaises(ValueError):
            w.recent(path=self.db,limit=0)

if __name__=="__main__":
    unittest.main()
