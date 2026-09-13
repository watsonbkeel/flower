# aibot 架构只读审计

审计日期：2026-09-13，Asia/Shanghai。本文记录源码与运行状态，不构成部署或功能验收。所有配置只按非敏感字段或是否存在记录；未调用模型、语音、摄像头、外设或业务 API。

## 1. 结论与证据口径

aibot 当前是一个围绕单台树莓派的语音助手：树莓派本地识别，云端接收文本、按需搜索、调用外部大模型，再向固定树莓派播放音频或请求可选外设。它没有现成的多业务 AI 能力网关、用户系统或 Device Registry，不能直接充当 flower 的控制后端。

- **代码已有**：在本次读取的文件中存在实现，不等于已配置或实物验证。
- **运行已见**：由宿主机 systemd、端口和文件核验确认，具体快照见 [CURRENT_SERVER_INVENTORY.md](CURRENT_SERVER_INVENTORY.md)。
- **未发现**：已检查范围内没有实现或运行证据，不能扩大成对所有远程系统的绝对否定。
- **未知**：需要设备、凭据、外部控制台或后续专项验证，本轮不补造结果。

## 2. 源码仓库与生产目录

| 对象 | 本次观察 | 影响 |
|---|---|---|
| `/root/aibot` | 包含项目、历史副本、备份及敏感配置资料，本身不是 Git 仓库 | 不把父目录当作部署版本 |
| `/root/aibot/asist-embodiment` | `main`；HEAD `cd5b34c446d5134c6346f290f7513380edba84a5`；提交时间 2026-09-03T14:13:21+08:00；工作区干净 | 整理后的代码基线 |
| `/opt/asist-embodiment` | `main`；HEAD `32900cb76c1ad013c52b518bc62ee3ed6b46e93f`；大量已修改、已删除、未跟踪文件 | 不能凭 HEAD 重建实际生产 |
| 当前脑端 | `nox-brain.service`，active/running，PID 1104，用户 asist，WorkingDirectory=`/opt/asist-embodiment/brain` | 当前服务实际从 `/opt` 运行 |
| 树莓派代码 | 本轮未登录树莓派 | 本机保存的 body 代码不代表远端运行版本 |

`sha256sum` 确认两处以下四个文件内容完全相同；本文对它们引用 `/opt` 的行号。

```text
brain/nox_voice_brain.py  a7b756d8ed5a8d34b9114001969a5fd64d9432b13431464e5b047a873464ad78
brain/nox_body_client.py b29dac5074ddced0a1269103f6c3ff5321090fd6f12c6c1a2d45e75849f9f06b
brain/web_search.py      123df019479e294e576a4788c11fc53c7499c0b818c791b2dc6dab32a0e101ad
brain/edge_tts_stream.py f1e5467993f9cce94df3bcd68b87ac9eb296cf9ff7484b3138187f4862f83eed
```

`diff -qr` 同时发现 body/shared、service 模板及 env example 不同。`/opt` 中还保留部分旧控制、适配器和记忆文件；这些文件存在不证明相应功能正在运行。不得把整理后仓库的 Bridge 鉴权、硬件范围或服务模板套用到未审计的树莓派。没有执行 git checkout/reset/clean/pull，也没有修改 safe.directory 的全局设置。

## 3. 当前数据流

```text
树莓派 USB 麦克风
  -> nox-voice：本地 Vosk、唤醒、打断
  -> 树莓派 Bridge POST /voice/input
  -> 云端 :8889 POST /voice/push
  -> 内存线程池：搜索路由 -> LLM -> 文本/外设响应解析
  -> 云端 Edge TTS / 可选 Piper -> FFmpeg 编码
  -> 树莓派 :9998 TCP 音频接收 -> 扬声器

云端 -> 固定树莓派 :8888 Bridge -> 本机 :9999 daemon -> 可选外设
```

云端框架是 Python 标准库 `HTTPServer`、`ThreadingMixIn` 和线程池，不是 FastAPI 或独立 Worker。主要证据：

- [nox_voice_brain.py:756](/opt/asist-embodiment/brain/nox_voice_brain.py:756)：脑端端口硬编码为 `8889`。
- [nox_voice_brain.py:758](/opt/asist-embodiment/brain/nox_voice_brain.py:758)：`ThreadPoolExecutor(max_workers=2)`。
- [nox_voice_brain.py:774](/opt/asist-embodiment/brain/nox_voice_brain.py:774)：`POST /voice/push` 收到 JSON 后先回复 200，再提交内存任务。
- [nox_voice_brain.py:801](/opt/asist-embodiment/brain/nox_voice_brain.py:801)：监听 `0.0.0.0`。
- [nox_voice_brain.py:23](/opt/asist-embodiment/brain/nox_voice_brain.py:23)：单个全局 `BODY_HOST`，固定下行 Bridge 地址。

这条链路没有持久化 jobs、任务认领、命令幂等或执行回执状态机。线程池的两个 worker 也不等于两个隔离的用户会话。

## 4. ASR、TTS、LLM 与 Agent

| 能力 | 代码已有 | 运行与复用边界 |
|---|---|---|
| ASR | 树莓派 `nox_voice_loop_v2.py` 加载 Vosk 并构造普通/唤醒识别器 | 云端入口接收文本；未发现云端通用 ASR 服务。树莓派当前进程及识别性能未实测 |
| TTS | brain 支持 Edge TTS，失败可尝试本地 Piper，最终向 Pi Bridge 回退 | 合成和固定设备播放耦合，未提供独立“文本换音频”的公共服务 API |
| LLM | OpenAI Chat Completions 兼容 HTTP 调用 | 可借鉴 Provider 接口；现有调用处于聊天流程内，不能把 `/voice/push` 当纯推理接口 |
| 搜索 | Tavily 及配置后的 Brave/Serper/SearXNG 备用路由 | 有文件计数、自然月配额；没有跨进程/跨业务配额服务 |
| Agent | 普通过程式路由、上下文拼接、LLM 输出解析、外设分发 | 没有独立的植物/喂鱼/机器人领域 Agent 注册中心 |
| 植物识别/天气 | 可选相机/本地视觉代码；时效问题可以触发网络搜索 | 未发现 flower 所需结构化植物候选识别 Provider、当地天气合约和养护证据链 |

源码位置：ASR [nox_voice_loop_v2.py:337](/root/aibot/asist-embodiment/body/nox_voice_loop_v2.py:337)；TTS [nox_voice_brain.py:232](/opt/asist-embodiment/brain/nox_voice_brain.py:232)、[回退逻辑:370](/opt/asist-embodiment/brain/nox_voice_brain.py:370)；LLM [调用层:382](/opt/asist-embodiment/brain/nox_voice_brain.py:382)；搜索路由 [处理函数:595](/opt/asist-embodiment/brain/nox_voice_brain.py:595)；硬件关键词路由 [处理函数:625](/opt/asist-embodiment/brain/nox_voice_brain.py:625)。运行时 Provider 配置和 CPU 结论见 [RESOURCE_AND_PORT_PLAN.md](RESOURCE_AND_PORT_PLAN.md)，不能仅凭默认值断言实际启用模型。

## 5. API、身份与设备连接

| 项目 | 已有/未有/未知 | 证据与含义 |
|---|---|---|
| 云端输入 API | 已有 `POST /voice/push` | brain `:774`；没有用户/设备注册、绑定或登录接口 |
| 云端输入鉴权 | 该处理器未实现鉴权、请求大小上限或接入限流 | 不能直接对公网或跨业务开放 |
| 整理后 Pi Bridge 鉴权 | 可选单一 `NOX_API_TOKEN`，未配置即放行 | [Bridge:175](/root/aibot/asist-embodiment/body/nox_brain_bridge.py:175)；远端实际配置未知 |
| 安全中间件 | `shared/security.py` 有 TokenAuth/RateLimiter 类，但没有接入上述主流程 | 类存在不等于生产入口已受保护 |
| Device Registry | 未发现 | 单一 `BODY_HOST` 不是注册中心；本机 `PeripheralManager` 只是驱动对象字典 |
| 用户管理 | 未发现 | 无账号、微信 openid、租户、所有权绑定或 token 生命周期 |
| 设备身份协议 | 当前 voice 消息没有业务 device_id/user_id | [Bridge:297](/root/aibot/asist-embodiment/body/nox_brain_bridge.py:297) |
| 网络连接 | HTTP 文本上行、HTTP 控制下行、TCP 音频下行 | 需要云端与 Pi 双向可达；不是 Pi 仅出站的公网设备网关 |
| 管理后台 | 未发现 Web 后台 | 提供 CLI、systemd 和日志；[xiaoai.sh:10](/root/aibot/asist-embodiment/scripts/xiaoai.sh:10) |

当前宿主机上 `8889` 没有 Nginx 代理。UFW 默认拒绝且未显式放行该端口；Tailscale/OpenVPN 流量另有允许规则。因此不能宣称已证实 `8889` 公网暴露，但应用无鉴权仍阻止它直接升级成共享平台入口。Tailnet ACL、云安全组和远端设备身份未在本轮验收。

整理后 Pi 默认端口来自 [nox_daemon.py:25](/root/aibot/asist-embodiment/body/nox_daemon.py:25)：内部命令 `127.0.0.1:9999`，音频 `0.0.0.0:9998`。音频接入 [nox_daemon.py:398](/root/aibot/asist-embodiment/body/nox_daemon.py:398) 未实现应用身份认证。不能在未来方案中直接把这两个端口映射公网。

## 6. 会话、记忆与数据库

脑端使用全局单一 `conversation`，默认保留最近 8 轮；最新请求序号、最近播报文本和音频流也是全局变量。证据为 [nox_voice_brain.py:59](/opt/asist-embodiment/brain/nox_voice_brain.py:59)、[:65](/opt/asist-embodiment/brain/nox_voice_brain.py:65)、[:92](/opt/asist-embodiment/brain/nox_voice_brain.py:92)、[:95](/opt/asist-embodiment/brain/nox_voice_brain.py:95)。多个设备直接推送会混用上下文，并可能互相取代回答或播放。

未发现脑端关系数据库、ORM、迁移或 Redis 队列。`brain/requirements.txt` 仅列 `edge-tts`；宿主机也未发现运行中的 PostgreSQL/MySQL/Redis，详见清单。具体文件存储：

- 整理后设备记忆 [assistant_memory.py:23](/root/aibot/asist-embodiment/body/assistant_memory.py:23)：Markdown + YAML frontmatter、JSON 生命周期数据。其 `store/search/recall` API 不代表脑端聊天已经接入长期记忆检索。
- Bridge 仅见 recent/stats 和启动/退出生命周期调用：[nox_brain_bridge.py:239](/root/aibot/asist-embodiment/body/nox_brain_bridge.py:239)、[:330](/root/aibot/asist-embodiment/body/nox_brain_bridge.py:330)。没有 flower 的用户确认、有效期、策略影响记录。
- 搜索用量 [web_search.py:47](/opt/asist-embodiment/brain/web_search.py:47)、[:69](/opt/asist-embodiment/brain/web_search.py:69)：进程内锁和 JSON 文件替换；不能让两个进程直接共享文件以协调配额。
- 可选人脸“数据库”实际为 JSON：[nox_face_recognition.py:283](/root/aibot/asist-embodiment/body/nox_face_recognition.py:283)，不等于账号或 Device Registry。
- `/opt/asist-embodiment/brain/:memory:.ses` 经 `file` 识别为 ASCII 文本；未读取其内容，不将文件名推断成 SQLite。

此次没有导入记忆模块：它在导入时可能创建目录，在 session_start/recall 时可能写文件。没有为了审计读取个人记忆内容。

## 7. 自动浇水的关键边界

当前脑端从 LLM 输出取 `peripherals[].action/params`，直接异步调用 Bridge，见 [nox_voice_brain.py:694](/opt/asist-embodiment/brain/nox_voice_brain.py:694)。整理后设备驱动注册器再调用对象公开方法，见 [peripherals.py:64](/root/aibot/asist-embodiment/body/peripherals.py:64)。这个通用外设路径没有 flower 要求的单一命令创建入口、可信时间、限额台账、标定、缺水和 `SAFE_HOLD` 门禁。

flower 不得以“给现有外设插件增加 pump”实现浇水，也不得让聊天 Agent 输出 GPIO/秒数/脉冲直接执行。以后语音入口只能形成经过身份验证和确认的业务意图，再进入 flower 云端决策和唯一 `create_command()`；Pi 始终经唯一 `can_dispense()` 执行。

另外，整理后 Bridge 的 `GET /photo`、`GET /look` 会实际触发拍照，见 [nox_brain_bridge.py:119](/root/aibot/asist-embodiment/body/nox_brain_bridge.py:119)、[:223](/root/aibot/asist-embodiment/body/nox_brain_bridge.py:223)。本轮没有调用这些接口；不能仅按 HTTP 方法判定现有 API 无副作用。

## 8. 部署与现有入口

- 当前 aibot 使用 systemd。仓库 unit 是模板，[nox-brain.service:8](/root/aibot/asist-embodiment/brain/services/nox-brain.service:8) 的参考用户名和目录会被 [install-brain.sh:29](/root/aibot/asist-embodiment/scripts/install-brain.sh:29) 替换；生产事实以已加载 unit 为准。
- 整理后仓库未发现 Dockerfile、Compose、前端/管理后台或数据库迁移；宿主机未发现 Docker 运行时。本轮不安装，也不迁移 aibot。
- 宿主机 Nginx 的 `cs.bkeel.com -> 127.0.0.1:7460` 属于独立 City Front 应用，不是 aibot 后台。未发现 aibot 公网业务域名；未发现 Caddy。
- flower 后续采用独立 Compose，宿主现有 Nginx 继续独占 80/443，flower 私有 proxy 只映射 `127.0.0.1:18080`。这是建议，未执行，详见 [TARGET_DEPLOYMENT_TOPOLOGY.md](TARGET_DEPLOYMENT_TOPOLOGY.md)。

## 9. 本次证据与未验收项

实际执行的只读命令包括：

```text
rg --files --hidden；rg -n <能力/鉴权/数据库/路由关键词> <源码目录>
nl -ba <源码文件> | sed -n <相关行>
git -c safe.directory=<明确仓库> status --short --branch
git -c safe.directory=<明确仓库> status --porcelain=v1
git -c safe.directory=<明确仓库> log -1 --format=... --date=iso-strict
git -c safe.directory=/opt/asist-embodiment diff --name-status --no-renames
diff -qr <整理后目录> <部署目录>
sha256sum <四对 brain 文件>
file /opt/asist-embodiment/brain/:memory:.ses
```

`diff` 返回 1 表示发现差异；最初 systemctl 沙箱拒绝由主代理在宿主机重新核实。未将权限拒绝当作组件不存在。测试执行 0、通过 0、失败 0；Mock 0、真实 Provider 请求 0、真实硬件测试 0。未验证树莓派现有版本、端到端语音、峰值资源、相机或泵，物理验收为 `BLOCKED_PHYSICAL`。没有对 flower 第 18 章验收或 DoD 作通过声明。

当前最重要的后续前提是：先确认 flower 文档包完整性；将 aibot 的真实部署版本漂移列为独立运维风险；保持业务隔离，并在经过批准的后续阶段逐步抽取共享能力。
