"""Offline-safe CLI, usable from GitHub Actions without any AI accounts."""
import argparse
import sys
import unittest
from pathlib import Path
import brain
import core


def main(argv=None):
 parser=argparse.ArgumentParser(description='Ultra Pro AI Studio Core v5 diagnostics')
 parser.add_argument('action',choices=['check','radar','summary','projects'])
 args=parser.parse_args(argv)
 if args.action=='check':
  print('Policy version:',brain.policy()['version'])
  print('Platforms:',', '.join(core.ENGINE_LABELS))
  print('Engine CLI tools:', {k:bool(v) for k,v in core.tool_status().items()})
  print('Policy text constraints:',brain.role_rules('implementer')[:200])
 elif args.action=='radar':
  brain.radar_check();print(brain.radar_report())
 elif args.action=='projects':
  for p,item in brain.list_projects().items():print(item['engine'],p)
 else:
  print('Projects:',len(brain.list_projects()))
  print('Evidence:',brain.evidence_summary())
  print('Policy:',brain.policy()['version'])
  print('Proposals:',len(brain.proposals()))
 return 0

if __name__=='__main__':sys.exit(main())
