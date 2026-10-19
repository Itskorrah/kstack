# KStack implementation status — v0.2 development checkpoint

Evidence rule: **implemented** means code is present; **local-verified** means automated checks exercised it; **host-accepted** requires a real Codex/Claude or platform session, not just valid installed files. No hosted GitHub Actions have been used.

| Original workstream | Implemented in this pass | Locally verified | Genuinely remaining |
|---|---|---|---|
| 01. Correctness and security | Conservative Agent Skills frontmatter subset; kernel-released state lock; recoverable host file generations, retained rollback and explicit recovery; ownership and symlink/junction checks | Yes, including interruption, rollback, tampering and separate-process lock tests | Full YAML/spec coverage, crash-at-every-boundary and native Windows/macOS validation, sandbox isolation, provenance attestations |
| 02. External integrations | Pinned clean-local-checkout package inspector/installer/remover, complete installed file hashes, explicit code review, sibling dependency graph and capability records | Yes, against disposable real Git checkouts | Evolve/pstack/BreakSwarm/RepoPilot live acceptance, authenticated provenance and licence review |
| 03. Host integration | Codex/Claude skill-file installer, honest host status, managed instruction blocks and rollback/recovery | Filesystem tested | Real host invocation, implicit routing, plugin registration and host-specific acceptance |
| 04. Project onboarding | Manifest detection, declared npm/pnpm/Cargo workspaces, per-root technology suggestions, safe bootstrap, managed instructions and reviewed v2 verification targets | Yes, synthetic mixed-workspace fixtures | Broader workspace syntax/languages, config migrations and actual host onboarding |
| 05. Intelligent routing | Project-aware risk/complexity and capability suggestions; reports available, installed-file-unverified and external capability status | Yes, deterministic fixtures and disposable installs | Semantic task classification, live host availability/invocation, and measured routing benchmarks |
| 06. Autonomous evaluation | Pinned source screening and manual independent review gate preserved | Mocked security/review tests | Real sandbox agent evaluator, signed evidence, baseline A/B trials and automated reviewer execution |
| 07. Skill lifecycle | Candidate revision history, bounded queue, lock export/inspect, crash-recoverable state rollback, transactional host install/rollback/removal and reviewed external dependency resolution | Yes | Automatic safe upgrades, lock import/sync, native crash and cross-platform validation |
| 08. Scheduled evolution | External-scheduler runner, week eligibility, maintenance queue and reporting prompt | Local deterministic schedule tests | OS task installation, network-backed live acceptance, substantive autonomous review |
| 09. Verification infrastructure | Explicit trusted project subprocess runner with per-workspace v2 targets, failures/timeouts and hash-linked evidence | Yes, actual subprocess and mixed-workspace tests | BreakSwarm/browser/native adapters, sandboxing, artifact provenance, more frameworks |
| 10. Development outcome learning | Validated self-reported outcome recording and descriptive aggregates | Yes | Automatically collected verified outcomes, meaningful causal comparisons and routing improvements |
| 11. GitHub delivery | Existing shipping guidance, local `delivery-plan` binding clean Git revision to passing checks/authorisation, read-only GitHub source discovery | Local real-Git + subprocess tests | Permission-bounded write adapter and end-to-end PR/merge verification using actual host tools |
| 12. Multi-agent orchestration | Role/profile guidance and existing SessionBridge catalogue | Advisory only | Real delegation to available workers, worktree isolation, host model/cost observation |
| 13. Cross-machine portability | Portable JSON lock export and integrity inspection, Codex/Claude file installs, host-generation rollback | Local Linux tests | Full lock import, Windows/macOS acceptance and multi-machine secure state sync |
| 14. Benchmarks | Verification evidence, project outcomes and test fixtures | Local tests | Comparative quality benchmarks with/without KStack and real coding hosts |
| 15. Packaging and documentation | CLI and wheel metadata, source-integrity docs, skills, README, changelog and handover | Wheel built and installed in a temporary venv; bundled profile, CLI doctor and weekly entry point checked | Published release, signed provenance and host/plugin marketplace acceptance |
| 16. Dashboard | CLI JSON views for queue, project, host and evidence | Local tests | Optional UI, avoid building before basic workflows accepted |

## What is not a supported claim

- The installer cannot establish that a model actually follows an installed skill.
- KStack is not a coding agent, autonomous unrestricted tool executor or container sandbox.
- Ratings in user-supplied review JSON are not independently authenticated.
- No actual external source package or native coding host is certified by simulated tests.
- No recurring OS task is registered merely by including a runner script.
- A test suite passing on Linux does not imply Windows/macOS acceptance.

See `CODEX_TODO.md` for prioritised remaining work, exact files, dependencies, blocked acceptance environments and test criteria.

## 20 October 2026 — Chat-mode P0 safety checkpoint

- Baseline main: b6924a1d29d07bd15325dbf666984ccb1e7c0450. Branch: fix/host-recovery-preflight-20261020.
- **Implemented (unverified):** Host creation rejects portable case/Unicode file aliases; host recovery checks the complete journal and required backups before rolling back any file; external package inspection rejects colliding package roots and file paths.
- **Tests added (not run):** tests/test_host_path_identity.py (8) and tests/test_external_portable_paths.py (2); scenarios cover a late user edit, corrupt backup, alias collisions, successful recovery and unsafe generation snapshots.
- **Evidence:** GitHub connector commit/readback confirmed. Local container has Python and Git but cannot resolve github.com for clone/download. No complete source checkout or full test run; no GitHub Actions invoked. Static readback is not a passing test.
- **Acceptance gate:** In a fresh checkout, run PYTHONPATH=src python -m unittest discover -s tests -v; python -m compileall -q src/kstack scripts tests; python scripts/kstack.py doctor; python scripts/kstack.py schedule-status. Repair failures, then separately test native Windows/macOS behaviour.
- **Residual risk:** During an actual recovery write failure, some files may still be restored while others await another recovery attempt; there is no atomic multi-file reader visibility and no cross-platform acceptance evidence yet.
