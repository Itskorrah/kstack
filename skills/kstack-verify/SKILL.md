---
name: kstack-verify
description: Independently verify coding-agent changes with locally executable tests, regressions, builds, security checks, screenshots and evidence before shipping.
---

# KStack verification

Use after meaningful code changes and before commits, pull requests, merges or release claims.

1. Reconcile the exact checked-out source, local changes, commit and acceptance criteria before testing.
2. Run fast appropriate checks: formatting, static analysis, type checking, unit and integration tests.
3. Run real workflows where feasible: browser/Playwright, device-native permissions, end-to-end and accessibility. Use BreakSwarm only for authorised local targets when installed and working.
4. Challenge negative cases: invalid inputs, cancellation, restart/recovery, interrupted writes, corrupt data, security boundaries and cross-platform behaviour.
5. For performance claims, record input sizes, environment, repetitions, baseline, delta and variance; never invent measurements.
6. Fix confirmed defects and rerun affected checks. Separate `passed`, `failed`, `not_run`, `blocked` and `unknown` by test.
7. Verify docs correspond to working behaviour; do not treat an old test run or checked-in screenshot as fresh evidence.
8. When GitHub Actions minutes are unavailable, do not invoke or rely on hosted workflows. Locally verified is not the same as remote CI passed.

Only make a readiness claim scoped to the checks that actually ran.
