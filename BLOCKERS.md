# BLOCKERS.md

以下项目不阻塞普通代码开发，但会阻塞对应真实部署/验收。

| ID | 事项 | 阻塞范围 | 状态 |
|---|---|---|---|
| B01 | 首次安装 Docker 与宿主网络变更授权 | 同机真实 Compose 部署 | OPEN |
| B02 | `flower-api.bkeel.com` DNS、TLS、微信合法域名/平台要求 | 正式公网/小程序上线 | OPEN |
| B03 | 微信 AppID/AppSecret/模板 | 真实微信登录与推送 | OPEN |
| B04 | 植物识别/搜索/天气/LLM 真实 Provider 凭据 | 真实 AI Provider 验收 | OPEN |
| B05 | 树莓派实物接线、泵/滴漏/土壤标定 | 自动守护物理验收 | OPEN |
| B06 | 异地备份目标 | 生产可恢复性验收 | OPEN |
| B07 | aibot 真实语音高峰共存测试授权/时段 | 同机容量最终验收 | OPEN |

开发代理应先用 Mock/独立测试环境推进，不得把这些未完成项伪装成 PASS。
