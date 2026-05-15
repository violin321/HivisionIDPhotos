#!/usr/bin/env python3
from pathlib import Path
roots = [Path('web/.next/standalone/.next/static/chunks'), Path('web/.next/standalone/.next/server/chunks/ssr')]
bad = []
missing = []
for root in roots:
    for path in root.glob('*.js'):
        text = path.read_text(errors='ignore')
        if 'NEXT_PUBLIC_API_BASE_URL' not in text:
            continue
        if '??"/api"' not in text and "??'/api'" not in text:
            missing.append(str(path))
        if '||!r' in text or '||!d' in text or '|| !apiBaseUrl' in text:
            bad.append(str(path))
if bad:
    raise SystemExit('old mock fallback remains in built chunks: ' + ', '.join(bad))
if missing:
    raise SystemExit('missing /api default in built chunks: ' + ', '.join(missing))
print('ok: built chunks default to /api and do not fallback to mock when API base is unset')
