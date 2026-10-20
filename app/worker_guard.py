"""Phase 2E: explicit fail-closed native agent gate."""
import os

def strict_worker_mode(env=None):
    return str((os.environ if env is None else env).get('PARDEX_REQUIRE_ISOLATED_AI','')).strip() == '1'

def guard_native_agent(env=None):
    if strict_worker_mode(env):
        raise RuntimeError('Isolated AI worker unavailable; native host CLI blocked.')
    return {'os_isolated':False,'mode':'native_owner_started'}
