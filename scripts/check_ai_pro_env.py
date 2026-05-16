#!/usr/bin/env python3
"""Print redacted AI Pro runtime configuration status.

This intentionally never prints API key values. It is safe to run in deployment
checks and CI logs.
"""

from __future__ import annotations

import json
import os


def status(value: str | None) -> str:
    return "configured" if value else "missing"


def main() -> int:
    provider = os.getenv("AI_PRO_PROVIDER") or os.getenv("GPT_IMAGE_PROVIDER") or "mock"
    api_base = os.getenv("GPT_IMAGE_API_BASE") or os.getenv("OPENAI_BASE_URL") or ""
    model = os.getenv("GPT_IMAGE_MODEL") or os.getenv("OPENAI_IMAGE_MODEL") or "gpt-image-2"
    image_size = os.getenv("GPT_IMAGE_SIZE") or "auto"
    image_size_policy = os.getenv("GPT_IMAGE_SIZE_POLICY") or "auto"
    key_status = status(os.getenv("GPT_IMAGE_API_KEY") or os.getenv("OPENAI_API_KEY"))
    configured = provider != "mock" and key_status == "configured"
    print(json.dumps({
        "aiPro": {
            "provider": provider,
            "providerConfigured": configured,
            "apiBase": status(api_base),
            "model": model,
            "apiKey": key_status,
            "timeoutSeconds": os.getenv("AI_PRO_TIMEOUT_SECONDS") or os.getenv("GPT_IMAGE_TIMEOUT") or os.getenv("OPENAI_IMAGE_TIMEOUT") or "45",
            "imageSize": image_size,
            "imageSizePolicy": image_size_policy,
            "fallbackIfMissingCredentials": True,
        }
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
