# 生产验收增量（v2.2.2）

- 修复版 `9ed1627c9b3067443fc23fa3ea3dbdc9085ec4dd`：`docker build`、SHA release 生成、Compose 显式迁移步骤、四容器健康检查及 HTTPS `/health`/`/ready` 均 exit 0/HTTP 200；生产 Alembic `0003_retention`。app/proxy/PG 镜像ID在 release manifest 中，均经发布脚本再次核验。
- 备份脚本再次执行 exit 0，API/Worker 停止后恢复，proxy 使用 Docker DNS 动态解析；随后公网 `/ready` 首次轮询即 200，复现条件下不再出现旧 IP 502。`20260922T144120Z-5d9d2d84` 独立恢复 exit 0，19 张公共表、migration `0003_retention`。`flower-backup.timer` enabled/active（03:30 Asia/Shanghai）；`systemctl start flower-backup.service` exit 0，service Result=success/ExecMainStatus=0，公网 `/ready=200`。
- `certbot renew --cert-name flower.bkeel.com --dry-run --non-interactive`: exit 0，模拟续期成功；certbot.timer active，Flower 专用 deploy hook 仅在 Flower 证书更新后校验并 reload Nginx。证书截止 2026-12-21；`flower.bkeel.com` `/health`、`/ready` TLS 验证成功均 200，未带令牌的植物和图片请求 401；生产 Mock 登录尝试返回 503 `WECHAT_NOT_CONFIGURED`，未启用旁路。
- 生产 `APP_ENV=production`、`DEV_MODE=false`、`DEV_AUTH_BYPASS=false`、`APP_BASE_URL=https://flower.bkeel.com`、`PROVIDER_MODE=mock`；仅 proxy 的 8080/tcp 映射 `127.0.0.1:18080`，API/PG 宿主端口均为空。`cs.bkeel.com` 200、Nginx/aibot/City Front/Tailscale/OpenVPN/SSH 均 active、Tailscale Running、UFW active。未实测 VPN 客户端连接及 aibot 真实语音高峰。
- 固定镜像归档 `release-images-9ed1627c9b3067443fc23fa3ea3dbdc9085ec4dd.tar` 的 SHA256 `942e7cd6dbe30834fc3542258f2b3ac00da72cea2ebe19333621eceafcaec53e`，`docker save` 与 `docker load` 均 exit 0；旧 `e679b65` 存在已知故障，不能作为上一已验证 release 宣称无重建业务回滚通过。
- **轮转缺陷：** 同一天多次备份只留下最新归档，较早已恢复验证的备份被移除；本轮发现并在 `tests/test_delivery.py` 中构造同日跨 release 失败测试，保留策略已修复为最近两个 release 各留一份最新快照。现存 `20260922T144451Z-146e06f5` 已重新独立恢复到 `flower_restore_timer`（exit 0，`0003_retention`、19表），`verified-backup.json` 更新指向该真实归档。待修复版发布后重新触发轮转验证。
- 最终私有实时快照 `.runtime/preflight-final.json` SHA256 `c49f63b11a145ffcfeaa9742f4d39c475bf7945501d6f40c539890257d34005d`；比安装前变更含 Docker/Flower 桥接、Flower 独立 Nginx/证书、备份 timer。原始快照、凭据、证书密钥和数据库不进入 Git。

真实 AI 调用、微信教育版真机、真实 Pi/泵、异地备份和语音高峰均无 PASS 证据，状态以 `BLOCKERS.md` 为准。
