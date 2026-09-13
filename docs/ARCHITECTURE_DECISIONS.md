# ARCHITECTURE_DECISIONS.md

## ADR-001 单一规格
v2.2.2 Server-Integrated 是唯一实现输入；旧版本只归档。

## ADR-002 单一完整决策引擎
完整植物浇水决策只在云端；Pi 只执行命令与版本化 fallback_policy。

## ADR-003 AI边界
LLM 只识别/整理知识，不输出最终水量、泵时长、脉冲数或 GPIO。

## ADR-004 两类命令超时
`claim_ttl_sec` 只决定 pending 命令是否过期；`session_max_duration_sec` 决定 started 后整次会话上限。

## ADR-005 权威账本
Pi SQLite 是硬件执行与滚动24小时硬限额权威；云端用于审计、展示和预检查。

## ADR-006 水量策略
不把单点土壤湿度百分点线性换算为整盆缺水毫升；按花盆安全脉冲补水并闭环停止。

## ADR-007 防虹吸
依赖液位低于自由空气喷嘴、机械固定和实测；普通单向阀不算防正向虹吸措施。

## ADR-008 异步任务
使用 PostgreSQL jobs + 独立 Worker，不把 FastAPI BackgroundTasks 当可靠队列。

## ADR-009 数据真实性
real/demo/test/mock 永远分开，趋势不足7天显示真实覆盖时长。

## ADR-010 BLE可替换
小米 BLE 无法稳定读取时切换 SHT30/AHT20 Provider，不阻塞核心系统。

## ADR-011 数据库强约束
主控植物和活跃补水命令使用数据库部分唯一索引。

## ADR-012 MVP边界
单设备、单主控植物、单泵；当前不建设通用物联网平台。

## ADR-013 同机但业务独立
Flower 与现有 aibot 共用物理服务器，但不共享业务数据库、会话、设备 token、命令链或运行目录。aibot 保持 systemd 现状。

## ADR-014 单一公网入口
宿主 Nginx 继续独占 80/443。Flower 内部 proxy 只绑定 `127.0.0.1:18080`；API/PG 不发布宿主端口。不启动 Caddy 抢占入口。

## ADR-015 不可变发布
Flower 应用镜像 tag 使用 Git commit SHA。生产 release 保存 Compose、环境清单、migration 版本与镜像摘要；`latest` 不作为回滚依据。

## ADR-016 显式生产 migration
生产 migration 由受控一次性 job 执行。API/Worker entrypoint 不自动 migration；迁移失败不切流量。

## ADR-017 语音与外设旁路禁止
任何 aibot peripheral、语音助手、本地 HTTP 调试接口或通用 Agent 不得直接/间接驱动 GPIO17/YYMOS。语音只能产生业务意图并进入 Flower `create_command()`，Pi 仍经过 `can_dispense()`。

## ADR-018 生产配置 fail-closed
production 下 `DEV_MODE=true`、`DEV_AUTH_BYPASS=true`、公网基址非 HTTPS 或关键 secret 为空时，API/Worker 拒绝启动。

## ADR-019 开发期安全通道
正式域名未就绪时，开发设备优先通过主动 SSH/Tailscale 加密隧道访问服务器环回开发端口；禁止 `verify=False` 和直接公开明文开发 API。

## ADR-020 平台化延后
当前不抽统一 ASR/TTS/LLM 服务、不建设 Device Registry、不迁移 aibot。出现第二个真实调用方且接口稳定后再抽无硬件副作用的共享能力。
