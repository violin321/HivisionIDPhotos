# Phase 5C — App Login Gate

Phase 5C adds an application-level login flow so nginx Basic Auth can be removed after a double-protection validation window.

## Environment

Required API process environment:

- `IDPHOTO_APP_USERNAME` — application login username
- `IDPHOTO_APP_PASSWORD` — application login password
- `IDPHOTO_APP_SESSION_SECRET` — HMAC secret for the signed session cookie

Already required from Phase 5B:

- `IDPHOTO_DOWNLOAD_SIGNING_SECRET` — HMAC secret for signed result download URLs

Optional:

- `IDPHOTO_APP_SESSION_TTL_SECONDS` — session lifetime, defaults to 12 hours
- `IDPHOTO_APP_COOKIE_SECURE` — defaults to secure cookies; set `0` only for local HTTP testing

## API

- `POST /api/auth/login`
  - JSON body: `{ "username": "...", "password": "..." }`
  - On success sets a signed, `HttpOnly`, `SameSite=Lax` cookie named `idphoto_ai_session`.
- `GET /api/auth/me`
  - Returns `{ "authenticated": true/false, "username": "..." | null }`.
- `POST /api/auth/logout`
  - Clears `idphoto_ai_session`.

Protected by app login:

- `GET /api/config`
- `GET /api/templates`
- `POST /api/uploads`
- `POST /api/tasks`
- `GET /api/tasks/{task_id}`
- `GET /api/downloads/{token}`

Public:

- `GET /api/health`

Legacy non-`/api` endpoints are left unchanged for compatibility with the original project surface.

## Frontend behavior

The Next.js web app now checks `/api/auth/me` on load.

- Unauthenticated users see a login form only.
- Successful login opens the Studio.
- The Studio header includes a logout button.
- Passwords are never hardcoded in the frontend.

Because `/api/config` and `/api/templates` are protected, the login page does not depend on them before authentication.

## CSRF stance

Phase 5C uses a simplified CSRF posture:

- session cookie is `HttpOnly` and `SameSite=Lax`;
- state-changing endpoints use JSON `POST` requests where applicable;
- CORS remains compatible with the existing adapter setup.

A separate CSRF token can be added later if cross-site embedding or broader third-party origins become a requirement.

## Migration plan

1. Keep nginx Basic Auth enabled.
2. Deploy API with all Phase 5C env vars set:
   - `IDPHOTO_APP_USERNAME`
   - `IDPHOTO_APP_PASSWORD`
   - `IDPHOTO_APP_SESSION_SECRET`
   - `IDPHOTO_DOWNLOAD_SIGNING_SECRET`
3. Restart the API/web services via the normal deployment owner path.
4. Run Phase 5C e2e through the Basic Auth wrapper:

   ```bash
   BASIC_AUTH_USER=... BASIC_AUTH_PASSWORD=... \
   IDPHOTO_APP_USERNAME=... IDPHOTO_APP_PASSWORD=... \
   API_BASE_URL=https://idphoto-ai.violinai.qzz.io \
   .venv/bin/python scripts/e2e_phase5c_auth.py
   ```

5. Manually verify browser flow:
   - Basic Auth prompt passes first;
   - app login page appears;
   - login opens Studio;
   - upload → task → signed download works;
   - logout returns to login gate.
6. After validation, remove nginx Basic Auth for this site only.
7. Re-run `scripts/e2e_phase5c_auth.py` without `BASIC_AUTH_USER/BASIC_AUTH_PASSWORD`.

## Local testing

For local HTTP testing, use a non-secret throwaway setup and disable Secure cookies:

```bash
IDPHOTO_APP_USERNAME=local-user \
IDPHOTO_APP_PASSWORD=local-password \
IDPHOTO_APP_SESSION_SECRET=local-session-secret-change-me \
IDPHOTO_DOWNLOAD_SIGNING_SECRET=local-download-secret-change-me \
IDPHOTO_APP_COOKIE_SECURE=0 \
.venv/bin/uvicorn deploy_api:app --host 127.0.0.1 --port 18084
```

Then run:

```bash
IDPHOTO_APP_USERNAME=local-user \
IDPHOTO_APP_PASSWORD=local-password \
API_BASE_URL=http://127.0.0.1:18084 \
.venv/bin/python scripts/e2e_phase5c_auth.py
```
