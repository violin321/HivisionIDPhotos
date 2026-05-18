# T12A social_photo 窄版（domain/API/prompt/mock）

T12A 只落第一版后端/类型/提示词注册/Mock 链路，不做大 UI 入口，不调用真实付费图片 provider。

## 范围

- 新增 AI Pro `mode="social_photo"`。
- 首批受控 preset：
  - `professional_social`
  - `friendly_social`
- `social_photo` 基于现有证件照/IDCreator 输出生成轻社交头像候选，不扩展为泛化写真或自由头像大模型玩法。
- 首版 `outputRatio` 默认 `1:1`。
- `social_photo` 结果始终标记为非正式证件用途：`notForOfficialDocument=true`。

## API 行为

通过 `/api/tasks` 的 `aiPro` 请求：

```json
{
  "enabled": true,
  "modes": ["social_photo"],
  "promptParams": {
    "socialStyle": "professional_social",
    "outputRatio": "1:1"
  },
  "consentAccepted": true
}
```

校验规则：

- `socialStyle` 必须是 `professional_social` 或 `friendly_social`。
- `prompt` / `customPrompt` / `custom_prompt` / `freePrompt` / `free_prompt` 对 `social_photo` 不被接受。
- 未配置真实 provider 或非 `ai_blue_formal_id_photo` 模式时走 mock/fallback，不上传到真实 AI 图片 API。

## Prompt registry

`hivision/plugin/ai_pro/prompts.py` 注册了两个 social prompt template。Prompt 明确约束：

- identity preservation
- realistic photo-like output
- no face reshaping
- no age/gender change
- not an official ID photo / not for official document use

## 可审计字段

Mock result 的 `qualityReport` / `promptMetadata` 包含：

- `mode` / `domain = social_photo`
- `style` / `socialStyle`
- `outputRatio = 1:1`
- `notForOfficialDocument = true`
- `noFaceReshaping = true`
- `noAgeGenderChange = true`

## 验证命令

```bash
python3 scripts/test-ai-pro-social-photo-t12a.py
python3 scripts/test-ai-pro-prompt-registry.py
python3 scripts/test-ai-pro-regression-fixtures.py
python3 -m py_compile deploy_api.py hivision/plugin/ai_pro/prompts.py hivision/plugin/ai_pro/engine.py
(cd web && npm run build)
```

## 非目标 / 后续

- T12B 再做 Web 大入口、样式选择 UI 和结果展示细化。
- T12C 再评估真实 provider smoke、provider size/ratio 策略和质量门禁扩展。
- 本阶段不合并 PR、不打 tag、不重启生产服务。
