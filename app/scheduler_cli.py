"""One-shot scheduler trigger; free dry-run is the default."""
import argparse
import json
import shift_scheduler

def main(args=None):
    p=argparse.ArgumentParser(description='PARDEX 2H scheduled AI shifts')
    p.add_argument('--execute',action='store_true',help='Execute one due and fully preapproved shift')
    a=p.parse_args(args)
    result=shift_scheduler.dispatch_due(execute=a.execute)
    print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
    return 2 if result.get('blocked') else 0

if __name__=='__main__':raise SystemExit(main())
