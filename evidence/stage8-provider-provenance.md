# 2026-09-23 Provider 来源边界验证

规格 v2.2.2 Server-Integrated；开发起点 `98a0116bbae788becb061b7d45bd73ebf9e25547`。

问题：规范化 HTTP 网关原先只对植物识别要求 `source_type=real`；若检索/天气返回 Mock 标签，单独调用仍会放行；若通知返回 `status=mock`，Worker可能记录成功作业但不能证明已送达。当前修复拒绝检索中的任意非真实来源、非真实天气以及状态非 `sent/real` 的通知回执。保留 `PROVIDER_MODE=mock` 的显式模拟行为，不给模拟数据贴真实标签。

- 实现前先新增四项 HTTP MockTransport 来源测试及混合检索测试；由于当时的受限沙箱无法执行测试夹具，首次运行超时退出，**不作为预期失败的运行证据**。环境恢复后新增通知回执测试，实测预期失败：`PYTHONPATH=backend .venv/bin/pytest -q backend/tests/test_providers.py -k 'rejects_non_real_results and notify'`，exit 1，`Failed: DID NOT RAISE DomainError`；修复后定向 `pytest -q backend/tests/test_providers.py`，exit 0，7 passed。
- `PYTHONPATH=backend .venv/bin/python scripts/test_postgres.py .venv/bin/pytest -q --junitxml=evidence/stage8-provider-provenance-postgres.xml`：exit 0，231 passed，1条Starlette TestClient/httpx上游弃用警告。完整单元/集成套件使用一次性独立PG，不触及生产DB。
- `npm test`（`miniapp/`）：exit 0，14 passed；`.venv/bin/ruff check backend/flower/services/providers.py backend/tests/test_providers.py`：exit 0；`git diff --check`：exit 0。
- 真实联网植物识别、园艺检索、LLM和天气请求次数均为0；HTTP模拟测试不算真实 AI 或教育版手机验收。B03/B04/B05/B06/B07/B08/B09保持原状态。
- 生产变更前 `python3 scripts/preflight.py .runtime/preflight-provider-before.json --compare .runtime/preflight-final.json`：exit 0，变化字段 `ports/nft/routes/addresses/tailscale`（包含动态值）；快照为私有文件，**未据此声称防火墙规则无差异**。变更前公网 `/ready` 与 City Front HTTPS 均200，Nginx/aibot/City Front/Tailscale/OpenVPN/SSH/Flower备份timer均active，四个Flower容器运行，API/Worker/PG健康。发布完成后的对照将另附。
