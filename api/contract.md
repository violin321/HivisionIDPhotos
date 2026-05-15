# HivisionIDPhotos Multi-Platform API Contract (Phase 0/1)

This contract defines the first Web v2 and future miniapp-compatible API surface for the multi-platform frontend. It is intentionally frontend-safe: no provider key, internal base URL, or GPT-image-2 credential is ever returned to web or miniapp clients.

## Design goals

- Keep the legacy Gradio experience and official `IDCreator` processing path intact.
- Use a task model so web, mobile browser, and WeChat Mini Program can share the same interaction pattern.
- Separate official ID photo output from optional AI enhance previews/results.
- Support anonymous users now, web tokens later, and future WeChat code exchange without hard-coding cookie-only auth.

## Miniapp-compatible notes

### Upload transport

- Uploads use `multipart/form-data` and must be compatible with `wx.uploadFile`.
- Clients send one image file field named `file` plus optional metadata fields such as `platform`, `source`, and `clientTraceId`.
- Server validates mime type, file size, dimensions, and unsafe content before creating an upload record.

### `POST /api/uploads`

Creates an expiring upload handle.

Request:

```http
POST /api/uploads
Content-Type: multipart/form-data
```

Response:

```json
{
  "uploadId": "upl_01h...",
  "fileId": "file_01h...",
  "mimeType": "image/jpeg",
  "expiresAt": "2026-05-14T18:00:00+08:00"
}
```

### Task lifecycle: `POST /api/tasks` + `GET /api/tasks/{id}`

Tasks use the shared status enum:

- `queued`
- `processing`
- `succeeded`
- `failed`
- `expired`

`POST /api/tasks` creates a processing task from an uploaded file.

```json
{
  "uploadId": "upl_01h...",
  "templateId": "cn-id-1inch",
  "platform": "web",
  "aiMode": "none",
  "options": {
    "background": "white",
    "renderOfficialIdPhoto": true,
    "renderAiEnhancePreview": false
  }
}
```

`GET /api/tasks/{id}` returns progress and result handles.

Succeeded response shape:

```json
{
  "taskId": "task_01h...",
  "status": "succeeded",
  "officialResult": {
    "fileId": "file_result_official_01h...",
    "previewUrl": "https://cdn.example.invalid/preview/off.jpg",
    "downloadUrl": "https://cdn.example.invalid/download/off.jpg",
    "expiresAt": "2026-05-14T18:30:00+08:00"
  },
  "aiEnhanceResult": {
    "fileId": "file_result_ai_01h...",
    "previewUrl": "https://cdn.example.invalid/preview/ai.jpg",
    "downloadUrl": "https://cdn.example.invalid/download/ai.jpg",
    "expiresAt": "2026-05-14T18:30:00+08:00"
  }
}
```

`previewUrl` and `downloadUrl` are designed to be consumed by:

- `wx.previewImage`
- `wx.downloadFile`
- `wx.saveImageToPhotosAlbum`

### Auth model

Do not assume cookie-only auth. Supported/future-compatible modes:

1. Anonymous session for low-friction web/mobile browser trials.
2. Web token for signed-in browser users.
3. Future WeChat code exchange (`wx.login` code -> backend session/token).

### `GET /api/config`

Returns frontend copy, compliance flags, feature gates, and disclaimers.

```json
{
  "consent": {
    "required": true,
    "title": "Photo processing consent",
    "body": "Your uploaded image is processed only for the selected ID photo task."
  },
  "privacy": {
    "retentionHours": 24,
    "deletionCopy": "Uploads and generated files expire automatically."
  },
  "aiDisclaimer": "AI enhance is optional and separate from official ID photo output.",
  "copy": {
    "productName": "HivisionIDPhotos Studio",
    "uploadCta": "Upload portrait"
  },
  "features": {
    "officialIdPhoto": true,
    "aiEnhancePreview": true,
    "wechatMiniappReady": true
  }
}
```

### Provider secrets and AI enhance boundary

- API keys are never shipped to frontend or miniapp clients.
- GPT-image-2 is called only from server-side code.
- AI enhance output is separated from official certificate photo output in task options, processing logs, result fields, and UI labels.
- Official ID photo rendering remains deterministic and must not be silently replaced by AI enhance output.

## Web v2 first-phase API surface

| Endpoint | Method | Purpose | Phase 0/1 behavior |
| --- | --- | --- | --- |
| `/api/config` | `GET` | Compliance copy, privacy copy, feature flags, UI copy | Contract only / mockable |
| `/api/uploads` | `POST` | `multipart/form-data` image upload | Contract only / mockable |
| `/api/tasks` | `POST` | Create official/AI processing task | Contract only / mockable |
| `/api/tasks/{id}` | `GET` | Poll task state and result URLs | Contract only / mockable |
| `/api/templates` | `GET` | List ID photo specifications/templates | Contract only / mockable |
| `/api/health` | `GET` | Basic service health and version | Contract only / mockable |

## Error shape

```json
{
  "error": {
    "code": "UPLOAD_EXPIRED",
    "message": "The uploaded file has expired. Please upload again.",
    "retryable": true,
    "traceId": "trace_01h..."
  }
}
```

## Compatibility checklist

- [x] `multipart/form-data` upload compatible with `wx.uploadFile`.
- [x] Expiring `uploadId` / `fileId` handles instead of direct local paths.
- [x] Task polling instead of long blocking requests.
- [x] Result URLs compatible with miniapp preview/download/save APIs.
- [x] Auth model supports anonymous, web token, and future WeChat code exchange.
- [x] Config endpoint centralizes consent, privacy, AI disclaimer, copy, and features.
- [x] No provider API key or GPT-image-2 base URL is exposed to clients.
- [x] AI enhance and official ID photo results are explicitly separated.
