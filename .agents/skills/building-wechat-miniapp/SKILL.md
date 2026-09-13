---
name: building-wechat-miniapp
description: Use when implementing the WeChat Mini Program, user flows, command status presentation, plant recognition confirmation, care cards, trends, memories, alerts, or offline demonstration UI.
---

# Building the WeChat Mini Program

## Required user truth

The UI must never say “watering complete” when the server only created a pending command. Present the real lifecycle: pending, claimed/starting, executing with pulse progress, succeeded, failed, timed out, or rejected.

## Main flows

Implement plant capture, Top-3 confirmation, manual-name fallback, environment/pot input, asynchronous care-profile generation, user confirmation, calibration gate, and automatic protection switch.

Display current relative soil moisture, air data freshness, water level, operating mode, main fault reason, latest explainable decision, and last watering. Manual watering accepts millilitres or portions, never GPIO seconds.

## Data authenticity

Every trend response and chart shows source type and coverage. If only 52 hours of real data exist, say so. Demo/test data must be visually labelled and cannot be merged into real curves. Watering markers must match actual session timestamps.

## Emotional layer

Show public horticultural knowledge, local conditions, and family memory as distinct sources. When a memory rule changes a decision, show the original words, the applied effect, and the count of real uses.

## Failure experience

Provide readable explanations for low water, safe hold, provider failure, storage low, stale temperature, calibration missing, claim expiry, and session timeout. Job waiting pages poll without blocking and allow users to leave and return.

All resource access must use the authenticated backend and enforce ownership server-side.
