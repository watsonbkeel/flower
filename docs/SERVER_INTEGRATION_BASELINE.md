# SERVER_INTEGRATION_BASELINE.md

## 2026-09-13 审计事实

- Debian 13，2 vCPU，约 7.5 GiB RAM；审计时约 6.7 GiB 可用、根盘约 71 GiB 可用。
- 宿主 Nginx 是当前唯一 80/443 Web 入口；`cs.bkeel.com -> 127.0.0.1:7460` City Front。
- aibot `nox-brain.service` 从 `/opt/asist-embodiment/brain` 运行，8889 已使用。
- aibot ASR 在 Pi 使用 Vosk；云端主要外部 LLM + Edge TTS，本地 Piper 为回退。
- aibot 没有可复用的多业务 Device Registry、用户系统、可靠 jobs 或公共 ASR/TTS/LLM API。
- `/opt/asist-embodiment` 存在未提交生产漂移；Flower 项目不得整理或重置它。
- 当前未发现 Docker/PostgreSQL 运行时。
- Tailscale、OpenVPN、DERP 等网络服务运行中。

## 冻结方案

- 同机、业务独立：Flower Compose 与 aibot systemd 并存。
- Flower：`proxy/api/worker/postgres`，生产只发布 `127.0.0.1:18080`。
- 宿主 Nginx 新增独立 `flower-api.bkeel.com` 虚拟主机；不使用 Caddy 抢 80/443。
- `/root/flower` 开发；`/srv/flower` production releases/shared。
- Flower PostgreSQL、uploads、secret、device identity、backup 全部独立。
- Worker 初始并发1；当前不部署本地 LLM 或云 ASR。
- 未来语音/小程序统一输入可路由到 Plant Domain，但补水永远保留 Flower 命令门和 Pi 本地安全门。

完整证据见 `docs/server-audit/`。
