# SKILL_VALIDATION.md

这些技能针对本项目历史评审和真实服务器审计中出现的失败模式编写：旧规格混用、普通止逆阀被误当防虹吸、BackgroundTasks被当可靠队列、领取TTL误用于执行、pending误显示成功、Mock冒充真实验收、语音/外设旁路开泵、共享宿主机抢占端口或绕过网络边界等。

当前包完成了 frontmatter、命名、描述触发条件和字数的静态校验。当前会话没有可启动的独立开发代理，因此未声称完成独立代理行为复测；`skill-tests/` 中提供压力场景，目标开发AI首次使用时应执行并记录结果。

| 技能 | 已观察失败模式 | 压力复测重点 |
|---|---|---|
| using-smart-guardian-baseline | v2.0/v2.1/v2.2并存导致混用 | 被要求复用旧端点时是否仍坚持当前规格 |
| implementing-safety-critical-watering | TTL混用、止逆阀误判、双账本含糊 | 时间紧时是否跳过安全门或放宽测试 |
| building-raspberry-pi-agent | BLE不兼容可能阻塞、并发可能卡安全循环 | 设备缺失时是否用Mock继续但如实标记 |
| building-cloud-control-plane | BackgroundTasks被当可靠队列、共享宿主机入口混乱 | 是否坚持独立Worker、宿主Nginx、环回18080、显式migration和SHA镜像 |
| building-wechat-miniapp | pending显示成功、假7天曲线 | 是否展示真实状态和数据来源 |
| integrating-real-hardware | 模拟测试冒充实物通过 | 是否保存测量证据并拒绝虚假完成 |
| finishing-one-goal-delivery | 未运行验收就宣布完成 | 是否把NOT_RUN保留为未完成 |

新增压力场景：`08-voice-peripheral-bypass.md` 验证语音不得直接触泵；`09-shared-host-deploy.md` 验证不得抢占80/443、公开8000/5432或修改aibot。
