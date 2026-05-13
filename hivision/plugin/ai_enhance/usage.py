from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict


class AIEnhanceUsageLogger:
    @staticmethod
    def enabled() -> bool:
        value = os.getenv("AI_ENHANCE_USAGE_LOG_ENABLED", "1").strip().lower()
        return value not in {"0", "false", "off", "no"}

    @staticmethod
    def log_path() -> Path:
        return Path(os.getenv("AI_ENHANCE_USAGE_LOG_PATH", "/tmp/hivision-ai-enhance-usage.jsonl"))

    @staticmethod
    def estimated_cost() -> float | None:
        raw = os.getenv("AI_ENHANCE_ESTIMATED_COST_PER_REQUEST")
        if raw is None or not raw.strip():
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    def append(self, payload: Dict[str, Any]) -> bool:
        if not self.enabled():
            return False
        path = self.log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        line = dict(payload)
        line.setdefault("timestamp", time.strftime("%Y-%m-%dT%H:%M:%S%z"))
        with path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(line, ensure_ascii=False) + "\n")
        return True


USAGE_LOGGER = AIEnhanceUsageLogger()
