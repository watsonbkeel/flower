# API_AND_DATA_CONTRACTS.md

## 1. 公共原则

- 业务 API 使用 `/api/v1`。
- `/health`、`/ready` 是根路径运维端点。
- 设备和用户接口均需鉴权；生产不允许 bypass。
- 所有时间数据库字段用 UTC/TIMESTAMPTZ；本地 watering windows 携带 IANA timezone。
- 命令状态和 Job 状态均可持久化、可幂等恢复。

## 2. 命令枚举

```text
source = cloud_auto | user_manual | local_fallback | maintenance_test
run_mode = real | demo | offline_demo
status = pending | claimed | executing | succeeded | failed | expired | timed_out | cancelled
```

`local_fallback` 不是云端命令来源；它是 Pi 对已签发 fallback_policy 的本地受限执行来源。

## 3. 命令时序字段

```text
claim_ttl_sec
claim_deadline_at
claimed_at
start_grace_sec
started_at
session_max_duration_sec
session_deadline_at
last_progress_at
finished_at
```

`expired` 只用于未领取/未开始的命令；`timed_out` 用于已开始且超过 session deadline 的会话。执行中不得重新用 `claim_ttl_sec` 判过期。

## 4. 设备 API

```text
POST /api/v1/device/auth/token
POST /api/v1/device/telemetry
POST /api/v1/device/commands/claim
POST /api/v1/device/commands/{id}/started
POST /api/v1/device/commands/{id}/progress
POST /api/v1/device/commands/{id}/result
POST /api/v1/device/events/batch
POST /api/v1/device/images
POST /api/v1/device/calibration
GET  /api/v1/device/fallback-policy
POST /api/v1/device/quota/reconcile
```

`commands/claim` 必须原子领取，使用数据库事务 + `FOR UPDATE SKIP LOCKED` 或等价原子更新。

## 5. 小程序 API

```text
POST /api/v1/auth/wechat-login
GET/POST /api/v1/plants
POST /api/v1/plants/{id}/capture
GET  /api/v1/plants/{id}/recognition
POST /api/v1/plants/{id}/confirm-species
POST /api/v1/plants/{id}/care-profile/generate
POST /api/v1/plants/{id}/care-profile/confirm
GET  /api/v1/plants/{id}/status
GET  /api/v1/plants/{id}/events
GET  /api/v1/plants/{id}/telemetry/series
POST /api/v1/plants/{id}/water
PUT  /api/v1/plants/{id}/auto-mode
GET/POST/PUT /api/v1/memories
POST /api/v1/memories/{id}/structure-rule
PUT  /api/v1/memories/{id}/enabled
GET  /api/v1/jobs/{id}
GET  /api/v1/alerts
PUT  /api/v1/alerts/{id}/read
GET  /api/v1/images/{id}
```

所有补水外壳最终只调用一次 `create_command()`；`/plants/{id}/water` 不复制安全逻辑。

识别读取响应包含 `status`、`capture_id`、`image_id`、`result`、`default_selection`、`retake_recommended` 和 `manual_input_available`。有拍照命令时，以最新命令为当前拍摄：非成功状态返回 `capture_<command.status>` 和空结果；成功后只读取服务器记录的 `started_at` 至 `finished_at` 范围内最新的 whole/leaf/flower 图片。无命令时读取最新识别用途图片，记忆照片不参与。

图片作业未完成时返回 `queued`/`running`，失败返回 `failed`，不退回历史候选。成功拍照但范围内没有图片返回 `image_missing`；无拍摄记录返回 `empty`。`succeeded` 才包含可确认候选。客户端轮询更新识别区域，并保留同图的显式选择与手动输入。

## 6. 健康端点

`GET /health`：进程存活，不访问外部 Provider。

`GET /ready`：检查数据库可达、migration head、必要 schema/索引已就绪；失败返回非2xx。不得泄露 secret。

## 7. Jobs

```text
queued -> running -> succeeded | failed
```

慢任务必须由独立 Worker 从 PostgreSQL jobs 原子领取；API 请求只创建 Job 并返回 job_id，不用 BackgroundTasks 作为可靠队列。

养护卡生成与记忆规则整理支持可选`Idempotency-Key`请求头（1-100字符），按用户、操作类型和目标资源隔离。同一键重放返回原job，包括其失败终态；用户主动重新生成或失败后重试使用新键。未提供请求键时，每次POST视为新操作。作业入队以数据库唯一约束和原子冲突处理去重；Worker每个job最多尝试3次，失败历史保留。

## 8. 趋势数据

趋势响应必须包含：

```text
source_type
coverage_start
coverage_hours
requested_range
points
watering_events
```

无真实历史时返回真实覆盖情况，不造假7天曲线。

## 9. 版本契约

API 响应、设备 telemetry 或诊断中应可追踪 `spec_version=2.2.2`、软件版本和设备固件版本。
