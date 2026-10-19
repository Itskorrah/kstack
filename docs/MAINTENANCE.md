# KStack operations and evolution

KStack is **externally scheduled**, not a daemon. Run the weekly maintenance entry point from an OS/user-authorised scheduler. The separate ChatGPT scheduled prompt produces intelligence reports but does not automatically inherit your local source checkout.

## One-off and weekly checks

```bash
python scripts/kstack.py doctor
python scripts/kstack.py status
python scripts/kstack.py queue
python scripts/kstack.py schedule-status
python scripts/maintenance_runner.py              # preview; NO network requests
python scripts/maintenance_runner.py --run        # single GitHub watchlist scan
```

The installed package exposes `kstack` and `kstack-weekly`. The runner uses the `Australia/Sydney` timezone for calendar-week eligibility and leaves a local record of the most recent attempt. It does **not** automatically create, install or execute an OS scheduler job. Use a trusted user's scheduler with the same commands. The monthly in-depth review is **not** marked complete by a mere GitHub metadata scan; the separate research task must provide that analysis.

A scanner's network failure is reported as a partial attempt, not a successful evaluation. A scheduled discovery is only a read-only source observation. It cannot silently install a third-party skill.

## Candidate evaluation and policy-gated promotion

```bash
python scripts/kstack.py scan
python scripts/kstack.py assess owner/repo:skills/name/SKILL.md
python scripts/kstack.py queue
# Run genuine sandboxed independent review first; see docs/REVIEW_SCHEMA.md
python scripts/kstack.py promote owner/repo:skills/name/SKILL.md --review /private/review.json --autonomous
python scripts/kstack.py install --host codex --scope global
```

If review evidence cannot be obtained, leave the candidate assessed or quarantined. Do not invent ratings, test artefacts or reviewer identity.

For a reviewed multi-file upstream package, use the distinct `external-install` workflow documented in the root README. The `--reviewed` flag is a manual user/operator assertion; it is not a cryptographic security guarantee.

## State backup and recovery

Back up the local state directory privately. `export-lock` generates a portable source/hash manifest but **does not include external skill bodies** and cannot install a copied manifest on a new machine. This avoids silently trusting unreviewed external packages on another device.

If the current generation is suspect:

1. Stop coding agents that might use the skill.
2. Inspect `kstack status`, `kstack evidence`, installed file hashes and any pending undo journal.
3. Quarantine the source and revoke secrets if exposed.
4. Restore the appropriate `kstack rollback N`, then re-run installation in each affected host; restart/reload the agent.
5. Re-run local tests and genuine host acceptance, then write a regression test and incident summary.

Never bypass branch protections, change external account access or run downloaded code merely to make an update succeed. Keep credentials out of state, source control and reports.

## Recommended cadence

| Timing | Operational activity |
|---|---|
| Weekly | Scan watched GitHub sources, deduplicate candidates and produce a concise report |
| Monthly | Deep review of promising candidates, security changes and verified stack effectiveness |
| Quarterly | Identify redundant skills, broken hosts, outdated instructions and excess context |
| After substantial work | Record permission-scoped, honest outcomes and failed acceptance tests |
| On new upstream release | Evaluate a pinned revision without silently replacing the active version |

Remaining unattended sandbox evaluation, signing and actual OS scheduler installation are tracked in `CODEX_TODO.md`.
