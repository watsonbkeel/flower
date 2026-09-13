# flower 与现有 aibot 的共存建议

日期：2026-09-13。性质：只读架构审计与待确认建议，未开发、未部署。

## 1. 结论

推荐 **B：同一服务器、两个业务独立，逐步复用 AI 能力**。近期让 flower 按原有 FastAPI + Worker + PostgreSQL + Pi 安全执行架构落地，复用现有宿主机 Nginx 和外部 Provider 接入经验；aibot 保持当前 systemd 运行方式。出现第二个明确语音调用方后，再抽出独立 ASR/TTS/LLM 能力服务。

这台主机可以作为单设备、单盆植物 MVP 的部署目标，但尚未通过共存容量和部署验收。2 vCPU 是主要约束；内存约 7.5 GiB、当前可用约 6.7 GiB、磁盘剩余约 71 GiB。flower 首版调用外部 AI、Worker 并发 1，并对新增容器设置预算；不在这里同时新增本地大模型或持续云 ASR。

## 2. 支撑结论的实际发现

- aibot 实际运行于 `/opt/asist-embodiment/brain`，是 Python 标准库 HTTPServer + 内存线程池，不是已经建成的 AI 设备云平台。
- `/root/aibot/asist-embodiment` 是干净源码仓库；`/opt` 的 Git HEAD 不同且有大量未提交内容。四个关键 brain 文件相同，不能据此推定所有 body/部署文件相同。
- 当前 ASR 在 Pi 的 Vosk 代码路径；云端主要接收文字。LLM 配置为 DeepSeek 外部 HTTPS 接口；Edge TTS 为远程合成，本机仍编码音频，失败可回退本地 Piper。
- 没有可直接供 flower 复用的独立云 ASR/TTS/LLM API，也没有统一用户系统、Registry、业务数据库或管理后台。`/voice/push` 会操作全局会话与固定 Pi，不能当纯能力接口。
- 主机没有发现 Docker 或运行中的 PostgreSQL。Nginx 已占用 80/443，服务 `cs.bkeel.com` 的 City Front；它不是 aibot 管理后台。
- aibot 8889 无应用鉴权，但 UFW 没有对非 VPN 流量放行它。VPN 内允许范围、云安全组和公网可达性未验收，不将“监听所有 IPv4”直接等同于“公网已开放”。
- 9 月 8 日起可见的 nox-brain 日志未记录新 Push/Response/TTS，因此资源快照只说明闲时情况。没有用主动语音测试干扰设备。
- flower 可见规格为 v2.2，GOAL 与项目 Skills 缺失；用户所述 v2.2.1 包的完整性仍待核对。

## 3. A / B / C 比较

| 方案 | 近期交付 | 风险/成本 | 结论 |
|---|---|---|---|
| A：flower 完全独立，不复用 aibot | 业务可独立交付；若另购服务器，部署边界最清楚 | 重复入口/运维和 Provider 工作；若另机则增加费用，但故障隔离更强 | 作为容量/网络验证失败后的替代；并非当前必须另购服务器 |
| B：同机、独立业务、逐步共享能力 | 保留原 flower 实施计划，复用当前基础设施经验 | 共享主机故障域，需要 Docker/VPN 验证与限额；现有语音服务不能直接当公共 API | 推荐 |
| C：立即统一 AI 设备云平台 | 要同时新建身份/注册/路由/会话/媒体/权限和迁移机制 | 打断 aibot、扩大 MVP、引入跨设备副作用和安全改造 | 当前不选；作为已验证能力逐步收敛后的结果 |

选择 B 不意味着立即开发一个公共平台。近期共享的是宿主入口及可验证的外部服务接入方式，业务数据库、密钥、命令、状态和安全门独立。

## 4. 必答问题

| 问题 | 明确建议 |
|---|---|
| flower 是否同服务器部署？ | 是，作为有限并发 MVP 的推荐目标；上线前通过资源、Docker/VPN 和独立入口验证。若不能保证现有语音体验，转独立主机或迁出推理 |
| 哪些现在值得复用？ | 宿主 Nginx/TLS 运维、外部 LLM/搜索接口经验、音频格式/分段/回退经验、VPN 运维经验。可选同一供应商，但独立项目凭据与预算 |
| 哪些不要现在共享？ | 全局聊天实例、`/voice/push`、记忆/配额文件、数据库、设备 token、用户/设备所有权、Worker/jobs、GPIO 驱动、命令和额度台账 |
| 两项目 Docker 如何隔离？ | flower 使用 flower-prod 独立网络/卷/配置/镜像生命周期；aibot 暂保留 systemd。未来容器化用 aibot-prod，不共用默认网络或运行目录 |
| PostgreSQL 一个实例多库还是独立容器？ | 现在只建 flower 专用 PostgreSQL 容器。aibot 当前没有 PG；未来若也需要，优先独立容器/卷/备份，不共享实例。开发测试另隔离 |
| Caddy/Nginx 如何编排？ | 现有宿主 Nginx 独占 80/443；flower 保留四服务，其中私有 Nginx proxy 只映射环回 18080。无需额外占公网入口的 Caddy |
| 域名/路径？ | 建议 flower-api.bkeel.com，尚未配置；保留 `/api/v1`、`/api/v1/device`、`/health`、`/ready`；不挤入 City Front 的路径 |
| 端口避免冲突？ | 生产环回 18080，staging 18081，开发 18082；API 8000/PG 5432 仅容器内部。避开现有 22/80/443/7460/8443/8889/VPN 端口，尤其不要公网绑定已放行的 8000 |
| ASR/TTS/LLM 如何成为共享能力？ | 先 Provider 接口与独立配置；后建无业务副作用、按应用认证/计费/限流的能力 API，TTS 只返音频，ASR 只返识别，LLM 不执行硬件 |
| Device Registry 现在统一？ | 不建统一服务；先统一 ID、身份与 capability 概念。flower 独立实现设备注册/绑定/轮换，真正多场景需求出现后映射迁移 |
| flower 仓库目录？ | `/root/flower`，独立仓库，backend/pi-agent/miniapp 分层，沿用当前合约与实施计划；不把 aibot 搬进来 |
| flower 生产目录？ | 建议 `/srv/flower/releases`、`current`、`shared/{config,postgres,uploads,backups}`，固定镜像，不运行开发检出 |
| 开发/生产如何隔离？ | 首选开发机/CI；不同 Compose project、database/卷、secret、设备 ID、source_type 和端口。同机测试按需运行，禁止指向生产数据库/真泵 |
| Pi 如何未来统一接云？ | 近期主动 HTTPS 遥测/命令领取；未来加主动 WSS 音频到云 ASR，统一已认证输入后路由至领域服务。所有补水仍经花盆唯一命令门与本地安全门 |
| 是否修改现有架构文档？ | 需要在确认后补充共存部署和未来阶段边界；不改浇水安全不变量，不把平台化加入当前 MVP。具体修改点见下表，本轮未改原文件 |

## 5. 建议的原文档修改点，仅列出

| 文件/章节 | 建议修改内容 | 范围与验收影响 |
|---|---|---|
| GOAL.md、FILE_LIST.txt、PACKAGE_MANIFEST、项目 Skills | 核对并补齐实际资料；明确 v2.2.1 是资料包版本还是规格版本 | 不擅自重建缺失原文，不默认改 SPEC_VERSION；技能未读不能进入对应实现任务 |
| SPEC_CURRENT.md 标题/版本及 ADR-001 | 如 v2.2.1 只是打包修订，保留 v2.2 规格并记包版本；如是新规格，必须由负责人提供修订并整体同步 | 防止两个当前基线并存 |
| SPEC 第 4/9/16 章，ARCHITECTURE_AND_BOUNDARIES | 加入“已有宿主 Nginx + flower 私有 proxy”的共存拓扑；明确四个 flower 服务和既有系统责任 | 四服务保留；私有 proxy 不抢公网端口，不访问 aibot 数据 |
| SPEC 第 9.2 章、README、实施计划 Task 1/12 | 采用 flower 独立仓库、nginx 模板、Compose overrides、独立 `/srv/flower` 发布布局 | 同步示例路径与启动入口，离线 Compose 仍可用 |
| SPEC 第 9.4/15 章、EXTERNAL_INPUTS | Provider 可用直连或未来内部能力 URL；填写独立凭据/预算需求，Worker 初始并发可设 1 | 所有真实 Provider 仍需合约、超时、Mock 和配额测试 |
| SPEC 第 12/14 章、API_AND_DATA_CONTRACTS | 明确用户/设备身份、数据库、令牌独立；未来身份映射不等于当前跨业务共享 | 当前既有 API 不需要为了平台化重命名；将来任何字段变更同步 Schema/迁移/客户端 |
| ARCHITECTURE_DECISIONS | 新增“同机独立业务”“共享能力不得产生硬件副作用”“Registry 延后”的 ADR | 保留现有 10 项决定，尤其确定性决策/HTTPS/jobs |
| DEPLOYMENT_RUNBOOK | 增加 Docker 首装前的 UFW/Tailscale/OpenVPN 检查、独立站点/证书、固定镜像、私有端口、数据备份/恢复和逐项目回滚 | 不把安装 Docker 当无影响操作；迁移只由唯一受控步骤执行 |
| TEST_AND_ACCEPTANCE_PLAN | 增加已有语音/City Front/VPN 共存、端口/网络隔离、数据库隔离、上传上限、资源与回退负载测试 | 不是本轮通过项；需后续独立证据 |
| SPEC 第 2/20 章、实施计划未来阶段说明 | 记载语音输入、共享 AI、统一 Registry 的演进条件，明确不属当前花盆 MVP | 先花盆闭环，避免立即做统一平台 |
| SAFETY_INVARIANTS/安全技能 | 如未来新增语音入口，明确它只提供意图，仍走同一 create_command/can_dispense | 安全实现变更时必须加载补齐的 safety-review 技能并增加测试；本轮不改变任何不变量 |
| PROJECT_STATUS/EXTERNAL_INPUTS | 下一阶段开始时登记审计结论、缺失资料、真实域名/凭据/硬件输入和当前阶段 | 本轮依用户范围未修改；不能将此次审计记为 Stage 0 实现完成 |

## 6. 交付与验证口径

八份文件：

1. [CURRENT_SERVER_INVENTORY.md](CURRENT_SERVER_INVENTORY.md)：主机、服务、网络、版本、命令证据。
2. [AIBOT_ARCHITECTURE_AUDIT.md](AIBOT_ARCHITECTURE_AUDIT.md)：代码和实际部署结构、能力与缺口。
3. [REUSE_MATRIX.md](REUSE_MATRIX.md)：组件级复用边界。
4. [TARGET_DEPLOYMENT_TOPOLOGY.md](TARGET_DEPLOYMENT_TOPOLOGY.md)：近期共存及未来家庭 AI 云路线。
5. [RESOURCE_AND_PORT_PLAN.md](RESOURCE_AND_PORT_PLAN.md)：实测资源、运行 Provider、端口和预算。
6. [FLOWER_REPOSITORY_PLAN.md](FLOWER_REPOSITORY_PLAN.md)：仓库、发布目录、环境隔离。
7. [RISKS_AND_BLOCKERS.md](RISKS_AND_BLOCKERS.md)：风险、缺失输入和未验收项。
8. 本文：方案选择与确认清单。

flower 分支/commit：无，尚未建 Git 仓库；本轮未提交。aibot 整理后源码为 main / `cd5b34c446d5134c6346f290f7513380edba84a5`；生产 main / `32900cb76c1ad013c52b518bc62ee3ed6b46e93f` 加未提交内容，不能当可重建发布点。

部署地址：flower 未部署；`https://flower-api.bkeel.com` 仅建议。已有 `https://cs.bkeel.com` 配置对应 City Front。主要生产服务观察为 active/running，不代表本轮完成端到端业务测试。

测试执行 0、通过 0、失败 0；Mock 0、真实 Provider 请求 0、真实硬件测试 0。物理验收 BLOCKED_PHYSICAL，未接触实物。所运行的只读检查及关键输出已列于清单；不把本轮报告当 SPEC 第 18 章验收。

文档复核：使用 Node `fs` 只读检查八个规定文件、非空内容、Markdown 代码围栏配对及本地链接目标，结果 8 通过、0 失败、额外文件 0；这是文档检查，不是业务测试。`rg` 常见密钥/私钥/Bearer 模式扫描无命中。复查花盆五个基线文件哈希、四个 aibot brain 文件哈希、nox-brain unit 与 Nginx 两个配置哈希，均与本轮读取时一致；整理后 aibot 工作区仍干净。nox-brain/Nginx/City Front/DERP 的 PID、启动时间和 NRestarts 均未变化，仍 active/running。

生产回滚：本轮没有部署或生产修改，无需回滚。未来按独立 flower 发布清单回滚镜像/配置及必要的数据备份，详细边界见风险报告。此阶段结束后停止，不继续实现业务或安装软件。

## 7. 最终推荐与开发前确认事项

**最终推荐：B，同机独立业务、按需共享能力。现在先交付 flower 安全花盆 MVP，aibot 保持原样；以后抽取 ASR/TTS/LLM 与统一输入，再按实际多设备需求建设 Registry。**

下一阶段开发前需要负责人确认：

1. 资料基线：提供/恢复 GOAL 和 8 个项目技能，并明确“v2.2.1 包”与当前 v2.2 SPEC 的关系，确认本报告所列文档修改方向。
2. 范围与优先级：接受先花盆闭环、语音与统一平台后续分期；确认比赛日期，以及现有语音体验不可接受的延迟/中断边界。
3. 仓库与目录：确认 flower 独立仓库 URL/默认分支，开发检出 `/root/flower`、生产 `/srv/flower` 的建议；说明未来是否与 aibot 共用同一台 Pi。
4. 域名与 Provider：确认 `flower-api.bkeel.com` 或指定替代域名、微信配置；选择识别/搜索/天气/LLM 及独立项目凭据、预算和音频数据保留要求，不在聊天/报告中提交秘密值。
5. 上线前安排：确认可接受的 Docker 安装/新 Nginx 站点变更窗口、异地备份位置与共存容量验证方式。该确认是下一阶段的生产变更授权边界，本轮未执行任何相关变更。
