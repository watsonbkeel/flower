# MANIFEST.md

## 核心入口

- `AGENTS.md`：代理规则与共享宿主机安全边界
- `GOAL.md`：唯一开发目标
- `SPEC_CURRENT.md`：v2.2.2 规格指针与哈希
- `PROMPT_ONE_GOAL.md`：服务器 Codex 单目标 Prompt
- `STATUS.md` / `BLOCKERS.md`：持续状态与阻塞

## 设计与实施

- `docs/specs/智慧守候_v2.2.2_Server-Integrated_冻结基线开发实施规格.md`
- `docs/SERVER_INTEGRATION_BASELINE.md`
- `docs/SAFETY_INVARIANTS.md`
- `docs/API_AND_DATA_CONTRACTS.md`
- `docs/ARCHITECTURE_DECISIONS.md`
- `docs/IMPLEMENTATION_PLAN.md`
- `docs/ACCEPTANCE_MATRIX.md`
- `docs/DEPLOYMENT_RUNBOOK.md`
- `docs/HARDWARE_WIRING.md`
- `docs/EXTERNAL_INPUTS.md`
- `docs/REVIEW_RESOLUTION_v2.2.2.md`
- `docs/AGENT_SKILL_LOADING.md`

## 真实服务器审计

`docs/server-audit/` 保留 8 份 2026-09-13 只读审计报告。

## Skills

`.agents/skills/*/SKILL.md` 为项目权威技能源；`scripts/install_project_skills.sh` 可选建立个人目录软链接。

## 完整文件清单

```text
.agents/skills/building-cloud-control-plane/SKILL.md
.agents/skills/building-raspberry-pi-agent/SKILL.md
.agents/skills/building-wechat-miniapp/SKILL.md
.agents/skills/finishing-one-goal-delivery/SKILL.md
.agents/skills/implementing-safety-critical-watering/SKILL.md
.agents/skills/integrating-real-hardware/SKILL.md
.agents/skills/using-smart-guardian-baseline/SKILL.md
AGENTS.md
BLOCKERS.md
GOAL.md
MANIFEST.md
PACKAGE_INFO.json
PROMPT_ONE_GOAL.md
README.md
SPEC_CURRENT.md
STATUS.md
docs/ACCEPTANCE_MATRIX.md
docs/AGENT_SKILL_LOADING.md
docs/API_AND_DATA_CONTRACTS.md
docs/ARCHITECTURE_DECISIONS.md
docs/DEPLOYMENT_RUNBOOK.md
docs/EXTERNAL_INPUTS.md
docs/FINAL_IMPLEMENTATION_REPORT_TEMPLATE.md
docs/HARDWARE_WIRING.md
docs/IMPLEMENTATION_PLAN.md
docs/REVIEW_RESOLUTION_v2.2.2.md
docs/SAFETY_INVARIANTS.md
docs/SERVER_INTEGRATION_BASELINE.md
docs/SKILL_STATIC_VALIDATION.txt
docs/SKILL_VALIDATION.md
docs/archive/README.md
docs/server-audit/AIBOT_ARCHITECTURE_AUDIT.md
docs/server-audit/CURRENT_SERVER_INVENTORY.md
docs/server-audit/FLOWER_REPOSITORY_PLAN.md
docs/server-audit/RECOMMENDATION.md
docs/server-audit/RESOURCE_AND_PORT_PLAN.md
docs/server-audit/REUSE_MATRIX.md
docs/server-audit/RISKS_AND_BLOCKERS.md
docs/server-audit/TARGET_DEPLOYMENT_TOPOLOGY.md
docs/specs/智慧守候_v2.2.2_Server-Integrated_冻结基线开发实施规格.md
evidence/README.md
scripts/install_project_skills.sh
scripts/validate_skills.py
skill-tests/01-baseline-conflict.md
skill-tests/02-pump-shortcut.md
skill-tests/03-missing-hardware.md
skill-tests/04-background-task.md
skill-tests/05-ui-optimism.md
skill-tests/06-fake-completion.md
skill-tests/07-timeout-semantics.md
skill-tests/08-voice-peripheral-bypass.md
skill-tests/09-shared-host-deploy.md
```
