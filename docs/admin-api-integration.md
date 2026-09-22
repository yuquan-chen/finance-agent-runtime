# 业务 API 接入设计

本文是未来接入 Admin/业务 API 的现行设计入口。当前仓库尚未实现业务 API Client、Payment Gateway 或 Admin 操作服务。

## 目标

把外部业务系统提供的页面能力转化为受控的领域操作：

```text
自然语言意图
  -> 领域对象和动作识别
  -> 后端加载授权范围
  -> typed Gateway 调用外部 API
  -> 结果标准化
  -> 展示 / 确认 / 状态跟踪
  -> 审计
```

页面路由只是产品导航信息，不能直接当作外部 API endpoint。一个页面可能需要多个接口，一个接口也可能服务多个页面。

## 动作分类

| 动作 | 性质 | 最低要求 |
| --- | --- | --- |
| 查询列表、详情、看板 | 只读 | 过滤范围、分页、字段脱敏、超时和审计 |
| 导出 | 只读但有数据外发风险 | 明确范围、列白名单、行数/文件大小限制、下载审计 |
| 审核、复核、驳回 | 有副作用 | 角色权限、状态机、确认、幂等、审计 |
| 开户、创建、提交 | 有副作用 | 服务端命令模型、字段校验、确认、幂等和错误恢复 |
| 配置 | 高影响写操作 | 权限、变更前后快照、确认、版本和回滚策略 |
| 导入 | 批量写操作 | 文件校验、批次 ID、重复策略、逐行失败结果和审计 |

有副作用的动作不能注册为 `MethodDraft(method_type="sql")`，也不能让 LLM 生成 URL、Header 或任意 JSON。

## 推荐代码边界

```text
src/finance_agent/business_api/
  models.py          领域对象、命令、分页和错误模型
  client.py          固定 base URL、认证、超时、重试和 request ID
  gateway.py         受控 endpoint / operation allowlist
  services/          客户、KYC、VA、付款等领域服务
  policy.py          组织、角色、账户范围和动作权限
  store.py           草稿、操作状态、幂等映射和外部引用
  audit.py           领域操作审计事件
  adapters/          每个外部 API 版本的请求/响应映射
```

如果领域包含异步状态或资金动作，还需要显式状态机和 webhook 去重处理。外部系统的状态是事实源，本项目只保存流程状态和外部引用，不能创建第二套业务账本。

## 接口契约记录模板

拿到真实接口文档后，每个 endpoint 先按下面结构登记：

```yaml
operation_id: payout.list
domain: payout
action: list
environment: sandbox
api_version: v1
method: GET
path: /replace-with-real-path
auth:
  scheme: replace-with-real-scheme
  required_scopes: []
resource_scope:
  organization: required
  account: optional
request:
  query: {}
  body: null
response:
  data_path: data
  pagination: replace-with-real-pagination
  status_fields: []
errors: []
side_effect: false
idempotency: not_applicable
sensitivity:
  hidden_fields: []
audit_event: business_api.payout.list
```

写操作必须补充：

```yaml
confirmation:
  required: true
  binds_to: [resource_version, actor, request_hash]
idempotency:
  supported: true
  location: header
state:
  external_reference_field: external_id
  terminal_statuses: []
retry:
  safe_to_retry: false
```

## 外部接口到领域模型的转换

外部 API 的字段不能直接泄漏到 Planner 或 UI。Adapter 应转换为稳定的内部模型，并保留：

- 外部 `request_id`、资源 ID 和 API 版本；
- 内部操作 ID 与外部资源 ID 的区别；
- 业务状态和可读失败原因；
- 原始响应的安全 hash，而不是未经筛选的完整响应；
- 需要展示的字段和禁止展示的字段。

## 接入顺序

1. 固定 sandbox/staging 环境和 API 版本，拿到 OpenAPI、Postman 或完整样例。
2. 建立 endpoint matrix 和 typed request/response models。
3. 先实现只读列表、详情和状态查询，补齐权限与字段脱敏测试。
4. 再实现草稿或预览类操作，不产生外部副作用。
5. 最后实现审核、开户、提交等写操作，增加确认、幂等和恢复测试。
6. API contract 稳定后，再接入 Agent intent routing 和 UI card。

## 当前禁止的实现方式

- 从用户消息读取 base URL、认证 Header 或任意 endpoint；
- 让 LLM 直接调用外部 API；
- 用数据库表名猜测 API 资源和权限；
- 用 HTTP 200 或“工具调用成功”推断业务成功；
- 把完整银行账号、证件、密钥或原始风控结果写进普通记忆；
- 在没有 API 状态事实、确认和幂等保障时接入资金动作。
