# OFFLINE_DEMO v2.2.2

## 已验证的软件演示

离线数据包为`backend/flower/data/offline_demo.json`，包含Top3候选、两条来源展示记录、养护知识、天气读数、待确认家庭规则和模拟通知结果。`MockProviders`直接读取此文件，源码发布包和后端镜像均携带它；配置`PROVIDER_MODE=mock`即可使用，无需外部Provider连接。所有值仍标记mock，来源URL仅为演示引用，不代表本次联网检索。天气与来源时间在模拟调用时生成，不是真实观测或抓取时间。

示例照片为`miniapp/assets/plant.jpg`，明确不是用户实物。开发启动器生成带mock标签的趋势；数据包不包含real遥测、命令、水量或GPIO参数。真实设备仍通过原有建单、安全门和本地账本执行，不能导入此包伪造真实趋势或绕过确认。

`backend/tests/test_full_mock_flow.py`运行图片上传、Mock Top3、品种确认、异步养护卡、显式确认、`create_command()`、Pi `can_dispense()`、多脉冲、回执和跨API对账。所有遥测与执行标注mock。它使用加速单调时钟，不是物理泵演示。

开发预览：`.venv/bin/python scripts/dev_server.py`，打开`http://127.0.0.1:18082/preview/`。

网页与原生小程序共享API和状态映射。原生项目目录为`miniapp`；设置`config.js`后导入微信DevTools。当前未提供AppID，DevTools真实验收为BLOCKED。

## 比赛前实物门

1. 完成`docs/HARDWARE_WIRING.md`接线、断电检查、P451/土壤标定及B08标定时长规则确认。
2. 记录三次流量、三次10分钟滴漏；最高水面低于固定自由出水口至少5cm。普通单向阀不作为正向防虹吸保证。
3. 准备现场电脑的独立Flower Compose、手机热点、备用SD卡和管路；本服务器未安装Docker。
4. 真实设备始终发送real遥测；缓存/Mock知识明确标记其来源，不能把模拟曲线合并到真实历史。
5. OFFLINE_DEMO仍通过云端建单和Pi安全门，不向语音/aibot peripheral开放GPIO。公网断网时，由现场独立云端提供业务API；完全无云时仅执行有效fallback。
6. 录像记录pending、领取、执行、脉冲、结果和安全拒绝。没有实物录像时只报告Mock演示。

## 必须补采的证据

- 十次kill -9与重启，断电流恢复最大值不超过5秒。
- 缺水20次均不开泵；土壤断线、NTP失信、策略到期和额度不足拒绝。
- BLE扫描与每分钟相机上传持续30分钟，安全线程不受阻塞。
- 断网5分钟进入保守策略、超过1小时SAFE_HOLD、恢复稳定3分钟后FULL。
- 启动真实遥测后每天检查缺口；七天图仅在真实覆盖达到后验收。

以上实物项全部尚未运行。不要把当前软件证据作为接通12V泵电源的授权。
