# STATUS.md

- 当前规格：v2.2.2 Server-Integrated
- 当前 Stage：0
- 实现状态：NOT_STARTED
- 架构审计：COMPLETE（只读，2026-09-13）
- 最近更新：2026-09-13

## 已完成

- [x] 服务器/aibot 只读审计 8 份报告
- [x] v2.2.2 Server-Integrated 基线生成
- [ ] 代码实现尚未开始

## 当前进行

- [ ] 将本包完整部署到 `/root/flower` 并校验规格/GOAL/Skills
- [ ] 初始化独立 Git 仓库/分支或 worktree

## 下一步

- [ ] 执行 Stage 0

## 已知共享宿主机事实

- Debian 13；2 vCPU；约 7.5 GiB RAM；约 71 GiB 可用磁盘（审计时）
- Nginx 已占用 80/443
- aibot `nox-brain.service` 从 `/opt/asist-embodiment/brain` 运行
- 当前未发现 Docker/PostgreSQL 运行时
- Tailscale、OpenVPN 均运行

所有数值需在正式部署窗口前重新取快照。
