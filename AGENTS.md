# AGENTS.md

## 1. 适用范围与权威顺序

本仓库用于开发“智慧守候·AI植物守护与记忆灌溉系统”。所有代理开始工作前必须依次读取：

1. `AGENTS.md`
2. `SPEC_CURRENT.md`
3. `GOAL.md`
4. `docs/SERVER_INTEGRATION_BASELINE.md`
5. `docs/SAFETY_INVARIANTS.md`
6. `docs/API_AND_DATA_CONTRACTS.md`
7. `docs/server-audit/RECOMMENDATION.md`
8. `docs/IMPLEMENTATION_PLAN.md`
9. 与当前任务匹配的 `.agents/skills/*/SKILL.md`

权威顺序：产品行为、安全边界、数据模型和验收以 `SPEC_CURRENT.md` 指向的 v2.2.2 规格为准；共享服务器事实以 `docs/server-audit/` 2026-09-13 审计为当前基线；执行纪律以本文件为准。旧规格只能归档，禁止合并回当前实现。

## 2. 单一目标执行方式

接到 `GOAL.md` 后持续推进到 Definition of Done，不等待逐阶段确认。只有以下情况暂停对应子任务：

- 必须由用户完成的物理接线、量杯标定、微信主体/控制台操作；
- 必须由用户授权的生产变更窗口，例如首次安装 Docker、修改宿主 Nginx、DNS/证书、生产发布；
- 缺少不可替代凭据且 Mock 也无法继续。

其他缺失输入先用 Mock/Provider/配置占位继续，并写入 `BLOCKERS.md`。

## 3. 开发与生产目录

- 开发仓库：`/root/flower`。
- Flower 生产根：`/srv/flower`。
- aibot 生产：`/opt/asist-embodiment`，**只读边界**；Flower 任务不得修改、reset、clean、checkout、pull、重启或迁移它。
- aibot 继续现有 systemd；Flower 使用独立 Compose project `flower-prod`。
- 宿主机 Nginx 继续独占 80/443；Flower 生产仅发布 `127.0.0.1:18080`。

## 4. 开发纪律

- 在独立分支或 worktree 工作，不覆盖用户未提交内容。
- 行为变更先写失败测试，再实现；安全逻辑必须有单元测试和故障注入测试。
- 每个 Stage 完成后运行验证、更新 `STATUS.md`、保存 `evidence/`、原子提交，再继续。
- 没有运行证据不得宣称通过；无真实硬件证据只能写 Mock/模拟通过。
- 首次安装 Docker 或修改 Flower 网络前后，必须比较 `ss`、systemd、Nginx、UFW/nft、路由、Tailscale、OpenVPN 和现有服务状态。

## 5. 不可违反的系统边界

- 当前唯一规格为 v2.2.2 Server-Integrated。
- 完整浇水决策只在云端；Pi 只执行命令和版本化 `fallback_policy`。
- LLM 不得输出最终水量、泵时长、GPIO 或脉冲数。
- 任何非本地 fallback 开泵都必须经过云端 `create_command()` 和 Pi `can_dispense()`。
- **任何 aibot peripheral、语音助手、本地 HTTP 调试接口、管理后台或通用 Agent 均不得直接或间接驱动 GPIO17/YYMOS。**
- Pi 本地水量台账是硬限额权威；云端是审计与预检查。
- `claim_ttl_sec` 只约束领取，`session_max_duration_sec` 只约束执行，严禁混用。
- SAFE_HOLD 永远不能开泵；任何不确定状态默认不浇水。
- 普通单向阀不得被描述为正向防虹吸装置。
- 模拟、演示、真实数据必须明确区分。
- 生产环境 `DEV_MODE=true`、`DEV_AUTH_BYPASS=true` 或公网基址非 HTTPS 时，应用必须拒绝启动。

## 6. 共享宿主机发布边界

- Flower 镜像使用 commit SHA 不可变 tag，不用 `latest` 作为回滚依据。
- 生产 migration 为显式一次性 job；API/Worker entrypoint 不自动 migration。
- PostgreSQL、uploads、备份均为 Flower 独立数据，不读取 aibot 数据。
- API 8000、PostgreSQL 5432 不发布宿主机；Flower proxy 只绑定 `127.0.0.1:18080`。
- 正式域名建议 `flower-api.bkeel.com`；未配置前不得伪称正式上线。

## 7. 技能加载

按任务显式读取对应 Skill；不要依赖运行时是否自动扫描 repo-local `.agents/skills/`：

- 规格冲突/开始任务：`using-smart-guardian-baseline`
- 泵、水位、额度、时间、命令执行：`implementing-safety-critical-watering`
- Pi、BLE、相机、GPIO、SQLite：`building-raspberry-pi-agent`
- FastAPI、PostgreSQL、Worker、共享服务器部署：`building-cloud-control-plane`
- 微信小程序、趋势、告警、记忆：`building-wechat-miniapp`
- 真实硬件、标定、断网：`integrating-real-hardware`
- 完成/部署/交付前：`finishing-one-goal-delivery`

## 8. 持续维护文件

- `STATUS.md`
- `BLOCKERS.md`
- `evidence/`
- `FINAL_IMPLEMENTATION_REPORT.md`

没有证据的项目不得在最终报告中写为“完成”。
