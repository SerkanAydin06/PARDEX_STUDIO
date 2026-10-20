"""Owner-invoked offline regression CLI; no autonomous model execution."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import isolated_worker


def main(argv=None):
    p = argparse.ArgumentParser(description='PARDEX offline Docker test worker')
    p.add_argument('operation', choices=('preview', 'run'))
    p.add_argument('source', help='Local project with app/ and tests/')
    p.add_argument('--image', required=True, help='Preloaded repository@sha256:<digest>')
    p.add_argument('--confirm', action='store_true', help='Explicitly approve one Docker run')
    args = p.parse_args(argv)
    if args.operation == 'run':
        result = isolated_worker.run_python_regression(args.source, args.image,
                                                       owner_confirms=args.confirm)
    else:
        result = isolated_worker.preflight(args.source, args.image)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if args.operation == 'preview' or result['passed'] else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, RuntimeError, PermissionError, OSError) as exc:
        print(type(exc).__name__ + ': ' + str(exc), file=sys.stderr)
        sys.exit(2)
