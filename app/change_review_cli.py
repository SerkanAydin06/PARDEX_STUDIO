"""Headless interface for *manual*, checksum-bound proposal review."""
from __future__ import annotations
import argparse
import json
import sys
import change_review


def main(argv=None):
    p = argparse.ArgumentParser(description='PARDEX AI code proposal review; no AI calls')
    p.add_argument('operation', choices=('stage', 'summary', 'diff', 'apply', 'rollback'))
    p.add_argument('--project')
    p.add_argument('--proposal')
    p.add_argument('--files', nargs='+')
    p.add_argument('--review-id')
    p.add_argument('--digest')
    p.add_argument('--confirm', action='store_true', help='Explicit owner approval; NOT identity verification')
    options = p.parse_args(argv)
    if options.operation == 'stage':
        result = change_review.stage(options.project, options.proposal, options.files)
    elif options.operation == 'diff':
        result = change_review.diff(options.review_id)
    elif options.operation == 'summary':
        result = change_review.summary(options.review_id)
    elif options.operation == 'apply':
        result = change_review.apply(options.review_id, options.digest,
                                     owner_confirms=options.confirm)
    else:
        result = change_review.rollback(options.review_id, options.digest,
                                        owner_confirms=options.confirm)
    print(result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, PermissionError) as exc:
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
        sys.exit(2)
