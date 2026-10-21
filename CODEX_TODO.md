# KStack — Implementation handover and remaining development

**Status:** v0.2 development preview, 19 October 2026. **Target repository:** `Itskorrah/kstack`, default branch `main`. This file is a **remaining-work ledger**, not an assertion that everything listed here is feasible in a single coding session. Read `IMPLEMENTATION_STATUS.md` first, run all local tests and inspect the current branch before editing.

## Operator instructions

1. Confirm the repository's actual current HEAD and preserve unrelated work. Read `AGENTS.md`, `docs/SECURITY.md`, `docs/ARCHITECTURE.md`, `IMPLEMENTATION_STATUS.md` and this file.
2. Establish a clean baseline using `PYTHONPATH=src python -m unittest discover -s tests -v`, `python -m compileall -q src/kstack scripts`, `python scripts/kstack.py doctor`, and `python scripts/kstack.py schedule-status`. Do not rely on GitHub Actions: the account's hosted allocation is exhausted.
3. Complete tasks **in dependency order**, not simply file order. Implement and locally test everything possible, then conduct real host/native/network acceptance where accessible. Create useful branch checkpoints; commit/push and merge **verified** changes to `main` when permitted and safe, without bypassing branch protection.
4. Do not fabricate sandbox results, host invocations, benchmarks, security assurances or provider identities. A successful file copy is not successful agent-skill invocation.
5. Keep the README, status matrix, release notes and this ledger synchronised with actual code, commands, tests and supported-platform evidence.
6. Task labels: **PARTIAL** = relevant code exists, more work required; **IMPLEMENTED–UNVERIFIED** = feature code exists but live acceptance needs another environment; **BLOCKED** = cannot truthfully be completed without external runtime/permissions; **NOT STARTED** = no meaningful implementation yet; **OPTIONAL** = enhancement beyond the essential v1 capability.

## Execution phases and task index

| Phase | ID | Priority | State | Workstream |
|---|---|---|---|---|
| A | KSK-101 | P0 | PARTIAL | Complete transactional host installation and recovery |
| A | KSK-102 | P0 | PARTIAL | Independent source/provenance and security validation |
| A | KSK-103 | P0 | PARTIAL | Standards-compliant skill parser and dependency graphs |
| A | KSK-104 | P0 | IMPLEMENTED–UNVERIFIED | Real Codex/Claude host acceptance |
| B | KSK-201 | P0 | PARTIAL | Production-ready Evolve integration |
| B | KSK-202 | P1 | PARTIAL | pstack/UI/Superpowers/Vercel integrations |
| B | KSK-203 | P1 | PARTIAL | BreakSwarm/RepoPilot integrations |
| B | KSK-204 | P1 | PARTIAL | Monorepo-aware bootstrap and host configuration |
| C | KSK-301 | P1 | PARTIAL | Semantic task classifier and actual capability inventory |
| C | KSK-302 | P1 | PARTIAL | Task orchestration, role coordination and fallbacks |
| C | KSK-303 | P1 | PARTIAL | End-to-end engineering verification adapters |
| D | KSK-401 | P1 | PARTIAL | Independent agent-in-sandbox skill evaluator |
| D | KSK-402 | P1 | PARTIAL | Authentic evidence and signed attestations |
| D | KSK-403 | P1 | PARTIAL | Lifecycle solver, upgrades and portable state import |
| D | KSK-404 | P1 | IMPLEMENTED–UNVERIFIED | Weekly runner and actual unattended maintenance |
| E | KSK-501 | P1 | PARTIAL | Real development outcome capture and feedback |
| E | KSK-502 | P1 | PARTIAL | Comparative coding benchmarks and metrics |
| E | KSK-503 | P1 | NOT STARTED | GitHub development/delivery adapter |
| F | KSK-601 | P2 | PARTIAL | Windows/macOS and additional coding-host acceptance |
| F | KSK-602 | P2 | PARTIAL | Wheel/plugin distribution and releases |
| F | KSK-603 | P3 | OPTIONAL | Local dashboard / advanced observability |

---

## Phase A — trustworthy foundation and host acceptance

### KSK-101 — Transactional installation and recovery

- **Original requirements:** Workstreams 01, 07, 13; crash safety, integrity, rollback, concurrency and recovery.
- **State:** PARTIAL. State mutations use an OS-released advisory lock with process/host metadata and explicit stale-owner recovery; old `.write-lock` directories require inspection. Core and external host changes share a lock and use staged, hash-checked file transactions, a write-ahead journal, retained core-generation backups, explicit recovery and rollback. Unmanaged files are never adopted. Local tests cover process contention, interruption recovery and preservation of unexpected user edits.
- **Remaining:** Validate abrupt interruption at every filesystem transition and native Windows/macOS semantics; complete host doctor checks for every retained generation and external manifest edge case; improve rollback reporting and test concurrent real host clients. Multi-file replacement is recoverable after `recover-install`, but readers can observe a partially replaced generation while an interrupted transaction awaits recovery.
- **Why not completed:** Only local Linux and deterministic process/filesystem fixtures are available; they cannot establish native host filesystem or cross-platform acceptance.
- **Files:** `src/kstack/installer.py`, `external.py`, `state.py`, `transaction.py`, `hosts.py`, `tests/test_installer.py`, `tests/test_lifecycle_extended.py`.
- **Implementation:** Retain the format-versioned host manifest, staging directory, commit-marker ordering, file/directory `fsync` where supported, preflight ownership, symlink/junction rejection, hash-checked backup and recovery. Continue fault injection at each write/replace boundary and preserve compatibility with old core manifests.
- **Tests:** Local `PYTHONPATH=src python -m unittest discover -s tests -v`, simulated interruption/recovery, a separate-process state lock, rollback and user-edit conflict cases. Still add exhaustive replace-boundary injection, host-install multiprocess contention, Windows ACL/drive cases and macOS APFS paths.
- **Acceptance:** After `recover-install`, an interrupted install returns to the complete previous generation; `doctor` detects inconsistent installed content; `rollback-install` restores the previous managed generation without touching unrelated files.

### KSK-102 — Independent source, provenance and security validation

- **Original:** 01, 06, 07; trust and untrusted third-party skills.
- **State:** PARTIAL. `security.py` performs conservative text screening; `external.py` requires a clean pinned local Git checkout, disables configured Git filesystem-monitor helpers during inspection, records hashes for every installed file and requires `--reviewed` plus `--allow-code` for non-documentation files. Host installs refuse unmanaged files and symlink/junction paths. GitHub metadata reads are pinned; none of these checks authenticates publisher identity or proves safety.
- **Remaining:** Authenticate provenance beyond a claimed local Git remote, inspect hooks and executable behavior, verify licences/redistribution rights, defend against instruction injection, and enforce isolation during rehearsals. Build maintained trust/revocation policies with publisher key rotation and an emergency disable path. Add immutable source archives and signed review/test evidence.
- **Why:** Robust security review requires external sandbox tools, trusted source identity and authenticated evidence, absent here.
- **Files:** `src/kstack/security.py`, `external.py`, `github_api.py`, `engine.py`, `data/policy.json`, `docs/SECURITY.md`.
- **Implementation:** Introduce typed provenance policy and capability manifest; static checks plus human/independent model challenge; isolated network-denied test runner; supply-chain licence/SBOM advisory checks. Treat downloaded instructions as data. Never treat allowlisted owner, regex pass or high rating as proof. Require stronger approval for executable hooks, secrets, network permissions and deployment.
- **Tests:** Malicious repository fixture, forged/moved tag, symlink escape, hidden executable, credential exfiltration prompt, recursive dependency, hostile frontmatter, revoked owner and sandbox-breakout attempts.
- **Acceptance:** Unsupported/unsafe sources fail closed with explanatory findings; eligible benign packages are reproducibly pinned; no untrusted package can acquire undeclared privileges during evaluation.

### KSK-103 — Standards-compliant skill metadata and dependency resolver

- **Original:** 01, 02, 07, 15.
- **State:** PARTIAL. `parse_skill` recognises a conservative subset of Agent Skills frontmatter fields, quoted scalars and folded/literal descriptions. `external.inspect_package` supports reviewed multi-file local packages and the KStack `kstack-package.json` format 1 extension for sibling version constraints, dependency ordering and capability providers.
- **Remaining:** Complete broader YAML/spec compatibility and official conformance fixtures; preserve and report licence/compatibility details more fully; support external dependencies beyond declared local siblings and define host-specific restrictions. The KStack package manifest is not an upstream standard.
- **Why:** Real external package diversity and complete specification variants were not available for live acceptance.
- **Files:** `src/kstack/security.py`, `external.py`, `installer.py`, `router.py`, `data/integrations.json`.
- **Implementation:** Document the parser's accepted subset and fail closed outside it. Keep dependency resolution deterministic, reject cycles, incompatible/missing siblings, path escapes, name/capability conflicts and mismatched files; preserve source commit and hashes. Add official positive/negative fixtures and publish the package extension schema.
- **Tests:** Specification-derived frontmatter fixtures, multi-file dependency package, collisions, code-containing paths, missing references, circular dependencies, incompatible versions and path escapes. A representative upstream package and real host remain untested.
- **Acceptance:** Every claimed supported package resolves and installs consistently; unsupported formats fail with actionable diagnostics and no partial writes.

### KSK-104 — Codex, Claude Code and ChatGPT plugin acceptance

- **Original:** 03 and 04.
- **State:** IMPLEMENTED–UNVERIFIED. Source includes Codex and Claude file installers, `kstack-router`/`kstack-project` instructions, managed onboarding blocks and portable plugin metadata. `host-status` deliberately reports `invocation_verified: false`.
- **Blocker:** Neither authenticated Codex nor Claude Code executable/session is available in this runner; plugin registration and personal account installation require eligible host access.
- **Files:** `.claude-plugin/plugin.json`, `plugin.json`, `skills/`, `src/kstack/installer.py`, `hosts.py`, `project.py`.
- **Actions:** On actual host versions: install into disposable project; check explicit `$kstack-router` or `/kstack-router` invocation, indirect activation from representative prompts, supported project scopes, session reload, plugin package registration, native tool permissions, conflicting existing installations and uninstall/rollback. Verify plugin-specific metadata and an MCP adapter only if genuinely required for live tools; a skill-only plugin has no live account access.
- **Tests:** Record host/build version, prompt, observed skill load, run transcript or verifiable log, execution outcome, negative-trigger tests, host upgrade regression.
- **Acceptance:** Real, authenticated Codex and Claude Code can discover, invoke and respect KStack in both explicit and implicit scenarios, with no false positives; unsupported ChatGPT/plugin surfaces are documented rather than claimed.

## Phase B — external skill ecosystems and project integration

### KSK-201 — Production Evolve integration

- **Original:** 02 and 04.
- **State:** PARTIAL. KStack catalogues `Itskorrah/evolve`; `external-install` can copy reviewed pinned packages from a clean local checkout. A KStack-specific manifest can resolve declared sibling skills, dependencies and capabilities, and optional scripts require an extra grant.
- **Remaining:** Validate the actual Evolve repository structure and licence, build a curated compatible package, and verify `$evolve` / `/evolve` functionality in real host sessions. Do not call the generic resolver a production Evolve adapter or copy an incomplete coordinator and call it integrated.
- **Blocker:** No actual Evolve checkout or coding host execution available in this sandbox; GitHub's remote clone URL is inaccessible from its shell.
- **Files:** `data/integrations.json`, `src/kstack/external.py`, `router.py`, `skills/kstack-router/SKILL.md`.
- **Actions:** Inspect upstream Evolve installer and licence; choose direct skill integration versus upstream documented installer; pin exact revision; implement adapter with dependency graph and verification. Use project-level and global scopes; avoid a second orchestrator.
- **Tests:** Fresh host install, Evolve audit/build/verify/ship workflow against disposable Python and web fixtures, rollback and missing-sibling handling.
- **Acceptance:** A significant implementation task reliably selects Evolve as lead, runs meaningful Evolve stages and tests the result without manual pasting of Evolve repository instructions.

### KSK-202 — Curated pstack, Superpowers, UI and Vercel skill integrations

- **Original:** 02, 05, 07.
- **State:** PARTIAL. These appear as catalogue suggestions and local package-install inputs, not automated usable adapters.
- **Remaining:** Implement project-specific resolution and tested installations for carefully selected architecture, independent-review, debugging/TDD, UI/accessibility and React/Next.js skills. Handle overlapping orchestrators, differing host syntax, licence notices and upstream restructuring.
- **Blocker:** Actual host invocation and upstream package materialisation unavailable.
- **Files:** `data/integrations.json`, `src/kstack/router.py`, `external.py`, `project.py`, `profiles/`.
- **Actions:** Pin a small approved initial set, define capability IDs and exact task triggers; build per-host adapter contracts; use upstream tools where possible; check version changes before upgrades. Don't install every available skill globally.
- **Tests:** Browser UI redesign fixture, React performance change, backend bug and review-only task; compare skill combinations to simpler baseline; independent host invocation.
- **Acceptance:** Relevant projects receive the minimal compatible set with no duplicate planning loop; every installed specialist is actually invocable and produces validated useful work.

### KSK-203 — BreakSwarm, RepoPilot and specialist service integrations

- **Original:** 02, 09, 11.
- **State:** PARTIAL. Catalogue records exist. No working BreakSwarm browser QA adapter or RepoPilot live-data adapter has been implemented.
- **Remaining:** Create capability-scoped adapter interfaces for BreakSwarm and RepoPilot. Run BreakSwarm only against explicitly authorised origins and record actual findings/screenshots/replays. Use RepoPilot read-only evidence as advisory portfolio prioritisation, never as independent permission to merge. MotionForge, Replica and SessionBridge may follow as optional specialists.
- **Blocker:** No working local BreakSwarm/RepoPilot server, browser runtime, live PAT or native GUI in this session.
- **Files:** `data/integrations.json`, `src/kstack/verification.py`, `hosts.py`, `queue.py`.
- **Actions:** Implement adapters after inspecting actual current APIs, avoid inventing endpoints; enforce target allowlists, timeouts, result schemas, artifact privacy, graceful unavailability.
- **Tests:** Synthetic vulnerable web app, fixed fixture, replay and export, plugin API denied/unavailable, partial evidence response, private metadata redaction.
- **Acceptance:** Real browser findings become reproducible regression evidence; portfolio recommendations remain clearly distinct from authorised code mutations.

### KSK-204 — Monorepo and persistent project configuration

- **Original:** 04.
- **State:** PARTIAL. `project.py` detects several root manifests and declared npm, pnpm and Cargo workspace members, reports per-root profile and owner-reviewed verification suggestions, writes a conservative `kstack.json` and managed instruction blocks. Config v2 accepts explicit per-root verification targets; commands are never auto-adopted from manifests.
- **Remaining:** Broaden nested/multi-root workspace and Swift/Expo/Flutter/native-tool detection, formalise type-safe config migrations and project policy precedence, and validate mixed projects in real host sessions. Keep suggested commands separate from trusted execution configuration.
- **Blocker:** Real mixed-project samples and native host environments required for credible acceptance.
- **Files:** `src/kstack/project.py`, `router.py`, `verification.py`, `profiles/`, `tests/test_new_features.py`.
- **Actions:** Extend the bounded workspace graph and checked-in config schema; add nested workspace and per-target toolchain coverage. Persist override explanations. Preserve pre-existing instructions under all circumstances.
- **Tests:** Synthetic monorepo with Python + Next + Rust, invalid profiles, pre-existing config, symlink attacks, host-specific projects.
- **Acceptance:** Project-scoped bootstrap selects correct capabilities across multiple languages without destructive edits or permission escalation.

## Phase C — routing, execution and quality

### KSK-301 — Semantic capability matching and measured router quality

- **Original:** 05, 10, 14.
- **State:** PARTIAL. `router.py` provides deterministic project-aware task/risk classification and now distinguishes available bundled workflows from files installed in the selected host scope. It checks external package capabilities and reports installed files as unverified by the host.
- **Remaining:** Add semantic intent classification, ambiguity/conflict handling, host-provided skill availability and confidence/provenance reporting. The on-disk capability registry cannot prove implicit invocation or actual skill behavior. Explicitly favour one lead orchestrator and minimal specialist overhead.
- **Blocker:** No live coding-host agent API or real implicit invocation test environment.
- **Files:** `src/kstack/router.py`, `project.py`, `hosts.py`, `external.py`, `data/integrations.json`.
- **Actions:** Add host-supplied availability evidence, deterministic fallback with explicit uncertainty, optional model-assisted reasoning, positive/negative routing fixtures from Jotstead/BreakSwarm/Clicky Bro and task-aware evaluation metrics.
- **Tests:** Cases where keyword-only router fails, trivial edits, mixed frameworks, specialist missing, credential-sensitive actions, duplicate skills, unstable host availability.
- **Acceptance:** Routing recommendations select relevant **installed** capabilities, do not imply a host invoked them, and materially improve acceptance outcomes against a documented baseline.

### KSK-302 — Bounded host-aware multi-agent coordination

- **Original:** 05, 11, 12.
- **State:** PARTIAL. Router plans are advisory; SessionBridge and Cost-Aware Orchestration are references. KStack does not execute workers or force model IDs.
- **Remaining:** Capability negotiation with real hosts, optional parallel workers with disjoint file/worktree ownership, safe handoffs, reviewer separation, cancellation, tool budgets, retries and cost-aware delegation. Do not build a new general coding-agent runtime without demonstrated need.
- **Blocker:** No Codex/Claude CLI authenticated worker execution, model identity or usage telemetry available here.
- **Files:** `src/kstack/router.py`, `hosts.py`, `data/integrations.json`; use `Itskorrah/codex-cost-aware-orchestration` as upstream reference.
- **Actions:** Add a host adapter protocol, error/cancellation contracts, worktree lifecycle, independent review hooks and SessionBridge import/export checks; preserve actual host limitations.
- **Tests:** Independent tasks in isolated worktrees, conflicting edits, unavailable worker, token-exhaustion fallback, partial completion, lost session, malicious handoff commands.
- **Acceptance:** Parallel work provides demonstrable value only when justified; integrated results pass fresh verification and actual model/cost metrics are not fabricated.

### KSK-303 — Reusable end-to-end quality and native/browser adapters

- **Original:** 09 and 11.
- **State:** PARTIAL. `verification.py` executes **trusted explicit** argument-list commands with a total timeout, captures real outcomes and appends local evidence. Config v2 can define reviewed commands per workspace target and runs them from each target directory. `kstack-verify` gives review instructions.
- **Remaining:** Build framework-specific verified check profiles, Playwright/BreakSwarm adapter, GUI screenshot capture, accessibility, native Swift/WPF/Flutter/React Native acceptance, broader failure/recovery coverage and reviewer isolation. Separate fresh tests from stale evidence. The current subprocess runner is **not sandboxed**.
- **Blocker:** Browser/native SDKs and approved real project environments absent; arbitrary untrusted test execution is prohibited.
- **Files:** `src/kstack/verification.py`, `evidence.py`, `project.py`, `skills/kstack-verify/SKILL.md`, `docs/ACCEPTANCE.md`.
- **Actions:** Add user-approved command profiles, capability checks, artefact hashes and targeted adapters with explicit target authorisation; use genuine native devices/OS where required.
- **Tests:** Real build, lint, unit/integration/browser E2E, screenshot golden checks, inaccessible browser, corrupted output, permission denial, timeout and cancellation.
- **Acceptance:** For every supported project type, KStack produces reproducible evidence of what actually passed, failed or remained inaccessible.

## Phase D — autonomous intelligence and dependable updates

### KSK-401 — Real isolated skill evaluation worker

- **Original:** 06, 08, 14.
- **State:** PARTIAL. Candidate discovery/assessment, screening and JSON review gates exist. No agent-backed evaluator or sandboxed rehearsal has been implemented.
- **Remaining:** Build independently run skill-vs-baseline experiments in disposable repositories using an actual coding host, with no real credentials, bounded compute/network and explicit capability policy. Evaluate with objective tests plus independent reviewer. Do not infer quality from keywords or a self-reported score.
- **Blocker:** No sandbox/container host with separately authenticated coding-agent execution available during this ChatGPT run.
- **Files:** `src/kstack/engine.py`, `security.py`, `verification.py`, `evidence.py`, `docs/REVIEW_SCHEMA.md`.
- **Actions:** Implement signed/verified review input contract with test fixture ID, host version, exact candidate SHA, commands, artefact hashes and factual outcomes. Separate candidate author from reviewer; require baseline trial; restrict remote I/O.
- **Tests:** Seeded defects, malicious skills, passing but ineffective skill, high scores with missing logs, stale baselines, incomplete runs, rejected candidates.
- **Acceptance:** Promotion gates depend on independently verifiable execution evidence and demonstrate measured value, not claims alone.

### KSK-402 — Attested evidence and security policy auditing

- **Original:** 01, 06, 09, 10.
- **State:** PARTIAL. `evidence.py` records a hash-linked journal; `feedback.py` explicitly marks self-reported outcomes. Neither provides signed provenance or independent reviewer identity.
- **Remaining:** Cryptographically attributable host/test attestations, verified artifact references, privacy/redaction policy, audit export and retention controls; stale evidence rejection after changed commits. Define signer trust/root, key rotation, offline verification and corruption recovery.
- **Blocker:** Trusted signature identity and actual execution worker environment unavailable.
- **Files:** `src/kstack/evidence.py`, `feedback.py`, `engine.py`, `docs/SECURITY.md`.
- **Actions:** Create evidence schema and verifier decoupled from mutable self-reported logs; reject invalid credentials, missing attestations, mismatched hashes and stale results. Do not claim hash chains resist full-file replacement.
- **Tests:** Forged reviewer, tampered log, replayed old evidence, wrong commit, expired signer, revoked key, leaked secrets.
- **Acceptance:** A verifier can independently establish who/what performed the stated test against exactly which code revision.

### KSK-403 — Full version/dependency lifecycle and portable lock import

- **Original:** 07, 13.
- **State:** PARTIAL. `portfolio.py` exports an immutable manifest and verifies locally cached objects; queue tracks source revisions; `transaction.py` provides rollback journal.
- **Remaining:** Full import/synchronisation with identical approved bytes, secure sharing or fetch of approved objects, dependency-aware upgrades, migration compatibility, package revocation, garbage collection, conflict resolution and per-host transactional sync.
- **Blocker:** Remote state distribution trust model, realistic cross-machine environments and package licences need independent testing.
- **Files:** `src/kstack/portfolio.py`, `external.py`, `transaction.py`, `installer.py`, `queue.py`.
- **Actions:** Define canonical portable lock format, signed source identity, verified object transport, host compatibility and explicit import authorisation. Never treat an external lockfile as permission to auto-promote arbitrary instructions.
- **Tests:** Fresh Windows/macOS machine, offline import with cached objects, missing object, wrong hash, revoked source, conflicting active versions, interrupted sync.
- **Acceptance:** Supported machines reproduce the same reviewed stack and recover safely; user secrets never enter the public catalogue.

### KSK-404 — Install and accept a real recurring maintenance job

- **Original:** 08.
- **State:** IMPLEMENTED–UNVERIFIED. `src/kstack/weekly.py`, `scheduler.py`, `queue.py` and `scripts/maintenance_runner.py` implement a once-per-week watchlist scan entry point and queue. No background daemon or task registration is claimed. The ChatGPT task prompt remains `docs/SCHEDULER_PROMPT.md`.
- **Blocker:** No user workstation scheduler control or background execution authorisation surface in the container. No public internet connectivity from its shell, so live GitHub scan must be accepted elsewhere.
- **Files:** `src/kstack/weekly.py`, `scheduler.py`, `engine.py`, `queue.py`, `docs/MAINTENANCE.md`, `docs/SCHEDULER_PROMPT.md`.
- **Actions:** Install a vetted launchd/Windows Task Scheduler/cron task at user-approved cadence, set minimal env/token read scopes, enable timeouts/log rotation, test missed runs and weekly/monthly reporting. Add safe independent review worker only after KSK-401/402. Avoid Actions minutes.
- **Tests:** Synthetic clock, DST transition, no network, API rate limit, crash/retry, duplicate invocation, blocked review, genuine scheduled trigger.
- **Acceptance:** A genuine recurring process runs, reports accurately and can promote only independently verified policy-eligible updates; inactive schedules are never reported active.

## Phase E — delivery, learning and real comparative evaluation

### KSK-501 — Verified outcome capture and learning

- **Original:** 10.
- **State:** PARTIAL. `feedback.py` stores validated, self-reported category/outcome records and descriptive counts. There is no causal learning or access to private agent session events.
- **Remaining:** Instrument approved coding hosts and verification adapters to record genuine task outcomes with consent, redaction, source revision, actual skill invocations and observed checks. Build data quality checks and evidence-based routing-rule proposals, with rollback and evaluation before promotion.
- **Blocker:** Real execution telemetry and consistent host access unavailable.
- **Files:** `src/kstack/feedback.py`, `evidence.py`, `hosts.py`, `router.py`.
- **Actions:** Introduce opt-in privacy-minimal event schema and records of actual invocation, compare same-task experiments, apply only verified improvements. Avoid retaining entire chats/private code without explicit permission.
- **Tests:** Malformed events, source mismatch, missing consent, invalid provenance, inconsistent baselines, sparse sample warnings.
- **Acceptance:** KStack can demonstrate, rather than merely assert, an improvement in skill selection from accumulated verified outcomes.

### KSK-502 — Quality benchmarks and experimental methodology

- **Original:** 14.
- **State:** PARTIAL. Deterministic tests, real local subprocess verification and self-reported outcomes exist; no coding-host A/B comparison has run.
- **Remaining:** Build version-pinned baseline/candidate benchmark corpus spanning correctness, Python, React/Next, UI, security, Rust, native acceptance, interruption and delivery. Record environment/model/tool parameters; independently measure acceptance tests, regressions, time and actual usage where accessible.
- **Blocker:** No authenticated coding hosts or full native/browser runtime in this environment.
- **Files:** `tests/`, `src/kstack/verification.py`, `feedback.py`, `router.py`, `docs/ACCEPTANCE.md`.
- **Actions:** Implement benchmark harness with controlled project snapshots, repetitions for nondeterministic agents, independent review and honest uncertainty. Treat subjective UI scores as reviewer observations, not objective proof.
- **Tests:** Non-improving skill, confounded model changes, missing usage, bad baseline, flaky tests, partial runs.
- **Acceptance:** Evidence supports that representative KStack workflows outperform suitable baselines without unacceptable overhead.

### KSK-503 — Permission-scoped GitHub development/PR/merge adapter

- **Original:** 11.
- **State:** NOT STARTED (beyond read-only discovery and `kstack-ship` instructions). No GitHub mutation adapter lives in the KStack Python package.
- **Remaining:** Add optional host-backed code delivery interface for branches, commits, PRs, reviews, current-head status and post-merge verification. Never infer permission to merge from a skill's documentation.
- **Why not attempted:** This ChatGPT environment has a GitHub connector and can deliver **this repository** externally, but that connector is not a library dependency automatically available to locally installed KStack; a reliable adapter requires per-host auth/tool interfaces and independent permissions design.
- **Files:** New capability adapter under `src/kstack/integrations/`, `skills/kstack-ship/SKILL.md`, `docs/SECURITY.md`.
- **Actions:** Define typed interface with read/write separation, explicit per-task authorisation and least-privilege account tokens; implement host-specific adapters rather than embedding credentials. Verify target branch after merge, record source/test linkage, handle protection rules, conflicts, stale PRs and failed remote checks. Never disable security or consume hosted Actions to force green.
- **Tests:** Mocked API denied, stale head, conflicting branch, branch protection, missing authority, changed diff after tests, partial merge, successful post-merge verification.
- **Acceptance:** Verified authorisations and evidence determine exactly which repository, commits and branch KStack can change; actual merge result is independently checked.

## Phase F — portability, release and optional UI

### KSK-601 — Real OS/host compatibility matrix

- **Original:** 03, 13, 15.
- **State:** PARTIAL. Linux/this container tests pass; skills install with Codex/Claude directory conventions. No native host acceptance or Windows/macOS tests have run in this session.
- **Remaining:** Test latest supported macOS/Windows/Linux, Python interpreter versions, PowerShell paths, symlink/junction behaviour, file locking and read/write permissions. Add Cursor, OpenCode, Gemini/Antigravity adapters only after validating their actual skill load conventions and host versions.
- **Blocker:** No remote/native OS sessions, Xcode/.NET/GUI tools or active coding hosts accessible.
- **Files:** `src/kstack/installer.py`, `external.py`, `state.py`, `project.py`, `hosts.py`, `docs/ACCEPTANCE.md`.
- **Tests:** Cross-platform install/reinstall/uninstall; clipboard/GUI host skills where relevant; malformed paths, interrupted operations, timezones, long paths, shell quoting.
- **Acceptance:** Each claimed host and OS combination has recorded actual installation and invocation tests; unsupported combinations are honestly labelled.

### KSK-602 — Package distribution, plugin and stable release

- **Original:** 15.
- **State:** PARTIAL. `pyproject.toml`, bundled assets, `plugin.json`, `.claude-plugin/plugin.json`, README and local package tests exist. A wheel built successfully, installed in a temporary clean venv, included `monorepo.json`, and passed `kstack doctor`; the `kstack-weekly` entry point returned help successfully.
- **Remaining:** Publish release artifacts with hashes/provenance, pin build tooling and reproduce builds; validate plugin marketplace/onboarding in actual hosts; exercise real install acceptance in authenticated hosts; formalise configuration schemas/version migrations and deprecation policy. Decide ownership/licence for third-party packages independently.
- **Blocker:** Live provider plugin registration and signed release identity unavailable. GitHub Actions minutes exhausted.
- **Files:** `pyproject.toml`, `plugin.json`, `.claude-plugin/plugin.json`, `README.md`, `CHANGELOG.md`, `docs/ARCHITECTURE.md`.
- **Tests:** Wheel build and clean temporary venv install, bundled profile presence, CLI doctor and weekly entry point checked locally. Still test host plugin discovery and invocation, checksum delivery, clean uninstallation and reproducible artifact provenance.
- **Acceptance:** A new user can install KStack from verified distribution and reproduce supported workflows without source modification.

### KSK-603 — Optional dashboard/observability

- **Original:** 16.
- **State:** OPTIONAL and NOT STARTED; core has JSON views for skill status, queue, host status and evidence.
- **Remaining:** Only after stable CLI integrations, optionally add a local-first UI showing installed versions, evidence, candidate evaluations, schedule, rollback preview and per-host status. Avoid duplicate state/permissions logic or decorative controls.
- **Why:** Not essential for immediate development quality; GUI runtime acceptance unavailable here. Prioritised below core acceptance by design.
- **Files:** Existing JSON CLI modules; future UI adapter calling verified operations.
- **Tests:** Keyboard navigation, accessibility, responsive layout, no secret exposure, no confusing false status labels, actual browser E2E.
- **Acceptance:** Interface genuinely improves maintainability and exposes exact CLI-supported behaviour, without creating a second untrusted mutation pathway.

---

## External acceptance environments required

- **Codex:** Authenticated Codex CLI/desktop, supported model access and project skill discovery. Verify explicit and implicit activation; never infer effective model name from configuration text alone.
- **Claude Code:** Authenticated Claude Code CLI, project/global plugin/skill support and permission checks.
- **macOS / Windows:** Native filesystem and host integration acceptance on actual OS versions. Linux tests alone are insufficient.
- **Browser:** Local authorised Playwright/BreakSwarm environment with working Chromium and test target.
- **Live GitHub:** Credential with limited repository permissions for authenticated watchlist/read, explicit write approval only for delivery; don't copy secrets into KStack files.
- **Full autonomous evaluation:** Credential-isolated worker environment capable of actually running models, capturing objective results and independently reviewing candidate skills.

## Single next action for Codex

1. Open the **latest `main`** of `Itskorrah/kstack` (not an older local snapshot) and reconcile it with this ledger.
2. Run the baseline tests and package checks locally; do not invoke GitHub Actions.
3. Begin **KSK-101 through KSK-104**, focusing on real host acceptance and genuinely transactional install/rollback; work through all remaining phases autonomously and update this file after each verified milestone.
4. Merge verified work when authorised and safe. If real host credentials are absent, implement/test standalone components and move on instead of blocking the whole programme.

**No future task in this file should be labelled complete until its objective acceptance criteria have genuinely been met.**

## 21 October 2026 update — PR #5 verified; PR #6 revision binding

### KSK-101 / KSK-103 — PR #5

- **State:** The recovery preflight and portable case/Unicode path-collision checks are merged into `main` at `034e191f9771c0b895b452a4ae31adefa142f6e3`.
- **Additional fix found during Windows verification:** State-lock metadata is read through the descriptor holding the Windows byte-range lock. Windows' invalid-process-ID result is treated as confirmed process absence. Installer tests compare native paths and skip symlink setup when Windows denies the required privilege.
- **Evidence:** On Windows with Python 3.13, 114 tests passed and 8 platform-dependent tests skipped; compileall, `doctor`, `schedule-status`, and `git diff --check` passed. Hosted Actions were not used.
- **Residual acceptance:** Native macOS and other host integrations remain unverified. Recovery preflights all entries but still replaces files one at a time; filesystem races and interruption during the recovery writes can require another recovery attempt.

### KSK-303 / KSK-503 — PR #6

- **State:** The verifier now compares before/after Git revision, branch, cleanliness, and a digest of the index, tracked changes, and non-ignored untracked file contents. It stores the digest rather than raw diffs. A dirty baseline can still verify when unchanged; changed or unavailable Git fingerprints produce an incomplete result.
- **Files:** `src/kstack/verification.py`, `src/kstack/delivery.py`, `tests/test_verification_revision_stability.py`, `README.md`, `docs/ARCHITECTURE.md`, `docs/SECURITY.md`.
- **Evidence:** Eight focused PR #6 regression tests passed locally. The combined full-suite and CLI checks are the remaining gate before merging PR #6.
- **Residual limits:** Ignored files are outside the Git fingerprint. Modified submodules and special files are treated as uninspectable; transient edits restored before the final snapshot cannot be detected. Git checks do not sandbox trusted verification commands or prove that commands exercised the intended behavior.
- **Resume:** Fetch `main`, run `PYTHONPATH=src python -m unittest discover -s tests -v`, `python -m compileall -q src/kstack scripts tests`, `python scripts/kstack.py doctor`, and `python scripts/kstack.py schedule-status`; repair failures and update both status files before merging.
