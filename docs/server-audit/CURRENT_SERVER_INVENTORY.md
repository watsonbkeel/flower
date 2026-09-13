# 当前服务器只读清单

审计日期：2026-09-13，时区 Asia/Shanghai。主要运行快照为 14:08-14:12，AI 配置/日志补核约在 14:24；证据是本次读取的真实宿主机状态，不是压力测试或部署验收。后续方案均未执行。

## 1. 审计范围与证据限制

- 已完整阅读可见的 `AGENTS.md`、`SPEC_CURRENT.md` 及审计前 `docs/` 下全部 17 个文件，包括架构决定、合约、部署/硬件/测试/离线演示手册、14 项实施计划和五份模板。
- `GOAL.md`、`.agents/skills/` 在解除沙箱后仍不存在。`FILE_LIST.txt` 声明了 8 个项目技能，但实际文件缺失。对 `/root`、`/opt` 深度 5 的名称检索没有找到项目技能或 GOAL；没有伪称已阅读缺失内容。
- 用户称资料包 v2.2.1；实际 `SPEC_CURRENT.md` 和其余基线文件均写 v2.2。可能是资料包修订号与规格号不同，也可能解压不完整，尚不能确定。
- `/root/flower` 尚非 Git 仓库，没有分支/commit，没有 backend、pi-agent、miniapp 实现。本次不初始化仓库、不创建开发分支、不修改 `PROJECT_STATUS.md`；按本轮明确范围，只新增本目录八份文档。
- 初始沙箱只暴露隔离 PID，systemctl/netlink 被拒绝，`.agents/.git` 被挂载遮蔽。切换到宿主机可见环境后重新检查；初始失败不作为服务不存在的证据。
- 不读取或公布 API key、设备 token、微信秘密、证书私钥、用户聊天内容。没有主动调用 ASR/TTS/LLM、设备 API 或业务入口，没有数据库查询、安装、重启、容器或防火墙变更。

## 2. 主机资源

| 项目 | 本次观测 | 证据 |
|---|---|---|
| 操作系统 | Debian GNU/Linux 13，DEBIAN_VERSION_FULL=13.6 | `/etc/os-release` |
| 内核/架构 | 6.12.95+deb13-amd64，x86_64，KVM | `uname -a`、`lscpu` |
| CPU | 2 vCPU，Intel Xeon Platinum 8255C @ 2.50GHz | `lscpu` |
| 内存 | 总计 7.5 GiB，已用约 855-870 MiB，可用约 6.7 GiB | 两次 `free -h` |
| Swap | 无 | `free -h` |
| 系统盘 | 80 GiB 虚拟盘；根分区 ext4 约 79 GiB，已用 7.6 GiB，余约 71 GiB | `lsblk`、`df -hT / /tmp` |
| 临时盘 | `/tmp` 是约 3.8 GiB 的 tmpfs，使用会占内存 | `df -hT / /tmp` |
| 负载 | 14:10 的 1/5/15 分钟 load 为 0.15/0.15/0.05 | `uptime` |
| 时间 | Asia/Shanghai，NTP=yes，NTPSynchronized=yes | `timedatectl show` |
| GPU | 未发现 GPU 推理进程或 nvidia-smi；不把 NVIDIA 名称的 unit 文件当作 GPU 证据 | 进程/可执行文件清单 |

`vmstat 2 6` 的首行是累计值，另五个 2 秒间隔样本：CPU idle 为 93/80/98/92/88%，iowait 为 0/0/0/0/1%，steal 为 0。采样包含审计活动，并未覆盖真实对话高峰。

主要进程 RSS 快照：nox-brain 约 25 MiB、city-front Node 约 77 MiB、tailscaled 约 115 MiB、云安全 YDService 约 82 MiB、journald 约 81 MiB。审计工具自身约 239 MiB，不能算成业务恒定用量。`ps %CPU` 是进程生命周期平均，不能代表 TTS 峰值。

## 3. 运行服务

| 服务 | 状态 / PID | 目录或职责 | 关键说明 |
|---|---|---|---|
| nox-brain.service | active/running，1104 | `/opt/asist-embodiment/brain`，用户 asist | Python 语音脑端；2026-09-08 22:13:09 启动，NRestarts=0 |
| nginx.service | active/running，1146；workers 1147/1148 | `/etc/nginx/` | 当前唯一 80/443 入口，服务 city-front |
| city-front.service | active/running，1092 | `/opt/city-front`，用户 chenyifan | Node Web FPS 应用，127.0.0.1:7460；不是 aibot 后台 |
| derper.service | active/running，1102 | `/opt/derper` | DERP relay，TCP 8443、UDP 3478，配置 hostname=derp.lan |
| tailscaled.service | active/running，1059 | Tailscale | 现有设备网络和运维路径，不应被新 Docker 网段破坏 |
| openvpn-server@server.service | active/running，1105 | OpenVPN | UDP 9988、tun0 |
| ssh.service | active/running，1081 | SSH | TCP 22 |
| chrony.service | active/running，1107 | 时间同步 | 本地 UDP 323 |
| 云代理 | tat_agent、barad_agent、YDService 等 | 云管理/监控/安全 | 需要计入资源基线 |

共观察到 19 个 active/running systemd service；其他为 acpid、cron、dbus、日志、登录、udev、终端与 user manager 等。certbot、apt、logrotate 等定时器存在。本次没有运行其中任何维护任务。

nox-brain 的 systemd 快照：MemoryCurrent=24,793,088 bytes，CPUUsageNSec=30,339,096,000，CPUQuotaPerSecUSec=infinity，MemoryMax=infinity，TasksMax=9161。CPU 累计约 30.3 秒是当前 service 周期计量，不能证明高峰有剩余容量。

补核 PID 1104 的白名单环境字段：配置 DeepSeek HTTPS 上游、模型名 `deepseek-v4-flash-vision-exp`，默认启用 Edge TTS，Tavily 凭据已配置。API key 仅报告已设置，未输出值。详细执行位置和依赖见 [RESOURCE_AND_PORT_PLAN.md](RESOURCE_AND_PORT_PLAN.md)。从 9 月 8 日起的该服务可见日志仅 8 条，未记录新 Push/Response/TTS，因而不将当前空闲状态当作正常语音高峰证据。

## 4. Docker 与数据库

- `docker ps ...` 返回 `docker: command not found`。
- 软件包清单、常见可执行路径、systemd service、进程、Unix socket、`/var/lib` 交叉检查：未发现已安装并运行的 Docker/containerd/Podman，也未发现容器运行证据。当前容器清单为“未发现容器运行时”，不是一次成功的 `docker ps` 返回零容器。
- 未发现运行中的 PostgreSQL/MySQL/MariaDB/Redis、对应 TCP/Unix socket、已安装数据库服务包或 aibot 数据库连接配置。
- aibot 使用内存、设备侧文件和搜索用量 JSON；`brain/:memory:.ses` 是文本文件，不能凭名称推断 SQLite。
- 不需要迁移“已有 aibot PostgreSQL”，因为没有证据表明它存在。远程数据库或未启用的自定义安装不能由上述检查绝对排除。

## 5. 网络、域名与入口

| 项目 | 已确认事实 |
|---|---|
| 主网卡 | eth0=10.5.0.13/22；默认网关 10.5.0.1 |
| OpenVPN | tun0=10.8.0.1/24 |
| Tailscale | tailscale0=100.109.178.124/32，另有 ULA IPv6 |
| 路由 | table 52 存在 Tailnet /32 及 192.0.2.0/24、198.51.100.0/24 路由，主表还有 VPC/VPN 路由 |
| 已配置公网候选 IP | Nginx/City Front 配置写 43.161.224.25；`getent ahostsv4 cs.bkeel.com` 也返回此地址。未从云控制台验证 NAT/安全组 |
| 已有公网域名 | cs.bkeel.com，为 City Front，不是 aibot API |
| Nginx 配置 | `/etc/nginx/sites-enabled/city-front` 链接到 `sites-available/city-front`；`conf.d` 无站点 |
| 路径 | 443 的 `/` 和 WebSocket `/rooms` 均转 127.0.0.1:7460；80 提供 ACME、指定下载路径和 HTTPS 跳转 |
| 上传限制 | 当前站点 `client_max_body_size 1m`，不能直接满足 flower 的 10 MiB 图片上限 |
| TLS | 当前证书 SAN 仅 cs.bkeel.com，有效期 2026-08-05 至 2026-11-03；不能给 flower 子域名直接复用 |
| Caddy | 未发现安装包、配置或服务 |

完整监听端口与建议端口见 [RESOURCE_AND_PORT_PLAN.md](RESOURCE_AND_PORT_PLAN.md)。没有主动访问生产网页或外部模型，因此 TLS 证书文件存在不等于完整公网连通性已验收。

## 6. 防火墙边界

`ufw status verbose`：active，入站 deny、出站 allow、转发 deny。显式放行 TCP 22/80/443/9988/8000 和 UDP 9988，IPv4/IPv6 均有规则。

`nft list ruleset` 显示真实路径还有 Tailscale、OpenVPN、云安全链。Tailscale 接口流量被允许，UDP 41641 被允许，OpenVPN 10.8.0.0/24 输入有放行。不能只看 UFW 摘要判断 VPN 访问。

nox-brain 监听 `0.0.0.0:8889`，但本机非 VPN 入站规则未显式放行该端口，默认拒绝；不能宣称已证实公网可访问。经 Tailnet/VPN 可达范围和上层 ACL 尚未验收，其应用无鉴权仍是跨设备复用风险。云安全组、Tailnet ACL、路由另一端和外部实测均未知。

## 7. 版本与可复现标识

| 对象 | 标识 |
|---|---|
| flower | 无 Git 分支/commit，本次仅文档输出 |
| aibot 整理后源码 | `/root/aibot/asist-embodiment`，main，`cd5b34c446d5134c6346f290f7513380edba84a5`，审计时干净 |
| aibot 实际部署 | `/opt/asist-embodiment`，main，HEAD `32900cb76c1ad013c52b518bc62ee3ed6b46e93f`，大量未提交修改/删除/未跟踪文件；HEAD 不足以重建生产 |
| 关键 brain 文件 | 两处的 nox_voice_brain.py、nox_body_client.py、web_search.py、edge_tts_stream.py 内容哈希相同；其他目录不能推定相同 |

本次读取时的 SHA-256：

```text
SPEC_CURRENT.md
bf1b646fb0c5c636c49e59d47d117a0d32db4989e426e0745d7627e4e7fafd99
docs/PROJECT_STATUS.md
ca7a55df0f31b898c294934dd402b6111cd827f2dbf760e7e104a4325cbbf284
/opt/asist-embodiment/brain/nox_voice_brain.py
a7b756d8ed5a8d34b9114001969a5fd64d9432b13431464e5b047a873464ad78
/etc/systemd/system/nox-brain.service
864966d8933b72001ae52b5ad8e92bcdcbedd6aa4fa6b864e33dca8ec65e006a
/etc/nginx/nginx.conf
c66fbe205bf46b5d125502e35605938ed37feef6e2b24325b1c088665caaf477
/etc/nginx/sites-available/city-front
d6b86ffee7aaa12ae8571f8ad8d1f0391d4dc7d33cd01fba3773533963d73e91
```

## 8. 执行命令与未执行项

代表性实际只读命令：

```text
cat AGENTS.md；分段 sed 阅读 SPEC_CURRENT.md；cat docs 下全部文档
rg --files --hidden；find /root /opt -maxdepth 5 ...；sha256sum ...
git --no-optional-locks -c safe.directory=<目标仓库> -C <目标仓库> status/log/diff ...
cat /etc/os-release；uname -a；lscpu；free -h；df -hT；lsblk；uptime
ps -eo pid,ppid,user,comm,%cpu,%mem,rss,etime --sort=-%cpu
vmstat 2 6
systemctl list-units --type=service --state=running --no-pager
systemctl list-unit-files --type=service --no-pager
systemctl show nox-brain.service nginx.service city-front.service derper.service ...
systemctl list-timers --all --no-pager
ss -lntup；ss -lxnp；ip -brief address；ip route show table all
ufw status verbose；nft list ruleset
dpkg-query -W ...；docker ps --no-trunc --format ...
cat /etc/nginx/nginx.conf /etc/nginx/sites-enabled/*
getent ahostsv4 cs.bkeel.com
openssl x509 -in /etc/letsencrypt/live/cs.bkeel.com/fullchain.pem -noout -subject -issuer -dates -ext subjectAltName
timedatectl show -p Timezone -p NTPSynchronized -p NTP
node -e <fs 只读解析 /proc/1104/environ，按白名单输出并隐藏凭据>
node -e <只读执行 journalctl -u nox-brain.service --since 2026-09-08 -n 1000 --no-pager -o json，聚合计数>
stat <Piper 程序/模型、ffmpeg、brain 源码和环境文件>
rg -n '^(Name|Version):' <语音 venv 的 dist-info/METADATA>
```

命令中的中文分号表示分别执行，不是部署脚本。不存在的路径/软件包产生的非零退出已在上述章节解释。

业务测试执行 0，通过 0、失败 0；并不代表功能通过。真实 Provider 请求 0，Mock 测试 0，真实硬件测试 0。物理验收保持 `BLOCKED_PHYSICAL`，原因是本轮只审计服务器且未连接实物。flower 规格第 18 章和 Definition of Done 均未在本轮验收；本轮仅覆盖用户要求的架构、环境与共存审计。

交付复核：`node -e` 使用 fs/path 检查本目录八份文件存在、非空、代码围栏配对和本地链接可解析，8/8 通过、0 失败、0 多余文件；常见秘密模式 `rg` 无匹配。再次 `sha256sum` 核验本报告列出的生产文件及花盆基线，均一致；再次 `systemctl show` 观察四项主要应用服务，PID/启动时间/NRestarts 不变；再次 `git --no-optional-locks ... status --porcelain=v1`，整理后 aibot 仓库为空输出。
