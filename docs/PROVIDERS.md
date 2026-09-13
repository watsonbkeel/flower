# Provider contracts v2.2.2

`PROVIDER_MODE=mock`为缺凭据时的默认。识别、资料、天气、结构化养护、记忆和通知均具有Provider边界。Mock返回值有明确来源标签；真实生产养护确认拒绝Mock资料。

`PROVIDER_MODE=http`连接独立规范化HTTPS网关，配置`PROVIDER_BASE_URL`、`PROVIDER_API_KEY`。网关操作为`/recognize`、`/search`、`/structure`、`/weather`、`/notify`。模型见`backend/flower/services/providers.py`与`knowledge.py`，设备密钥不传入Provider。

- 识别上传base64图片，返回最多3个候选、置信度、输入质量和来源。
- search接收学名、位置、城市和检索词，返回带URL/时间/来源类型的CareSource。
- structure接收明确任务及JSON Schema，养护知识和家庭记忆分别校验。Schema禁止最终水量、时长、GPIO和脉冲参数。
- weather返回观测时间、有效期、雨量/气温与来源；过期天气不会冒充实时预测。
- 天气缓存由Worker持续检查；最新已确认有效养护卡缺少可用天气时创建`weather_refresh`作业。每张卡每小时最多创建一组作业，失败最多尝试3次；活跃作业不会重复入队。写回前校验卡片确认状态、地点、来源及有效期，降雨决策只使用当前有效且来源匹配的数据。
- 网络请求超时和重试有界，调用预算保存在PostgreSQL；慢请求属于Worker。

真实识别、联网检索、LLM、天气网关和微信订阅推送尚无凭据，不宣称真实调用或消息送达。告警去重后进入独立通知job，Mock通知结果保存在job，只有real/sent回执才填写pushed_at。网关必须遵守发送幂等键，真实微信模板映射和订阅授权需在B03解除后联调。
