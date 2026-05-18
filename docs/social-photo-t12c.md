# Social Photo T12C — real provider smoke + gates v1

T12C extends the controlled `social_photo` beta path with a real-provider smoke harness and the first local quality gate audit fields.

## Scope

- `social_photo` remains narrow: `professional_social` and `friendly_social` only.
- Custom/free prompts are still rejected.
- Outputs are explicitly `notForOfficialDocument` and keep identity-preservation metadata.
- Real provider calls are opt-in only; CI/default local runs do not call paid APIs.

## Provider size / ratio

- ID-photo AI Pro behavior is unchanged by default: provider size remains `auto` unless `GPT_IMAGE_SIZE` or `GPT_IMAGE_SIZE_POLICY=match-aspect` is configured.
- `social_photo` has a product-level `1:1` output contract, so the engine requests the nearest square provider size by default: `1024x1024`.
- Metadata exposes:
  - `providerSizeRequested`
  - `providerAspectRatioRequested`
  - `providerSizeUsed` / `providerOutputSize` when a provider image is returned
  - `providerAspectRatio` when dimensions are readable

## Composition / realism gate v1

The first gate is deliberately conservative and local-testable:

- Composition uses OpenCV face rectangles when available to audit single-person, centered head-and-shoulders framing.
- Realism uses lightweight edge-density and color-bucket heuristics to flag degenerate/cartoon-like outputs.
- These social-photo composition/realism findings are warning-only in v1 to avoid false rejections.
- Stable warning/failure codes:
  - `SOCIAL_PHOTO_COMPOSITION_WARNING`
  - `SOCIAL_PHOTO_COMPOSITION_FAILED` (reserved; not expected in warning-only v1 path)
  - `SOCIAL_PHOTO_REALISM_WARNING`

Identity guard is still run through the existing AI Pro identity check. Identity drift failures remain hard fallback-safe errors.

## Real provider smoke

Script:

```bash
python3 scripts/smoke-social-photo-provider-t12c.py
```

Default behavior is safe and skips provider calls. To run a real smoke:

```bash
AI_PRO_PROVIDER=metapi \
GPT_IMAGE_API_BASE=https://your-provider.example/v1 \
GPT_IMAGE_API_KEY=... \
GPT_IMAGE_MODEL=gpt-image-2 \
python3 scripts/smoke-social-photo-provider-t12c.py --real --sample demo/images/test0.jpg
```

The script runs both styles and prints a redacted JSON summary including style, provider size/ratio, quality/fallback status, identity/composition/realism summaries, and `notForOfficialDocument`.

## Local regression commands

```bash
python3 scripts/test-ai-pro-provider-size.py
python3 scripts/test-social-photo-t12c-gates.py
python3 scripts/test-ai-pro-social-photo-t12a.py
python3 scripts/test-ai-pro-quality-gate.py
python3 -m py_compile deploy_api.py hivision/plugin/ai_pro/engine.py hivision/plugin/ai_pro/quality.py hivision/plugin/ai_pro/prompts.py scripts/smoke-social-photo-provider-t12c.py scripts/test-social-photo-t12c-gates.py
```
