# KStack implementation status — v0.2 development checkpoint

Evidence rule: **implemented** means code is present; **local-verified** means automated checks exercised it; **host-accepted** requires a real Codex/Claude or platform session, not just valid installed files. No hosted GitHub Actions have been used.

| Original workstream | Implemented in this pass | Locally verified | Genuinely remaining |
|---|---|---|---|
| 01. Correctness and security | Missing-install doctor fixed; cooperative locking; crash-recoverable promotion/rollback; explicit candidate/package boundaries | Yes, including simulated crashes and tampering | Richer specification parser, actual sandbox isolation, provenance attestations, multi-process/machine validation |
| 02. External integrations | Pinned clean-local-checkout skill package inspector/installer, binary copying behind explicit reviews, installed integrity checks | Yes, against disposable real Git checkout | Full Evolve/pstack/BreakSwarm/RepoPilot live acceptance, transitive deps and provenance/licences |
| 03. Host integration | Codex/Claude installer, honest host status, managed instruction blocks | Filesystem tested | Real host invocation, implicit routing, plugin registration and host-specific acceptance |
| 04. Project onboarding | Manifests detection, profiles, safe bootstrap, AGENTS/CLAUDE sections, verification config | Yes | More languages, monorepo detection, config migrations and actual host onboarding |
| 05. Intelligent routing | Project-aware risk/complexity and capability suggestions, specialist preference scoring | Yes, deterministic fixtures | Semantic task classification, model-backed planning, real installed-specialist matching and benchmarks |
| 06. Autonomous evaluation | Pinned source screening and manual independent review gate preserved | Mocked security/review tests | Real sandbox agent evaluator, signed evidence, baseline A/B trials and automated reviewer execution |
| 07. Skill lifecycle | Candidate revision history, bounded queue, lock export/inspect, crash-recoverable rollback | Yes | Full multi-file package policy, dependency solver, automatic safe upgrades, lock import/sync |
| 08. Scheduled evolution | External-scheduler runner, week eligibility, maintenance queue and reporting prompt | Local deterministic schedule tests | OS task installation, network-backed live acceptance, substantive autonomous review |
| 09. Verification infrastructure | Explicit trusted project subprocess runner, failures/timeouts, hash-linked evidence | Yes, actual subprocess tests | BreakSwarm/browser/native adapters, sandboxing, artifact provenance, more frameworks |
| 10. Development outcome learning | Validated self-reported outcome recording and descriptive aggregates | Yes | Automatically collected verified outcomes, meaningful causal comparisons and routing improvements |
| 11. GitHub delivery | Existing shipping guidance, local `delivery-plan` binding clean Git revision to passing checks/authorisation, read-only GitHub source discovery | Local real-Git + subprocess tests | Permission-bounded write adapter and end-to-end PR/merge verification using actual host tools |
| 12. Multi-agent orchestration | Role/profile guidance and existing SessionBridge catalogue | Advisory only | Real delegation to available workers, worktree isolation, host model/cost observation |
| 13. Cross-machine portability | Portable JSON lock export and integrity inspection, Codex/Claude file installs | Local Linux tests | Full lock import, Windows/macOS acceptance and multi-machine secure state sync |
| 14. Benchmarks | Verification evidence, project outcomes and test fixtures | Local tests | Comparative quality benchmarks with/without KStack and real coding hosts |
| 15. Packaging and documentation | CLI and wheel metadata, source-integrity docs, two new skills, README, changelog and handover | Package build/check where available | Published release, signed provenance and host/plugin marketplace acceptance |
| 16. Dashboard | CLI JSON views for queue, project, host and evidence | Local tests | Optional UI, avoid building before basic workflows accepted |

## What is not a supported claim

- The installer cannot establish that a model actually follows an installed skill.
- KStack is not a coding agent, autonomous unrestricted tool executor or container sandbox.
- Ratings in user-supplied review JSON are not independently authenticated.
- No actual external source package or native coding host is certified by simulated tests.
- No recurring OS task is registered merely by including a runner script.
- A test suite passing on Linux does not imply Windows/macOS acceptance.

See `CODEX_TODO.md` for prioritised remaining work, exact files, dependencies, blocked acceptance environments and test criteria.
