# KStack operations and continuous improvement

## Cadence

- **Weekly:** research relevant developer agents/skills, watch monitored upstreams, record candidates and deltas, reject hype without evidence.
- **Monthly:** deeper review of the top candidates, version changes, licence changes, duplicate capability and measured project quality.
- **Quarterly:** review active skills for redundancy, weak selection, security posture, context bloat and regression costs.
- **After development sessions:** record verified failure patterns, missing acceptance gates, relevant before/after outcomes and useful specialist guidance. No local data is uploaded automatically.

The weekly ChatGPT scheduled intelligence brief is independent from the local KStack command line. It **does not exist until the user creates it**, and it must not assume the scheduled environment can access the user's local checkout or run isolated tests.

## Routine commands

```bash
python scripts/kstack.py list
python scripts/kstack.py maintenance                  # network reads only; no activation
python scripts/kstack.py status
python scripts/kstack.py doctor
```

Maintenance is read-only with respect to GitHub but writes local discovery/assessment state. It downloads only `SKILL.md` candidate text for review. GitHub API limits and source changes are reported as errors, not invented matches.

**High-autonomy** promotion also requires review files from independent rehearsals:

```bash
python scripts/kstack.py maintenance --apply --reviews /private/reviews
python scripts/kstack.py install --host codex --scope global --dry-run
python scripts/kstack.py install --host codex --scope global
```

Use `--bundled-only` for just KStack's original skills, and `--state` for an alternate local state directory. Different workstations need separate installations and careful sharing of reviewed, nonsecret approved state. Do not commit `~/.kstack` to this public repository.

## Quality criteria

Keep candidate adoption small: prioritise demonstrated user value and specific coding domains. For a difficult task, prefer additional local verification to multiplying parallel agents. Each new skill needs a precise triggering description, real nontrivial instructions, a distinct role and an honest failure/permission boundary. Never promote a tool merely because it is popular or recently announced.

## Incident handling

1. Stop using a suspicious agent skill in the host; remove access to sensitive workspaces and revoke exposed credentials if needed.
2. Inspect the active manifest and pinned hash; run `rollback N` to the appropriate pre-change snapshot.
3. Reinstall managed skills into each host and restart each agent process.
4. Investigate exact source, reviewer evidence and any host actions. If needed, remove the trust source from `data/policy.json` and the watchlist.
5. Add a reproducible regression case before considering future updates.

## Unverified milestones

- First authenticated GitHub discovery against all watched upstreams.
- Complete real-world skill invocation under Codex, Claude Code and ChatGPT plugin hosts.
- Cross-platform Windows/macOS install/reload acceptance.
- External Evolve/pstack/BreakSwarm automated adapters and regression tests.
- Independent reviewer attestation signatures or verifiable host logs.

KStack's first release should be called a **local-first functional foundation**, not a production-autonomous continuous-coding agent.
