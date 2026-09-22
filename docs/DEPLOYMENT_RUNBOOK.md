# DEPLOYMENT_RUNBOOK.md

## 1. 已知宿主机基线

以 `docs/server-audit/CURRENT_SERVER_INVENTORY.md` 为 2026-09-13 快照：宿主 Nginx 已占 80/443，aibot 为 systemd 服务，Tailscale/OpenVPN 运行，当前未发现 Docker/PostgreSQL。正式变更前必须重新取快照，不把旧审计当实时状态。

## 2. 生产目录与端口

```text
/root/flower                         开发 Git 仓库
/srv/flower/releases/<git-sha>/     不可变发布清单
/srv/flower/current                 当前 release 软链接
/srv/flower/shared/config/          production.env
/srv/flower/shared/postgres/        Flower 独立 PG 数据
/srv/flower/shared/uploads/         私有上传
/srv/flower/shared/backups/         本机滚动备份
```

Flower Compose project：`flower-prod`。

```text
宿主 127.0.0.1:18080 -> flower proxy:8080
api:8000                  容器内部
postgres:5432             容器内部
worker                    无监听
```

## 3. 首次 Docker 安装前的共享宿主机审计

记录到 `evidence/deploy/preflight/`：

```bash
ss -lntup
systemctl list-units --type=service --state=running --no-pager
ufw status verbose
nft list ruleset
ip -brief address
ip route show table all
systemctl show nginx.service nox-brain.service tailscaled.service openvpn-server@server.service
nginx -T
free -h
df -hT /
```

首次安装 Docker/启用 bridge 后重复同组检查，并确认 City Front、aibot、Tailscale、OpenVPN 未回归。不得以 `ufw active` 代替 nft/NAT 实际检查。

## 4. 构建与不可变 release

1. 在干净 commit 构建应用镜像 `flower-app:<git-sha>`；API 和 Worker 复用同一镜像。
2. 记录 `docker image inspect` 的 image ID/RepoDigest（若有）。
3. 将 release Compose、`IMAGE_TAG=<git-sha>`、migration head、配置字段清单和校验和写入 `/srv/flower/releases/<git-sha>/`。
4. 不使用 `latest` 作为生产固定版本；至少保留当前和上一已验证镜像。
5. 为防止本机 image prune 破坏回滚，可把已验证 release 镜像导出为受控 OCI/tar 归档或推送受控 registry；具体方式在首次部署时固定并测试。

## 5. 生产发布顺序

1. 确认 production hard gate 配置合法：`DEV_MODE=false`、`DEV_AUTH_BYPASS=false`、HTTPS 基址、secret 非默认。
2. `docker compose ... config`。
3. 启动/确认 `postgres` 健康。发布工具通过Compose `up --wait --wait-timeout 120`等待健康；超时退出，不继续迁移。
4. 升级前运行 `backup.sh`，备份 DB + uploads + release manifest + checksums。
5. **显式一次性 migration**：`docker compose ... run --rm api alembic upgrade head`。API/Worker entrypoint 不执行 migration。
6. migration 成功后启动 `api`、`worker`、`proxy`，同样等待Compose健康状态。API或Worker不健康时退出，不能仅凭API HTTP响应认定发布成功。
7. 验证 `127.0.0.1:18080/health` 与 `/ready`。
8. 若是首次公网接入，写入 `flower.bkeel.com` 独立 Nginx server block，先 `nginx -t`，再 reload。
9. 从外部验证 HTTPS、设备 auth、图片上传限制和小程序 API。
10. 保存发布日志到 `evidence/deploy/<git-sha>/`。

## 6. 宿主 Nginx

- 继续独占 80/443，不安装 Caddy 抢端口。
- 独立 `server_name flower.bkeel.com`，代理 `http://127.0.0.1:18080`。
- 不修改 `cs.bkeel.com` 既有路由语义。
- Flower 图片路径代理允许至少 10MiB + multipart 开销；业务层仍硬限制 10MiB。
- `/health`、`/ready` 位于根路径，不带 `/api/v1`。

## 7. 开发期无域名联调

优先让 Pi 主动建立 SSH/Tailscale 加密隧道，把 Pi 本地环回端口转发到服务器 `127.0.0.1:18082` 开发 proxy；Pi 访问自己的 `127.0.0.1`。这是 development-only 例外。

禁止：

- `verify=False`；
- 自签证书却不固定 CA/证书；
- 把 `0.0.0.0:8000` 或明文开发 proxy 公开公网。

production 必须使用有效 HTTPS 域名。

## 8. 树莓派发布

保持12V泵电源关闭完成 install/diagnose，再进行1秒泵测试与三项标定。未完成物理验收时自动守护必须关闭。Pi 端发布保留上一 release 目录和 systemd 软链接；回滚第一步强制关泵。

## 9. 回滚

### 应用

- 切回上一 release 的固定 `IMAGE_TAG=<previous-sha>`；
- 使用 `docker compose up -d --no-build` 或等价方式，禁止现场重新 build 作为唯一回滚办法；
- 验证 `/health`、`/ready`、设备 claim、缺水禁泵、City Front、aibot、VPN。

### 数据库

不自动 `alembic downgrade`。migration 应尽量向后兼容；若新 schema 不能被旧 release 读取，按已演练的 release 前备份恢复独立 Flower DB。不得影响 aibot 或 City Front 数据。

## 10. 定时备份

- 默认每日一次（建议 03:30 Asia/Shanghai，可配置）；
- 保留 7 份日备份 + 4 份周备份；
- 备份 PostgreSQL、uploads、release manifest 与校验和；
- 本机备份之外必须确定一个异地目标后才能把灾备验收标 PASS；
- `restore.sh` 至少在独立测试实例成功恢复一次。

## 11. 发布容量门

初始 Worker 并发 1。与 aibot 共存验收至少记录 CPU、可用内存、I/O、Flower 快速接口 p95 和真实语音体验。目标：Flower 快速接口 p95 <500ms；aibot 真实对话性能相对其单独运行基线劣化不超过20%。无真实高峰样本时标 NOT_RUN/BLOCKED，不得伪称 PASS。

## 12. 本仓库可执行工具（尚未生产运行）

- `scripts/release.py --output .runtime/releases` 从干净commit生成开发发布包，未build时manifest明确为NOT_BUILT。
- 获得窗口后构建`docker build -t flower-app:$(git rev-parse HEAD) backend`，拉取Compose指定的PG/proxy镜像，重新生成`--inspect-images`清单。清单保存三个image ID，release.env将PG/proxy锁定为ID。
- 将当前和上一release的三个镜像分别`docker save`到受控存储并计算SHA256；恢复时先`docker load`，生产脚本校验tag对应的实际ID，禁止现场build。
- `scripts/deploy.sh /srv/flower/releases/<sha>`调用同一生产发布入口；也可用`scripts/production.py deploy /srv/flower/releases/<sha>`，回滚使用`rollback`。仅在环境`FLOWER_PRODUCTION_AUTHORIZED=1`的明确授权窗口使用。它们不会安装Docker或修改宿主Nginx、防火墙、VPN。
- 生产窗口安装的Compose v2必须支持`up --wait --wait-timeout`；先通过`docker compose up --help`确认。工具等待PG健康后显式迁移，再等待API/Worker健康；失败时保持current链接，按第9节回滚。
- `nginx/flower-api.host.conf`为独立站点模板，证书路径须先存在；不得直接覆盖现有站点。
- `/srv/flower/shared/uploads`及`backups`由容器UID 10001可写；PG目录由指定PG镜像用户维护，不能混用aibot目录。
- `deployment/flower-backup.timer`、`.service`与`backup-production.sh`为待安装模板。备份期间停止API/Worker写入；需在窗口中验证该短暂停机及设备fallback。
- 备份CLI：`python scripts/backup.py backup --directory <backups> --uploads <uploads> --manifest <release.json>`，`DATABASE_URL`仅从环境读取；DB密码不进入命令行。
- 恢复CLI：`python scripts/backup.py restore --directory <one-backup> --uploads <new-empty-path> --target-database flower_restore_<name>`，仅创建独立新DB，不覆盖现有数据。应使用专用测试PG连接。
- 首次部署前，先仅启动Flower PG，导出空库/已有数据备份，再做显式migration。生产发布所需`verified-backup.json`必须对应当次已验证备份及独立恢复记录，不得以空占位文件替代。
- `scripts/preflight.py <private-output> --compare <before>`只在正式窗口运行；原始网络信息与Nginx哈希记录应保持私有，脱敏后才进入evidence。

当前开发环境已运行真实PostgreSQL备份/独立恢复测试，但Docker build、Compose config/runtime、生产timer、真实域名和上一镜像回滚仍为NOT_RUN/BLOCKED。
