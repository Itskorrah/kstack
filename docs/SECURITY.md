# Security policy, trust boundaries and residual risks

KStack installs instructions that an AI coding host may interpret while possessing powerful filesystem, network or account permissions. This is a **supply-chain and prompt-injection boundary**. Neither an allowlisted publisher, source hash, passing regex scan nor high model-assigned score is a safety certificate.

## Threat model

| Boundary | Primary threat | Implemented restriction | Residual risk |
|---|---|---|---|
| GitHub discovery | Attacker-controlled source, remote redirects, changed branches | API host fixed, redirects disabled, source pinned by Git commit, oversized/truncated data rejected | Owner compromise, forged review context, GitHub API errors |
| Candidate text | Host-directed prompt injection or exfiltration instruction | Heuristic screening, quarantine, separate promotion gate | Text can deceive an agent even with no executable blocks |
| External checkout | Modified or untracked code, local filesystem escape or Git helper execution | Exact HEAD SHA, clean Git status, tracked ordinary files, no symlinks, bounded file size, configured filesystem monitor disabled | Git remote URL may be spoofed; no cryptographic publisher attestation |
| External package copy | Runnable scripts copied into a host skill folder | Manual `--reviewed`; non-documentation requires `--allow-code`; copy never executes code | The host may execute copied code after later invocation |
| Local verification | Malicious test command | Argument-array format, `shell=False`, timeouts, reduced environment, explicit `--run` | **Not a sandbox.** Trusted command can read filesystem/network or spawn other commands |
| Installer | Collisions, user edits, symlinks, interrupted update | Refuse to adopt unmanaged files, check symlink/junction ancestors, stage and hash files, journal multi-file changes, commit manifests last, retain rollback snapshots | Files become visible one at a time; recovery is required after an interrupted process, and native Windows/macOS behavior is unverified |
| Promotion / rollback | Partial multi-file state and stale reviews | Immutable source/content binding, undo journal, OS-released advisory lock, snapshots and explicit stale-lock recovery | Local user can rewrite unsigned JSON state and fabricate review text |
| Local evidence | Corrupted or rewritten logs | Hash-linked append-only records, integrity verification | Full log can be regenerated without an independent trust root |
| ChatGPT/Codex/Claude | Wrong effective model, unavailable tool, implicit host authority | Host status reports no invocation acceptance until tested | Actual model/tool privileges belong to the host, not KStack |
| Public repository | Accidental leak of credentials/project data | State defaults to `~/.kstack`, token from process environment | User must avoid committing logs, secrets or private data |

## High-autonomy promotion policy

Autonomy does **not** imply unrestricted privileges. Only pinned, single-file Markdown skills from approved publishers, with zero static blockers and independently attested sandbox evidence, qualify for KStack's current automatic promotion gate. `--autonomous` does not execute downloaded code. Actual independent review data is supplied externally; the current CLI validates its format and thresholds but cannot authenticate the reviewer or prove rehearsal occurred. **Do not use production secrets or sensitive workspaces in candidate evaluation.**

Multi-file packages can be copied from a clean Git checkout using `external-install` after explicit manual review. This is a separate host-installation workflow, not candidate auto-promotion. Source pinning doesn't make a multi-file package safe: scrutinise scripts, tools, hooks, transitive dependencies and licence obligations.

Upgrades requesting credential access, executable hooks, new networks, account permissions, deployments, payments or security bypasses require separate authority. A third-party skill's own text is never a valid grant of permission.

## Developer rules

- Never execute arbitrary downloaded installation scripts during discovery or automated assessment.
- Don't paste tokens into GitHub issues or KStack's public repository. Use narrow host permissions and process-environment credentials where supported.
- Run only **trusted** project verification commands, and use disposable fixtures for unknown projects. `verify-project --run` does not create isolation.
- Preserve active generation until a complete replacement has been verified; detect and recover pending state or host-file journals under their respective locks with `recover-install` for host files.
- Inspect locks with `lock-status`. State mutations use `.kstack-write.lock`; recover a verified stale owner explicitly with `recover-lock --owner-pid PID`. Legacy `.write-lock` directories still block writes and require inspection. KStack never steals live or unverifiable locks.
- Handle host file ownership, symlink/junction paths and installed content hashes defensively. Real Windows/macOS acceptance is still pending.
- Verify reviewers and outputs through trustworthy independent evidence where possible. User-generated score fields and hash chains alone are insufficient for unattended supply-chain decisions.

## Incidents and recovery

1. Disable or stop the suspicious skill in the host; stop dependent agents.
2. Revoke any exposed credentials and restrict host network/filesystem access as needed.
3. Inspect `~/.kstack/active.json`, `history.json`, `candidate-revisions.json`, `evidence.json` and host-managed manifests. Treat local files as evidence with limited integrity guarantees.
4. If a promotion/rollback was interrupted, the next locked state mutation will attempt undo-journal recovery. If a host file update was interrupted, inspect the journal and run `kstack recover-install --host HOST --scope SCOPE`; for uncertain state, stop and investigate rather than manually editing manifests.
5. Run `kstack rollback N` against a verified approved-state snapshot, or `kstack rollback-install --host HOST --scope SCOPE` for a retained host generation, then restart actual agent sessions.
6. Quarantine compromised publishers/versions and fix the root cause; add a genuine regression test before re-adoption.

## Explicit outstanding security work

Independent host/sandbox execution, signed reviewer/test attestations, external dependencies outside the declared local sibling graph, simultaneous multi-host updates, platform-specific privilege review and durable cross-machine provenance are not implemented. Host transactions are recoverable but not simultaneously visible across files; Windows/macOS behavior still requires acceptance. These are tracked in `CODEX_TODO.md` under KSK-101/102/103/401/402/403.
