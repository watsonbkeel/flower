# EXTERNAL_INPUTS.md

## 已知服务器事实（2026-09-13 审计）

- Debian 13，2 vCPU，约 7.5 GiB RAM；审计时约 6.7 GiB 可用、约 71 GiB 磁盘可用。
- Nginx 已占 80/443，现有 `cs.bkeel.com` 指向 City Front。
- aibot 生产服务 `nox-brain.service` 从 `/opt/asist-embodiment/brain` 运行；该生产目录存在未提交漂移，不得由 Flower 项目整理。
- aibot 8889 已使用；Tailscale、OpenVPN、DERP 等现有网络服务必须保留。
- 当前未发现 Docker 和 PostgreSQL 运行时；首次安装 Docker 属共享宿主机生产变更。
- Flower 推荐生产环回端口 18080，staging 18081，development 18082。

## 不阻塞代码开发，可先 Mock

- 植物识别/搜索/天气/LLM Provider 与独立项目 Key
- 微信 AppID/AppSecret、订阅消息模板
- `flower.bkeel.com` DNS/TLS
- 小米温湿度计型号/MAC/bindkey
- 摄像头最终型号
- 泵和土壤标定实测值

## 正式上线前必须由用户/控制台完成或授权

- 首次 Docker 安装与共享宿主网络变更窗口；
- 新 Flower Nginx server block、DNS、证书；
- 微信后台 request/upload/download 合法域名配置；
- 根据实际托管地区核验当期备案/主体/平台要求；
- 微信真实 AppID/secret/体验成员/发布；
- 树莓派与12V硬件接线、泵/滴漏/土壤标定；
- 异地备份目标；
- 同机真实语音高峰共存测试时段。

## 规则

缺失输入时实现接口、Mock、契约测试和配置项。任何未实际完成的域名、微信、Provider、物理或容量项都写 `BLOCKED/NOT_RUN`，不得用占位值标 PASS。
