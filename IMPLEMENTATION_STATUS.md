# KStack implementation status — v0.2 development checkpoint

Evidence rule: **implemented** means code is present; **local-verified** means automated checks exercised it; **host-accepted** requires a real Codex/Claude or platform session, not just valid installed files. No hosted GitHub Actions have been used.

| Original workstream | Implemented in this pass | Locally verified | Genuinely remaining |
|---|---|---|---|
| 01. Correctness and security | Conservative Agent Skills frontmatter subset; kernel-released state lock; recoverable host file generations, retained rollback and explicit recovery; ownership and symlink/junction checks | Yes, including before/after staged backup and new-file writes, managed-file replacements, journal interruption, rollback, tampering, separate-process state locking, and Windows Python 3.13 regressions | fsync/snapshot fault coverage, native macOS host validation, sandbox isolation and provenance attestations |
| 02. External integrations | Pinned clean-local-checkout package inspector/installer/remover, complete installed file hashes, explicit code review, sibling dependency graph and capability records | Yes, against disposable real Git checkouts | Evolve/pstack/BreakSwarm/RepoPilot live acceptance, authenticated provenance and licence review |
| 03. Host integration | Codex/Claude skill-file installer, honest host status, managed instruction blocks and rollback/recovery | Filesystem tested | Real host invocation, implicit routing, plugin registration and host-specific acceptance |
| 04. Project onboarding | Manifest detection, declared npm/pnpm/Cargo workspaces, per-root technology suggestions, safe bootstrap, managed instructions and reviewed v2 verification targets | Yes, synthetic mixed-workspace fixtures | Broader workspace syntax/languages, config migrations and actual host onboarding |
| 05. Intelligent routing | Project-aware risk/complexity and capability suggestions; specialists require task signals, with project profiles only refining a match | Six synthetic routing regression contracts pass (not an independent holdout); disposable install checks | Independently sourced comparative corpus, semantic ambiguity handling, live host availability/invocation |
| 06. Autonomous evaluation | Pinned source screening and manual independent review gate preserved | Mocked security/review tests | Real sandbox agent evaluator, signed evidence, baseline A/B trials and automated reviewer execution |
| 07. Skill lifecycle | Candidate revision history, bounded queue, lock export/inspect, crash-recoverable state rollback, transactional host install/rollback/removal and reviewed external dependency resolution | Yes | Automatic safe upgrades, lock import/sync, native crash and cross-platform validation |
| 08. Scheduled evolution | External-scheduler runner, week eligibility, maintenance queue and reporting prompt | Local deterministic schedule tests | OS task installation, network-backed live acceptance, substantive autonomous review |
| 09. Verification infrastructure | Explicit trusted project subprocess runner with per-workspace v2 targets, failures/timeouts, hash-linked evidence and revision/worktree-bound Git checks | Yes, actual subprocess, mixed-workspace, changed-HEAD, dirty-baseline and changed-index tests | BreakSwarm/browser/native adapters, sandboxing, ignored-file integrity, artifact provenance and more frameworks |
| 10. Development outcome learning | Validated self-reported outcome recording and descriptive aggregates | Yes | Automatically collected verified outcomes, meaningful causal comparisons and routing improvements |
| 11. GitHub delivery | Existing shipping guidance, local `delivery-plan` binding clean Git revision to passing checks/authorisation, read-only GitHub source discovery | Local real-Git + subprocess tests | Permission-bounded write adapter and end-to-end PR/merge verification using actual host tools |
| 12. Multi-agent orchestration | Role/profile guidance and existing SessionBridge catalogue | Advisory only | Real delegation to available workers, worktree isolation, host model/cost observation |
| 13. Cross-machine portability | Portable JSON lock export and integrity inspection, Codex/Claude file installs, host-generation rollback | Local Linux evidence plus Windows Python 3.13 suite | Full lock import, macOS host acceptance and multi-machine secure state sync |
| 14. Benchmarks | Verification evidence, project outcomes and test fixtures | Local tests | Comparative quality benchmarks with/without KStack and real coding hosts |
| 15. Packaging and documentation | CLI and wheel metadata, source-integrity docs, skills, README, changelog and handover | Wheel built and installed in a temporary venv; bundled profile, CLI doctor and weekly entry point checked | Published release, signed provenance and host/plugin marketplace acceptance |
| 16. Dashboard | CLI JSON views for queue, project, host and evidence | Local tests | Optional UI, avoid building before basic workflows accepted |

## What is not a supported claim

- The installer cannot establish that a model actually follows an installed skill.
- KStack is not a coding agent, autonomous unrestricted tool executor or container sandbox.
- Ratings in user-supplied review JSON are not independently authenticated.
- No actual external source package or native coding host is certified by simulated tests.
- No recurring OS task is registered merely by including a runner script.
- Local Windows unit tests do not prove macOS behavior or actual agent-host invocation.

See `CODEX_TODO.md` for prioritised remaining work, exact files, dependencies, blocked acceptance environments and test criteria.

## 21 October 2026 — PR #5/#6 merged; routing regression slice

- **PR #5 merged:** Host recovery validates all journal entries and required backups before rollback, rejects case/Unicode path aliases, and safely checks recovery roots. Merge commit: `034e191f9771c0b895b452a4ae31adefa142f6e3`.
- **Windows fix included in PR #5:** State locks now read owner metadata through the locked descriptor; Windows invalid-PID errors correctly identify absent processes. Installer assertions use native paths and account for unavailable symlink privileges.
- **Executed on Windows, Python 3.13:** PR #5 checkpoint — 114 passed, 8 skipped. Combined PR #5/#6 suite — 123 passed, 8 skipped. `python -m compileall -q src/kstack scripts tests`, `python scripts/kstack.py doctor`, `python scripts/kstack.py schedule-status`, and `git diff --check` passed.
- **PR #6 merged:** Verification stores pre/post Git snapshots and compares commit, branch, clean state, and a digest over Git-visible changes. The digest covers staged/index metadata, tracked file contents, and non-ignored untracked file contents without storing raw diffs. Unchanged dirty working trees remain eligible; changed or unavailable fingerprints do not produce a verified result. Merge commit: `d9c21a274b1d231cc8315bbe13b1228321ba93d8`.
- **Focused evidence:** All 9 tests in `tests/test_verification_revision_stability.py` passed in the combined suite, including pre-existing dirty tracked/untracked files, index-only state changes, unchanged dirty trees, moving HEAD, unavailable commands and timeout receipts.
- **Limitations:** Ignored files and transient edits restored before the final snapshot are not detected. Modified submodules and special files yield an unavailable fingerprint. Verification commands remain trusted code and are not sandboxed. No native macOS or live agent-host acceptance has been run.
- **KSK-301 routing slice:** Specialist recommendations require a task-language signal; a project profile can adjust relevance only after a task match. Added explicit pstack terms for authentication, authorization, permissions, secrets, databases and migrations. A six-case synthetic regression suite covers UI accessibility, backend API, browser regression, frontend performance, security review and database migration. It was authored alongside this change, so it is not an independent benchmark. The standalone report marks host invocation unverified.
- **Routing contract result:** `python scripts/route_benchmark.py` reports 6/6 contracts passing and 1.0 workflow recall, required-specialist recall and candidate precision. These metrics describe this synthetic regression set only. The full Windows Python 3.13 suite passed 124 tests with 8 platform-dependent skips; compileall, `doctor`, `schedule-status`, and `git diff --check` passed. The benchmark did not invoke an agent host.

## 21 October 2026 — KSK-101 host transaction fault matrix

- Added `tests/test_host_transaction_failures.py` with injected failures before and after backup/staged-new writes and each replacement in a generation containing create, update, delete and manifest-last behavior.
- Added commit-journal removal failure and durable-journal interruption cases. Recovery restores the previous generation or completes cleanup on the next recovery call; retained snapshots and staging directories are checked.
- The four focused tests pass on Windows with Python 3.13. Full local suite: 128 passed, 8 platform-dependent skips; compileall, `doctor`, `schedule-status`, and the routing regression benchmark passed. fsync/snapshot-write failure coverage, host installer multiprocess contention, and native macOS filesystem acceptance remain outstanding. Hosted Actions were not used.
