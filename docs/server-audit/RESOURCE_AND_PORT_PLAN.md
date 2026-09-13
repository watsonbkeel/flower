# 资源与端口规划

2026-09-13 只读实测与建议。下列预算不是性能承诺，建议端口没有绑定或开放。原始环境摘要见 [CURRENT_SERVER_INVENTORY.md](CURRENT_SERVER_INVENTORY.md)。

## 1. 当前监听端口

| 端口 | 地址/协议 | 所属 | 处理原则 |
|---|---|---|---|
| 22 | 全 IPv4/IPv6 TCP | SSH | 保留 |
| 80/443 | 全 IPv4/IPv6 TCP | 现有 Nginx | 保留唯一公网 Web 入口 |
| 7460 | 127.0.0.1 TCP | city-front Node | 已用，不分给 flower |
| 8889 | 0.0.0.0 TCP | nox-brain | 已用，不作为共享 AI API |
| 8443 | 通配 TCP | DERP | 已用，不能当备用 HTTPS 端口 |
| 3478 | 通配 UDP | DERP/STUN | 保留 |
| 9988 | 0.0.0.0 UDP | OpenVPN | 保留；TCP 9988 有防火墙放行但未观察到监听 |
| 41641 | 通配 IPv4/IPv6 UDP | Tailscale | 保留 |
| 61516 / 43351 | Tailnet IPv4 / IPv6 TCP | tailscaled 动态监听 | 不视为固定业务端口，保留 |
| 323 | 127.0.0.1 / ::1 UDP | chrony | 保留 |
| 68 / 546 | eth0 IPv4 / IPv6 UDP | DHCP 客户端 | 系统网络，不分配 |

宿主机未观察到 5432/6379/3306/11434/8000/18080/18081/18082 监听。其中 **8000 已被 UFW 对公网放行**，不能因为空闲就将开发服务绑定 `0.0.0.0:8000`。

代码中的 Pi Bridge 8888、Pi 控制 9999、Pi 音频 9998 位于设备侧；不是本服务器空闲或运行中的服务证据。云端程序配置名 `SERVER_AUDIO_PORT=9998` 指向 Pi 目标端口。

## 2. flower 建议分配

| 环境/服务 | 宿主机绑定 | 容器内部 | 公网 |
|---|---|---|---|
| production proxy | 127.0.0.1:18080 | proxy:8080 | 仅经 Nginx 443 |
| staging proxy | 127.0.0.1:18081 | proxy:8080 | 默认关闭，SSH 隧道或经审阅的专用域名 |
| development proxy | 127.0.0.1:18082，仅需同机开发时 | proxy:8080 | 关闭 |
| FastAPI | 不发布 | api:8000 | 关闭 |
| PostgreSQL | 不发布 | postgres:5432 | 关闭 |
| Worker | 无监听 | 从 jobs 表领取任务 | 关闭 |
| 未来共享 AI | 暂不分配/启动 | 后续独立服务决定 | 默认仅内部认证访问 |

不同 project 内部都用 8000/5432 不冲突；冲突发生在宿主机 IP:port 发布。同机部署前再次检查 `ss -lntup`，由发布记录固定端口，不在故障时自动寻找并开放随机公网端口。

Compose 网络应有项目独立前缀。可在下一阶段评估 172.30.40.0/24、172.30.41.0/24 等候选网段，但必须核对 VPC、Tailnet 路由、家庭局域网及其他 Docker 网络后再定；当前快照未见这些路由，不等于将来不会重叠。不要占用 10.5.0.0/22、10.8.0.0/24、100.64.0.0/10、已公布的 Tailscale 子网或 IPv6 ULA 范围。

## 3. ASR/TTS/LLM 的 CPU 判断

### 运行配置核对

14:24 左右对白名单读取 `/proc/1104/environ`，结合 2026-09-03 修改、早于本次进程启动的实际源码确认：

| 配置 | 运行环境与实际代码的结果 |
|---|---|
| LLM 上游 | `https://api.deepseek.com/v1/chat/completions` |
| LLM 模型配置名 | `deepseek-v4-flash-vision-exp`；只确认配置字符串，不据名称宣称视觉/植物识别能力已验收 |
| LLM 凭据 | OPENAI_API_KEY 已设置，未输出值 |
| TTS | SERVER_TTS_ENABLED/PROVIDER 未显式覆盖，代码默认 enabled=true、provider=edge |
| Edge 音色/编码 | 未覆盖，代码默认 zh-CN-XiaoxiaoNeural / en-HK-YanNeural，rate=+8%，Opus=64k |
| 本地回退 | 未覆盖，默认使用 `/opt/piper-bench-venv/bin/piper` 与 `zh_CN-huayan-medium.onnx`，两者实际存在；模型约 63.2 MB |
| 依赖文件 | dist-info 显示 edge-tts 7.2.8、piper-tts 1.7.0、onnxruntime 1.29.0；ffmpeg 可执行文件存在。未运行推理 |
| 线程环境 | OMP_NUM_THREADS/OPENBLAS_NUM_THREADS/MKL_NUM_THREADS 均未显式设置；不据此断言底层实际线程数 |
| 搜索 | Tavily key 已设置，月度应用限额 960，超时 10 秒；Brave/Serper key 和 SearXNG URL 未设置 |
| Pi 目标 | BODY_HOST=100.73.202.93，为 Tailnet 地址；NOX_API_TOKEN 在脑端环境未设置，远端 Bridge 的实际配置仍未知 |

只读聚合 `journalctl -u nox-brain.service --since 2026-09-08 -n 1000 --no-pager -o json`：得到 8 条日志，时间截止于 2026-09-08 22:13:09 CST，Push received、Response、TTS 计数均为 0。没有输出聊天内容。服务活跃但这段日志没有近期对话证据，因此本次资源采样是闲时基线，不能声称覆盖用户正常对话，更不能据此判断现有语音已经损坏。

### 执行位置与风险

| 能力 | 当前实现证据 | 同机风险 |
|---|---|---|
| ASR | aibot body 代码在 Pi 用 Vosk 识别，然后上报文字；服务器无 ASR 模型进程 | 当前不会因云端 ASR 推理与 flower 争 CPU；Pi 实际硬件未在本轮检查 |
| LLM | 脑端 HTTP 调用外部兼容接口，无本地 LLM 推理进程 | 本机主要是网络/JSON 处理；外部并发、账单和失败更关键 |
| Edge TTS | 远程生成音频，本机子进程处理音频与 ffmpeg/Opus 编码 | 会用 CPU，但不是在本机运行 Edge 声学模型；不能说“完全无 CPU 成本” |
| Piper 回退 | `/opt/piper-bench-venv` 和 `/opt/piper-bench-models`，本机 CPU 推理及编码 | 对仅 2 vCPU 主机有真实突发竞争风险，尤其远程 TTS 故障时 |
| 未来云 ASR/本地 LLM | 当前未部署 | 不默认加到该 2 vCPU 主机；先选外部服务或独立推理主机 |

`/opt/asist-embodiment/docs/voice-optimization-learning.md:186` 保存历史 Piper 基准：约 308 汉字生成约 56 秒音频，首音 0.896-1.019 秒，完整合成 6.882-7.100 秒。它是已有文档记录，本轮没有复测，也没有原始 CPU/内存峰值数据，不能推导为并发容量保证。

本次 nox-brain 约 25 MiB RSS，五个 vmstat 间隔 CPU idle 为 80%-98%。这证明采样时空闲，不证明实际对话或 Piper 回退时无争抢。代码虽有两条语音工作线程、全局单音频流，但没有可靠多应用公平队列，也没有 systemd CPU/内存硬限制；不将全局播放互斥当作资源隔离。

结论：**同机部署一个依赖外部 Provider 的 flower MVP 合理；同机同时扩建云 ASR、本地 LLM 或多设备 Piper 服务缺少容量证据。**

## 4. 初始资源预算，待预发布验证

| flower 服务 | CPU 配额建议 | 内存上限建议 | 初始并发 |
|---|---:|---:|---|
| API | 0.25 CPU | 384 MiB | 1 进程，短请求异步 I/O |
| Worker | 0.40 CPU | 768 MiB | 1 实例，JOB_MAX_CONCURRENCY=1 |
| PostgreSQL | 0.30 CPU | 512 MiB | 控制连接池，总连接初始不超过 30 |
| 内部 proxy | 0.05 CPU | 64 MiB | 常规轻量转发 |
| 合计 | 1.00 CPU | 1,728 MiB | 不含 Docker daemon、备份/构建临时资源 |

这些值是为了限制新业务的初始影响，不是资源预留或时延保证。aibot 当前没有限额，仍可能争用全部 CPU；要获得硬性服务质量隔离，需要独立主机或经过单独评估的现有服务资源控制。

预计容器正常工作集小于上限，但要通过真实镜像及图片处理验证。数据库初始可评估 shared_buffers=128 MiB、保守 work_mem 与连接池，避免“连接数 × work_mem × 并发算子”扩大内存。配置必须进入运行清单，不在报告中把估计值当已生效配置。

主机预算留出至少 2 GiB 可用内存和约一半 CPU 调度余量给 aibot、City Front、VPN、系统及突发。没有 swap，容器超额或主机内存耗尽会被 OOM；不在本轮加 swap。构建镜像、依赖安装、数据库恢复优先放在开发机/CI，避免和真实语音同时运行。

## 5. 存储预算

当前根盘剩余约 71 GiB。建议 flower 首阶段设约 25 GiB 的运维预算，例如数据库 5 GiB、上传 5 GiB、镜像 5 GiB、可轮换本地备份 10 GiB；这是管理阈值，不是已经建立的磁盘配额。

图片按需拍摄，保留期和容量联动；压缩、缩略图及清理在 Worker 处理。日志采用有界轮转，例如每容器 10 MiB × 3。备份必须另有异地副本，本机备份不能抵抗整机故障。

`/tmp` 是 tmpfs，不适合长期保存图片、模型或数据库备份。数据库数据与 uploads 放在 `/srv/flower/shared` 下的持久盘路径。可设置可用磁盘低于 20 GiB 或 20% 预警、低于 10 GiB 禁止新大文件与备份任务；关键存储失败应告警并遵守安全保持策略。

## 6. 下一阶段容量门

本轮没有触发真实语音、合成音频或压力流量。未来预发布应先获得实际使用高峰的被动观测，再在授权窗口验证：正常对话、Edge 失败回退、图片上传/识别、命令领取、Worker 重试、备份等重叠时的 CPU、RSS、I/O 和尾延迟。

可先采用以下暂定退出标准，由实测修订：

- 真实对话 p95 首音/完整响应相对单独运行基线劣化不超过 20%，不能靠空闲快照验收。
- flower `/health`、`/ready`、telemetry、claim 在不含外部 Provider 的处理时段，p95 目标小于 500 ms；无数据库锁死、任务丢失或重复命令执行。
- CPU 总使用持续 5 分钟超过 70%、可用内存低于 2 GiB、持续排队或发生 OOM，进入扩容/调整调查；这些是预警门，非充分性能证明。
- 若 Piper 回退使实时体验或 flower 控制链路不达标，优先迁出推理/选择外部 TTS；若只是花盆 Worker 突发，先降低其并发和预算内耗时工作。
- 多设备语音、持续云 ASR、本地大模型上线前重新做容量评估；必要时升级至至少 4 vCPU 或拆出推理主机，规格取决于实际模型和并发。

Docker 安装和新增路由验证必须包括 UFW/NAT、Tailscale、OpenVPN、City Front WebSocket 和现有 aibot 连接。本轮只记录这一发布前条件，没有修改任何规则或服务。
