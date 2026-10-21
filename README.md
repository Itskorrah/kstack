# kstack

**A local-first toolkit for focused, reviewable coding-agent workflows.**

Inspect a project, route a task to a relevant workflow, install managed skill instructions into an existing host, and verify only the commands you trust.

**Python 3.10+ · MIT · No runtime dependencies · Local-first**

[Quick start](#quick-start) · [Project workflow](#project-workflow) · [Capabilities](#capabilities) · [Security](#security-and-limitations) · [Documentation](#documentation)

> **v0.2 preview.** kstack provides a functional local CLI for project inspection, workflow routing, skill-file management, and verification. It works alongside Codex or Claude Code; it does not start an agent or prove that a host loaded or followed installed instructions. See the [implementation status](IMPLEMENTATION_STATUS.md).

## Use with Codex — copy-and-paste workflows

Open the **target project** in Codex. This prompt installs or reuses kstack safely, **verifies** its setup and immediately routes and performs real work.

```text
In my current Codex project, set up and use https://github.com/Itskorrah/kstack. Read the current README, AGENTS.md, docs/SECURITY.md and prompts/codex/setup-and-run.md. Inspect existing installed skills and Git state. Check out kstack into a safe temporary location, read its README, AGENTS.md, security model and actual CLI help. In the currently open target project, run the Python 3.10+ CLI's `doctor`, `list`, `inspect-project --project TARGET` and `route TASK --project TARGET`. Preview project-local install with `install --host codex --scope project --project TARGET --dry-run` and project bootstrap with `bootstrap --project TARGET --instructions`; apply only ownership-safe reviewed changes. Verify with `doctor --host codex --scope project --project TARGET` and `host-status`. Use the routed guidance to carry out a real, scoped target-project task. kstack does not itself invoke an agent, so Codex must perform the task and verification. Avoid installing duplicate orchestrators or executing third-party skill packages discovered by kstack. External package review, commit-pinning and explicit approvals are required. Preview verification commands before `verify-project --run`; the runner is not a sandbox. Run local verification; commit and push verified scoped changes on a feature branch, open a PR and merge when permitted without bypassing branch protections or security. Do not rely on GitHub Actions. Report evidence and blockers.
```

Additional copyable prompts: [full setup](prompts/codex/setup-and-run.md) · [update](prompts/codex/update.md) · [resume](prompts/codex/resume.md) · [extended autonomous](prompts/codex/autonomous.md).

## Why kstack

Project instructions become stale, and broad prompts make it harder to keep work consistent. kstack keeps reusable workflows discoverable, recommends a focused workflow for each task, and makes project changes and verification explicit.

It is designed to work with the coding-agent host you already use. Project detection and routing run locally, and the Python package uses only the standard library.

## Quick start

Requires Python 3.10 or later. Git is needed for reviewed external-package workflows.

```bash
git clone https://github.com/Itskorrah/kstack.git
cd kstack

python scripts/kstack.py doctor
python scripts/kstack.py list
python scripts/kstack.py inspect-project --project .
python scripts/kstack.py route "Fix a workspace regression" --project .
```

Install the bundled skills into Codex:

```bash
python scripts/kstack.py install --host codex --scope global --dry-run
python scripts/kstack.py install --host codex --scope global
python scripts/kstack.py doctor --host codex --scope global
python scripts/kstack.py host-status --host codex --scope global
```

Use `--host claude` for Claude Code. Choose `--scope project` and provide `--project PATH` to install for one repository. The installer manages only files owned by kstack and refuses to adopt or overwrite unmanaged files.

`doctor` and `host-status` check installed files and their integrity. They do not prove that a coding-agent host loaded or invoked those files.

## Project workflow

Inspect a project, preview setup changes, and route a task:

```bash
python scripts/kstack.py inspect-project --project /path/to/app
python scripts/kstack.py bootstrap --project /path/to/app --instructions
python scripts/kstack.py bootstrap --project /path/to/app --instructions --apply
python scripts/kstack.py route "Refactor the settings screen" --project /path/to/app
```

Project inspection recognizes declared npm, pnpm, and Cargo workspace roots. It can suggest per-root verification targets, but does not turn suggestions into trusted commands. Review the setup preview before using `--apply`.

To run project verification, configure commands you trust and explicitly request execution:

```bash
python scripts/kstack.py verify-project --project /path/to/app
python scripts/kstack.py verify-project --project /path/to/app --run --timeout 120
```

The first command previews configured checks. The second runs them. This runner is not a security sandbox.

For Git projects, verification records before-and-after revision and worktree fingerprints. It stores a digest of tracked changes and non-ignored untracked files, not their contents. A changed or unavailable Git fingerprint leaves the result incomplete, even when every command passes. Ignored files are outside this check; non-Git projects remain supported without revision binding.

## Capabilities

- **Project setup:** Inspect known manifests, identify declared workspaces, and create a project profile or managed instruction sections while preserving existing content.
- **Task routing:** Recommend relevant bundled workflows from task signals; project profiles can refine a specialist match but cannot create one. Routing is deterministic metadata-based guidance, not model-driven reasoning or host invocation.
- **Skill management:** Install, uninstall, inspect, recover, and roll back kstack-managed skill files for Codex and Claude Code.
- **External packages:** Copy manually reviewed skills from a clean, commit-pinned Git checkout. Verify installed-file integrity and declared sibling dependencies; refuse to overwrite unowned files.
- **Discovery and maintenance:** Scan watched repositories, keep candidate sources pinned, and expose local review and maintenance queues. Candidate content is not executed.
- **Local verification:** Preview or run owner-configured project commands and inspect the local evidence journal.

For command options, run `python scripts/kstack.py --help` or `python scripts/kstack.py COMMAND --help`.

### External skill packages

Review the upstream source, licence, files, and permissions before installing anything. kstack copies files; it does not run upstream install scripts. The optional `kstack-package.json` format describes sibling skills and capabilities for kstack and is not a general package standard. Use `external-uninstall --name PACKAGE --dry-run` to preview removal; removal checks file ownership and integrity and protects installed dependents.

## Discovery and maintenance

The scanner reads the repositories in `data/watchlist.json`. It may require `GITHUB_TOKEN` for network reads.

```bash
python scripts/kstack.py scan
python scripts/kstack.py maintenance
python scripts/kstack.py queue
python scripts/kstack.py schedule-status
```

Discovery pins candidate revisions and applies review gates, but submitted review records are not independently authenticated by kstack. The `kstack-weekly` entry point can be run by an external scheduler; kstack does not register a scheduled task or run a background service.

## Security and limitations

- Treat skill files and repository content as untrusted instructions. Pinning and screening reduce risk but do not establish trust.
- External package installation requires a deliberate review and copies content without executing it. The optional `--allow-code` flag is an explicit risk decision for packages that include code or assets.
- Project verification runs commands configured by the project owner only when `--run` is supplied. It does not isolate those commands.
- Local state is not encrypted. File locks and recovery journals protect against interrupted writes, not a malicious local account.
- A successful install or file-integrity check is not evidence that Codex or Claude Code invoked a skill.

Read the [security model](docs/SECURITY.md), [architecture](docs/ARCHITECTURE.md), and [acceptance plan](docs/ACCEPTANCE.md) for details.

## Documentation

- [Implementation status](IMPLEMENTATION_STATUS.md) — what works and what still needs acceptance
- [Known gaps and handover](CODEX_TODO.md) — remaining development work
- [Architecture](docs/ARCHITECTURE.md) — system design and data flow
- [Security](docs/SECURITY.md) — trust boundaries and safeguards
- [Acceptance plan](docs/ACCEPTANCE.md) — evidence required for host and platform claims
- [Review schema](docs/REVIEW_SCHEMA.md) and [maintenance procedures](docs/MAINTENANCE.md)

## Development

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src/kstack scripts
python scripts/kstack.py doctor
```

See [AGENTS.md](AGENTS.md) for repository conventions. Keep changes local-first, add tests for behavior changes, and describe verification results accurately.

## Licence

kstack's code and bundled skills are licensed under the [MIT License](LICENSE). Third-party content remains under its own licence.
