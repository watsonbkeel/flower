# ACCEPTANCE_MATRIX.md

| ID | 要求 | 类型 | 证据 |
|---|---|---|---|
| SPEC-001 | 仅实现 v2.2.2 | 静态 | 规格哈希、代码搜索 |
| HOST-001 | Flower 未修改 `/opt/asist-embodiment` | 静态/部署 | pre/post hash/git/status |
| HOST-002 | 宿主 Nginx 唯一占用80/443，Flower只发布127.0.0.1:18080 | 部署 | ss + compose config |
| HOST-003 | API 8000、PG5432无宿主发布 | 部署 | ss/docker inspect |
| HOST-004 | Docker变更后 UFW/nft/Tailscale/OpenVPN/City Front/aibot无回归 | 集成 | pre/post报告 |
| HOST-005 | Worker初始并发1，资源预算受控 | 配置/运行 | env + metrics |
| AUTH-001 | production + DEV_AUTH_BYPASS=true 拒绝启动 | 自动化 | 启动测试 |
| AUTH-002 | production + 非HTTPS APP_BASE_URL 拒绝启动 | 自动化 | 启动测试 |
| NET-001 | 开发期不使用 verify=False | 静态 | 搜索/测试 |
| NET-002 | 正式Pi业务使用有效HTTPS域名 | 集成 | TLS请求证据 |
| VOICE-001 | aibot peripheral/语音/调试接口不能直接驱动pump/GPIO17 | 静态+自动化 | 依赖边界测试 |
| STATE-001 | SAFE_HOLD所有来源禁泵 | 自动化+实物 | 逐来源测试 |
| CMD-001 | claim TTL仅约束pending | 自动化 | 超时测试 |
| CMD-002 | session deadline独立于claim TTL | 自动化 | >60秒会话 |
| DB-001 | 一个设备仅一主控植物 | DB | 部分唯一索引 |
| DB-002 | 一设备仅一活跃dispense | DB | 部分唯一索引 |
| MIG-001 | API/Worker entrypoint不自动migration | 静态/部署 | entrypoint检查 |
| MIG-002 | production migration显式一次性运行 | 部署 | 发布日志 |
| REL-001 | 镜像tag使用commit SHA | 部署 | image inspect/release manifest |
| REL-002 | 上一release可`--no-build`回滚 | 部署 | 回滚演练 |
| HEALTH-001 | `/health`只做存活探针 | 自动化 | API测试 |
| HEALTH-002 | `/ready`检查DB/migration readiness | 自动化 | API测试 |
| BACKUP-001 | DB+uploads+manifest定时备份 | 运行 | timer/日志 |
| BACKUP-002 | 独立测试实例恢复成功 | 集成 | restore evidence |
| BACKUP-003 | 异地备份目标存在 | 运维 | offsite evidence |
| PERF-001 | Flower快速设备接口p95 <500ms目标 | 性能 | 压测报告 |
| PERF-002 | aibot真实对话相对基线劣化≤20%目标 | 性能 | 同机共存测试；无高峰样本则NOT_RUN |
| PI-001 | P451缺水20次禁泵 | 实物/Mock | 日志/测量 |
| PI-002 | kill后≤5秒恢复OFF | 实物 | 10次最大值 |
| PI-003 | 泵流量、滴漏mean/max、最小剂量标定 | 实物 | 标定表 |
| DEC-001 | 完整决策只在云端 | 静态 | Pi无完整修正公式 |
| DEC-002 | LLM输出无执行参数 | 自动化 | Schema测试 |
| DATA-001 | Stage2后真实遥测立即开始 | 运行 | 首条real时间戳 |
| DATA-002 | demo/test/mock不冒充real | 自动化+UI | API/UI证据 |
| JOB-001 | Worker重启任务可恢复 | 自动化 | 重启测试 |
| API-001 | pending不显示浇水成功 | UI | 状态链证据 |
| HW-001 | 防虹吸结构/空气间隙/滴漏合格 | 实物 | 照片+测量 |
| DEMO-001 | OFFLINE_DEMO明确标识外部数据，硬件链真实 | 集成 | 演示证据 |

最终报告逐项填写 PASS / FAIL / NOT_RUN / BLOCKED；NOT_RUN 不能算完成。
