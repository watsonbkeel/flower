# flower 仓库与环境隔离建议

2026-09-13 架构建议，未建仓、未创建部署目录、未实现业务代码。推荐保留一个独立 flower 仓库，项目名使用 flower，产品和 SPEC 标识继续按确认后的基线管理。

## 1. 当前资料基线

`/root/flower` 是约 192 KiB 的文档目录，尚无有效 `.git`。已读 `SPEC_CURRENT.md` 明确为 v2.2；本轮找不到 GOAL 和八个项目技能。不能宣称 v2.2.1 完整包校验已通过，也不应擅自将 v2.2 的安全规则替换为口头的“平台架构”。

现有 `docs/PROJECT_STATUS.md` 的 Stage 0-7 均为 NOT_STARTED。本次只在 `docs/server-audit/` 输出审计，不把 Stage 0 的健康端点、迁移或 Compose 骨架记为完成。

## 2. 推荐仓库结构

```text
/root/flower/                         独立源码/开发检出，非生产运行目录
  AGENTS.md
  GOAL.md                            补齐用户指定资料后再纳入，不代写缺失原文
  SPEC_CURRENT.md                    唯一有效规格
  README.md
  CONTRIBUTING.md
  .agents/skills/                     补齐项目技能
  .github/workflows/                  后续 CI
  .gitignore
  .env.example                       只有字段和非秘密默认值
  docker-compose.yml                 四服务通用结构
  compose.production.yml             生产环回绑定、限制与持久化覆盖
  compose.development.yml             开发端口、Mock、隔离数据覆盖
  backend/
    Dockerfile
    requirements.txt                 配套锁定依赖文件
    alembic.ini
    migrations/
    app/
      main.py
      worker.py
      config.py
      db.py
      api/
      models/
      schemas/                       Pydantic/OpenAPI 合约来源
      safety/
      services/
        commands.py                  唯一 create_command()
        decision/                    唯一完整确定性决策
        fallback_policy/
        jobs/
        recognition/
        care_research/
        weather/
        llm/
      tests/
  pi-agent/
    app/
      safety/gate.py                 唯一 can_dispense()
      safety/quota.py
      policy/fallback_policy.py
      sensors/
      camera/
      actuators/
      cloud/
      commands/
      storage/
    tests/
    install.sh
    calibrate.sh
    diagnose.sh
    emergency_pump_off.sh
    smart-guardian.service
  miniapp/
    pages/
    services/
    utils/
  nginx/                             flower 私有 proxy 模板
  deploy/host-nginx/                  未来外层独立站点模板，非现有配置副本
  deploy.sh
  backup.sh
  restore.sh
  cleanup.sh
  tests/repository/
  demo-data/                         必须显式 demo
  docs/
    server-audit/                    本次八份报告
    reports/
    archive/
    superpowers/plans/
```

沿用现有 backend/pi-agent/miniapp 边界；不把 aibot 搬入此仓库，不提前增加 agent-platform、registry-server、MQTT broker 或公共数据库。与规格中 `caddy/` 相比，建议选择 `nginx/`，在下一阶段同步目录文档和实施任务，不在本轮创建这些目录。

合约以 backend Pydantic、OpenAPI 和 Alembic 为源，必要时输出版本化 JSON Schema 供 Pi 校验。不要另建手工复制的“公共合约包”使两边各自修改。未来真正有第二个调用方时再决定是否抽出独立共享仓库。

## 3. 推荐生产目录

```text
/srv/flower/
  releases/<release-id-or-commit>/    固定 Compose/配置模板和发布清单
  current -> releases/<release-id>/   当前已验证发布
  shared/
    config/production.env            受限权限，不入 Git
    postgres/                        独立数据目录，由容器数据库 UID 使用
    uploads/                         私有图片，不由公网静态目录裸露
    backups/<utc-timestamp>/          数据库+uploads+清单+校验和
    logs/                            仅确有文件日志时使用；容器日志有界
```

选择 `/srv/flower` 作为业务生产部署根，而非 `/root/flower` 或 `/opt/asist-embodiment`。应用使用带 SHA/摘要的不可变镜像；releases 保存与镜像匹配的部署清单，生产容器不 bind-mount 开发源码。数据路径必须独立于 release，以免切换版本误换数据目录。

部署使用专门账户/受限配置权限，API/Worker 容器非 root。生产环境文件只允许部署管理者读取；数据库目录 UID/GID 以选定镜像为准，不照搬宿主用户名。异地备份目标另定，不能只依赖 `/srv/flower/shared/backups`。

所有服务命令明确指定 production compose、环境文件和 `flower-prod` project。根目录名称是建议，本轮没有创建 `/srv/flower`、改用户或权限。

## 4. 开发与生产隔离

| 项目 | 开发/测试 | 生产 |
|---|---|---|
| 首选位置 | 开发电脑或独立 CI runner | 当前服务器 `/srv/flower` |
| 同服务器备用 | `/root/flower` 开发检出，临时项目且有预算 | 独立发布目录，不现场编辑运行代码 |
| Compose project | flower-dev / flower-test / flower-staging | flower-prod |
| 数据 | 独立临时 PostgreSQL、上传目录、测试账号 | flower 专用 PostgreSQL 和持久化 uploads |
| 网络/端口 | 环回 18082；staging 18081，按需运行 | 环回 18080，经宿主机 Nginx |
| 密钥 | Mock 或专门测试凭据 | 独立生产凭据；不复制 aibot key |
| 数据来源 | mock/demo/imported_test 明示 | real 与明确的受控演示来源，不能混标 |
| 鉴权绕过 | 仅开发显式开启，默认关闭更稳妥 | DEV_AUTH_BYPASS=false，DEV_MODE=false |
| 硬件 | Fake/Mock，默认不接真实 GPIO | 独立物理验收后才接真设备/开启自动化 |
| 构建与迁移 | 可失败、可重建的临时环境 | 固定镜像，迁移有锁且失败可见，避免 API/Worker 同时竞跑 |

不要让 development `.env` 指向生产 database，不共享 Docker volume，也不要给测试服务安装生产设备 secret。备份恢复演练必须恢复到独立测试实例，不覆盖生产。2 vCPU 主机不适合同时跑三套环境和依赖构建，staging 按需启动，编译优先外移。

## 5. 后续开发顺序

1. 核对完整文档包和规格版本，恢复缺失 GOAL/Skills；将本次审计作为明确输入，不改安全不变量。
2. 确认独立仓库 URL、默认分支和项目目录，才执行 Stage 0 建仓/分支工作；不在 aibot 目录初始化或清理文件。
3. 按现有 14 项计划推进 backend、Pi Fake 安全门和合约；外部输入缺失继续用 Mock，状态写入既有 EXTERNAL_INPUTS/PROJECT_STATUS。
4. 先完成花盆 MVP，voice-first、共享能力服务和 Registry 分期处理；本轮长期拓扑不是新增 MVP 的开发清单。
5. 完成开发机/预发布验收、备份恢复演练、资源验证后，再安排 Docker 与 Nginx 的独立生产变更窗口。

## 6. 未来仓库拆分时机

至少两个业务实际需要同一 AI 能力、接口已稳定时，才建立独立 `home-ai-capabilities` 仓库和版本化 API。flower 保持领域所有权；aibot 保持会话体验；未来平台可以统一认证/入口/设备登记，但不合并业务数据库或复制花盆安全决策。

当前 aibot 生产目录存在未提交漂移。任何后续 aibot 重构前，先独立保存实际部署文件、配置和可恢复版本；不得通过拉取、重置、清理将其强行变成仓库 HEAD。
