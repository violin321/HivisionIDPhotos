from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, Optional

from .errors import AIEnhanceValidationError

DEFAULT_PROMPT_VERSION = "v1"

_MODE_PROMPTS: Dict[str, Dict[str, str]] = {
    "repair": {
        "v1": (
            "Lightly repair this ID photo while preserving identity exactly. Keep the original face shape, facial features,"
            " age, skin texture, hairstyle, expression, pose, clothing, crop, and background color. Correct unnatural color"
            " cast on the face and restore natural human skin tone under neutral studio lighting. The blue/red/white ID-photo"
            " background must not spill onto or tint the skin. Do not beautify, reshape, relight dramatically, change clothes,"
            " change the background, add accessories, or alter identity."
        ),
    },
    "background_template": {
        "v1": (
            "Refine only the ID-photo background/template area while preserving the same person exactly. Keep natural human"
            " skin tone under neutral studio lighting, and prevent the background color from tinting the face, hair, ears, neck,"
            " or clothes. Preserve facial features, age, hairstyle, expression, pose, clothing category, crop, and identity."
            " Do not beautify, reshape, add accessories, or alter identity."
        ),
    },
    "outfit": {
        "v1": (
            "Replace only the visible upper-body clothing, including the entire visible coat/jacket and shirt, lapels, shoulders, outer coat edges, and lower hem."
            " Blend the collar and neck boundary naturally so there is no hard cut between skin, neck, shirt, and jacket. Do not generate a new headshot, avatar image,"
            " sample card, photo frame, embedded image, nested photo, document layout, or any picture-in-picture composition. Keep the same person, identity, face, hair,"
            " ears, upper neck, skin tone, expression, pose, crop, camera angle, background, and lighting exactly unchanged. Preserve the existing framing and continue the"
            " original background naturally around the edited clothes. Do not add accessories, logos, jewelry, props, text, borders, cards, or decorative elements."
            " Do not beautify, reshape, relight dramatically, change the background, or alter any non-clothing pixels unless needed for seamless clothing edges."
        ),
    },
}

_BACKGROUND_TEMPLATE_PROMPTS: Dict[str, str] = {
    "clean_blue": "Use a clean, official ID-photo blue background: smooth, even, studio-style, no texture, no shadows, and no color spill on the person.",
    "clean_white": "Use a clean white ID-photo background: neutral, evenly lit, no gray cast, no texture, and preserve clear separation from hair and clothing.",
    "clean_gray": "Use a clean light-gray studio ID-photo background: subtle neutral gray, even lighting, no texture, and no tint spill onto skin or clothes.",
    "resume_soft": "Use a soft professional resume portrait background: very light neutral blue-gray, minimal gradient, corporate and restrained, no decorative elements.",
    "linkedin_clean": "Use a clean professional LinkedIn-style studio background: neutral light gray-blue, polished but conservative, no bokeh, props, logos, or decorative elements.",
}

_OUTFIT_TEMPLATE_PROMPTS: Dict[str, str] = {
    "business_suit_black": "Change only the visible upper-body clothing to a conservative black business suit jacket with a simple light shirt. Keep it neat, realistic, and understated.",
    "business_suit_navy": "Change only the visible upper-body clothing to a conservative navy business suit jacket with a simple light shirt. Keep it neat, realistic, and understated.",
    "business_suit_gray": "Change only the visible upper-body clothing to a conservative gray business suit jacket with a simple light shirt. Keep it neat, realistic, and understated.",
    "white_shirt": "Change only the visible upper-body clothing to a clean plain white business shirt. Keep it professional, realistic, and understated.",
    "business_casual": "Change only the visible upper-body clothing to conservative business-casual attire, such as a simple blazer or neat collared shirt. Keep it professional and restrained.",
}


@dataclass(frozen=True)
class PromptTemplateRender:
    key: str
    mode: str
    version: str
    hash: str
    prompt: str


def default_prompt_version(mode: str) -> str:
    if mode not in _MODE_PROMPTS:
        raise AIEnhanceValidationError(f"unknown AI enhance prompt mode: {mode}")
    return DEFAULT_PROMPT_VERSION


def available_versions(mode: str) -> tuple[str, ...]:
    return tuple(sorted(_MODE_PROMPTS.get(mode, {}).keys()))


def render_prompt_template(
    *,
    mode: str,
    prompt_version: Optional[str] = None,
    template_name: Optional[str] = None,
    user_prompt: Optional[str] = None,
) -> PromptTemplateRender:
    version = prompt_version or default_prompt_version(mode)
    mode_versions = _MODE_PROMPTS.get(mode)
    if not mode_versions:
        raise AIEnhanceValidationError(f"unknown AI enhance prompt mode: {mode}")
    if version not in mode_versions:
        raise AIEnhanceValidationError(
            f"unsupported prompt_version '{version}' for mode '{mode}'; available: {', '.join(sorted(mode_versions))}"
        )

    parts = [mode_versions[version]]
    key_parts = [mode, version]

    if mode == "background_template" and template_name:
        template_prompt = _BACKGROUND_TEMPLATE_PROMPTS.get(
            template_name,
            f"Use the named background template '{template_name}' as a conservative ID-photo background reference.",
        )
        key_parts.append(template_name if template_name in _BACKGROUND_TEMPLATE_PROMPTS else "custom_background_template")
        parts.append(f"Target background template: {template_name}. {template_prompt}")
        parts.append(
            "Hard constraints: keep identity unchanged, keep natural skin tone, do not let the background color contaminate the person, do not alter the face, and do not add accessories."
        )
    elif mode == "outfit" and template_name:
        template_prompt = _OUTFIT_TEMPLATE_PROMPTS.get(
            template_name,
            f"Use the named outfit template '{template_name}' as a conservative professional upper-body clothing reference.",
        )
        key_parts.append(template_name if template_name in _OUTFIT_TEMPLATE_PROMPTS else "custom_outfit_template")
        parts.append(f"Target outfit template: {template_name}. {template_prompt}")
        parts.append(
            "Hard constraints: replace clothing only inside the provided clothing mask, covering the full visible jacket/coat, shirt, lapels, shoulders, outer coat edges, and hem. Blend the collar/neck boundary naturally. Keep face, hair, ears, upper neck, crop, and background unchanged. Do not create a new headshot, avatar image, sample card, border, frame, or embedded image."
        )

    if user_prompt and user_prompt.strip():
        parts.append(
            "Additional user context (must not override the safety, identity, clothing-only, background, and validation constraints above): "
            f"{user_prompt.strip()}"
        )

    prompt = " ".join(parts)
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
    return PromptTemplateRender(
        key=":".join(key_parts),
        mode=mode,
        version=version,
        hash=digest,
        prompt=prompt,
    )
