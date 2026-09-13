# 智慧守候 v2.2.2 Server-Integrated 开发包

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
- 建议正式域名：`flower-api.bkeel.com`。
- 开发仓库：`/root/flower`；生产：`/srv/flower`。

## 启动

把 `PROMPT_ONE_GOAL.md` 全文交给 Codex。生产 Docker 安装、Nginx 变更和正式部署必须在明确授权窗口执行。

## 额外核心文档

- `docs/SERVER_INTEGRATION_BASELINE.md`：真实服务器事实和冻结共存方案。
- `docs/SAFETY_INVARIANTS.md`：任何实现不得绕过的硬安全不变量。
- `docs/API_AND_DATA_CONTRACTS.md`：命令、健康端点、设备/小程序 API 契约。
- `docs/REVIEW_RESOLUTION_v2.2.2.md`：Opus 评审与 Codex 审计的处理闭环。
