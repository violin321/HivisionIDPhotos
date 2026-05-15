#!/usr/bin/env python3
from pathlib import Path
text = Path('web/lib/api-client.ts').read_text()
for bad in ["|| !apiBaseUrl", "const apiBaseUrl = (process.env.NEXT_PUBLIC_API_BASE_URL ?? '').replace"]:
    if bad in text:
        raise SystemExit(f'bad default mock trigger remains: {bad}')
for good in ["NEXT_PUBLIC_API_BASE_URL ?? '/api'", "const useMockApi = process.env.NEXT_PUBLIC_USE_MOCK_API === 'true';"]:
    if good not in text:
        raise SystemExit(f'missing expected guard: {good}')
print('ok: production defaults to /api and mock requires explicit NEXT_PUBLIC_USE_MOCK_API=true')
