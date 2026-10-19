---
name: kstack-audit
description: Investigate the architecture, security, correctness and blast radius of a planned codebase change before adopting an implementation approach.
---

# KStack audit

Use this before risky refactors, data migrations, provider integrations or broad UI work. Establish the actual implementation and avoid claims inferred from READMEs alone.

1. Map current modules, entrypoints, data contracts, state transitions, dependencies and failure domains.
2. Establish a repeatable baseline, including known failing tests and environmental limitations. Preserve private data and source history.
3. Trace affected callers, side effects, formats, external dependencies and backward-compatibility requirements. Mark unknowns explicitly.
4. Compare a small set of sensible designs on risk, change friction, testability, accessibility, latency and maintainability.
5. Threat-model untrusted inputs, secret handling, permissions, network calls and data deletion where relevant.
6. Recommend the smallest coherent improvement with measurable acceptance criteria and a rollback plan.
7. Treat second-agent reviews as challenges, not rubber stamps. Use independent evidence to resolve disagreements.

Do not advocate a rewrite purely for aesthetics or turn speculative security concerns into confirmed vulnerabilities.
