from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

DEFAULT_PROMPT_VERSION = "2026-05-phase1"
FALLBACK_TEMPLATE_ID = "ai_repair_basic"
SUPPORTED_MODES = {"ai_repair", "ai_blue_formal_id_photo", "executive_headshot", "social_photo"}
SOCIAL_PHOTO_STYLES = {"professional_social", "friendly_social"}

MODE_ALIASES: dict[str, str] = {
    "repair": "ai_repair",
    "ai_repair": "ai_repair",
    "background_template": "ai_blue_formal_id_photo",
    "outfit": "executive_headshot",
    "social_photo": "social_photo",
    "ai_blue_formal_id_photo": "ai_blue_formal_id_photo",
    "executive_headshot": "executive_headshot",
}

MODE_TEMPLATE: dict[str, str] = {
    "ai_repair": "ai_repair_basic",
    "ai_blue_formal_id_photo": "ai_blue_formal_id_photo",
    "executive_headshot": "executive_headshot_apple_style",
    "social_photo": "professional_social",
}

PROMPT_TEMPLATE_REGISTRY: dict[str, dict[str, dict[str, Any]]] = {
    "executive_headshot_apple_style": {
        DEFAULT_PROMPT_VERSION: {
            "id": "executive_headshot_apple_style",
            "version": DEFAULT_PROMPT_VERSION,
            "mode": "executive_headshot",
            "status": "mock",
            "creditCost": 3,
            "usageLabel": "non_official_portrait",
            "userParamsSchema": {"outfit": "string", "expression": "string", "style": "string", "retouchLevel": "low|medium|high"},
            "promptMetadata": {"styleFamily": "executive studio portrait", "officialUse": False, "warning": "AI 形象照 / 非正式证件用途"},
        },
    },
    "ai_blue_formal_id_photo": {
        DEFAULT_PROMPT_VERSION: {
            "id": "ai_blue_formal_id_photo",
            "version": DEFAULT_PROMPT_VERSION,
            "mode": "ai_blue_formal_id_photo",
            "status": "mock",
            "creditCost": 2,
            "usageLabel": "official_candidate",
            "userParamsSchema": {"backgroundColor": "white|blue|red|gray|custom", "outfit": "string", "expression": "string", "retouchLevel": "low|medium|high"},
            "promptMetadata": {"operation": "generic ID photo AI enhancement", "outfitBaseline": "dark suit, white shirt", "cameraTexture": "Canon 5D-like", "warning": "AI 增强证件照候选，需按提交平台要求核验"},
        },
    },
    "cn_blue_480x640_20_40kb": {
        DEFAULT_PROMPT_VERSION: {
            "id": "cn_blue_480x640_20_40kb",
            "version": DEFAULT_PROMPT_VERSION,
            "mode": "ai_blue_formal_id_photo",
            "status": "spec_profile",
            "creditCost": 0,
            "usageLabel": "official_candidate",
            "userParamsSchema": {"outputSpec": "480x640", "backgroundColor": "blue"},
            "promptMetadata": {
                "specProfile": {"width": 480, "height": 640, "dpi": 300, "fileKbRange": [20, 40], "backgroundColor": "blue"},
                "qualityRules": ["single frontal face", "plain blue background", "verify platform file-size constraints"],
            },
        },
    },

    "professional_social": {
        DEFAULT_PROMPT_VERSION: {
            "id": "professional_social",
            "version": DEFAULT_PROMPT_VERSION,
            "mode": "social_photo",
            "status": "mock",
            "creditCost": 0,
            "usageLabel": "non_official_social_photo",
            "userParamsSchema": {"socialStyle": "professional_social", "outputRatio": "1:1"},
            "promptMetadata": {
                "domain": "social_photo",
                "socialStyle": "professional_social",
                "styleFamily": "professional social profile photo",
                "identityPreservation": True,
                "realistic": True,
                "noFaceReshaping": True,
                "noAgeGenderChange": True,
                "notForOfficialDocument": True,
                "officialUse": False,
                "warning": "轻社交头像 / 非正式证件用途",
            },
        },
    },
    "friendly_social": {
        DEFAULT_PROMPT_VERSION: {
            "id": "friendly_social",
            "version": DEFAULT_PROMPT_VERSION,
            "mode": "social_photo",
            "status": "mock",
            "creditCost": 0,
            "usageLabel": "non_official_social_photo",
            "userParamsSchema": {"socialStyle": "friendly_social", "outputRatio": "1:1"},
            "promptMetadata": {
                "domain": "social_photo",
                "socialStyle": "friendly_social",
                "styleFamily": "friendly social profile photo",
                "identityPreservation": True,
                "realistic": True,
                "noFaceReshaping": True,
                "noAgeGenderChange": True,
                "notForOfficialDocument": True,
                "officialUse": False,
                "warning": "轻社交头像 / 非正式证件用途",
            },
        },
    },
    "ai_repair_basic": {
        DEFAULT_PROMPT_VERSION: {
            "id": "ai_repair_basic",
            "version": DEFAULT_PROMPT_VERSION,
            "mode": "ai_repair",
            "status": "mock",
            "creditCost": 1,
            "usageLabel": "preview_repair",
            "userParamsSchema": {"retouchLevel": "low|medium|high", "style": "natural"},
            "promptMetadata": {"operation": "local mock repair preview", "officialUse": False},
        },
    },
}


@dataclass(frozen=True)
class PromptResolution:
    template: dict[str, Any]
    prompt_template_id: str
    prompt_version: str
    prompt_template_hash: str
    mode: str
    requested_mode: str
    fallback_reason: str | None = None


@dataclass(frozen=True)
class BuiltAIProPrompt:
    prompt: str
    prompt_template_id: str
    prompt_version: str
    prompt_hash: str
    prompt_template_hash: str
    spec_profile: dict[str, Any] | None = None
    quality_rules: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    fallback_reason: str | None = None


def _stable_hash(value: Any) -> str:
    payload = value if isinstance(value, str) else repr(value)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _template_hash(template: dict[str, Any]) -> str:
    digest_source = {key: value for key, value in template.items() if key != "promptTemplateHash"}
    return hashlib.sha256(repr(sorted(digest_source.items())).encode("utf-8")).hexdigest()[:16]


def canonical_mode(mode: str | None) -> tuple[str, str | None]:
    requested = str(mode or "").strip() or "ai_blue_formal_id_photo"
    canonical = MODE_ALIASES.get(requested)
    if canonical:
        reason = None if canonical == requested else f"mode_alias:{requested}->{canonical}"
        return canonical, reason
    return "ai_repair", f"unknown_mode:{requested}"


def resolve_prompt_template(mode: str | None, requested_version: str | None = None, user_params: dict[str, Any] | None = None) -> PromptResolution:
    requested_mode = str(mode or "").strip() or "ai_blue_formal_id_photo"
    resolved_mode, mode_fallback = canonical_mode(requested_mode)
    template_id = MODE_TEMPLATE.get(resolved_mode, FALLBACK_TEMPLATE_ID)
    if resolved_mode == "social_photo":
        style = str((user_params or {}).get("socialStyle") or "").strip()
        if style in SOCIAL_PHOTO_STYLES:
            template_id = style
    versions = PROMPT_TEMPLATE_REGISTRY.get(template_id)
    fallback_parts = [mode_fallback] if mode_fallback else []
    if not versions:
        template_id = FALLBACK_TEMPLATE_ID
        versions = PROMPT_TEMPLATE_REGISTRY[template_id]
        fallback_parts.append("template_missing")
    version = requested_version or DEFAULT_PROMPT_VERSION
    if version not in versions:
        fallback_parts.append(f"unknown_version:{version}")
        version = DEFAULT_PROMPT_VERSION if DEFAULT_PROMPT_VERSION in versions else sorted(versions)[0]
    template = dict(versions[version])
    return PromptResolution(
        template=template,
        prompt_template_id=str(template["id"]),
        prompt_version=str(template["version"]),
        prompt_template_hash=_template_hash(template),
        mode=resolved_mode,
        requested_mode=requested_mode,
        fallback_reason=";".join(fallback_parts) or None,
    )


def flatten_prompt_templates() -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for template_versions in PROMPT_TEMPLATE_REGISTRY.values():
        for template in template_versions.values():
            enriched = dict(template)
            enriched["promptTemplateHash"] = _template_hash(template)
            flattened.append(enriched)
    return flattened


def build_ai_pro_prompt(
    *,
    mode: str,
    ai_pro: dict[str, Any],
    template: dict[str, Any] | None = None,
    spec_context: dict[str, Any] | None = None,
    requested_version: str | None = None,
    fallback_reason: str | None = None,
) -> BuiltAIProPrompt:
    resolution = resolve_prompt_template(mode, requested_version, ai_pro.get("promptParams") or {})
    resolved_template = dict(template or resolution.template)
    params = ai_pro.get("promptParams") or {}
    spec_profile = (spec_context or {}).get("specProfile") if spec_context else None
    quality_rules = list((spec_context or {}).get("qualityRules") or [])

    if spec_context and resolution.mode == "ai_blue_formal_id_photo":
        background_name = spec_context["backgroundName"]
        background_hex = spec_context["backgroundHex"]
        background_rgb = list(spec_context["backgroundRgb"])
        custom_label = "custom " if spec_context["customBackground"] else ""
        prompt_parts = [
            f"Create a conservative AI-enhanced formal ID photo candidate from the provided deterministic IDCreator result, using a plain {custom_label}{background_name} background exactly matching RGB {background_rgb} / HEX {background_hex}.",
            "Preserve IDCreator's existing output size, crop, head/body ratio, top margin, frontal ID-photo composition, and deterministic specification; do not reframe or resize.",
            "Preserve the same person's identity, facial features, age, expression, pose, and natural proportions; do not beautify into a different person.",
            f"The background must remain the selected {background_name} color with no gradient, texture, scenery, decorations, or unintended color shift.",
            "Only apply restrained AI enhancement: natural skin tone, subtle cleanup, conservative studio lighting, and artifact reduction.",
            "Do not present this as a guaranteed official deterministic result; it is an AI candidate requiring human/platform verification.",
            f"Outfit guidance: {params.get('outfit') or 'dark suit, white shirt'}.",
            f"Retouch level: {params.get('retouchLevel') or 'medium'}; style: {params.get('style') or 'natural'}.",
            f"Target spec reference: {spec_profile}.",
        ]
    elif resolution.mode == "social_photo":
        social_style = str(params.get("socialStyle") or resolved_template.get("id") or "professional_social")
        output_ratio = str(params.get("outputRatio") or "1:1")
        style_direction = (
            "professional, trustworthy, modern work-network avatar"
            if social_style == "professional_social"
            else "friendly, approachable, natural social avatar"
        )
        prompt_parts = [
            f"Create a narrow-scope social_photo from the provided existing ID photo input using the {social_style} preset.",
            "This is for informal social/profile use only and is not an official ID photo or official document output.",
            "Preserve the same person's identity, facial features, face shape, age, gender presentation, hairstyle, expression, and natural proportions.",
            "Do not reshape the face, do not change age or gender, do not make the person look like someone else, and do not apply exaggerated beautification.",
            "Keep the result realistic and photo-like, with conservative lighting and cleanup only.",
            f"Style direction: {style_direction}.",
            f"Output ratio: {output_ratio}; keep a centered head-and-shoulders composition suitable for a light social avatar.",
            f"Selected controlled params: {{'socialStyle': {social_style!r}, 'outputRatio': {output_ratio!r}}}.",
        ]
    else:
        prompt_parts = [
            f"Use AI Pro template {resolved_template['id']} version {resolved_template['version']} for mode {resolution.mode}.",
            "Preserve the same person's identity, facial features, age, pose, and natural proportions.",
            "Keep edits conservative; do not claim deterministic official IDCreator output.",
            f"Selected params: {params}.",
        ]
    prompt = " ".join(prompt_parts)
    prompt_hash = _stable_hash(prompt)
    combined_fallback = ";".join(part for part in [resolution.fallback_reason, fallback_reason] if part) or None
    metadata = {
        "promptKey": f"{resolved_template['id']}:{resolved_template['version']}",
        "promptTemplateId": resolved_template["id"],
        "promptVersion": resolved_template["version"],
        "promptHash": prompt_hash,
        "promptTemplateHash": _template_hash(resolved_template),
        "requestedMode": resolution.requested_mode,
        "resolvedMode": resolution.mode,
        "fallbackReason": combined_fallback,
    }
    return BuiltAIProPrompt(
        prompt=prompt,
        prompt_template_id=str(resolved_template["id"]),
        prompt_version=str(resolved_template["version"]),
        prompt_hash=prompt_hash,
        prompt_template_hash=_template_hash(resolved_template),
        spec_profile=spec_profile,
        quality_rules=quality_rules,
        metadata=metadata,
        fallback_reason=combined_fallback,
    )
