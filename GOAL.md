# GOAL.md

## 唯一目标

在 `/root/flower` 独立仓库中，严格依据 `SPEC_CURRENT.md` 指向的 v2.2.2 Server-Integrated 冻结规格，完整实现、测试、部署并交付“智慧守候·AI植物守护与记忆灌溉系统”单设备、单盆植物 MVP。

### 云端

在现有共享服务器上保持 aibot 不变，Flower 独立部署：

- 宿主机现有 Nginx 继续独占 80/443；
- Flower Compose：`proxy + api + worker + postgres`；
- 只发布 `127.0.0.1:18080 -> proxy`；
- API/PG 不发布宿主端口；
- Worker 初始 `JOB_MAX_CONCURRENCY=1`；
- PostgreSQL、uploads、backup、secret 独立；
- 生产 release 位于 `/srv/flower/releases/<git-sha>`，镜像使用 commit SHA tag；
- production migration 显式执行，不随 API/Worker 启动自动运行。

### 树莓派

实现 USB 摄像头、ADS1115 土壤传感器、P451 水位、小米 BLE/有线温湿度备用、YYMOS-1 + 12V 蠕动泵、本地 SQLite 安全台账、systemd、安全 fallback。

### 小程序与 AI

完成识别确认、养护卡、状态、补水、自动守护、真实趋势、记忆、告警；识别/检索/LLM/天气全部 Provider 化并带 Mock。

### 安全

- 单一云端完整决策；
- `create_command()` + `can_dispense()` 双门；
- 语音/aibot peripheral 不得旁路控制泵；
- claim TTL 与 session duration 分离；
- Pi 台账为硬限额权威；
- SAFE_HOLD 永不浇水；
- 物理防虹吸和脉冲闭环；
- real/demo/mock 明确区分。

## 当前范围边界

当前 MVP 不建设统一家庭 AI 平台、不抽共享 Device Registry、不增加云 ASR、不迁移 aibot。未来语音只预留“输入意图 -> Flower 领域服务 -> create_command”的扩展边界。

## 完成标准

只有 v2.2.2 Definition of Done 全部满足，并在 `FINAL_IMPLEMENTATION_REPORT.md` 中逐项提供自动化、部署或实物证据，目标才算完成。生产变更必须在明确授权窗口进行。
