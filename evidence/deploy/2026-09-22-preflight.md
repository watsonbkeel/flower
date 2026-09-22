# 2026-09-22 Flower 首次部署前检查（脱敏摘要）

- `python3 scripts/preflight.py .runtime/preflight-before.json`: exit 0；SHA256 `7839efe3a18df45e4692b0962bd1d548e95e1fb5997425fa8ec1e1355c9d1329`。
- `tar -czf .runtime/host-before-nginx-letsencrypt.tar.gz -C /etc nginx letsencrypt`: exit 0；SHA256 `f8594f5e02379784bdba36cc008b99e4e76b04949285a02d2669b3248820e1aa`；备份权限 0600；原始内容不提交。
- 首次 `apt-get install -y docker.io docker-compose`: exit 100（镜像索引中 tini 404）；`apt-get update`: exit 0；再次安装: exit 0。`docker version`: 26.1.5+dfsg1；`docker compose version`: 2.26.1-4，支持 `up --wait --wait-timeout`。
- `python3 scripts/preflight.py .runtime/preflight-after-docker.json --compare .runtime/preflight-before.json`: exit 0；变化：ports/services/nft/routes/addresses/tailscale，均因 Docker 服务及桥接网络动态字段；`ufw`、`nginx_hashes`、`nginx_test`、现有 `service_state` 未变化。Docker 新增自己的 nft 链，未手改宿主防火墙。
- 前后 `systemctl is-active nginx nox-brain city-front tailscaled openvpn-server@server ssh`: 全部 active；`https://cs.bkeel.com/`: HTTP 200，TLS 验证成功；本地 City Front：HTTP 200；`tailscale status --json` BackendState=Running。
- 安装前 `/srv/flower` 不存在，`127.0.0.1:18080` 空闲；可用内存约 6.0 GiB，根盘可用约 69 GiB。`flower.bkeel.com` 解析 `43.161.224.25`，当前 HTTPS 证书名称不匹配，未宣称上线。
- 开发回归 `PYTHONPATH=backend .venv/bin/python scripts/test_postgres.py .venv/bin/pytest -q`: exit 0，223 passed，1 warning；`npm test -- --runInBand`（miniapp）: exit 0，13 passed。

原始快照包含 VPN、地址和 Nginx 信息，仅存放于忽略的私有 `.runtime/`。该阶段尚未创建 Flower 网络、容器、数据库或证书；需在这些变更后重新比较并验证。
