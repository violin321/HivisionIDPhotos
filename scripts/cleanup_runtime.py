#!/usr/bin/env python3
"""Clean expired HivisionIDPhotos runtime uploads/results/tasks.

Keeps queued/processing task artifacts and uses the same
IDPHOTO_RUNTIME_TTL_SECONDS configuration as deploy_api.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deploy_api import RUNTIME_TTL_SECONDS, cleanup_runtime  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean expired uploads/results/tasks from .runtime.")
    parser.add_argument("--dry-run", action="store_true", help="count expired artifacts without deleting them")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON (default; kept for explicit timer usage)")
    args = parser.parse_args()

    try:
        result = cleanup_runtime(dry_run=args.dry_run)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1

    print(json.dumps({"ok": True, "dryRun": args.dry_run, "ttlSeconds": RUNTIME_TTL_SECONDS, "removed": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
