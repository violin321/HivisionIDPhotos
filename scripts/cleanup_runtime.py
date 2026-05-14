#!/usr/bin/env python3
"""Clean expired HivisionIDPhotos runtime uploads/results/tasks.

Keeps queued/processing task artifacts and uses the same IDPHOTO_RUNTIME_TTL_SECONDS
configuration as deploy_api.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deploy_api import RUNTIME_TTL_SECONDS, cleanup_runtime  # noqa: E402


def main() -> int:
    result = cleanup_runtime()
    print(json.dumps({"ok": True, "ttlSeconds": RUNTIME_TTL_SECONDS, "removed": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
