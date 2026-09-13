# IMPLEMENTATION_PLAN.md

## 总体规则

每个 Stage 都执行：测试先行 → 最小实现 → 全量回归 → evidence → 原子提交。真实遥测在 Stage 2 后立即并行积累。Flower 代码开发可持续推进；共享宿主机生产变更需要授权窗口。

## Stage 0：v2.2.2 基线与独立仓库

- 校验 `SPEC_CURRENT.md`、GOAL、7个项目 Skills、server-audit 8份报告。
- 确认 `/root/flower` 独立 Git；不把 `/opt/asist-embodiment` 纳入版本控制。
- 创建 backend/pi-agent/miniapp、Compose overrides、tests/evidence。
- `/health`、`/ready` 合约；production fail-closed 配置测试。
- 固化宿主端口/systemd/Nginx/UFW/nft/Tailscale/OpenVPN preflight 脚本，但不做生产修改。

**门**：旧 v2.2 包不再作为输入；aibot 未被修改；基础测试可跑。

## Stage 1：Pi 安全核心（Mock优先）

实现 GPIO/P451/ADS1115/SQLite账本/状态机/`can_dispense()`/watchdog/BLE/相机/标定工具。加入测试证明任何语音/外设旁路都不能直接调用 pump driver。

## Stage 2：云端设备链路

FastAPI、Flower 专用 PostgreSQL、Alembic、设备鉴权、telemetry/events/fallback/quota、command create/claim/started/progress/result、两类超时与两个部分唯一索引。

**门**：并发 claim 100 次只1次成功；>60秒多脉冲不被 claim TTL 中断；Stage 2 通过当天开始 `source_type=real` 只读遥测。

## Stage 3：可靠 Worker 与识别

PostgreSQL jobs、独立 Worker、重试/恢复/幂等、图片生命周期/鉴权/低磁盘门、Top3和手动输入。`JOB_MAX_CONCURRENCY=1` 初始配置。

## Stage 4：知识/天气/LLM/唯一决策

Provider+Mock、证据来源、冲突处理、Schema、确定性决策、IANA timezone fallback、家庭记忆规则。LLM输出无执行参数。

## Stage 5：微信小程序

登录、植物、识别、养护卡、状态、手动/自动、时间线、记忆、告警、趋势真实性。`pending` 不等于成功。

## Stage 6：聚合、清理、连续数据

telemetry_hourly、30天 raw、365天 hourly、图片/命令/job清理、备份脚本、真实趋势。

## Stage 7：共享宿主机部署准备与共存测试

- 生成 `proxy/api/worker/postgres` Compose，生产只绑定 `127.0.0.1:18080`。
- commit SHA 镜像、release manifest、显式 migration、上一 release 无重建回滚。
- Docker 首装前后网络快照与回归脚本。
- 宿主 Nginx Flower 站点模板，不修改现有 City Front 文件。
- production auth/HTTPS hard gate。
- 定时备份与独立测试恢复。
- 在获授权后安装 Docker/新增 Nginx 站点/真实部署。
- 观测 aibot + Piper回退 + Flower Worker 资源重叠；未获高峰证据标 NOT_RUN。

## Stage 8：实物、离线演示与最终交付

断网/NTP/缺水/传感器/kill/容器重启/BLE相机压力、防虹吸、滴漏、5秒恢复；OFFLINE_DEMO；最终报告逐项链接 evidence。

终态仅允许 `COMPLETE` 或 `HARD_BLOCKED`。
