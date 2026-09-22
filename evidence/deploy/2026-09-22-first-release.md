# 首次生产发布与备份故障复核（v2.2.2）

- 首次发布 commit `e679b65994394ac9a2adcf2e3612aa65b71b9b25`，`docker build`、PG/proxy 镜像拉取、`scripts/release.py --inspect-images`、Compose config 均 exit 0；`/srv/flower/releases/<sha>` 与镜像ID核验通过。
- 仅启动 PostgreSQL 后健康检查通过；首次备份 `20260922T142134Z-ee751210`、校验和验证及独立恢复 `flower_restore_pre_migration` 均 exit 0。源库与恢复库公共表数均为0，图片目录均为空；`verified-backup.json` 指向该真实备份及恢复记录。
- `FLOWER_PRODUCTION_AUTHORIZED=1 .venv/bin/python scripts/production.py deploy ...`: exit 0。生产 migration 显式执行一次，版本 `0003_retention`；API/Worker/PG 健康，proxy 运行；环回及公网 `/health`、`/ready` 均为 200，软件版本返回首次发布 SHA。API/PG 无宿主端口，proxy 仅发布 `127.0.0.1:18080`。
- `certbot certonly --webroot ... -d flower.bkeel.com`: exit 0；证书 CN `flower.bkeel.com`，2026-12-21 到期。独立站点 `nginx -t` 和 reload exit 0，HTTPS TLS 验证成功，未授权的植物和图片接口均返回 401，City Front 返回 200。
- 迁移后备份脚本 `sh /srv/flower/current/deployment/backup-production.sh`: exit 0，产物 `20260922T142926Z-8db76b77`；独立恢复 `flower_restore_post_migration`: exit 0，版本 `0003_retention`、公共表19张。此操作短暂停止 API/Worker。
- **真实故障：** 备份后 API 虽恢复健康，公网和环回 `/ready` 返回 502。proxy 日志显示仍连接旧 API 容器 IP，DNS 解析在 Nginx 启动时被缓存。`docker compose --project-name flower-prod restart proxy` exit 0 后 `/ready` 恢复 200。`tests/test_deployment_sequence.py::test_proxy_resolves_api_again_after_container_restart` 实现前 exit 1，实现后6项定向测试 exit 0。修复需构建新 release 并重复备份验证，首次发布不算完整生产验收。
- Docker/Flower 网络变更后私有快照分别存于 `.runtime/preflight-after-docker.json` 与 `.runtime/preflight-after-flower-network.json`。后者差异含 Flower 桥接及新独立 Nginx/证书文件；City Front 200，Nginx/aibot/City Front/Tailscale/OpenVPN/SSH active，Tailscale Running。没有主动语音或 VPN 客户端端到端高峰测试。

原始私有证据、DB 转储、证书、配置与凭据仅保存在本机未提交目录；本文件不包含密钥或原始网络规则。
