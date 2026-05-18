#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deploy_api import build_ai_pro_results, normalize_ai_pro_request  # noqa: E402
import deploy_api  # noqa: E402
from hivision.plugin.ai_pro.engine import AIProEngine, AIProEngineConfig  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SAMPLE = ROOT / "demo" / "images" / "test0.jpg"


def redact_summary(result: dict[str, Any]) -> dict[str, Any]:
    metadata = result.get("promptMetadata") or {}
    ai_quality = result.get("aiQualityReport") or {}
    checks = ai_quality.get("checks") or {}
    return {
        "style": metadata.get("socialStyle") or result.get("promptTemplateId"),
        "status": result.get("status"),
        "providerStatus": metadata.get("providerStatus"),
        "providerSizeRequested": metadata.get("providerSizeRequested"),
        "providerSizeUsed": metadata.get("providerSizeUsed"),
        "providerAspectRatio": metadata.get("providerAspectRatio") or metadata.get("providerAspectRatioRequested"),
        "quality": {
            "status": metadata.get("qualityGateStatus") or result.get("qualityGate", {}).get("status"),
            "passed": ai_quality.get("passed") if ai_quality else result.get("qualityGate", {}).get("passed"),
            "fallbackToFree": result.get("fallbackToFree"),
            "fallbackReason": result.get("qualityGate", {}).get("fallbackReason") or metadata.get("fallbackReason"),
            "warningCodes": [item.get("code") for item in (ai_quality.get("warnings") or [])],
            "errorCodes": [item.get("code") for item in (ai_quality.get("errors") or [])],
        },
        "identity": (checks.get("identity") or {}).get("status"),
        "composition": (checks.get("composition") or {}).get("status"),
        "realism": (checks.get("realism") or {}).get("status"),
        "notForOfficialDocument": metadata.get("notForOfficialDocument"),
    }


def make_ai_pro(style: str) -> dict[str, Any]:
    raw = SimpleNamespace(enabled=True, modes=["social_photo"], promptParams={"socialStyle": style, "outputRatio": "1:1"}, consentAccepted=True)
    return normalize_ai_pro_request(raw)


def prepare_input(sample: Path, result_dir: Path) -> None:
    result_dir.mkdir(parents=True, exist_ok=True)
    target = result_dir / "official_idcreator.png"
    with Image.open(sample) as image:
        image.convert("RGB").save(target)


def provider_ready() -> bool:
    return bool((os.getenv("GPT_IMAGE_API_KEY") or os.getenv("OPENAI_API_KEY")) and (os.getenv("AI_PRO_PROVIDER") or os.getenv("GPT_IMAGE_PROVIDER")))


def run_case(style: str, sample: Path, output_root: Path) -> dict[str, Any]:
    task_id = f"t12c_{style}"
    result_dir = output_root / task_id
    prepare_input(sample, result_dir)
    results, stage = build_ai_pro_results(
        task_id,
        result_dir,
        make_ai_pro(style),
        {"fileId": f"free_{style}", "previewUrl": "dry-run-free-preview", "downloadUrl": "dry-run-free-download"},
        {"passed": True, "score": 95},
        options={"background": "white", "width": 295, "height": 413, "dpi": 300},
    )
    return {"stage": stage, "summary": redact_summary(results[0] if results else {})}


def main() -> None:
    parser = argparse.ArgumentParser(description="T12C social_photo real provider smoke. Safe by default: no paid API call without --real and provider env.")
    parser.add_argument("--real", action="store_true", help="Actually call configured GPT image provider. Requires env credentials/provider.")
    parser.add_argument("--sample", type=Path, default=DEFAULT_SAMPLE, help="Local sample image path. Not uploaded unless --real is set.")
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".runtime" / "social_photo_t12c_smoke", help="Local output directory.")
    args = parser.parse_args()

    if not args.sample.is_file():
        raise SystemExit(f"sample image not found: {args.sample}")

    real_ready = args.real and provider_ready()
    if not args.real:
        print(json.dumps({"status": "skipped", "reason": "pass --real to call provider; dry-run only", "styles": ["professional_social", "friendly_social"]}, ensure_ascii=False))
        return
    if not real_ready:
        print(json.dumps({"status": "skipped", "reason": "provider env missing; set AI_PRO_PROVIDER/GPT_IMAGE_PROVIDER and GPT_IMAGE_API_KEY or OPENAI_API_KEY", "styles": ["professional_social", "friendly_social"]}, ensure_ascii=False))
        return

    deploy_api.ai_pro_engine = AIProEngine(AIProEngineConfig.from_env())
    deploy_api.RESULT_DIR = args.output_dir
    args.output_dir.mkdir(parents=True, exist_ok=True)

    summaries = []
    for style in ("professional_social", "friendly_social"):
        summaries.append({"style": style, **run_case(style, args.sample, args.output_dir)})
    print(json.dumps({"status": "completed", "realProviderCalled": True, "outputDir": str(args.output_dir), "cases": summaries}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
