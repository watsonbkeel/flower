# aibot 与 flower 复用矩阵

审计日期：2026-09-13。本文区分“复用已有服务”“复用代码/接口经验”“未来抽取”；所有未来动作均未执行。基线证据见 [AIBOT_ARCHITECTURE_AUDIT.md](AIBOT_ARCHITECTURE_AUDIT.md) 和 [CURRENT_SERVER_INVENTORY.md](CURRENT_SERVER_INVENTORY.md)。

## 1. 推荐范围

推荐 B：同一服务器承载两个独立业务，flower 保持自己的 API、Worker、数据库、命令与安全边界。aibot 继续按当前 systemd 运行。现阶段最有价值的复用是外部 Provider 接入模式、运维入口和语音经验；没有证据支持立即复用一个现成的“AI 设备云平台”。

“可复用”不意味着复制生产密钥、修改现有服务或共享运行目录。flower 最初直接配置自己的 Provider；若选同一家上游，优先分项目 key、配额和计费标识。后来出现第二个明确调用方时，再将无硬件副作用的能力抽成独立服务。

## 2. 组件矩阵

| 组件 | 当前证据 | 现在的决定 | 后续复用条件 |
|---|---|---|---|
| 服务器计算/磁盘 | 2 vCPU、约 7.5 GiB RAM；当前闲时资源有余量 | 可同机；设置 flower 资源预算并保留峰值余量 | 对话与 Worker 并发性能实测通过；必要时把语音推理移出 |
| Nginx/TLS 运维 | Nginx 已服务 City Front 的 `cs.bkeel.com` | 复用宿主 Nginx 作为唯一公网入口；新增独立站点须后续审批 | flower 域名、DNS、证书、上传限制和回滚准备完成 |
| Caddy | 未发现已安装或运行 | 不为复用而新增第二个宿主 80/443 入口 | flower Compose 如保留 proxy，可内部运行；不得抢占现有入口 |
| Docker | 当前未安装，aibot 用 systemd | flower 单独 Compose；不迁移 aibot | 后续安装前审查 Docker/UFW/VPN 转发影响 |
| 云端 LLM Provider | brain 有 Chat Completions 兼容调用，位于聊天函数内部 | 复用接口经验；flower 独立适配、独立配置与预算 | 抽成独立 API 后加入服务鉴权、超时、审计、限流与调用方计费 |
| `POST /voice/push` | 单 Pi、全局会话、先返回 200、后异步处理，带音频/外设副作用 | 不复用为 flower 入口或通用 LLM API | 未来以新网关/适配器接入；既有聊天服务保持原业务边界 |
| ASR | Vosk 代码位于 Pi；未发现云端 ASR API | 借鉴 Pi 音频采集/唤醒；flower MVP 不增加语音开发 | 后续语音阶段独立 ASR 合约和并发资源预算；先确认云端/边缘分工 |
| TTS | Edge/Piper 与固定 Pi 播放耦合 | 借鉴音色、分段、Opus 和回退经验；不直接调用旧聊天入口合成 | 新 TTS API 返回音频或媒体流，不接收任意设备地址、不执行硬件动作 |
| FFmpeg/音频协议 | brain 编码，Pi 解码播放 | 可借鉴格式与兼容测试；不共享单个播放器状态 | 媒体流按会话/设备隔离，使用受鉴权的出站连接或安全下载 |
| 网络搜索 | Tavily/Brave/Serper/SearXNG 适配、自然月计数 | 复用 Provider 思路和失败策略，flower 独立检索合约与配额 | 搜索来源、时间、缓存、错误类型、每业务额度进入统一服务 |
| 搜索 JSON 用量文件 | 进程内锁 + 文件替换 | 禁止两个业务共享文件 | 将配额持久化到支持原子更新的中心服务；不要靠同文件协调 |
| 天气 | 聊天可通过搜索获取时效信息 | 不当作 flower 结构化天气 Provider | flower 实现天气字段、坐标/城市、有效期、失败降级和来源记录 |
| 植物识别 | 有通用相机/可选视觉代码，未见 flower 识别合约 | 不复用为已经验收的植物识别服务 | 独立模型 Provider、候选/置信度、用户确认、来源标识 |
| Agent 路由 | 单过程聊天/搜索/硬件关键词逻辑 | 不抽象成统一多场景 Agent 框架 | 植物业务完成后，再按明确业务合约扩展场景路由 |
| 用户登录/微信身份 | aibot 未发现账号体系或微信登录 | flower 独立实现用户认证与绑定 | 将身份模型映射到未来家庭/设备体系，之后再评估统一身份服务 |
| Device Registry | 单个 `BODY_HOST`，无设备注册/吊销/所有权服务 | 不建共享 Registry 服务；flower 自有设备表 | 先统一 ID/能力字段语义，未来多设备需求真实出现后再迁移 |
| Pi 外设注册器 | `PeripheralManager` 是本机驱动字典 | 仅借鉴故障隔离；不得把它当云端设备注册中心 | 统一接入可以报告 capabilities，驱动与安全执行仍留在领域 agent |
| 对话上下文 | 全局 8 轮内存历史、全局最新请求序号 | 不共享；不同业务/用户/设备必须隔离 | 统一入口用显式 conversation_id 和授权主体进行路由 |
| 长期记忆 | 设备侧 Markdown/YAML/JSON，脑端未见完整确认闭环 | 不共享文件、不直接影响 flower 策略 | flower 独立存确认状态、适用范围、有效期和影响审计；未来仅通过授权 API 使用 |
| 数据库 | aibot 无已发现关系 DB，flower 需要 PostgreSQL | 只新建 flower 自己的一套 PostgreSQL 容器和数据卷 | 未来另一个业务需 PG 时再评估独立实例或隔离 database；不凭空创建第二个实例 |
| jobs/Worker | aibot 是内存线程池 | 不复用；flower 独立 PostgreSQL jobs 和 Worker | 通用推理任务也不能替代领域可靠命令/审计队列 |
| 命令通道 | aibot 直接 HTTP 外设动作，没有 flower 安全状态机 | 禁止共享控制路径 | 任何语音/小程序入口均经 flower `create_command()`，Pi 经 `can_dispense()` |
| Pi 本地安全执行 | aibot 没有完整浇水门禁 | flower pi-agent 独立实现唯一安全门与限额台账 | 上层设备网关可以统一，泵的最终决策权与紧急停止留在本地 |
| Tailscale/OpenVPN | 当前服务器正在运行，Pi 通信依赖双向路径的设计 | 复用已有运维经验；本轮不改配置、不扩大信任范围 | 未来设备主要出站 HTTPS/WSS；VPN 保留维护用途，审查 ACL |
| 日志和运行账户 | aibot systemd 用户 asist；生产目录存在漂移 | 运维可统一观测，账户、日志权限、配置与数据仍分开 | 统一 request_id/脱敏规则与监控视图，避免收集不必要语音/聊天内容 |

## 3. 不能误判的现有能力

1. [nox_voice_brain.py:774](/opt/asist-embodiment/brain/nox_voice_brain.py:774) 的 `/voice/push` 会进入对话、搜索、音频和外设流程。它不是纯 ASR、TTS 或 LLM API，也没有已完成的跨业务鉴权。
2. [nox_voice_brain.py:65](/opt/asist-embodiment/brain/nox_voice_brain.py:65)、[:92](/opt/asist-embodiment/brain/nox_voice_brain.py:92) 的全局会话，以及 [:23](/opt/asist-embodiment/brain/nox_voice_brain.py:23) 的固定 Pi 地址，决定了不能直接将第二类设备并入同一实例。
3. [peripherals.py:20](/root/aibot/asist-embodiment/body/peripherals.py:20) 的本机驱动注册不承担用户设备所有权、认证、密钥轮换或设备生命周期。
4. [web_search.py:47](/opt/asist-embodiment/brain/web_search.py:47)、[:69](/opt/asist-embodiment/brain/web_search.py:69) 的计数锁只在单进程内有效。即便使用两个独立文件，同一上游账号的总额度仍可能合并计算，需要上游项目额度或未来中心预算控制。
5. [nox_voice_brain.py:694](/opt/asist-embodiment/brain/nox_voice_brain.py:694) 允许模型转发通用外设动作。语音触发补水必须跨入 flower 的业务确认与安全命令链，不能复用这条路径执行泵。

## 4. 未来共享能力的最小合约方向

下列字段是未来讨论方向，不要求在当前 flower MVP 同时实现，也不构成对 v2.2 已有 JSON 合约的直接修改。

| 能力 | 输入/输出方向 | 必须保持的边界 |
|---|---|---|
| ASR | 受控音频格式、语言、request_id -> 文本、置信信息、耗时、Provider 标识 | 限时长/大小；不得输出硬件动作 |
| TTS | 文本、音色、格式 -> 音频或媒体流、过期时间、Provider 标识 | 返回媒体，不直接连接任意 Pi；不接受通用 shell/网络目标 |
| LLM | 明确任务类型、上下文、输出 Schema -> 验证后的结果与用量 | 领域代码决定哪些字段允许；不能输出可执行浇水参数 |
| 搜索/天气/识别 | 明确查询/城市/图片引用 -> 结构化结果、来源、时间、有效期 | flower 自己负责证据使用、确认和策略决策 |

所有共享接口应从认证后的服务身份确定调用业务与权限，不能只相信请求体中的 device_id/user_id。控制请求的身份、设备所有权、确认状态和授权始终由业务层验证。Provider key 留在云端，按调用方设并发/额度/超时；输入输出带可追踪 request_id，并遵守 flower 的 `source_type` 区分。

当需要统一家庭 AI 设备云时，推荐先统一接入和身份语义，再统一无副作用的 AI 能力，最后按真实多设备需求抽取 Registry。长期目标是 Pi 采集和执行、云端理解与领域路由；本地可信时间、标定、缺水、限额和 `SAFE_HOLD` 等门禁不能随平台化而移走。

## 5. 本轮状态

本文件只提出复用判断：没有修改 aibot、数据库、Docker、systemd、Nginx/Caddy 或防火墙，没有部署 flower。程序测试执行 0、通过 0、失败 0；Mock 0、真实 Provider 请求 0、硬件测试 0。物理项未验收，保持 `BLOCKED_PHYSICAL`。

下一阶段先确认资料包完整性、flower 部署域名与资源预算、独立 Provider 凭据和设备范围；具体确认清单以 [RECOMMENDATION.md](RECOMMENDATION.md) 为准。
