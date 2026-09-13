---
name: finishing-one-goal-delivery
description: Use when preparing to claim completion, deploy, hand off, freeze a release, or produce the final implementation and acceptance report for Smart Guardian.
---

# Finishing One-Goal Delivery

## Completion gate

“Implemented” is not “verified.” Before claiming completion, run the complete automated suite, deployment checks, database constraints, backup/restore, offline demo, and every available hardware test in the acceptance matrix.

## Evidence contract

For each acceptance ID record PASS, FAIL, NOT_RUN, or BLOCKED with a reproducible command or physical record. NOT_RUN and BLOCKED are not PASS. Never state that real hardware passed based on Mock tests.

## Release checks

- Verify the current spec hash and version metadata.
- Ensure no old-spec behavior or aliases remain.
- Confirm all services are healthy and migrations are at head.
- Confirm secrets are absent from Git and logs.
- Check command claim/session timeouts, fallback timezone, partial unique indexes, data retention, storage-low handling, and Pi/cloud quota reconciliation.
- Back up database and uploads, then prove restoration in a clean environment.
- Record branch, commit, images, deployed URLs, Pi service status, and rollback instructions.

## Final documents

Update `STATUS.md` to COMPLETE only when every mandatory item passes. Otherwise use HARD_BLOCKED and state the smallest user action needed. Produce `FINAL_IMPLEMENTATION_REPORT.md` from the template, link evidence, list exact unverified items, and give the command that resumes work.

Do not hide warnings, reduce test scope, delete failing tests, or reinterpret requirements to obtain a green report.

## 共享宿主机完成门

部署完成声明必须有：固定 SHA 镜像、显式 migration、上一 release 无重建回滚、Nginx/City Front/aibot/VPN 共存检查、备份恢复证据。没有真实高峰数据时容量项写 NOT_RUN，不得宣称通过。
