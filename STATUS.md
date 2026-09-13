# STATUS.md

- 当前规格：v2.2.2 Server-Integrated
- 当前 Stage：1
- 实现状态：IN_PROGRESS
- 架构审计：COMPLETE（只读，2026-09-13）
- 最近更新：2026-09-13

## 已完成

- [x] 服务器/aibot 只读审计 8 份报告
- [x] v2.2.2 Server-Integrated 基线生成
- [x] Stage 0：基线校验、独立分支、后端配置/健康端点、显式迁移、Compose骨架及preflight脚本
- [x] Stage 1安全核心：67项累计自动化测试通过（55项Pi Mock/单元测试）；硬件适配层已实现，实物未验收

## 当前进行

- [x] 规格 SHA-256、GOAL、七个 Skills、八份审计报告校验
- [x] 独立分支 `feat/flower-v2.2.2`，起点 `08534ae`

## 下一步

- [ ] Stage 2：PostgreSQL设备链路、双时钟与设备常驻循环

## 开发证据

- `evidence/stage0-red.xml`：实现前预期失败（模块尚不存在）。
- `evidence/stage0-green.xml`：开发自动化验证；SQLite仅用于本阶段迁移/探针测试，不代表PostgreSQL或Compose运行通过。
- 未重复全面服务器审计，未执行preflight或任何生产修改。
- `evidence/stage1-green.xml`：67 passed，含缺水20次禁泵、20次重启保额、独立定时器关泵、>60秒会话及会话超时。
- Stage 1中的常驻采集/云客户端与安装诊断工具将在Stage 2接入实际设备合约后完成；真实Pi安装、BLE/摄像头压力与物理标定均BLOCKED_PHYSICAL。

## 已知共享宿主机事实

- Debian 13；2 vCPU；约 7.5 GiB RAM；约 71 GiB 可用磁盘（审计时）
- Nginx 已占用 80/443
- aibot `nox-brain.service` 从 `/opt/asist-embodiment/brain` 运行
- 当前未发现 Docker/PostgreSQL 运行时
- Tailscale、OpenVPN 均运行

所有数值需在正式部署窗口前重新取快照。
