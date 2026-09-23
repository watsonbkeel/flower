# 2026-09-23 Provider 来源边界生产发布

基线：v2.2.2 Server-Integrated；冻结规格 SHA-256 `4481d48605aec47660d2cdefb7a004ed2169bb8531302ecdf803c3c12718cf95`。生产 release 为 `bbb19b8e7eed52ce5d7aa61edd22681a6b129948`；旧版 `208d0548ec7b9db27aa8e94c14412dbd7f466d1e` 保留供回滚。原始网络快照、生产配置和恢复证明只保存在本机私有目录，不进入 Git。

## 发布前门

- `scripts/preflight.py .runtime/preflight-provider-before.json`：已在行为提交时执行，实时私有快照已存在；本次读取前核对 `git status --short` 仅有用户未跟踪 `PROMPT_NEXT_PHASE.md`，未修改该文件。DNS/TLS/服务与当前 release 均按实际状态复核。`sha256sum docs/specs/智慧守候_v2.2.2_Server-Integrated_冻结基线开发实施规格.md`：exit 0，与冻结值一致。
- `systemctl start flower-backup.service`：exit 0；旧 release 的当次备份 `/srv/flower/shared/backups/20260923T025011Z-d1091097`，随后由 `scripts/backup.py restore` 在新的 `flower_restore_provider` 库及新的上传目录恢复：exit 0。`scripts/backup.py verify` exit 0，恢复库 `alembic_version=0003_retention`，公共表 19 张；备份重启后公网 `/ready` 为 HTTP 200。随后写入私有 `verified-backup.json` 的真实恢复证明，发布程序再次校验归档。
- 仓库 `evidence/stage8-provider-provenance.md` 记录构建前完整独立PG回归 231 passed、原生小程序 14 passed、Ruff 通过；HTTP 故障测试用 MockTransport，不等于真实服务联调。

## 发布与发布后验证

- `docker build -q -t flower-app:<完整SHA> backend`：exit 0；应用镜像ID `sha256:32fff6a41fabd7b83c86a23b6a81413e30a4f8a47f605f81bd933bea048e1aa3`。`scripts/release.py --output .runtime/releases --inspect-images`：exit 0；不可变清单复制至 `/srv/flower/releases/<完整SHA>`；`docker compose ... config --quiet`：exit 0。
- `FLOWER_PRODUCTION_AUTHORIZED=1 .venv/bin/python scripts/production.py deploy /srv/flower/releases/<完整SHA>`：exit 0；核对镜像ID和实际恢复证明，等待PG健康，**显式**执行一次性 `alembic upgrade head`，再等待 API/Worker/proxy 健康，切换 current。没有由 API/Worker 入口自动迁移。
- 生产 `/srv/flower/current -> /srv/flower/releases/bbb19b8e7eed52ce5d7aa61edd22681a6b129948`；`https://flower.bkeel.com/health` HTTP 200、返回该 SHA 和规格2.2.2，`/ready` HTTP 200；数据库 `alembic_version=0003_retention`。匿名 `/api/v1/plants` 和 `/api/v1/images/<id>` 均 HTTP 401；无微信配置的 Mock code 登录 HTTP 503，未开启鉴权绕过。
- `systemctl start flower-backup.service` 再次 exit 0；新版归档 `20260923T025329Z-1fb41160` 校验 exit 0，恢复到另一全新库 `flower_restore_provider_new` 和新的上传目录 exit 0，迁移 `0003_retention`、公共表19张。已更新私有恢复证明指向新版归档。生产目前没有实有用户图片，因此没有以此声明生产图片的非空恢复验收。
- `docker save` 新版应用、固定PG/proxy镜像归档 exit 0；`release-images-bbb19b8e7eed52ce5d7aa61edd22681a6b129948.tar` SHA-256 `4fedb1b7d8cac154677cfd6709b45a20b041f0231edac76f9892a28749f1cf59`，权限0600；旧版镜像归档仍在私有备份目录。
- `scripts/production.py rollback /srv/flower/releases/208d054...`：exit 0，公网 `/health` 软件版本切换为旧SHA，`/ready` 200；随后 `scripts/production.py deploy /srv/flower/releases/bbb19b8...`：exit 0，新SHA和 `/ready` 200。无现场构建/拉取；切回新版本运行了显式迁移且仍在 `0003_retention`。

## 共存与限制

- `scripts/preflight.py .runtime/preflight-provider-after.json --compare .runtime/preflight-provider-before.json`：exit 0，变化字段为 `ports/nft/routes/addresses`；审阅差异，网络差异是本轮容器重建的 veth/NAT，未手工更改 UFW/nft/VPN。`nginx -t` exit 0；nginx、nox-brain、city-front、tailscaled、openvpn-server@server、ssh 和 flower-backup.timer 均 active；aibot、Nginx 等服务 `MainPID`/`NRestarts` 未因本次发布改变。`https://cs.bkeel.com/` HTTP 200，Tailscale `BackendState=Running`，UFW active。
- `docker inspect`：API、Worker、PostgreSQL 没有宿主端口发布；唯一 proxy 绑定 `127.0.0.1:18080->8080`。宿主仅由既有 Nginx 监听 80/443。正式域名证书 TLS 链验证 exit 0，CN `flower.bkeel.com`，有效期至 2026-12-21；certbot.timer active（既有续期 dry-run 见 2026-09-22 证据，本次未重复演练）。
- 生产独立配置核对为 `PROVIDER_MODE=mock`、真实网关URL/key和微信 AppID/AppSecret 缺失、`APP_BASE_URL=https://flower.bkeel.com`、`DEV_MODE=false`、`DEV_AUTH_BYPASS=false`；未发生真实 Provider、微信真机、GPIO、水泵或 aibot 主动语音调用。异地备份与实际 VPN 客户端连通/语音高峰未验收。阻塞项见 `BLOCKERS.md`。
