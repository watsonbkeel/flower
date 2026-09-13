# v2.2.2 单一 Goal 开发 Prompt

把下面整段发送给服务器上的 Codex。正确的 v2.2.2 包应已解压到 `/root/flower` 根目录。

---

你是 `/root/flower` 项目的总负责工程师。持续完成 `GOAL.md` 的唯一目标，直到 Definition of Done；不要每个 Stage 都等待我继续发 Prompt。

开始前必须依次读取：

1. `AGENTS.md`
2. `SPEC_CURRENT.md`
3. `GOAL.md`
4. `docs/SERVER_INTEGRATION_BASELINE.md`
5. `docs/SAFETY_INVARIANTS.md`
6. `docs/API_AND_DATA_CONTRACTS.md`
7. `docs/server-audit/RECOMMENDATION.md`
8. `docs/server-audit/CURRENT_SERVER_INVENTORY.md`
9. `docs/server-audit/AIBOT_ARCHITECTURE_AUDIT.md`
10. `docs/server-audit/TARGET_DEPLOYMENT_TOPOLOGY.md`
11. `docs/server-audit/RESOURCE_AND_PORT_PLAN.md`
12. `docs/IMPLEMENTATION_PLAN.md`
13. `docs/ARCHITECTURE_DECISIONS.md`
14. 当前任务对应的 `.agents/skills/*/SKILL.md`

先校验：`SPEC_CURRENT.md` 必须指向 v2.2.2；`GOAL.md` 和 `.agents/skills/` 必须存在。如果仍看到 v2.2 旧包，立即停止写代码并报告资料基线错误。

## 共享服务器硬边界

- aibot 实际生产 `/opt/asist-embodiment` 只读，不得修改、reset、clean、pull、checkout、重启或迁移。
- Flower 开发仓库 `/root/flower`；生产 `/srv/flower`。
- 宿主 Nginx 继续占用 80/443；Flower 生产只映射 `127.0.0.1:18080`。
- 不把 API 8000 或 PostgreSQL 5432 发布到宿主机。
- 不使用 Caddy 抢占宿主 80/443。
- Flower 使用独立 PostgreSQL、数据卷、密钥、设备身份和备份。
- 任何语音/aibot peripheral/调试接口不得直接驱动 GPIO17；语音未来只能形成业务意图并进入 Flower `create_command()`。

## 执行方式

- 先检查仓库和 Git 状态，建立独立分支/worktree；不覆盖审计报告和用户未提交内容。
- 按实施计划持续推进 backend、worker、pi-agent、miniapp、测试、Mock、文档和部署脚本。
- 行为改动测试先行；Stage 完成后运行验证、更新 `STATUS.md`、写 evidence、原子提交，然后继续。
- 缺 API key、微信凭据、BLE bindkey、域名或实物时先完成 Mock/Provider/契约/测试，相关真实验收写 `BLOCKERS.md`，其余任务继续。
- 首次安装 Docker、修改宿主 Nginx/DNS/证书或正式生产部署属于共享服务器变更，必须准备 preflight、备份和回滚，并等待明确生产变更授权；不要擅自动生产环境。
- production 下 `DEV_MODE`/`DEV_AUTH_BYPASS`/HTTPS 硬门必须 fail closed。
- 生产 migration 只允许显式一次性 job；API/Worker entrypoint 禁止自动迁移。
- 镜像以 commit SHA 固定 tag；回滚必须能不重新 build 直接使用上一 release。
- Worker 初始并发=1；不要在当前服务器新增本地 LLM 或持续云 ASR。
- 未运行的实物/高峰容量测试不得写 PASS。

最终交付完整源码、固定 release 构建方案、Compose、Nginx Flower 站点模板、迁移、测试、Pi systemd、Mock/真实 Provider 切换、备份/恢复、离线演示、`FINAL_IMPLEMENTATION_REPORT.md` 和全部证据。

现在开始。先完成基线校验和仓库审计，然后自动进入第一个未完成 Stage；除真正硬阻塞或生产变更授权外不要停在“只给计划”。

---
