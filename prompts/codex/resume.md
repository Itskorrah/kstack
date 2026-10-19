# kstack — Resume verified work in Codex

## Copy into Codex

```text
Work in my currently open Codex project. Use https://github.com/Itskorrah/kstack as the source of truth. Read its latest README, AGENTS instructions, actual CLI help and the linked workflow guidance. Preserve existing work, review tools before execution and do not stop at installation.

Inspect Git status, installed files, kstack queue/maintenance records, project profiles and previous actual checks. Reconcile records against current code, select the next incomplete scoped task and continue execution and verification; do not infer success from older chat summaries.

Avoid installing duplicate orchestrators or executing third-party skill packages discovered by kstack. External package review, commit-pinning and explicit approvals are required. Preview verification commands before `verify-project --run`; the runner is not a sandbox.

After local verification, follow the scoped Git delivery policy below. Report actual results, not assumptions.
```

## Permissions, verification and safe delivery

- Work against the current target project unless the user specifically requests changes to the kstack source. Inspect Git status, remotes, existing Codex configuration and AGENTS instructions. Preserve pre-existing changes; no reset, clean, force-push or overwriting unmanaged skills.
- Inspect source, provenance, licence and exact installation commands first. Prefer project-local integration. No credentials, global model or authentication edits, billable services or deployment without distinct approval.
- This prompt authorises scoped implementation and local checks, then commit to a feature branch, push, PR and **merge verified changes automatically where permitted**. Respect branch protections, required checks/reviews and stricter project permission rules. Never merge known critical defects. GitHub Actions allocation may be exhausted: do not dispatch workflows; run meaningful local checks and label hosted CI unverified.
- Report installed/reused skills, actual command results, host-loading limits, changed files, PR/merge state and blockers. File-integrity checks alone cannot certify that Codex invoked a skill.
