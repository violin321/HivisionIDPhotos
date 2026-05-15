# Phase 5A 应用层安全加固

本阶段只加固现有 Web v2 + FastAPI 工作流，不改变输出边界：`officialResult` 仍由 Hivision `IDCreator` 生成；可选 AI preview 仍标记为 `local-derived-preview`，不接入 GPT-image-2，也不需要外部模型密钥。

## 上传限制

API 端点：`POST /api/uploads`

默认策略：

- 最大上传体积：`20MB`，可用 `IDPHOTO_MAX_UPLOAD_BYTES` 覆盖；与 nginx `client_max_body_size 20m` 对齐。
- 允许 MIME：`image/jpeg`、`image/png`、`image/webp`。
- 允许扩展名：`.jpg`、`.jpeg`、`.png`、`.webp`。
- 校验 magic bytes：JPEG / PNG / WebP 文件头必须匹配声明类型。
- 图片解码检查：使用 Pillow `Image.verify()` 验证可解码。
- 最大像素数：默认 `24_000_000`，可用 `IDPHOTO_MAX_IMAGE_PIXELS` 覆盖。

错误行为：

- 非允许 MIME：`400 INVALID_FILE_TYPE`
- 非允许扩展：`400 INVALID_FILE_EXTENSION`
- 空文件：`400 EMPTY_UPLOAD`
- 超体积：`413 FILE_TOO_LARGE`
- magic bytes 或解码失败：`400 INVALID_IMAGE_BYTES`
- 超像素：`413 IMAGE_TOO_LARGE`

错误统一返回 JSON：

```json
{
  "detail": {
    "error": {
      "code": "INVALID_FILE_TYPE",
      "message": "Only JPG, PNG, or WebP image uploads are supported.",
      "retryable": true
    }
  }
}
```

## 自动清理 / TTL

运行时目录：

- `.runtime/uploads`
- `.runtime/results`
- `.runtime/tasks.json`

默认 TTL：`6 小时`，可用环境变量覆盖：

```bash
export IDPHOTO_RUNTIME_TTL_SECONDS=21600
```

触发点：

- API 启动后执行一次轻量 cleanup。
- 创建 upload 前执行 cleanup。
- 创建 task 前执行 cleanup。
- 查询 task 前执行 cleanup。
- 可手动或 cron 运行脚本：

```bash
.venv/bin/python scripts/cleanup_runtime.py
```

保护规则：

- `queued` / `processing` 任务视为活跃任务，不删除其关联 upload / result。
- 已完成、失败、过期任务超过 TTL 后，从任务状态中移除，并删除对应 result 目录。
- 未被任务状态引用的过期孤儿文件/目录也会被清理。

## e2e 用法

### 本地

```bash
API_BASE_URL=http://127.0.0.1:18084 \
  .venv/bin/python scripts/e2e_phase5a_api.py
```

脚本流程：

1. `GET /api/health`
2. `GET /api/config`
3. `GET /api/templates`
4. 负向测试：`text/plain` 上传应返回 4xx。
5. 负向测试：构造超大 JPEG 上传应返回 `413/4xx`。
6. 正向流程：upload -> task -> poll -> `officialResult`。
7. 检查 AI preview 标记仍为 `local-derived-preview`。

### 公网 Basic Auth

公网地址可用 nginx Basic Auth 保护。脚本支持环境变量注入，不会打印密码：

```bash
API_BASE_URL=https://idphoto-ai.violinai.qzz.io \
BASIC_AUTH_USER='<user>' \
BASIC_AUTH_PASSWORD='<password>' \
  .venv/bin/python scripts/e2e_phase5a_api.py
```

也可用 URL 内 auth，但不推荐；若使用环境变量，脚本输出只显示 `basicAuth: true`，不会输出 Authorization header 或密码。

## 前端提示

Web v2 右侧状态栏新增隐私提示：仅接受 JPG/PNG/WebP、上传有大小限制、上传和结果会自动过期。
