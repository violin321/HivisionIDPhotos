#!/usr/bin/env python3
"""Lightweight static smoke for T12B Social Photo Beta Web UI wiring.

This deliberately avoids paid providers and browser automation. It checks that the
front-end exposes only controlled social presets, sends the narrow payload, and
surfaces fallback/non-official metadata in the result panel.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CHECKS = {
    "WorkflowControls.tsx": [
        "Social Photo Beta",
        "SOCIAL_PHOTO_MODE: AiProMode = 'social_photo'",
        "professional_social",
        "friendly_social",
        "生成适合社交平台使用的自然头像，不适用于官方证件办理。",
        "promptParams: { socialStyle: style.value, outputRatio: '1:1' }",
        "不开放自由 prompt",
    ],
    "StudioShell.tsx": [
        "requestedAiProMode === 'social_photo'",
        "socialStyle: ((normalizedAiPro.promptParams?.socialStyle as SocialStyle | undefined) ?? 'professional_social')",
        "outputRatio: '1:1'",
    ],
    "ResultPanel.tsx": [
        "Social Photo Beta",
        "socialStyleLabel",
        "fallbackUsed",
        "fallbackReason",
        "notForOfficialDocument",
        "Social Photo Beta candidate",
    ],
}


def main() -> int:
    failures: list[str] = []
    for relative, needles in CHECKS.items():
        path = ROOT / "web" / ("components" if relative == "StudioShell.tsx" else "features/idphoto-workflow" if relative == "WorkflowControls.tsx" else "features/result") / relative
        text = path.read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                failures.append(f"{path.relative_to(ROOT)} missing: {needle}")

    doc = ROOT / "docs/social-photo-t12b.md"
    if not doc.exists():
        failures.append("docs/social-photo-t12b.md missing")
    else:
        doc_text = doc.read_text(encoding="utf-8")
        for needle in ["mode", "social_photo", "promptParams.socialStyle", "fallbackReason", "notForOfficialDocument"]:
            if needle not in doc_text:
                failures.append(f"docs/social-photo-t12b.md missing: {needle}")

    if failures:
        print("T12B UI smoke failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("T12B UI smoke passed: Social Photo Beta UI payload and report display markers found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
