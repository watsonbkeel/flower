# 智慧守候 v2.2.2 Server-Integrated

当前源码已完成Stage 0-8的开发/Mock验证与部署准备。整体交付状态为`HARD_BLOCKED`，生产发布、微信控制台和实物验收尚未完成。逐项证据见`FINAL_IMPLEMENTATION_REPORT.md`。

## 从空环境运行开发预览

需要Python 3.13及venv、Git；Node 22+仅用于小程序自动化验证。以下命令在本仓库运行：

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python scripts/dev_server.py
```

打开`http://127.0.0.1:18082/preview/`。仅监听环回，使用独立SQLite和明确标注的Mock设备、图片及外部知识。开发启动器显式迁移并启动API/Worker；生产entrypoint不会迁移。端口已占用时使用`--port 18083`。远程查看可用SSH本地端口转发，不公开明文端口。

模拟器仍经过真实Flower建单和Pi安全执行代码。演示后6小时内再次补水可能被间隔门拒绝，这是预期行为。`.runtime`包含本机开发凭据、数据库和日志，不进Git。

## 自动化验证

```bash
.venv/bin/pytest
npm --prefix miniapp ci
npm --prefix miniapp test
.venv/bin/ruff check backend pi-agent tests
```

默认测试使用SQLite，并明确跳过仅能在PG运行的行锁并发与独立恢复测试。完整证据必须使用PostgreSQL：

```bash
mkdir -p .runtime/vendor .runtime/pg
cd .runtime/vendor
apt-get download postgresql-17 postgresql-client-17 libpq5
cd ../..
for package in .runtime/vendor/postgresql-17_*.deb .runtime/vendor/postgresql-client-17_*.deb .runtime/vendor/libpq5_*.deb; do
    dpkg-deb -x "$package" .runtime/pg
done
PYTHONPATH=backend .venv/bin/python scripts/test_postgres.py .venv/bin/pytest --junitxml=evidence/local-postgres.xml
```

上述PG二进制方案验证于Debian 13 amd64，使用临时Unix socket，测试结束销毁集群；不安装数据库服务、不监听TCP。其他平台可在独立PG测试库设置`TEST_DATABASE_URL`运行pytest，该数据库会被测试清空，严禁指向生产。

浏览器测试：`cd miniapp && npx playwright install chromium`，运行`scripts/verify-preview.js`；依赖库和中文字体的开发目录方案见`evidence/stage5.md`。`scripts/verify-workflow.js`用于新鲜Mock设备的补水/养护/记忆流程，受真实软件额度限制。

## 服务与发布

- API：`PYTHONPATH=backend .venv/bin/uvicorn flower.main:create_app --factory --host 127.0.0.1 --port 18082`。
- Worker：`PYTHONPATH=backend .venv/bin/python -m flower.worker`，需与API使用同一环境配置。
- 显式迁移：配置`DATABASE_URL`后在`backend`执行`../.venv/bin/alembic upgrade head`。
- 设备注册/密钥轮换/撤销：`python -m flower.manage`；一次性密钥只保存于独立秘密配置。
- Pi安装：将`pi-agent`准备到实物独立`/opt/smart-guardian`，断开泵电源后按`pi-agent/README.md`与`docs/HARDWARE_WIRING.md`操作；本服务器不执行Pi安装脚本。
- 原生小程序：`miniapp/README.md`。外部网关：`docs/PROVIDERS.md`。离线演示：`docs/OFFLINE_DEMO.md`。
- 不可变release、Compose、独立Nginx、备份恢复和回滚：`docs/DEPLOYMENT_RUNBOOK.md`。授权前只运行`scripts/release.py --output .runtime/releases`准备开发包；没有image ID的manifest为NOT_BUILT。
- 发布入口：`scripts/deploy.sh <release>`，在明确生产授权窗口内使用；等待数据库及API/Worker健康，迁移仅作为显式步骤执行。

任何生产部署必须先解除`BLOCKERS.md`中相应项目并获得明确窗口授权。本仓库不会修改aibot生产或宿主网络。

## 原始基线说明

本包是服务器真实审计后的唯一开发基线，用于服务器 Codex 在 `/root/flower` 以单一 Goal 持续开发。

## 先确认

- `SPEC_CURRENT.md` 指向 v2.2.2。
- `GOAL.md` 存在。
- `.agents/skills/` 存在。
- `docs/server-audit/` 含 2026-09-13 八份只读审计报告。

如果服务器仍只有 v2.2 `SPEC_CURRENT.md`、`PROJECT_STATUS.md` 且缺 `GOAL.md`/Skills，说明解压了旧包，不要开始开发。

## 已冻结的服务器方案

- 推荐 B：aibot 与 Flower 同一服务器、业务独立。
- aibot 保持 `/opt/asist-embodiment` + systemd，不由 Flower 项目修改。
- Flower 独立 Compose：`proxy/api/worker/postgres`。
- 宿主 Nginx 继续占用 80/443；Flower 只发布 `127.0.0.1:18080`。
- 正式域名：`flower.bkeel.com`。
- 开发仓库：`/root/flower`；生产：`/srv/flower`。

## 启动

把 `PROMPT_ONE_GOAL.md` 全文交给 Codex。生产 Docker 安装、Nginx 变更和正式部署必须在明确授权窗口执行。

## 额外核心文档

- `docs/SERVER_INTEGRATION_BASELINE.md`：真实服务器事实和冻结共存方案。
- `docs/SAFETY_INVARIANTS.md`：任何实现不得绕过的硬安全不变量。
- `docs/API_AND_DATA_CONTRACTS.md`：命令、健康端点、设备/小程序 API 契约。
- `docs/REVIEW_RESOLUTION_v2.2.2.md`：Opus 评审与 Codex 审计的处理闭环。
