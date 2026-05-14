# Phase 5B Signed Downloads / Cleanup Timer Prep / Auth Roadmap

Phase 5B keeps the existing Web v2 + FastAPI flow and adds application-layer controls around generated result files. It does **not** call GPT-image-2, does **not** require OpenAI keys, and does **not** change nginx/PM2/system cron directly.

## Signed result downloads

Result handles now prefer short-lived signed API URLs instead of exposing `.runtime/results/...png` as the direct download entry.

- Endpoint: `GET /api/downloads/{token}`
- Returned fields: `officialResult.previewUrl`, `officialResult.downloadUrl`, `aiEnhanceResult.previewUrl`, `aiEnhanceResult.downloadUrl`
- Token payload contains:
  - relative file path under `.runtime/results`
  - `purpose`: `preview` or `download`
  - expiration timestamp
- Signature: HMAC-SHA256 over the encoded payload.
- Secret: `IDPHOTO_DOWNLOAD_SIGNING_SECRET`
  - If set, tokens survive process restarts until expiry.
  - If missing, the API generates an ephemeral in-process secret and logs a non-sensitive warning. Existing signed links then become invalid after restart.
- Default token TTL: `min(IDPHOTO_DOWNLOAD_TTL_SECONDS, IDPHOTO_RUNTIME_TTL_SECONDS)`; `IDPHOTO_DOWNLOAD_TTL_SECONDS` defaults to `1800` seconds.
- File response headers include `Cache-Control: private, no-store`.

Security guardrails:

- The token is verified with constant-time HMAC comparison.
- The resolved file path must stay inside `.runtime/results` after `Path.resolve()`.
- Missing/expired/tampered files return `403` or `404` JSON errors.
- Static `/runtime/results` remains mounted for compatibility, but frontend/API consumers should treat signed `downloadUrl` as the preferred entry.

Recommended production env:

```bash
export IDPHOTO_DOWNLOAD_SIGNING_SECRET='<32+ random bytes from a password manager>'
export IDPHOTO_DOWNLOAD_TTL_SECONDS=1800
export IDPHOTO_RUNTIME_TTL_SECONDS=21600
```

## Cleanup timer preparation

`scripts/cleanup_runtime.py` now supports stable JSON output and dry-run mode:

```bash
# Count expired artifacts without deleting them
IDPHOTO_SKIP_STARTUP_CLEANUP=1 .venv/bin/python scripts/cleanup_runtime.py --dry-run --json

# Delete expired artifacts
IDPHOTO_SKIP_STARTUP_CLEANUP=1 .venv/bin/python scripts/cleanup_runtime.py --json
```

`IDPHOTO_SKIP_STARTUP_CLEANUP=1` is recommended for timer execution so importing `deploy_api.py` does not run an additional startup cleanup before the script's explicit dry-run/non-dry-run call.

Recommended schedule: every 15–30 minutes. Phase 5B only provides examples; it does not install timers.

### systemd user timer example

See:

- `deploy/systemd/idphoto-ai-cleanup.service.example`
- `deploy/systemd/idphoto-ai-cleanup.timer.example`

Example operator flow (Main/SAFE_EXEC should handle actual installation):

```bash
mkdir -p ~/.config/systemd/user
cp deploy/systemd/idphoto-ai-cleanup.*.example ~/.config/systemd/user/
# Rename files to remove .example and adjust WorkingDirectory/ExecStart if needed.
systemctl --user daemon-reload
systemctl --user enable --now idphoto-ai-cleanup.timer
```

### cron example

See `deploy/cron/idphoto-ai-cleanup.cron.example`.

## Basic Auth replacement roadmap

Current state: nginx Basic Auth remains the production gate for Phase 5B.

Lightweight Phase 5C direction (no database required initially):

1. Add app login endpoint, e.g. `POST /api/auth/login`, accepting username/password from env-backed credentials.
2. On success, issue an `HttpOnly; Secure; SameSite=Lax` signed session cookie.
3. Add `GET /api/auth/me` and `POST /api/auth/logout`.
4. Protect app API routes and web pages with middleware/session verification.
5. Keep nginx Basic Auth during migration, then remove it only after cookie auth has e2e coverage and rollback docs.
6. Rotate/centralize credentials after migration.

Why not fully replace Basic Auth in 5B:

- The current public perimeter already works.
- A rushed login page without rate limiting/session invalidation would be weaker than the current nginx gate.
- The smallest safe step is signed downloads + a documented auth migration path.

## Phase 5B e2e

```bash
API_BASE_URL=http://127.0.0.1:18084 \
  .venv/bin/python scripts/e2e_phase5b_api.py
```

Public Basic Auth protected endpoint:

```bash
API_BASE_URL=https://idphoto-ai.violinai.qzz.io \
BASIC_AUTH_USER='<user>' \
BASIC_AUTH_PASSWORD='<password>' \
  .venv/bin/python scripts/e2e_phase5b_api.py
```

The script:

1. uploads a test image;
2. creates/polls a task;
3. asserts `officialResult.downloadUrl` starts with `/api/downloads/`;
4. GETs the signed URL and checks `200 image/*` plus `Cache-Control: private, no-store`;
5. tampers with the token and expects `403` or `404`;
6. never prints passwords or Authorization headers.
