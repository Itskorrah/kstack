<div align="center">

# KStack

**A better default for coding agents. A developer stack that improves on evidence.**

Portable skills · Local-first tooling · High-autonomy governance · Reproducible installs

[Quick start](#quick-start) · [How it works](#how-kstack-works) · [Update policy](#evolution--updates) · [Architecture](docs/ARCHITECTURE.md) · [Security](docs/SECURITY.md) · [Maintainer guide](docs/MAINTENANCE.md)

</div>

> **Status — v0.1 foundation.** KStack is an installable, Python-standard-library skill management CLI, four developer workflows plus one onboarding skill, a portable plugin manifest, project-specific routing, read-only GitHub candidate discovery, evidence-based promotion and rollback. Local unit tests pass. **It is not an always-on agent, does not integrate or execute all external frameworks, and has not completed authenticated GitHub API or ChatGPT/Codex/Claude host acceptance.** [Limitations](#current-limitations) are part of the product contract.

## Why KStack

Repeatedly pasting an enormous development prompt is a poor way to enforce engineering standards. KStack keeps the stable parts in versioned skills, makes relevant instructions discoverable to compatible hosts, and treats external skills as *candidates* until there is evidence they improve actual projects.

KStack prefers **one lead workflow plus the smallest relevant specialists**. Adding more agents isn't the goal. Better tested, maintainable software is.

```text
Task in Codex or Claude Code
           │
           ▼
  KStack router + project profile
           │
           ├── Engineering audit / architecture
           ├── Evolve, if separately installed and appropriate
           ├── Framework and UI specialists, if present
           └── Independent verification
           │
           ▼
  Fresh local checks → verified delivery

Read-only GitHub discovery ──> Quarantine / assessment
                                      │
                     pinned source + independent rehearsal
                                      │
                          policy and evidence gate
                                      │
                         promote / revert / reinstall
```

## Quick start

Requirements: **Python 3.10+** and a local checkout. No `pip install` is necessary for the checkout CLI; no runtime dependencies, API key or hosted CI are required for offline commands.

```bash
git clone https://github.com/Itskorrah/kstack.git
cd kstack
python scripts/kstack.py list
python scripts/kstack.py route "Improve the Jotstead web interface and test it" --profile web
python scripts/kstack.py install --host codex --scope global --dry-run
python scripts/kstack.py install --host codex --scope global
python scripts/kstack.py doctor --host codex --scope global
```

For Claude Code:

```bash
python scripts/kstack.py install --host claude --scope global --dry-run
python scripts/kstack.py install --host claude --scope global
python scripts/kstack.py doctor --host claude --scope global
```

Install in one project instead:

```bash
python scripts/kstack.py install --host codex --scope project --project /absolute/path/to/project
```

The installer writes **only managed `SKILL.md` files** to supported host directories. It will refuse to overwrite pre-existing different content or locally modified managed files. `--dry-run` previews changes; `uninstall` removes only KStack-managed files. Reload the host and test skill discovery yourself — the `doctor` command verifies files and hashes, not model behaviour.

For both hosts, the installed core skills are `kstack-router`, `kstack-audit`, `kstack-verify`, `kstack-ship` and `kstack-setup`. For example, a configured Codex agent can be asked to use `$kstack-router`; in Claude Code, use `/kstack-router`. Natural-language skill selection is host-dependent and must be verified after installation.

## How KStack works

| Component | Included | Responsibility |
|---|---|---|
| KStack Router | Yes | Choose minimal relevant workflows; no agent-process execution |
| KStack Audit | Yes | Inspect actual architecture, blast radius and threats |
| KStack Verify | Yes | Fresh local testing and honest, scoped evidence |
| KStack Ship | Yes | Release documentation and authorised GitHub delivery |
| KStack Setup | Yes | Guide one-time skill installation and verification |
| Project profiles | Yes | Web, native desktop, mobile, Python, AI agent, general |
| External ecosystem catalogue | Yes | Evolve, pstack, Superpowers, UI skills, Vercel, BreakSwarm and more **as metadata** |
| GitHub candidate scanner | Yes | Check pinned source trees and find `SKILL.md` candidates (needs network) |
| Auto-promotion gate | Yes | Requires stringent screening, independent sandbox review and pinned content |
| Runtime multi-agent swarm | No | Uses an existing coding host; never claims to spawn agents |
| BreakSwarm/RepoPilot MCP bridge | Not yet | Their catalogue entries are not working integrations |
| Hosted scheduled job | Not provisioned | A scheduler prompt is provided; it must be separately installed |

KStack will not copy third-party repositories or execute their scripts merely because the catalogue lists them. Use their own documented installation processes and respect licence obligations.

### Commands

| Command | What it actually does |
|---|---|
| `list` | Show bundled and promoted skills, plus tracked external integrations |
| `route "task" --profile web` | Suggest KStack skills and conditional project guidance |
| `scan` | Read configured GitHub repositories and record changed source commits |
| `assess "owner/repo:path/to/SKILL.md"` | Read skill at an immutable commit; screen, score, quarantine and hash |
| `promote ID --review review.json --autonomous` | Adopt only if independently reviewed and all high-autonomy gates pass |
| `maintenance [--apply --reviews DIR]` | Discover/assess candidates; optionally promote qualifying reviewed ones |
| `status` | Produce a machine-readable state and blocker report |
| `rollback SNAPSHOT` | Restore prior active-skill manifest; reinstall hosts afterwards |
| `install` / `uninstall` | Install or remove managed host skills without overwriting user edits |
| `doctor` | Verify local source/installed file integrity |

Use `python scripts/kstack.py COMMAND --help` for arguments. GitHub reads may require `GITHUB_TOKEN` for sufficient API rate limits or private repositories; this variable is read from the process environment, not saved in KStack. Do not put tokens in files or chat.

## Evolution & updates

High autonomy **does not mean trust every update**. KStack has three stages:

1. **Discover** — a scheduled assistant can research official releases and nominate new tools; the CLI scans specifically watched GitHub repositories and pins their commit SHA.
2. **Evaluate** — locally examine the exact `SKILL.md`, detect executable dependencies or suspicious instructions, confirm project relevance and independently rehearse the skill in a disposable test project. The preliminary CLI score is not an AI quality judgement.
3. **Promote** — an independently produced evidence review (`docs/REVIEW_SCHEMA.md`) must pass the configured threshold. The high-autonomy flag allows eligible additions without an extra manual review step. Approved text is stored by SHA-256 and installed only when requested.

For a dry research pass:

```bash
python scripts/kstack.py maintenance
python scripts/kstack.py status
```

After an independent reviewer has created a truthful review JSON file and actually rehearsed the candidate in an isolated environment:

```bash
python scripts/kstack.py maintenance --apply --reviews /private/path/to/reviews
python scripts/kstack.py install --host codex --scope global
```

A change to a monitored upstream repository creates a new candidate; it does not silently replace an already approved revision. Auto-promotion accepts **single-file Markdown-only** skills, requires an allowlisted publisher, no screening flags, and an independent score of at least **92/100** with security confidence at least **95/100**. No skill code, hooks or external scripts run during screening or installation. These are restrictive *policy rules*, not a guarantee that text cannot contain malicious instructions. Review the [threat model](docs/SECURITY.md).

If you prefer to switch back to a previous generation:

```bash
python scripts/kstack.py rollback 1
python scripts/kstack.py install --host codex --scope global
```

`rollback 1` means “restore the state saved before the first promotion” — not “version 1 of a particular skill”. The snapshots reside under `~/.kstack/snapshots/` and are local. Reinstall or update each host after any manifest change; a rollback does not remotely update agents.

For a weekly watch and monthly deeper recommendation process, use the [ready-to-copy scheduled brief](docs/SCHEDULER_PROMPT.md). **No scheduled task is currently created or running by this repository.**

## Installation and security model

KStack stores local state at `~/.kstack/` by default (override with `--state`). Discovery contacts only GitHub's API. Candidate source is pinned to commit SHA and stored as UTF-8 Markdown in a content-addressed object store. Neither the scanner nor the installer invokes source text as commands.

Credentials are passed through environment variables. The CLI does not log a token. Host-installed skills can influence agents that possess powerful tools — review any skill before giving it authority, particularly third-party instructions. A trusted GitHub account, a clean regex scan and an apparently high evaluation score **do not certify safety**.

The repository is currently public; never place private project data, API keys or personal test output inside it.

## Development and verification

From the checkout:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src/kstack scripts/kstack.py
python scripts/kstack.py doctor
```

No GitHub Actions are required, configured or used by KStack's local verification. Tests cover parsing, path restrictions, quarantine, pinned candidates, independent-review gates, promotion, rollback, file ownership, installs, failure handling and routing. Unit tests with a fake GitHub API **do not prove live rate limits, actual remote response compatibility or production-host integration**.

## Current limitations

- No agent/model is executed by the KStack Python CLI; agent routing is a recommendation. Sol/Luna model selection is determined by your coding host and its actual availability.
- External integrations are explicitly *catalogue entries*, not already installed features. KStack does not yet install Evolve, pstack or BreakSwarm automatically.
- An independent agent or human must do the actual semantic quality/security review and isolated rehearsal; the CLI validates the review's structure, not the truth of the claims.
- Only `SKILL.md`-only Markdown packages qualify for unattended promotion. More complex dependencies or executable capabilities remain quarantined.
- Periodic discovery runs only when something invokes `scan` or `maintenance`; no background service or scheduled task is bundled.
- ChatGPT plugin availability, compatibility and installation still require testing in an actual host. The portable plugin manifest alone does not register a cloud app or grant integrations.
- Runtime downloads, licence attribution, live OAuth, Windows native host behaviour and public release distribution remain outside the verified v0.1 scope.

See [architecture](docs/ARCHITECTURE.md), [maintenance](docs/MAINTENANCE.md), [review evidence contract](docs/REVIEW_SCHEMA.md) and [security](docs/SECURITY.md) for specifics.

## Licence

KStack's original code and its own skills are MIT-licensed. Third-party skill and tool licences remain their respective authors' licences. The external catalogue lists references only and does not relicense upstream content.
