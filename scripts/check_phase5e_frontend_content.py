#!/usr/bin/env python3
"""Lightweight Phase 5E frontend content check.

Builds can minify/split strings, so this script checks source files and the
compiled .next tree when present for the required settings/theme/i18n/provider
copy. It intentionally verifies GPT-image-2 is only mentioned as reserved UI
copy and not imported as a real provider integration.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = [
    ROOT / 'web/lib/preferences.tsx',
    ROOT / 'web/components/StudioShell.tsx',
    ROOT / 'web/app/globals.css',
]

REQUIRED_SOURCE_TOKENS = [
    '实验室控制台设置',
    '外观',
    '语言',
    'AI Provider（预留）',
    'local-derived-preview',
    'GPT-image-2 未接入',
    '正式证件照仍由 IDCreator 生成',
    "type ThemePreference = 'light' | 'dark' | 'system'",
    "type LanguagePreference = 'zh-CN' | 'en-US'",
    "window.localStorage.setItem(THEME_KEY",
    "window.localStorage.setItem(LANGUAGE_KEY",
    "prefers-color-scheme: dark",
    ":root[data-theme='dark']",
]

BUNDLE_TOKENS = [
    '实验室控制台设置',
    'AI Provider',
    'local-derived-preview',
    'GPT-image-2',
]


def read_text(path: Path) -> str:
    return path.read_text(encoding='utf-8') if path.exists() else ''


def main() -> int:
    source_blob = '\n'.join(read_text(path) for path in SOURCE_FILES)
    missing = [token for token in REQUIRED_SOURCE_TOKENS if token not in source_blob]

    next_dir = ROOT / 'web/.next'
    if next_dir.exists():
        bundle_blob = ''
        for path in next_dir.rglob('*'):
            if path.is_file() and path.suffix in {'.js', '.html', '.json', '.txt'}:
                try:
                    bundle_blob += path.read_text(encoding='utf-8', errors='ignore')
                except OSError:
                    continue
        missing.extend(f'bundle:{token}' for token in BUNDLE_TOKENS if token not in bundle_blob)

    forbidden_real_provider_markers = [
        'openai.chat.completions',
        'OPENAI_API_KEY',
        "from 'openai'",
        'new OpenAI',
    ]
    forbidden = [token for token in forbidden_real_provider_markers if token in source_blob]

    if missing or forbidden:
        if missing:
            print('Missing Phase 5E content tokens:')
            for token in missing:
                print(f'  - {token}')
        if forbidden:
            print('Forbidden real provider integration markers found:')
            for token in forbidden:
                print(f'  - {token}')
        return 1

    print('Phase 5E frontend content check passed: settings/theme/language/provider reservation copy present; no real GPT-image-2 integration markers found.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
