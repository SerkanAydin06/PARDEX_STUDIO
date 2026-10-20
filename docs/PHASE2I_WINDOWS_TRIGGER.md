# Phase 2I — Windows Task Scheduler integration (owner-controlled)

### What works
- `app/windows_trigger.py` creates/removes exactly one scheduled task under the **current interactive Windows user**, least privilege, one instance at a time. It expires after a bounded 1–7 days. Windows must be running and the user logged in.
- Every 5–60 minutes Windows starts `app/scheduler_cli.py` for one tick. The **default task is dry-run**: it checks due shifts without AI calls, billing, task acceptance, autonomous retries or secret access.
- User can preview task configuration locally and explicitly confirm registration/removal using `06_WINDOWS_AI_TETIKLEYICI.cmd` or `python app/windows_trigger_cli.py --preview|--install --confirm|--status|--remove --confirm`.
- Advanced, *risk-acknowledged* native execution installation is possible only with `--install --confirm --execute --acknowledge-unisolated`. The 2H engine **still separately requires** owner-preauthorized exact task IDs, per-schedule native consent, process environment `PARDEX_ALLOW_SCHEDULED_NATIVE_AI=1` and strict isolation mode **off**. **Do not enable on a computer with confidential files unless risks are assessed.** This option is NOT accessible from the simple CMD menu.
- Scheduler registration itself does not buy cloud services, contact model APIs, execute AI commands or enable spending.

### Important limitations
- **This is a Windows trigger, not a secure AI sandbox**. Claude/Codex/Gemini subscription logins do not automatically run safely in a container. `PARDEX_REQUIRE_ISOLATED_AI=1` blocks native agents; it does not cause them to run in a container.
- Docker's existing `worker_guard.offline_python_tests` is for **offline verification**, not for authenticated agent work.
- No always-on service while logged out, no installation as SYSTEM/admin, and no promise a Windows registration works before real Windows testing.
- Scheduler command may fail depending on Windows Task Scheduler policies and permissions. There is no OS test in this Linux CI environment.
- Tick execution is one-shot and finite; only the 2H `dispatch_due` may claim an armed shift, and its own two approvals and SQLite locking remain authoritative. The Windows Task Scheduler cannot force a blocked job to execute.

### Verification and rollback
Run `python -m unittest discover -s tests -p 'test_*.py' -q`. PR automated checks run Python tests on Linux; inspect a Windows 10/11 machine before enabling real native execution. To undo installation, run `06_WINDOWS_AI_TETIKLEYICI.cmd` option 4, or `python app/windows_trigger_cli.py --remove --confirm`. Revert the PR to remove source code. **Reverting GitHub code alone does not remove an already installed Windows scheduled task.**
