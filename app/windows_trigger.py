"""Owner-controlled Windows Task Scheduler integration for PARDEX.

Schedules a bounded one-shot *tick* every few minutes for at most seven days.
Default is reporting-only. Opting into --execute is not a sandbox and will
still require the two original 2H permissions before any CLI invocation.

Only the user's interactive, least-privileged account is used. No credentials,
password, provider tokens, elevation, hidden account, or paid service setup.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path
import shutil
import subprocess
import sys

TASK_NAME = 'PARDEX_STUDIO_Owner_Worker_Tick'


def _ps(value):
    """Represent literal Windows paths/arguments safely inside PowerShell."""
    if not isinstance(value, str) or not value or any(ord(x) < 32 for x in value):
        raise ValueError('Invalid Windows path or argument')
    return "'" + value.replace("'", "''") + "'"


def _paths(*, python=None, cli=None):
    try:
        exe=Path(python if python is not None else sys.executable).expanduser().resolve(strict=True)
        script=Path(cli if cli is not None else Path(__file__).with_name('scheduler_cli.py')).expanduser().resolve(strict=True)
    except (OSError,RuntimeError) as exc:
        raise ValueError('Python executable or scheduler CLI file not found') from exc
    if not exe.is_file() or not script.is_file() or script.name!='scheduler_cli.py' or script.parent.name!='app':
        raise ValueError('Expected existing Python and PARDEX app/scheduler_cli.py')
    # Reject quote characters in the inner quoted cmdline argument; these
    # characters cannot be part of normal Windows filenames anyway.
    if '"' in str(script) or '"' in str(exe):
        raise ValueError('Unsafe path containing double quote')
    return exe,script


def preview(*, every_minutes=5, for_days=7, execute=False, python=None, cli=None):
    """No Windows call or AI invocation. Establish exact installation contract."""
    if type(every_minutes) is not int or not 5<=every_minutes<=60:
        raise ValueError('Frequency must be between 5 and 60 minutes')
    if type(for_days) is not int or not 1<=for_days<=7:
        raise ValueError('Installation must expire within 1 to 7 days')
    if type(execute) is not bool:
        raise ValueError('Execute must be a boolean')
    exe,script=_paths(python=python,cli=cli)
    return {'task_name':TASK_NAME,'python':str(exe),'scheduler_script':str(script),
            'every_minutes':every_minutes,'expires_after_days':for_days,
            'tick_mode':'dispatch_once' if execute else 'preview_only',
            'os_user':'current_interactive_user','privileges':'least',
            'no_elevation':True,'run_only_when_logged_on':True,
            'concurrent_instance_policy':'ignore_new','automatic_retry':False,
            'owner_task_approvals_required':True,
            'runtime_native_opt_in_required':bool(execute),
            'real_ai_sandbox_provided':False,'service_runs_when_logged_out':False}


def _powershell(body,*,runner=None,platform=None,which=None):
    os_type=os.name if platform is None else platform
    if os_type!='nt':
        raise RuntimeError('Windows Task Scheduler is only available on Windows')
    binary = (shutil.which if which is None else which)('powershell.exe')
    if not binary:
        raise RuntimeError('Windows PowerShell unavailable; no installer executed')
    encoded=base64.b64encode(body.encode('utf-16-le')).decode('ascii')
    command=[binary,'-NoLogo','-NoProfile','-NonInteractive','-EncodedCommand',encoded]
    executor=subprocess.run if runner is None else runner
    try:
        result=executor(command,capture_output=True,text=True,timeout=35,check=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError('Windows Task Scheduler timed out; check task state manually') from exc
    if result.returncode!=0:
        # Do not leak Windows login names, secret paths, or environment from stderr.
        raise RuntimeError('Windows Task Scheduler rejected operation; check task state locally')
    return result.stdout.strip()


def _install_script(plan):
    py,script=plan['python'],plan['scheduler_script']
    arg='-B "' + script + '"' + (' --execute' if plan['tick_mode']=='dispatch_once' else '')
    return '''$ErrorActionPreference = 'Stop'
Import-Module ScheduledTasks -ErrorAction Stop
$user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute {exe} -Argument {arg} -WorkingDirectory {wd}
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes {minutes}) -RepetitionDuration (New-TimeSpan -Days {days})
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 35) -StartWhenAvailable:$false
Register-ScheduledTask -TaskName {task} -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force -ErrorAction Stop | Out-Null
Write-Output 'PARDEX_TASK_REGISTERED'
'''.format(exe=_ps(py),arg=_ps(arg),wd=_ps(str(Path(script).parent)),minutes=plan['every_minutes'],days=plan['expires_after_days'],task=_ps(TASK_NAME))


def install(*, owner_confirms=False, acknowledges_native_risk=False, execute=False,
            every_minutes=5, for_days=7, python=None, cli=None,
            runner=None, platform=None, which=None):
    """Installation requires explicit owner confirmation; native mode extra consent."""
    if owner_confirms is not True:
        raise PermissionError('Owner must explicitly confirm Windows task registration')
    if execute and acknowledges_native_risk is not True:
        raise PermissionError('Native unisolated execution requires separate risk acknowledgment')
    p=preview(every_minutes=every_minutes,for_days=for_days,execute=execute,python=python,cli=cli)
    out=_powershell(_install_script(p),runner=runner,platform=platform,which=which)
    if out!='PARDEX_TASK_REGISTERED':
        raise RuntimeError('Cannot verify Windows task registration')
    return dict(p,registered=True,windows_registration_reported=True)


def status(*,runner=None,platform=None,which=None):
    body=("$ErrorActionPreference='Stop'\nImport-Module ScheduledTasks -ErrorAction Stop\n"
          "$t = Get-ScheduledTask -TaskName " + _ps(TASK_NAME) + " -ErrorAction SilentlyContinue\n"
          "if ($null -eq $t) { Write-Output 'NOT_INSTALLED' } else { Write-Output 'INSTALLED' }\n")
    outcome=_powershell(body,runner=runner,platform=platform,which=which)
    if outcome not in ('INSTALLED','NOT_INSTALLED'):
        raise RuntimeError('Could not verify Windows task status')
    return {'task_name':TASK_NAME,'installed':outcome=='INSTALLED',
            'installation_does_not_prove_ai_execution':True}


def remove(*,owner_confirms=False,runner=None,platform=None,which=None):
    if owner_confirms is not True:
        raise PermissionError('Owner must explicitly confirm Windows task removal')
    body=("$ErrorActionPreference='Stop'\nImport-Module ScheduledTasks -ErrorAction Stop\n"
          "Unregister-ScheduledTask -TaskName " + _ps(TASK_NAME) + " -Confirm:$false -ErrorAction Stop\n"
          "Write-Output 'PARDEX_TASK_REMOVED'\n")
    outcome=_powershell(body,runner=runner,platform=platform,which=which)
    if outcome!='PARDEX_TASK_REMOVED':
        raise RuntimeError('Could not verify Windows task removal')
    return {'removed':True,'task_name':TASK_NAME}
