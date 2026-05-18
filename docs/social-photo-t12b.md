# T12B Social Photo Beta UI

T12B adds the smallest Web UI entry for the T12A `social_photo` mock/fallback path. It does not call a real paid image provider and does not tune provider size/ratio behavior.

## UI behavior

- In the existing AI Pro section, users can choose:
  - `ID Photo / 证件照 AI 增强` (existing flow)
  - `Social Photo Beta`
- When `Social Photo Beta` is selected, the UI shows only controlled style presets:
  - `Professional` → `promptParams.socialStyle="professional_social"`
  - `Friendly` → `promptParams.socialStyle="friendly_social"`
- The UI shows the disclaimer:
  - `生成适合社交平台使用的自然头像，不适用于官方证件办理。`
- Free/custom prompt inputs are not exposed for `social_photo`.
- ID Photo / AI Pro official-photo flow is kept unchanged for existing modes.

## Request payload

For Social Photo Beta, `/api/tasks` receives:

```json
{
  "aiPro": {
    "enabled": true,
    "modes": ["social_photo"],
    "promptParams": {
      "socialStyle": "professional_social",
      "outputRatio": "1:1"
    },
    "consentAccepted": true
  }
}
```

The Web client intentionally strips ID-photo-only AI Pro prompt params (`outfit`, free-form `style`, background output spec) from the Social Photo Beta `promptParams`.

## Result / quality report display

The result panel now surfaces Social Photo Beta metadata when present:

- `style` / `socialStyle`
- `notForOfficialDocument`
- `fallbackUsed`
- `fallbackReason`
- a concise identity/quality/fallback warning

Fallback keeps displaying Free Core output and makes clear that Social Photo Beta is non-official.

## Verification

```bash
python3 scripts/test-social-photo-t12b-ui.py
(cd web && npm run build)
```

Optional mock browser smoke:

```bash
cd web
NEXT_PUBLIC_USE_MOCK_API=true npm run dev
```

Then upload an image, enable AI Pro, choose `Social Photo Beta`, select `Professional` or `Friendly`, consent, and create the task. The mock result should show Social Photo Beta quality/fallback metadata and the non-official disclaimer.

## Not in T12B / T12C follow-up

- No real provider smoke.
- No provider ratio/size tuning.
- No deeper composition/realism gate beyond T12A mock metadata display.
