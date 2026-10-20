"""Phase 2E: explicit fail-closed native agent gate."""
import os

def strict_worker_mode(env=None):
    return str((os.environ if env is None else env).get('PARDEX_REQUIRE_ISOLATED_AI','')).strip() == '1'

def guard_native_agent(env=None):
    if strict_worker_mode(env):
        raise RuntimeError('Isolated AI worker unavailable; native host CLI blocked.')
    return {'os_isolated':False,'mode':'native_owner_started'}

def offline_python_tests(project, image, *, timeout=120, docker=None, runner=None,
                         owner_confirms=False, env=None):
    """Staged 2J offline test gate; no original project mount or host fallback."""
    from isolated_worker import run_python_regression
    return run_python_regression(project, image, timeout=timeout, docker=docker,
        runner=runner, owner_confirms=owner_confirms, env=env)
