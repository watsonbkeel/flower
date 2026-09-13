---
name: using-smart-guardian-baseline
description: Use when starting work in the Smart Guardian repository, resolving conflicting requirements, or deciding which specification and project instructions are authoritative.
---

# Using the Smart Guardian Baseline

## Core rule

`SPEC_CURRENT.md` is the only product specification pointer. Read it before planning or editing. Product behavior comes from the pointed v2.2.2 spec; execution discipline comes from `AGENTS.md`.

## Required checks

1. Verify the spec file exists and its SHA-256 matches `SPEC_CURRENT.md`.
2. Search implementation plans and code for references to v2.0, v2.1, v2.2, or v2.2.1 outside archive/history.
3. Treat files under `docs/archive/` as historical evidence only.
4. Record the active spec version in generated reports, migrations, API metadata, Pi telemetry, and release notes.

## Conflict handling

- Current spec versus old spec: current spec wins.
- Spec versus implementation convenience: spec wins; raise a blocker rather than weakening safety.
- Product requirement versus process instruction: use the spec for behavior and `AGENTS.md` for workflow.
- Genuine contradiction inside v2.2.2: stop only the affected change, document exact sections in `BLOCKERS.md`, and continue independent work.

## Red flags

- Copying an old endpoint because it already has sample code.
- Keeping two status models “for compatibility”.
- Reintroducing CloudBase, ESP32, relay, or pressure-water designs without an approved spec change.
- Silently editing the frozen spec.

A feature is not complete if it cannot name the current spec version and acceptance item it satisfies.
