"""Small local Windows Task Scheduler management console (no API calls)."""
from __future__ import annotations

import argparse
import json
import windows_trigger


def main(argv=None):
    parser=argparse.ArgumentParser(description='PARDEX owner-controlled Windows task trigger')
    action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--preview',action='store_true')
    action.add_argument('--status',action='store_true')
    action.add_argument('--install',action='store_true')
    action.add_argument('--remove',action='store_true')
    parser.add_argument('--confirm',action='store_true',help='Explicit owner approval of install/removal')
    parser.add_argument('--execute',action='store_true',help='Schedule native dispatch instead of zero-AI preview')
    parser.add_argument('--acknowledge-unisolated',action='store_true',help='Accept OS-unisolated native CLI risk')
    parser.add_argument('--every',type=int,default=5)
    parser.add_argument('--days',type=int,default=7)
    args=parser.parse_args(argv)
    try:
        if args.preview:out=windows_trigger.preview(every_minutes=args.every,for_days=args.days,execute=args.execute)
        elif args.status:out=windows_trigger.status()
        elif args.install:out=windows_trigger.install(owner_confirms=args.confirm,
            acknowledges_native_risk=args.acknowledge_unisolated,execute=args.execute,
            every_minutes=args.every,for_days=args.days)
        else:out=windows_trigger.remove(owner_confirms=args.confirm)
    except (ValueError,PermissionError,RuntimeError,OSError) as err:
        print(json.dumps({'ok':False,'type':type(err).__name__,
                          'reason':'Task Scheduler configuration or permission check failed'},ensure_ascii=False))
        return 2
    print(json.dumps(out,ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
