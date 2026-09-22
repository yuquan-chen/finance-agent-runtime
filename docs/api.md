# 当前 Runtime API

本文记录当前仓库已经实现的 HTTP API。它不描述未来的 WavePaid Admin API 或支付 API。

## 基础接口

| Method | Path | 说明 |
| --- | --- | --- |
| `GET` | `/` | 返回单页聊天 UI |
| `GET` | `/health` | 健康检查 |
| `GET` | `/v1/skills` | 返回 Skill manifest |
| `POST` | `/v1/frontend-events` | 保存前端结构化诊断事件 |
| `POST` | `/api/clear-memory` | 清理当前身份的模型可见记忆 |

## Sessions 和 Side Skills

| Method | Path | 说明 |
| --- | --- | --- |
| `GET/POST` | `/v1/sessions` | 列出或创建会话 |
| `GET/DELETE` | `/v1/sessions/{session_id}` | 读取或删除会话 |
| `POST` | `/v1/sessions/{session_id}/pin` | 设置置顶状态 |
| `GET` | `/v1/sessions/{session_id}/history` | 读取会话历史 |
| `GET/PUT` | `/v1/sessions/{session_id}/skill-state/{skill_key}` | 读取或更新 Skill 状态 |
| `GET/POST` | `/v1/sessions/{session_id}/skill-sessions` | 列出或打开 Side Skill session |
| `GET` | `/v1/skill-sessions/{skill_session_id}` | 读取 Side Skill session |
| `POST` | `/v1/skill-sessions/{skill_session_id}/messages` | 发送 Side Skill 消息 |
| `POST` | `/v1/skill-sessions/{skill_session_id}/attachments` | 上传 Side Skill 材料 |
| `POST` | `/v1/skill-sessions/{skill_session_id}/close` | 关闭 Side Skill session |

## Runs 和遗留确认动作

| Method | Path | 说明 |
| --- | --- | --- |
| `POST` | `/v1/runs` | 创建一次 Agent run |
| `GET` | `/v1/runs/stream` | 通过 SSE 创建 run 并返回阶段事件 |
| `GET` | `/v1/runs/{request_id}` | 读取 run 安全状态 |
| `POST` | `/v1/runs/{request_id}/analysis-plan/approve` | 兼容历史待确认分析计划；新查询不会进入 |
| `POST` | `/v1/runs/{request_id}/method-review/approve` | 兼容历史待确认方法；新查询不会进入 |
| `POST` | `/v1/runs/{request_id}/method-review/revise` | 兼容历史待确认方法的修改 |
| `POST` | `/v1/runs/{request_id}/data-authorization/approve` | 授权数据读取 |
| `POST` | `/v1/runs/{request_id}/prior-result-authorization/approve` | 授权使用之前的私有结果 |

普通只读查询通过 `Query Guard` 后自动执行，不生成用户确认卡。上表接口只为历史待确认任务保留；真正有副作用的能力未来应使用独立的命令和确认协议。确认动作由服务端按 `request_id`、当前身份和幂等键保护。

## Attachments 和 KYC

| Method | Path | 说明 |
| --- | --- | --- |
| `POST` | `/v1/sessions/{session_id}/attachments` | 上传会话材料 |
| `GET` | `/v1/sessions/{session_id}/attachments/{attachment_id}` | 读取会话材料 |
| `POST` | `/v1/sessions/{session_id}/attachment-intent` | 路由材料意图 |
| `POST` | `/v1/sessions/{session_id}/kyc/{skill_key}/attachment-intake` | 处理材料识别结果 |
| `POST` | `/v1/sessions/{session_id}/kyc/{skill_key}/attachment-reviews/{attachment_id}/confirm` | 确认材料识别结果 |
| `POST` | `/v1/sessions/{session_id}/kyc/{skill_key}/uploads/{upload_id}` | 保存 KYC 草稿材料 |
| `POST` | `/v1/sessions/{session_id}/kyc/{skill_key}/ocr` | 执行本地 OCR |
| `GET` | `/v1/sessions/{session_id}/kyc/{skill_key}/draft` | 读取 KYC 草稿 |
| `GET` | `/v1/sessions/{session_id}/kyc/{skill_key}/draft/export` | 导出 KYC 草稿 |

当前 KYC 接口不会提交外部 KYC 系统、执行 Face ID 或修改外部审批状态。

## 身份和资源隔离

所有会话、run、Skill session、附件和 KYC 草稿请求都应在当前 `user_id + workspace_id` 范围内访问。

- `AUTH_MODE=local`：从请求头读取开发身份。
- `AUTH_MODE=required`：校验签名 JWT 后建立身份。
- 资源不属于当前身份时按不存在处理，避免泄露资源存在性。

## 响应安全边界

Run 响应包含查询计划、方法、校验摘要和结果证据。普通只读查询不返回确认卡字段；历史待确认任务仍可返回兼容卡片。真实查询结果不应被复制到普通对话历史、RunStore 或模型可见记忆中。

使用 FastAPI 自动生成的 `/docs` 或 `/openapi.json` 查看当前 Pydantic 请求/响应 schema。
