# REVIEW_RESOLUTION_v2.2.2.md

## 外部评审已吸收

- claim TTL 与多脉冲 session 已在 v2.2.1 分离，本版保留；
- 固定 commit SHA 镜像，解决“上一镜像不存在”的回滚漏洞；
- production migration 改为显式一次性 job；
- Compose 统一服务名 `proxy/api/worker/postgres`；
- production 下 DEV_AUTH_BYPASS/DEV_MODE/非HTTPS fail-closed；
- 无正式域名的开发设备使用加密隧道，不允许 `verify=False`；
- `/health`、`/ready` 纳入正式契约；
- 增加每日备份、保留和异地备份门；
- 语音/aibot peripheral 不得绕过 Flower 安全链；
- Docker/UFW/VPN/Nginx 审计扩展到全部 systemd/端口/路由。

## 真实服务器审计已吸收

- 采用 B：同机、独立业务；
- aibot 保持 systemd，不迁移；
- Flower 使用独立 Compose + 独立 PostgreSQL；
- 宿主 Nginx 继续独占 80/443；内部 proxy 127.0.0.1:18080；
- `/root/flower` 开发，`/srv/flower` 生产；
- Worker 并发初始 1；
- 2 vCPU 是主要容量约束，Piper 回退为同机资源风险；
- 当前不建设统一 ASR/TTS/LLM 服务或 Device Registry；
- Tailscale 保留维护用途，生产 Flower 设备业务使用主动 HTTPS；
- aibot `/opt` 生产漂移作为独立运维风险，不由 Flower 项目修复。
