# Architecture and decisions

**v0.1 design objective:** have a small, inspectable engineering standard available to local coding hosts while evolving third-party skill selections with evidence. No daemon, database, browser service or LLM API key is needed.

## Boundaries

1. **Canonical KStack skills** (`skills/`) are portable `SKILL.md` documents with minimal trigger descriptions; the CLI installs copies into supported host folders. A separately bundled wheel copy exists so pip installs can operate without the Git repository. `AGENTS.md` and `CLAUDE.md` are repository instructions, not automatically written into arbitrary projects.
2. **Catalogue and profiles** (`data/`, `profiles/`) supply declarative metadata and advisory routing; they do not install or execute external tools.
3. **Read-only discovery** (`github_api.py`, `engine.py`) receives a curated list of GitHub owners/repos and directory prefixes. It reads metadata, resolves the default branch once to a commit SHA, then enumerates the immutable tree. Candidate IDs are `owner/repo:path/to/SKILL.md`.
4. **Quarantine and evaluation** records source SHA, content hash, declared name and description, bounded static screening and preliminary score. This is a triage mechanism, not a semantic security review.
5. **Promotion** requires explicit CLI option, curated publisher, Markdown-only single-file package, zero findings, named independent reviewer, actual sandbox rehearsal, two evidence statements and high quality/security thresholds. Approved content is immutable and stored by hash.
6. **Host installer** verifies ownership and hashes before installing; it is idempotent, non-destructive toward unmanaged content and prunes obsolete *owned* files on a subsequent sync. It does not start agents, choose model settings or install third-party executables.

## State contract

State defaults to `~/.kstack`, not a tracked GitHub directory:

```text
candidates.json         # discovered, assessed and quarantined observations
active.json             # exact approved active set (pinned hashes and commits)
history.json            # monotonically numbered promotion/rollback actions
objects/<sha256>.md     # approved immutable candidate text and assessed text
snapshots/000001.json   # prior active manifest for rollback
last-discovery.json     # time, errors and changed candidates
```

This state is personal and can expose metadata about private projects. Store and back up it appropriately, never check it into a public repository, and protect OS permissions. For multi-machine use, transfer reviewed non-secret manifest data only after verifying source identity. **There is no distributed-state sync protocol** in v0.1.

## Promotion state machine

```text
(discover) -> discovered
                 |
              assess
                 |
       +---------+-----------+
       |                     |
    assessed              quarantined
       |                     |
   independent          explanation +
   sandbox review        manual resolution
       |
  trusted + high score + no blockers
       |
     promoted -> active manifest -> next managed host install
       |
   rollback snapshot -> next managed host install
```

A new upstream SHA is a new candidate for evaluation, not an implicit upgrade. The same skill name from two active sources is forbidden. GitHub API errors are reported; incomplete/disappeared source is not treated as a passing evaluation.

## Important non-goals

- No background agent swarm or forced Sol/Luna model configuration.
- No wholesale vendoring of pstack, Evolve or third-party licences.
- No automatic remote shell execution, npm install, pip install, hooks or credential access.
- No automatic GitHub branch, issue, PR or release mutation from the scanner.
- No claim that the ChatGPT/Claude/Codex plugin hosts are equivalent.

## Extension path

Add validated integrations as adapters with separately tested host support, isolated capability scopes and explicit licence handling. BreakSwarm is the first attractive QA adapter, but its real external target use must be accepted before it becomes a release gate. Portfolio selection (RepoPilot) should remain advisory rather than authorising merges. Project-level routing could eventually use observed task outcomes instead of keyword matching, but evaluated baselines must precede any learning claims.
