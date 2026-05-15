# Phase 5D Observability + Abuse Prevention

Phase 5D adds privacy-safe audit logging, lightweight in-process rate limiting, and an authenticated admin stats API for the idphoto-ai trial deployment.

## Scope

- GPT-image-2 is **not** connected in this phase.
- `officialResult` remains deterministic Hivision `IDCreator` output.
- `aiEnhanceResult` remains a local-derived preview when requested.

## Audit log

Audit events are appended as JSON Lines to:

```text
.runtime/audit.jsonl
```

### Event types

The API records:

- `login` — success / failure
- `logout` — success
- `upload` — success / failure
- `task_create` — success / failure
- `task_complete` — success / failure
- `download` — success / failure
- `rate_limit_hit` — blocked request

### Fields

Common fields:

- `ts` — UTC ISO timestamp
- `event` — event name
- `status` — `success`, `failure`, or `blocked`
- `requestId` — inbound `x-request-id` / `x-correlation-id`, or generated `req_*`
- `route` — request route where available
- `ipHash` — HMAC-SHA256 hash prefix of client IP
- `sessionHash` — HMAC-SHA256 hash prefix of app session cookie, or `anonymous`
- `user` — app username when known
- `taskId` / `uploadId` — internal task/upload handles where relevant
- `durationMs` — operation duration where measured
- `errorCode` — stable API error code where relevant

Event-specific safe fields may include `mimeType`, `bytes`, `templateId`, `aiMode`, `purpose`, `scope`, `limit`, and `windowSeconds`.

### Privacy boundaries

The audit log intentionally does **not** store:

- raw original image filenames
- original image URLs or filesystem paths
- download tokens
- cookies / session token contents
- password values
- `Authorization` headers
- complete raw IP addresses

The IP hash secret uses `IDPHOTO_AUDIT_IP_HASH_SECRET` when set. If unset, it falls back to `IDPHOTO_APP_SESSION_SECRET`, then a local default suitable only for development. Production should set a stable private `IDPHOTO_AUDIT_IP_HASH_SECRET` to make hashes consistent across restarts without exposing raw IPs.

## Rate limits

Implemented in process memory with a 60-second sliding window. This is intentionally simple and non-distributed; multiple workers/hosts will each enforce their own bucket.

Environment variables:

```bash
IDPHOTO_RATE_LIMIT_UPLOADS_PER_MINUTE=10
IDPHOTO_RATE_LIMIT_TASKS_PER_MINUTE=10
IDPHOTO_RATE_LIMIT_LOGIN_PER_MINUTE=10
```

Rules:

- `POST /api/auth/login` → login bucket
- `POST /api/uploads` → upload bucket
- `POST /api/tasks` → task bucket
- `/api/health` is not rate-limited

Buckets are keyed by privacy-safe IP hash plus session fingerprint where available. Set a limit to `0` to disable that specific limiter.

When a limit is exceeded, the API returns HTTP `429`:

```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Too many requests. Please retry later.",
    "retryable": true
  }
}
```

The same event is recorded as `rate_limit_hit` in the audit log.

## Admin stats API

Authenticated endpoint:

```http
GET /api/admin/stats
```

Unauthenticated requests return `401` (or `503` if app login is not configured).

Response fields:

- `phase` — current service phase, `5D`
- `generatedAt` — UTC ISO timestamp
- `today` — UTC-day counters
  - `logins`
  - `uploads`
  - `tasksSucceeded`
  - `tasksFailed`
  - `downloads`
  - `rateLimitHits`
- `last24h` — rolling 24-hour counters with the same fields
- `runtime`
  - `uploadsBytes`
  - `resultsBytes`
  - `uploadsTracked`
  - `tasksTracked`
- `recentErrorCodesTop` — top recent error codes from the audit log
- `rateLimits`
  - `uploadsPerMinute`
  - `tasksPerMinute`
  - `loginPerMinute`
  - `storage` = `in-process`

The web Studio includes a small authenticated “Admin stats” panel that calls this API after login and can be refreshed manually.

## Validation

Run the regular Phase 5D e2e against a local or deployed API:

```bash
IDPHOTO_APP_USERNAME=... \
IDPHOTO_APP_PASSWORD=... \
API_BASE_URL=http://127.0.0.1:8000 \
.venv/bin/python scripts/e2e_phase5d_observability.py
```

To validate low-threshold rate limiting, start a local API with a low login threshold, then run:

```bash
IDPHOTO_E2E_EXPECT_LOGIN_RATE_LIMIT=1 \
IDPHOTO_APP_USERNAME=... \
IDPHOTO_APP_PASSWORD=... \
API_BASE_URL=http://127.0.0.1:8000 \
.venv/bin/python scripts/e2e_phase5d_observability.py
```

The e2e verifies:

1. `/api/health` reports phase `5D`.
2. unauthenticated `/api/admin/stats` is blocked.
3. login → upload → task → signed download succeeds.
4. admin stats counters increase reasonably.
5. optional low-threshold login limiter returns `429 RATE_LIMITED`.
