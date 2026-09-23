# 智慧守候 v2.2.2 最终开发交付报告

## 1. 交付摘要

- 最终状态：**HARD_BLOCKED**。云端生产部署已验证；真实Provider、微信真机、异地备份及实物验收仍受阻，完整GOAL尚未完成。
- 分支：`feat/flower-v2.2.2`；交付commit为本报告所在提交，可用`git rev-parse HEAD`查询。
- 规格：v2.2.2 Server-Integrated。
- SHA-256：`4481d48605aec47660d2cdefb7a004ed2169bb8531302ecdf803c3c12718cf95`，冻结文档未修改。
- 开发地址：`http://127.0.0.1:18082/preview/`，只监听环回，明确Mock设备/数据。
- 生产地址：`https://flower.bkeel.com`；当前release：`/srv/flower/releases/208d0548ec7b9db27aa8e94c14412dbd7f466d1e`；镜像ID及证据见`evidence/deploy/2026-09-22-final-release.md`；Pi实物运行版本未取得。
- 小程序源码：`miniapp`，版本2.2.2；真实微信DevTools/手机未验收。
- 源码Stage提交：0 `eb90011`，1 `9491260`，2 `82ef59a`，3 `8c649c7`，4 `31959ac`，5 `183f75f`，6 `98f02c4`，7 `25455c5`，8 `7b32770`；交付复核修复见本报告所在提交。

## 2. 架构与实现

FastAPI提供独立用户/设备鉴权、图片、植物、命令、趋势、记忆及告警API。PostgreSQL保存命令、小时聚合、作业租约和审计。Worker独立进程、初始并发1，处理有界Provider请求、识别、养护、记忆、通知和清理。

完整决策只在云端。所有云端补水统一进入`create_command()`；Pi执行前经`can_dispense()`、SQLite预扣、watchdog、独立水位线程及单调时钟会话截止。设备独立遥测线程使用自己的SQLite和HTTP连接，长会话中继续报告WATERING。fallback的版本/哈希/时区/有效期均校验，在线撤销清除缓存，执行中到期停泵。

Pi包含ADS1115、P451、GPIO17、SHT30/被动ATC1441 BLE及USB相机适配、标定数据校验、安装/诊断/紧急关泵/systemd文件。加密或不兼容BLE明确报告不可用并可切换有线Provider；未声称支持未经验证的具体小米型号。

小程序覆盖状态、手动补水、自动守护、品种确认、养护卡、趋势、事件、记忆图文/规则和告警。浏览器预览是额外开发客户端，不能替代原生微信验收。真实知识/天气/微信使用Provider和秘密配置边界，当前运行的是Mock。

独立离线数据包位于`backend/flower/data/offline_demo.json`，Mock Provider直接读取并通过原有Schema校验。包含Top3、两条来源展示记录、知识、模拟天气、待确认记忆规则和模拟通知；不包含真实遥测或执行参数。规格21.2的17项交付文件映射见`evidence/stage8-delivery-inventory.md`，文件齐备不代表生产或实物验收完成。

## 3. 共享宿主机边界

未修改`/root/aibot`或`/opt/asist-embodiment`；aibot仍由原systemd运行。根据2026-09-22授权安装Docker/Compose，仅在`/srv/flower`部署Flower独立数据/配置/备份并新增Flower专属Nginx站点与证书。未手改UFW/nft、Tailscale、OpenVPN或City Front站点。没有重复全面服务器审计；安装与建Flower网络前后实时快照见`evidence/deploy/`。

Compose项目为独立`flower-prod`，生产只发布`127.0.0.1:18080`；API/PG不发布宿主端口。四服务健康、证书续期演练、显式migration、生产备份/独立恢复、无构建短时回滚均有实际运行证据。真实语音高峰及VPN客户端端到端仍待验收。

## 4. 自动化证据

| 命令/范围 | 结果 | 证据 |
|---|---|---|
| `PYTHONPATH=backend .venv/bin/python scripts/test_postgres.py .venv/bin/pytest --junitxml=evidence/stage8-offline-data-postgres.xml` | PASS，222项 | [PostgreSQL回归](evidence/stage8-offline-data-postgres.xml) |
| Pi时钟恢复、回执分页及适配器定向测试 | PASS，14项；修复前6项失败 | [复核说明](evidence/stage8-recovery.md) |
| 天气缓存刷新、失败重试、上下文变更与降雨输入 | PASS，11项，Mock Provider/独立Worker子进程 | [天气复核](evidence/stage8-weather.md) |
| `npm --prefix miniapp test` | PASS，13项 | [Node执行记录](evidence/stage8-species-photo-node-green.tap) |
| 本轮完整PostgreSQL回归、小程序原生测试 | PASS，225项Python、14项Node；含备份轮转失败测试先行 | [生产终检](evidence/deploy/2026-09-22-final-release.md) |
| 识别候选排序、重拍选择清除、手动/候选切换、低置信度提示 | PASS，Mock，桌面/手机 | [识别确认](evidence/stage8-recognition.md) |
| Playwright桌面1440x1000、手机390x844六页面/图像/canvas/溢出 | PASS，Mock | [浏览器检查](evidence/stage5-browser.json) |
| 浏览器pending到succeeded、养护确认、记忆规则、自动开关 | PASS，Mock | [工作流](evidence/stage8-browser-workflow.json) |
| 天气零值/过期/缺失、独立来源标签、刷新保留输入，桌面/手机 | PASS，Mock | [天气UI](evidence/stage8-weather-browser.json)、[复核说明](evidence/stage8-weather-ui.md) |
| 慢任务失败后重新操作、同键重放、并发入队、浏览器重试 | PASS，Mock/独立PG/SQLite | [任务复核](evidence/stage8-job-retry.md) |
| 品种变更与记忆规则撤销后的策略一致性 | PASS，Mock/独立PG | [品种](evidence/stage8-species.md)、[记忆策略](evidence/stage8-memory-policy.md) |
| 记忆编辑、启用和Worker写回并发竞争 | PASS，3项真实PG锁竞争/Mock规则 | [并发复核](evidence/stage8-memory-concurrency.md) |
| DB+uploads+manifest独立恢复、校验和与保留策略 | PASS，真实独立PG | [恢复测试](tests/test_delivery.py)、[Stage 7](evidence/stage7-postgres.xml) |
| 后端/Pi依赖审计 | PASS，无已知漏洞 | [backend](evidence/backend-dependency-audit.json)、[Pi](evidence/pi-dependency-audit.json) |
| Ruff及`git diff --check` | PASS | [Stage 8说明](evidence/stage8.md) |
| 开发环回100请求、4并发 | p95 39.26ms | [开发探针](evidence/development-health.json) |

未屏蔽一条Starlette TestClient/httpx弃用警告。依赖审计是验证时已知漏洞检查，不代表未来无漏洞。PG测试使用解包二进制和私有Unix socket，结束后关闭销毁；未安装宿主DB服务。

## 5. 实物测试

| 项目 | 结果 | 证据 |
|---|---|---|
| Pi安装/开机自启、GPIO/ADS1115/P451/YYMOS/泵 | BLOCKED | B05，无实物运行证据 |
| 三次流量、三次10分钟滴漏、最小剂量及土壤标定 | BLOCKED | B05/B08，无测量值 |
| 水面低于出口5cm、固定空气间隙、防虹吸/≤3mL滴漏 | BLOCKED | 无照片/量杯记录 |
| 缺水20次、十次kill后≤5秒电流恢复 | BLOCKED | 软件Mock通过，不填写物理测量值 |
| BLE与每分钟相机上传并发30分钟 | BLOCKED | 无实物压力记录 |
| 真实断网、NTP故障、7天遥测 | BLOCKED | 无real数据 |

## 6. 验收矩阵

PASS只覆盖本行注明的类型；包含部署/实物要求的条目不会以Mock替代。

| ID | 状态 | 证据/限制 |
|---|---|---|
| SPEC-001 | PASS | 规格SHA、基础测试；未使用旧规格实现 |
| HOST-001 | PASS | aibot目录未修改，systemd服务保持active；无真实语音高峰证据 |
| HOST-002 | PASS | 独立flower-prod Compose四服务及Nginx入口实际健康 |
| HOST-003 | PASS | docker inspect确认仅proxy发布环回18080 |
| HOST-004 | BLOCKED | 前后快照及闲时共存通过；真实VPN客户端/语音高峰待B07 |
| HOST-005 | BLOCKED | Worker并发1与资源预算已部署；高峰容量待B07 |
| AUTH-001 | PASS | production鉴权绕过拒绝测试 |
| AUTH-002 | PASS | production非HTTPS拒绝测试 |
| NET-001 | PASS | 客户端TLS验证开启，HTTP只允许开发环回 |
| NET-002 | BLOCKED | DNS/TLS和公网API通过；Pi实物HTTPS请求待B05 |
| VOICE-001 | PASS | 泵驱动调用边界静态测试；无aibot接入 |
| STATE-001 | BLOCKED | SAFE_HOLD所有来源Mock拒绝；实物待B05 |
| CMD-001 | PASS | pending领取截止与独立启动宽限期测试 |
| CMD-002 | PASS | 多脉冲超过60秒、绝对会话截止、进度不续期 |
| DB-001 | PASS | 真实PG主控植物部分唯一索引拒绝违规 |
| DB-002 | PASS | 真实PG活跃补水部分唯一索引及100并发领取仅1成功 |
| MIG-001 | PASS | API/Worker无自动migration；开发启动器显式运行 |
| MIG-002 | PASS | 生产显式migration执行，当前head `0003_retention` |
| REL-001 | PASS | 固定SHA镜像已构建，清单记录实际ID和归档校验和 |
| REL-002 | PASS | 两版间无构建切换并恢复；旧版存在轮转缺陷，不作长期回滚目标 |
| HEALTH-001 | PASS | /health独立存活探针测试 |
| HEALTH-002 | PASS | /ready检查DB和migration head |
| BACKUP-001 | PASS | 生产timer启用并触发，同日两release备份保留验证通过；仅本机 |
| BACKUP-002 | PASS | 生产最新空业务库恢复19张表；开发非空图片及哨兵另有测试 |
| BACKUP-003 | BLOCKED | B06，无异地目的地 |
| PERF-001 | NOT_RUN | 仅开发SQLite p95 39.26ms；生产设备接口待测 |
| PERF-002 | BLOCKED | B07，无aibot高峰/语音基线对照 |
| PI-001 | BLOCKED | Mock缺水20次禁泵通过，缺物理证据 |
| PI-002 | BLOCKED | 无十次kill后电流OFF测量 |
| PI-003 | BLOCKED | B05/B08，无实测标定 |
| DEC-001 | PASS | 云端唯一完整确定性决策，Pi仅执行与fallback |
| DEC-002 | PASS | LLM知识Schema禁止执行参数 |
| DATA-001 | BLOCKED | Stage 2后无Pi可连接，尚无首条real遥测 |
| DATA-002 | PASS | API/Mock UI来源隔离、缺口覆盖、Mock空气不混入real字段 |
| JOB-001 | PASS | 租约恢复、尝试次数、旧Worker结果隔离、进程有界 |
| API-001 | PASS | 浏览器创建pending到终态验证，原生状态映射测试 |
| HW-001 | BLOCKED | 无防虹吸结构和滴漏物理证据 |
| DEMO-001 | BLOCKED | Mock离线流程通过；真实硬件/DevTools待B05/B09 |

## 7. 安全与数据专项

规格21.4的25项Definition of Done对照如下，避免将软件阶段完成等同于总目标完成：

| DoD | 结果 | 对照 |
|---|---|---|
| 1 Docker一键部署 | PASS | 独立Compose四服务上线、固定SHA release |
| 2 API/Worker健康 | PASS | 生产健康探针、备份重启后公网ready200 |
| 3 Pi自启动 | BLOCKED | systemd文件已有，实物未安装 |
| 4 ADS1115/P451/YYMOS/泵可用 | BLOCKED | 仅适配/Mock |
| 5 三项标定 | BLOCKED | B05/B08 |
| 6 防虹吸 | BLOCKED | 缺测量 |
| 7 相机上传 | BLOCKED | Mock上传通过，实物待测 |
| 8 Top3与手动输入 | PASS（Mock） | Worker/API自动化 |
| 9 养护知识有来源 | BLOCKED | 来源结构已验证，真实检索凭据缺失 |
| 10 云端决策测试 | PASS | 确定性决策测试 |
| 11 断网fallback | BLOCKED | Mock策略/时区/执行通过，实物断网待测 |
| 12 SAFE_HOLD不浇水 | BLOCKED | 所有来源Mock通过，物理门待测 |
| 13 跨重启限额/恢复 | PASS（Mock） | SQLite重启/24小时恢复测试 |
| 14 小程序pending到succeeded | BLOCKED | 浏览器/状态映射通过，原生微信待验收 |
| 15 真实趋势来源 | BLOCKED | 标签/缺口/隔离通过，尚无真实遥测 |
| 16 家庭经验影响留痕 | PASS（Mock） | 决策对照与审计事件 |
| 17 BLE备用Provider | PASS（Mock） | Provider切换测试，具体设备待测 |
| 18 相机BLE并发 | BLOCKED | 实物30分钟测试未运行 |
| 19 OFFLINE_DEMO DevTools | BLOCKED | Mock端到端通过，B09未解除 |
| 20 两类超时 | PASS | claim/启动宽限/session分别验证 |
| 21 fallback时区 | PASS | IANA策略测试 |
| 22 两个部分唯一索引 | PASS | PostgreSQL违规写入/并发测试 |
| 23 图片/聚合/清理 | PASS | 低空间、来源隔离、校验后删除 |
| 24 双账本对账测试 | PASS | API与SQLite完整往返、篡改/迟到/时间测试 |
| 25 空环境部署手册 | PASS | 首次空库经备份恢复、显式迁移、发布验证；异地灾备另见B06 |

开泵前持久预扣、缺水/传感器/时钟/模式故障中途关泵、独立watchdog、跨重启保额均通过Mock故障测试。GPIO读回不是电流测量，普通单向阀不作为正向防虹吸装置。

按command_id、脉冲序号/水量、可信时间和本地已持久回执对账；缺证据或篡改不减少额度。迟到结果可被接收并核验，但保留云端timed_out历史。不确定记录保守占额24小时且保留审计。fallback补水按local_id写独立审计会话，重放不重复记账。

交付复核修复了Pi启动后NTP校时导致时间永久不可信的问题：跳变立即失去信任，稳定30秒后重新验证NTP，恢复FULL仍须经过原有180秒健康窗口。NTP探测期间的跳变也拒绝信任；共享时钟状态由锁保护。回执查询在100项分页前过滤本地fallback，避免大量历史fallback记录阻塞云端命令对账，保留原始审计与额度。

天气缓存不再只随养护卡生成更新。Worker为最新已确认有效养护卡的缺失/过期天气创建幂等刷新job，失败最多尝试3次，每小时最多新建一组尝试；已有活跃job不重复入队。网络请求在独立作业进程执行，写回前复核养护卡、地点和数据来源。过期、未来时间、格式错误或来源不匹配的天气不参与降雨判断，也不覆盖已有缓存。真实Provider验收仍待B04。

原生小程序与浏览器预览共用天气展示规则：0°C和0mm正确保留，缺失值不填0；过期、时间异常、来源不匹配明确标示且隐藏当前读数。天气来源与养护知识来源独立显示，并标出观测时间。浏览器天气定时刷新只更新环境区域，不清空品种确认表单。

识别响应按置信度降序返回候选，最高项达到0.75才默认选择；低于0.45提示重拍。原生页面收到新图片时清除旧选择，同图轮询保留用户输入。两个客户端均按最后一次手动编辑或候选选择提交品种，仍须用户确认。

重拍期间不再显示旧拍摄候选。接口按最新拍照命令的服务器执行起止时间限定图片范围，排除记忆照片，明确显示拍照、排队、识别和失败状态；最新图片失败也不回退历史结果。浏览器与原生页面轮询更新结果，保留同图用户选择；缺图与拍照失败不误报补水失败。契约与测试见`evidence/stage8-recognition-lifecycle.md`。

品种确认提交当前识别的图片ID，后端验证植物、设备及图片用途并锁定保存主图，不再自动使用最后上传的照片。无图片ID时保留现有主图。清理任务锁定过期图片并跳过正在确认的记录，避免确认与清理竞争后主图引用丢失。见`evidence/stage8-species-photo.md`。

养护卡按冻结规格12.4显示有效期与更新提示。过期或期限异常时，历史已确认状态不再显示为当前有效；确认按钮禁用，保留重新生成入口。浏览器局部刷新状态，原生页面使用同一状态模型，不清空用户的品种输入。见`evidence/stage8-care-validity.md`。

养护研究与记忆整理以每次用户操作的请求键去重，不再被资源更新时间绑定到旧的失败job。相同请求键重放返回原job；新操作创建新job并保留失败历史。通用作业入队使用数据库原子冲突处理，8个并发同键请求只写入一条job。重新生成养护卡仍产生待确认的新版本，不自动替换已确认知识。

品种重新确认时，旧养护卡和离线策略立即在云端失效，旧卡不能通过再次确认恢复。品种确认、养护卡激活及自动模式切换按设备、植物的统一顺序加锁，与命令创建串行化。并发确认和品种修改、研究期间品种变化的故障注入已通过；Pi缓存撤销仍需设备下一次同步。

编辑、解除植物关联或重新整理已启用的家庭经验时，按当前已确认规则重编译原植物的fallback策略；没有有效养护卡则撤销策略。每次发新版本同时停用旧版本，避免新版本到期后重新下发旧策略。策略JSON和云端有效期均受养护卡剩余有效期与7天上限约束，哈希按最终期限计算。

记忆编辑、启用及Worker结果写回在读取可变规则状态时使用行锁，避免读取旧启用标志后遗漏撤销或策略重编译。并发编辑已清除结构化规则时，后到的启用请求返回409，不能让未确认原文生效。三个PostgreSQL锁竞争故障注入均先失败后通过。

Worker在Provider调用前和结果提交时检查租约；提交检查失败回滚同一事务中的识别、养护卡、天气、记忆/策略和通知状态。故障注入覆盖5类结果及恢复重试，见`evidence/stage8-worker-atomic.md`。已发送的外部通知不能由数据库回滚撤回，Provider仍须遵守发送幂等键；测试没有实际发送通知。

Worker持续维护主控植物的有效fallback策略，默认提前86400秒续期（`FALLBACK_RENEW_BEFORE_SEC`）。续期复用唯一编译器和设备锁，保持7天及养护卡有效期上限，不续发未确认/过期养护卡或已撤销设备。策略期限已抵达养护卡到期时间时不重复生成。模拟跨周续期及Pi哈希/版本验证见`evidence/stage8-policy-renewal.md`，不是实物连续运行证据。

小时聚合按设备、植物、UTC小时和来源隔离；仅完整小时入库。清理前复核样本数、覆盖时间、平均/极值和水位比，30天raw/365天hourly下限受配置约束。晚到已清理小时的数据保留待核验，不覆盖旧聚合。被植物/记忆引用的图片长期保留。

## 8. 备份、发布与回滚

`scripts/backup.py`打包PG custom dump、uploads、release manifest和校验和，保留7份日备份/4份周备份，并额外保护最近两个release的最新备份。恢复只允许新建`flower_restore_*`测试库及新的图片目录，不覆盖现有DB。生产timer已经手动触发并验证独立恢复；尚无异地目的地。生产图片目录当前为空，非空图片恢复只在开发测试证明。

`scripts/release.py`从干净commit导出源码和清单；未构建明确为NOT_BUILT。完成镜像构建后记录实际ID，生产脚本核验文件/镜像和近期恢复证明，migration显式执行。回滚使用上一SHA且`--no-build --pull never`，不自动alembic downgrade。

`scripts/deploy.sh`提供规格要求的发布入口，沿用生产授权门。实际发布先等待PG健康、执行显式migration，再等待API/Worker健康后原子切换current；无构建双向回滚演练通过。首次备份发现静态DNS导致API重启后502，已以动态解析修复并实际复验；随后发现同日轮转删除跨release备份，已修复并两次触发timer验证。证据见`evidence/deploy/2026-09-22-final-release.md`。

## 9. 尚未完成与恢复路径

已解除B01生产授权、B02 DNS/TLS和B10 GitHub发布。剩余`BLOCKERS.md` B03/B04/B05/B06/B07/B08/B09：微信教育版控制台/真机、真实Provider网关与预算、实物与标定规则、异地备份及共享宿主真实语音高峰。B08冻结规格内部1秒maintenance上限与10秒流量标定要求的矛盾只暂停实际标定开泵路径。完整Git历史已推送至公开仓库`watsonbkeel/flower`的`main`；一次性凭据未写入远端、Git配置、提交或证据，临时文件已删除。

下一步无需重做服务器全面审计或重复已验生产发布。外部凭据经`/srv/flower/shared/config/production.env`注入后重新运行真实Provider/微信联调并验收；硬件按`docs/OFFLINE_DEMO.md`补采测量；B06提供异地备份目的地。生产保持Mock Provider直到真实服务证据成立，凭据禁止进入Git。

开发复验命令：`PYTHONPATH=backend .venv/bin/python scripts/test_postgres.py .venv/bin/pytest`。完整生产和实物Definition of Done满足之前，终态保持HARD_BLOCKED。
