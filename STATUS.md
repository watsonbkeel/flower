# STATUS.md

- 当前规格：v2.2.2 Server-Integrated
- 当前 Stage：8（开发与Mock交付已归档）
- 实现状态：HARD_BLOCKED
- 架构审计：COMPLETE（只读，2026-09-13）
- 最近更新：2026-09-13

## 已完成

- [x] 服务器/aibot 只读审计 8 份报告
- [x] v2.2.2 Server-Integrated 基线生成
- [x] Stage 0：基线校验、独立分支、后端配置/健康端点、显式迁移、Compose骨架及preflight脚本
- [x] Stage 1安全核心：67项累计自动化测试通过（55项Pi Mock/单元测试）；硬件适配层已实现，实物未验收
- [x] Stage 2设备链路：86项累计测试在独立PostgreSQL 17.11通过；鉴权、原子领取、双时钟、遥测、回执和保守对账
- [x] Stage 3：可靠Worker子进程、租约与重试、图片鉴权/低空间保护、Top3 Mock识别与手动确认；累计93项通过
- [x] Stage 4：知识/天气/LLM Provider、完整确定性决策、保守策略编译、记忆确认及生效记录；累计123项PostgreSQL测试通过
- [x] Stage 5：微信登录合约、原生七页面、记忆编辑/照片、任务恢复、鉴权趋势与浏览器Mock预览；128项PostgreSQL测试、6项Node测试通过
- [x] Stage 6：完整小时幂等聚合、逐字段复核后30天raw清理、365天hourly保留、图片/任务/命令清理及Worker调度；132项累计PostgreSQL测试通过
- [x] Stage 7开发准备：SHA发布清单、显式migration/无build回滚脚本、Nginx/timer模板、DB+uploads+manifest备份与独立PG恢复；136项累计通过，依赖审计无已知漏洞
- [x] Stage 8开发验证：独立遥测、执行中策略到期/撤销、启动宽限期、迟到回执、逐命令对账、fallback审计、通知job、离线Mock链路及浏览器操作验证；累计149项PostgreSQL测试通过
- [x] Stage 8交付复核修复：Pi时钟跳变后稳定重验恢复、fallback回执不阻塞云端对账；累计155项PostgreSQL测试通过
- [x] Stage 8天气缓存复核：独立Worker刷新过期天气、持久重试、旧上下文结果隔离与降雨输入校验；累计166项PostgreSQL测试通过
- [x] 原生页面6项Node验证、桌面/手机Playwright截图与命令/养护/记忆工作流验证
- [x] 天气展示复核：零值、缺失、过期、来源分离及自动刷新保留表单；8项Node测试和桌面/手机Playwright验证通过
- [x] 用户任务重试复核：新请求可重新研究/整理，同键重放去重，并发入队原子化；170项PostgreSQL测试、9项Node测试通过
- [x] 品种变更安全复核：旧养护卡失效、并发确认隔离、迟到研究结果拒绝；173项PostgreSQL测试通过
- [x] 家庭记忆策略复核：编辑/移除关联/重新整理刷新策略，策略有效期不超过养护卡；178项PostgreSQL测试通过
- [x] Worker事务复核：提交时租约过期回滚全部业务结果，过期任务不调用Provider；184项PostgreSQL测试通过
- [x] 策略续期复核：有效养护卡下由Worker提前续发、版本并发去重、临近养护卡到期不反复续发；190项PostgreSQL测试通过
- [x] 识别确认复核：候选按置信度排序、重拍清除旧选择、手动/候选最后操作优先及低置信度提示；194项PostgreSQL、11项Node及桌面/手机浏览器检查通过
- [x] 记忆并发复核：编辑、启用及Worker写回先锁定当前记录，过时启用拒绝、策略同步重编译；197项PostgreSQL测试通过，包含3项锁竞争故障注入
- [x] 养护卡有效期呈现：过期/异常期限明确提示重新生成，禁止过期确认，轮询保留品种输入；12项Node及197项PostgreSQL测试通过
- [x] 最终报告及验收矩阵：`FINAL_IMPLEMENTATION_REPORT.md`

## 当前进行

- [x] 规格 SHA-256、GOAL、七个 Skills、八份审计报告校验
- [x] 独立分支 `feat/flower-v2.2.2`，起点 `08534ae`

## 下一步

- [ ] 生产授权窗口：Docker/Compose/Nginx/DNS/TLS/备份timer/回滚/共存高峰验证
- [ ] 微信平台与真实Provider配置、原生DevTools/手机验证
- [ ] 真实Pi安装、标定、防虹吸、缺水/断网/kill/相机BLE压力及真实遥测

本轮已完成可在开发环境验证的实现，未满足完整GOAL Definition of Done，不标记COMPLETE。解除对应`BLOCKERS.md`事项后按部署/实物手册继续。

## 开发证据

- `evidence/stage0-red.xml`：实现前预期失败（模块尚不存在）。
- `evidence/stage0-green.xml`：开发自动化验证；SQLite仅用于本阶段迁移/探针测试，不代表PostgreSQL或Compose运行通过。
- 未重复全面服务器审计，未执行preflight或任何生产修改。
- `evidence/stage1-green.xml`：67 passed，含缺水20次禁泵、20次重启保额、独立定时器关泵、>60秒会话及会话超时。
- Stage 1中的常驻采集/云客户端与安装诊断工具将在Stage 2接入实际设备合约后完成；真实Pi安装、BLE/摄像头压力与物理标定均BLOCKED_PHYSICAL。
- Stage 2已接入Pi常驻循环、云客户端、配置/安装/诊断工具，均未在实物安装。
- `evidence/stage2-postgres.xml`：86 passed；PostgreSQL使用解包二进制和私有Unix socket，测试结束后关闭和清理，未安装宿主数据库服务。
- DATA-001真实遥测：BLOCKED_PHYSICAL；Stage 2通过当天未连接Pi，未产生real记录。
- `evidence/stage8-recovery-audit-red.xml`：修复前6项预期失败；`evidence/stage8-recovery-audit-green.xml`：14项定向测试通过。
- `evidence/stage8-recovery-postgres.xml`：155 passed，保留1项上游弃用警告。时钟故障为注入测试，没有新增实物验收证据。
- `evidence/stage8-weather-postgres.xml`：166 passed；新增11项天气刷新/故障测试，包含真实Worker子进程与Mock天气，详见`evidence/stage8-weather.md`。

## 已知共享宿主机事实

- Debian 13；2 vCPU；约 7.5 GiB RAM；约 71 GiB 可用磁盘（审计时）
- Nginx 已占用 80/443
- aibot `nox-brain.service` 从 `/opt/asist-embodiment/brain` 运行
- 当前未发现 Docker/PostgreSQL 运行时
- Tailscale、OpenVPN 均运行

所有数值需在正式部署窗口前重新取快照。
