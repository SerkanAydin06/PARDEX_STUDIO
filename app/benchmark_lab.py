"""Phase 2E benchmark: compare SOURCE BEFORE editing; no AI calls."""
from pathlib import Path
import hashlib
import json
import core

SKIP={'.git','.studio','node_modules','Library','Temp','Saved','build','dist','__pycache__'}
EXT={'.py','.gd','.cs','.ts','.js','.kt','.dart','.json','.yml','.yaml','.godot','.md','.html','.css'}
def fingerprint(project):
    base=Path(project).resolve(strict=True)
    if core.project_type(base)=='unknown':raise ValueError('Unknown project')
    rows=[];total=0
    for f in sorted(base.rglob('*')):
        rel=f.relative_to(base)
        if any(x in SKIP for x in rel.parts):continue
        if f.is_symlink():raise ValueError('Symlinks disallowed in benchmark source')
        if not f.is_file() or f.suffix.lower() not in EXT:continue
        total+=f.stat().st_size
        if total>20000000 or len(rows)>=4000:raise ValueError('Benchmark corpus too large')
        rows.append((rel.as_posix(),hashlib.sha256(f.read_bytes()).hexdigest()))
    if not rows:raise ValueError('No source files')
    return {'fingerprint':hashlib.sha256(json.dumps(rows).encode()).hexdigest(),
            'files':len(rows),'engine':core.project_type(base)}
def comparable(a,b,task_a,task_b,test_a,test_b,version_a,version_b):
    params=(task_a,task_b,test_a,test_b,version_a,version_b)
    valid=all(isinstance(x,str) and x.strip() and len(x)<500 for x in params)
    equal=bool(valid and a.get('fingerprint')==b.get('fingerprint')
        and a.get('engine')==b.get('engine')
        and task_a==task_b and test_a==test_b and version_a==version_b)
    return {'ready_for_owner_approved_pilot':equal,'quality_or_cost_proven':False}
