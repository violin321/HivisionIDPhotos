#!/usr/bin/env python3
from pathlib import Path
text = Path('web/lib/api-client.ts').read_text()
required = [
    "const normalizedPath = path.startsWith('/') ? path : `/${path}`;",
    "if (apiBaseUrl === '/api' && normalizedPath.startsWith('/api/')) return normalizedPath;",
    "return `${apiBaseUrl}${normalizedPath}`;",
]
for item in required:
    if item not in text:
        raise SystemExit(f'missing apiUrl normalization guard: {item}')
if '`${apiBaseUrl}${path}`' in text:
    raise SystemExit('old apiUrl concatenation remains')
print('ok: apiUrl does not turn /api + /api/foo into /api/api/foo')
