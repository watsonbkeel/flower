# STATUS.md

- 当前规格：v2.2.2 Server-Integrated
- 当前 Stage：0
- 实现状态：IN_PROGRESS
- 架构审计：COMPLETE（只读，2026-09-13）
- 最近更新：2026-09-13

## 已完成

- [x] 服务器/aibot 只读审计 8 份报告
- [x] v2.2.2 Server-Integrated 基线生成
- [x] Stage 0：基线校验、独立分支、后端配置/健康端点、显式迁移、Compose骨架及preflight脚本

## 当前进行

- [x] 规格 SHA-256、GOAL、七个 Skills、八份审计报告校验
- [x] 独立分支 `feat/flower-v2.2.2`，起点 `08534ae`

## 下一步

- [ ] Stage 1：Pi安全核心和故障注入测试

## 开发证据

- `evidence/stage0-red.xml`：实现前预期失败（模块尚不存在）。
- `evidence/stage0-green.xml`：开发自动化验证；SQLite仅用于本阶段迁移/探针测试，不代表PostgreSQL或Compose运行通过。
- 未重复全面服务器审计，未执行preflight或任何生产修改。

## 已知共享宿主机事实

- Debian 13；2 vCPU；约 7.5 GiB RAM；约 71 GiB 可用磁盘（审计时）
- Nginx 已占用 80/443
- aibot `nox-brain.service` 从 `/opt/asist-embodiment/brain` 运行
- 当前未发现 Docker/PostgreSQL 运行时
- Tailscale、OpenVPN 均运行

所有数值需在正式部署窗口前重新取快照。
