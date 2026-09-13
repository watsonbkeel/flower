# SAFETY_INVARIANTS.md

这些是不允许任何实现、语音入口、调试工具或平台化重构绕过的硬不变量。

1. 不确定即不浇水；SAFE_HOLD / STARTING 永不开泵。
2. 缺水、土壤关键传感器故障、时间不可信、标定缺失、额度不足、泵忙、重复命令均阻断执行。
3. 所有非 `local_fallback` 补水必须先经过云端唯一 `create_command()`；Pi 最终必须经过唯一 `can_dispense()`。
4. **任何 aibot peripheral、语音助手、本地 HTTP 调试接口、管理后台、通用 Agent 都不得直接或间接驱动 GPIO17、YYMOS 或 pump driver。**
5. LLM/ASR 结果是不可信输入，只能生成业务意图或知识；不能生成最终 mL、秒数、脉冲数、GPIO 命令。
6. `claim_ttl_sec` 只在 pending/claim 阶段使用；执行开始后只看 `session_max_duration_sec` / session deadline。
7. Pi SQLite 台账是实际执行与24小时硬限额权威；云端只做预检查、审计和展示。冲突时取更保守值并告警。
8. 开泵前先预扣额度；异常中断不得通过重启清空额度。
9. GPIO 回读只代表控制信号，不代表电机真实电流断开；不得把软件看门狗描述为硬件断电保护。
10. 普通单向阀不能作为正向防虹吸依据；必须满足液位低于开放空气喷嘴、机械固定和停泵滴漏验收。
11. 生产 `DEV_MODE` / `DEV_AUTH_BYPASS` / 非 HTTPS 基址必须 fail closed。
12. Flower 不得修改、重置或复用 aibot 的生产运行目录、设备 token、全局会话或外设执行路径。
13. real/demo/test/mock 数据必须可区分；Mock 不能当真实硬件或生产验收证据。
14. 生产数据库迁移显式执行；migration 失败不得启动新 release。
15. Flower 只发布宿主环回 18080；API/PG 不直接暴露宿主公网。

任何违反上述规则的实现必须拒绝合并，即使它能更快完成演示。
