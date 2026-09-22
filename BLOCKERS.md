# BLOCKERS.md

以下项目不阻塞普通代码开发，但会阻塞对应真实部署/验收。

| ID | 事项 | 阻塞范围 | 状态 |
|---|---|---|---|
| B01 | 首次安装 Docker 与宿主网络变更授权 | Docker 26.1.5、Compose 2.26.1、Flower 独立容器网络已部署并完成前后检查 | RESOLVED |
| B02 | `flower.bkeel.com` DNS、TLS | 解析 43.161.224.25；受信任证书及续期演练、HTTPS 健康均通过；微信合法域名另见 B09 | RESOLVED |
| B03 | 微信教育版项目 AppID、AppSecret、订阅消息模板/权限 | 真实微信登录与推送 | BLOCKED_EXTERNAL |
| B04 | Flower 专用识别、园艺检索、LLM、天气真实服务的规范化 HTTPS 网关或各原生 API 凭据、模型、预算 | 真实 AI 调用与额度验收；生产仅 Mock 且 Mock 登录被拒绝 | BLOCKED_EXTERNAL |
| B05 | 树莓派实物接线、泵/滴漏/土壤标定 | 自动守护物理验收 | BLOCKED_PHYSICAL |
| B06 | 异地备份目标与可用访问方式 | 本机备份恢复通过，异地灾备验收 | BLOCKED_EXTERNAL |
| B07 | 用户发起的 aibot 真实语音高峰测试时段 | 共存容量和真实语音延迟最终验收 | BLOCKED_EXTERNAL |
| B09 | 微信教育版控制台合法 request/upload/download 域名、真实 AppID 导入、DevTools、手机授权/发布 | 原生小程序登录、发布和订阅消息端到端验收 | BLOCKED_EXTERNAL |

开发代理应先用 Mock/独立测试环境推进，不得把这些未完成项伪装成 PASS。

## 开发交付时仍需用户提供

- B03/B09：用户在教育版控制台获取 AppID/AppSecret，配置 `flower.bkeel.com` 的 request/upload/download 合法域名、确认订阅消息权限/模板，在微信开发者工具导入 `miniapp`，真机登录并提交发布。AppSecret 仅写入 `/srv/flower/shared/config/production.env`（0600），绝不写前端/Git；必要时提供教育版专用 API 差异资料。
- B04：用户选定 Flower 专用四类真实服务和调用预算，提供规范化 HTTPS 网关的 URL、key、模型/额度及 `/recognize`、`/search`、`/structure`、`/weather` 契约；若仅有厂商原生 API，提供厂商名称、接口/权限/模型资料以实现适配。通过生产私有配置注入；不得引用 aibot 私有凭据。
- B05/B08：用户连接实物并提供标定/防虹吸测量记录，明确规格内部1秒维护上限与10秒流量标定的矛盾。任何实际开泵前必须解决。
- B06/B07：提供可用异地备份位置及密钥注入方式，并安排用户自己操作的 aibot 真实语音高峰窗口；当前服务 active/空闲检查不代替远端备份和语音体验证据。

没有真实设备，因此Stage 2当天真实遥测未能开始，当前不能提交真实七天趋势、防虹吸、滴漏或kill后电流恢复证据。

## 规格内部待澄清项

- B08：规格7.4要求10秒流量/5秒滴漏标定，5.4.2及8.2将本机maintenance_test限制为1秒，14.3又规定所有非fallback补水经过云端。暂停真实标定开泵路径；继续实现测量数据校验、Mock执行与不通电工具，不新增远程maintenance命令或绕过安全门。需明确专用标定模式的授权及安全门规则。
- 规格12.2示例残留`spec_version=2.2.1`，依据0.3、3.5及SPEC_CURRENT唯一版本要求统一实现`2.2.2`；冻结文档不修改。
