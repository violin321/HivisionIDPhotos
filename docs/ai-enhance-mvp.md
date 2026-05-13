# AI Enhance MVP

## 概述

Phase 1 提供一个**独立**的 AI 增强插件骨架和独立 `POST /ai_enhance` API。
该能力**不接入** `/idphoto` 主链路，也**不修改** `hivision/creator/__init__.py` 的核心流程。

当前支持：
- `mode=repair`
- `mode=background_template`
- `mode=outfit`（Beta：AI 正装预览，仅用于简历头像/形象照参考，不建议作为正式证件照提交）
- `mode=social_photo`（AI 社交/简历头像，仅非正式用途；不作为正式证件照）
- `provider=gpt-image-2`

Phase 3A 在此基础上补了三类能力：
- 可选 debug 落盘（默认关闭）
- provider 输出基础质量门禁（validator）
- metadata / WebUI 状态扩展与 smoke 测试基线

Phase 3B 继续补充：
- 进程内 rate limit / concurrency guard
- usage log / request_id / estimated_cost
- API `client_id` 扩展
- WebUI 等待提示与友好限流文案

Phase 4A.2 针对 `outfit` Beta 补充：
- lower-body crop/composite 编辑路线，避免整图重绘脸、头发、背景
- `AIEnhanceRequest.mask_base64` / `edit_region` 结构字段，便于 provider 支持 mask 时透传
- protected face/upper region 色偏 guard
- WebUI 状态显示 `mask_edit` / `crop_edit` / `face_protected` / `color_guard_passed`

## 环境变量

```bash
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.openai.com/v1   # 可选
OPENAI_IMAGE_MODEL=gpt-image-2              # 可选，默认 gpt-image-2
OPENAI_IMAGE_TIMEOUT=30                     # 可选，单位秒
AI_ENHANCE_DEBUG_SAVE=0                     # 可选，1/true/on 时开启 debug 落盘
AI_ENHANCE_DEBUG_DIR=/tmp/hivision-ai-enhance-debug  # 可选，debug 输出目录
AI_ENHANCE_RATE_LIMIT_ENABLED=1             # 可选，默认开启进程内限流
AI_ENHANCE_RATE_LIMIT_WINDOW_SECONDS=300    # 可选，默认 300 秒
AI_ENHANCE_RATE_LIMIT_MAX_REQUESTS=10       # 可选，默认每个 key 10 次窗口请求
AI_ENHANCE_MAX_CONCURRENT_REQUESTS=2        # 可选，默认每个 key 最多 2 个并发请求
AI_ENHANCE_USAGE_LOG_ENABLED=1              # 可选，默认开启 usage JSONL
AI_ENHANCE_USAGE_LOG_PATH=/tmp/hivision-ai-enhance-usage.jsonl  # 可选，usage log 路径
AI_ENHANCE_ESTIMATED_COST_PER_REQUEST=0.15  # 可选，估算单次请求成本
```

说明：
- 未配置 `OPENAI_API_KEY` 时，不会上传图片到外部 provider。
- `OPENAI_BASE_URL` 用于兼容代理网关或兼容 OpenAI Images API 的服务。
- `AI_ENHANCE_DEBUG_SAVE` 默认关闭；不开启时不会落任何调试文件。
- 开启 debug 后，每次请求会写入独立目录，保存输入图、provider 输出图、metadata JSON。
- rate limit key 当前按 `provider + mode + client_id` 组合；若未提供 `client_id`，则退化为 `global`。
- WebUI 默认以 `client_id=webui` 调用，方便和其他调用方隔离限流窗口。

## 隐私与上传说明

`/ai_enhance` 只有在 `consent=true` 且 provider 已正确配置时，才会尝试把图片发送给外部 AI provider。

以下情况**不会上传图片**：
- `consent=false`
- 缺少 `OPENAI_API_KEY`
- 命中 rate limit / concurrency guard

## 请求参数

以 `multipart/form-data` 提交：

- `input_image_base64`：必填，base64 图片，可带 `data:image/...;base64,` 前缀
- `mode`：必填，`repair` / `background_template` / `outfit` / `social_photo`
- `provider`：可选，当前仅支持 `gpt-image-2`
- `consent`：可选，默认 `false`
- `prompt`：可选，追加保守补充说明
- `template_name`：可选，`background_template` 的背景模板名、`outfit` 的正装模板名，或 `social_photo` 的头像模板名（`resume_clean` / `linkedin_professional` / `soft_profile`）
- `return_base64`：可选，默认 `true`
- `client_id`：可选，用于区分调用方限流窗口；未传时为全局 key
- `mask_base64`：可选，编辑 mask。当前 `outfit` WebUI 路径会内部生成；外部调用通常无需手动传
- `edit_region`：可选，编辑区域 metadata。当前 `outfit` WebUI 路径会内部生成；外部调用通常无需手动传

## curl 示例

### 1) consent=false，本地 fallback

```bash
curl -X POST http://127.0.0.1:8080/ai_enhance \
  -F 'input_image_base64=data:image/png;base64,AAA...' \
  -F 'mode=repair' \
  -F 'provider=gpt-image-2' \
  -F 'consent=false'
```

### 2) consent=true，但未配置 API key，fallback

```bash
curl -X POST http://127.0.0.1:8080/ai_enhance \
  -F 'input_image_base64=data:image/png;base64,AAA...' \
  -F 'mode=background_template' \
  -F 'provider=gpt-image-2' \
  -F 'consent=true'
```

### 3) 带 client_id 调用

```bash
curl -X POST http://127.0.0.1:8080/ai_enhance \
  -F 'input_image_base64=data:image/png;base64,AAA...' \
  -F 'mode=repair' \
  -F 'provider=gpt-image-2' \
  -F 'consent=true' \
  -F 'client_id=webui'
```

### 4) outfit Beta 正装预览

```bash
curl -X POST http://127.0.0.1:8080/ai_enhance \
  -F 'input_image_base64=data:image/png;base64,AAA...' \
  -F 'mode=outfit' \
  -F 'template_name=business_suit_black' \
  -F 'provider=gpt-image-2' \
  -F 'consent=true' \
  -F 'client_id=webui'
```

`outfit` 仅作为 AI 正装预览 Beta，不作为正式证件照默认输出。当前实现优先采用 lower-body crop/composite：只把衣服/肩膀下半区 crop 给 provider，返回后合成回原图；同时保留 `mask_base64` / `edit_region` 字段，若后续 provider 明确支持 `images + mask`，可直接走 mask edit。

### 5) social_photo 非正式社交/简历头像

```bash
curl -X POST http://127.0.0.1:8080/ai_enhance \
  -F 'input_image_base64=data:image/png;base64,AAA...' \
  -F 'mode=social_photo' \
  -F 'template_name=resume_clean' \
  -F 'provider=gpt-image-2' \
  -F 'consent=true' \
  -F 'client_id=webui'
```

`social_photo` 仅用于 AI 社交/简历头像预览等非正式用途，不作为正式证件照输出。Prompt 明确要求保持身份、脸型、五官、年龄和发型主体，不生成正式证件照，不夸张美化；输出仍通过 identity guard，异常时 fallback，不影响正式 IDCreator 主链路结果。

## 响应示例

### fallback 响应

```json
{
  "status": false,
  "image_base64": "data:image/png;base64,...",
  "metadata": {
    "fallback_used": true,
    "fallback_reason": "consent_missing",
    "error_code": "CONSENT_REQUIRED",
    "latency_ms": 0,
    "provider": "gpt-image-2",
    "mode": "repair",
    "ai_generated": false,
    "validation_passed": false,
    "validation_warnings": [],
    "debug_input_path": null,
    "debug_output_path": null,
    "debug_metadata_path": null,
    "request_id": "d72f...",
    "estimated_cost": null,
    "rate_limited": false,
    "usage_logged": true
  },
  "message": "AI enhancement skipped because consent=false; image was not uploaded."
}
```

### 成功响应

```json
{
  "status": true,
  "image_base64": "data:image/png;base64,...",
  "metadata": {
    "fallback_used": false,
    "fallback_reason": null,
    "error_code": null,
    "latency_ms": 842,
    "provider": "gpt-image-2",
    "mode": "repair",
    "ai_generated": true,
    "validation_passed": true,
    "validation_warnings": [],
    "debug_input_path": "/tmp/hivision-ai-enhance-debug/20260512-220000-repair-abcd1234/input.png",
    "debug_output_path": "/tmp/hivision-ai-enhance-debug/20260512-220000-repair-abcd1234/output.png",
    "debug_metadata_path": "/tmp/hivision-ai-enhance-debug/20260512-220000-repair-abcd1234/metadata.json",
    "request_id": "d72f...",
    "estimated_cost": 0.15,
    "rate_limited": false,
    "usage_logged": true
  },
  "message": "AI enhancement completed"
}
```

## fallback 行为

以下情况会走 fallback：

1. `consent=false`
2. provider 未配置（例如缺少 `OPENAI_API_KEY`）
3. provider 超时
4. provider 返回错误 / 响应缺图
5. provider 输出未通过基础 validator（例如 decode 失败、尺寸异常、明显蓝色污染）
6. `outfit` 的 protected face/upper region 色偏 guard 失败
7. 输入参数不合法（返回 validation fallback metadata）
8. 命中 `RATE_LIMITED`
9. 命中 `TOO_MANY_CONCURRENT_REQUESTS`

fallback 的特点：
- `metadata.fallback_used=true`
- `metadata.error_code` 会给出可读错误码
- 若 `return_base64=true`，返回原图 base64；否则返回 `null`
- `metadata.ai_generated=false`
- `metadata.validation_passed=false`
- `metadata.rate_limited=true` 仅在命中限流/并发保护时为真

## Rate limit / 并发保护

当前实现是**标准库进程内限流**，不是分布式队列。

特点：
- key = `provider + mode + client_id`
- 若没有 `client_id`，则回退到 `global`
- 命中 rate limit 时**不会调用 provider**
- 命中 concurrency guard 时**不会调用 provider**
- 两种情况下都会直接返回 fallback metadata 与友好 message

适用边界：
- 适合单进程 WebUI / API 保护
- 多进程 / 多副本部署时，每个进程各自维护窗口，不共享全局状态

## Usage log

默认写入 JSONL：

```bash
/tmp/hivision-ai-enhance-usage.jsonl
```

每次请求记录字段：
- `timestamp`
- `request_id`
- `provider`
- `mode`
- `status`
- `fallback_reason`
- `error_code`
- `latency_ms`
- `validation_passed`
- `estimated_cost`
- `rate_limited`
- `template_name`

注意：
- usage log **不会记录图片 base64**
- `usage_logged` 反映本次返回前是否成功写入 usage log
- `estimated_cost` 当前仅支持环境变量静态估算，不做 provider token/image 真实计费解析

## Validator（基础质量门禁）

当前 `hivision/plugin/ai_enhance/validator.py` 做的是低成本门禁：
- 图片是否可 decode
- shape / channel 是否合理
- 分辨率是否在基本范围内
- 是否存在明显蓝色偏色污染

`outfit` 额外通过 `hivision/plugin/ai_enhance/outfit_protection.py` 做 protected face/upper region guard：
- 构造保守 lower-body crop/mask，默认保护图像上方约 56% 区域
- provider 只接收衣服/肩膀 crop，返回后合成回原图
- 对合成结果的保护区域做 RGB/BGR mean delta 与 blue shift 检测

当前不会做复杂人脸 embedding / identity similarity 检测；如果后续要增强，可在 validator 层继续扩展。`outfit` 仍不能作为正式身份一致性/证件照合规判断依据。

建议错误码：
- `IMAGE_DECODE_FAILED`
- `BAD_IMAGE_SHAPE`
- `BAD_IMAGE_CHANNELS`
- `COLOR_CAST_DETECTED`
- `PROTECTED_REGION_CHANGED`
- `FACE_COLOR_SHIFT_DETECTED`
- `OUTFIT_COLOR_GUARD_FAILED`

## Debug 落盘

开启：

```bash
export AI_ENHANCE_DEBUG_SAVE=1
export AI_ENHANCE_DEBUG_DIR=/tmp/hivision-ai-enhance-debug
```

行为：
- 每次请求创建一个独立目录
- 保存 `input.*`、`output.*`、`metadata.json`
- metadata 中返回 `debug_input_path` / `debug_output_path` / `debug_metadata_path`
- `metadata.json` 中请求体会对 `input_image_base64` 做 `<redacted>` 处理

## WebUI 状态扩展

WebUI 的 AI 状态文本现在会附带：
- 固定等待提示：`AI 生成可能需要 1–2 分钟，请勿重复点击`
- provider / mode / latency
- validation pass/fail
- request_id（短前缀）
- estimated_cost（若配置）
- rate limit / concurrency guard 的友好文案
- fallback / error code / warnings
- `outfit` 时额外显示 `mask_edit` / `crop_edit` / `face_protected` / `color_guard_passed` / `protected_region_delta`

说明：
- 当前仍是同步执行，不额外引入异步队列
- 重点是把“慢”解释清楚，并减少重复点击造成的资源浪费

## 测试基线

新增 smoke 脚本：

```bash
python3 scripts/test-ai-enhance-smoke.py
python3 scripts/test-ai-outfit-mask-guard.py
```

覆盖点：
- `consent=false` fallback
- 未配置 key 的 fallback
- validator 对明显蓝色污染样本的检测
- metadata 扩展字段
- debug 落盘路径与 metadata.json
- rate limit 命中
- concurrency guard 命中
- usage log 写入且不含 base64
- `outfit` mode schema、template_name 透传、consent=false fallback、usage log mode/template 记录、prompt 约束
- `outfit` lower-body mask/crop 不覆盖脸部保护区
- crop/composite 保护区域 delta 检测
- protected region 色偏 guard 失败检测
- service metadata 中的 `mask_edit` / `crop_edit` / `face_protected` / `color_guard_passed`

## Prompt 约束

当前内置 prompt 为保守模式：
- `repair` 仅允许轻度修复
- `background_template` 仅允许背景模板整理
- `outfit` 仅允许编辑脖子以下衣服区域
- 明确要求**保留身份特征**
- 不允许改变年龄、肤色、发型、表情、姿态、裁切、背景和光照
- `outfit` 不加配饰、不改身份、不要夸张美化
- 不做美颜、瘦脸、重塑五官等身份改动

## 当前限制

- 当前只实现单 provider：`gpt-image-2`
- provider 接口按 OpenAI Images API 兼容方式封装，便于后续替换 endpoint
- `outfit` 仍为 Beta 预览能力；`social_photo` 为非正式头像预览能力
- fallback 当前返回原图，不做本地增强替代算法
- AI 输出仍只作为预览/独立接口结果，不替换正式证件照默认输出
- 进程内 limiter 不跨进程共享，若后续上多 worker，需要升级到共享状态或网关层限流

## WebUI background_template 模板与前后对比

WebUI 的「AI 增强预览」现在支持在 `ai_mode=background_template` 时选择背景模板。当前模板名：

- `clean_blue`：干净证件照蓝底
- `clean_white`：干净白底
- `clean_gray`：干净浅灰底
- `resume_soft`：简历用柔和职业背景
- `linkedin_clean`：LinkedIn/职业头像风格的干净背景

模板选择只在 `background_template` 语义下传给 provider；`repair` 模式会忽略 `template_name`，避免修复模式被背景模板影响。

WebUI 预览区保留状态文本，并拆成两张图：

- **AI 输入预览**：实际送给 provider 的图片（来自已生成的高清证件照）
- **AI 输出预览**：provider 返回或 fallback 的 AI 预览图

AI 输出仍然只是预览，不会替换正式「标准照 / 高清照 / 排版照」输出，也不修改 `IDCreator` 主链路。状态文本会显示 provider、mode、template、latency、validation 等摘要信息，便于判断当前请求是否使用模板以及是否 fallback。


## WebUI outfit Beta 正装预览

WebUI 的「AI 增强预览」现在支持 `ai_mode=outfit`。选择该模式后，模板下拉会切换为「正装模板（Beta）」，当前模板名：

- `business_suit_black`：保守黑色商务西装
- `business_suit_navy`：保守藏青商务西装
- `white_shirt`：简洁白色商务衬衫
- `business_casual`：保守商务休闲

显示规则：
- `repair`：不显示模板下拉，忽略 `template_name`
- `background_template`：显示背景模板下拉，并将 `template_name` 传给 provider
- `outfit`：显示正装模板下拉，并将 `template_name` 传给 provider

边界：
- `outfit` 只生成 AI 正装预览，用于简历头像/形象照参考
- 不建议作为正式证件照提交
- 不替换 WebUI 的正式「标准照 / 高清照 / 排版照」输出
- 不修改 `/idphoto` 与 `IDCreator` 主链路
- 当前 validator 仅做低成本图像质量门禁，不做正式身份一致性校验
- 当前采用 lower-body crop/composite，而不是整图重绘；provider 接收到的是衣服/肩膀 crop
- metadata 会记录 `mask_edit=true`、`crop_edit=true`、`face_protected=true`、`color_guard_passed=true/false` 与 `protected_region_delta`
- 保护区基于保守几何启发式（默认上方约 56%），不是人脸 embedding / landmark 级校验；极端构图可能需要后续接入现有人脸框/关键点进一步优化
