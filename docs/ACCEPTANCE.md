# KStack verification and real-host acceptance

## Local development checks

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src/kstack scripts
python scripts/kstack.py doctor
python scripts/kstack.py queue
python scripts/kstack.py schedule-status
python scripts/kstack.py host-status --host codex --scope global
python scripts/kstack.py lock-status
```

A `doctor` invocation **without** `--host` validates package data; with `--host` it requires an actual managed installation manifest and checks that installed skills match the active generation. Neither mode executes Codex or Claude.

The local suite also exercises staged host-generation rollback/recovery, unmanaged-file conflicts, separate-process state locking, pinned multi-file local packages with sibling version/capability declarations, dependent-aware external removal, available versus installed workflow reporting, and synthetic monorepo inspection. These are local fixtures; they do not certify third-party integrations or real host invocation.

## Disposable project smoke test

Create a temporary project containing a small Python module and real regression tests. Set trusted `verification_commands` explicitly through `kstack.json`, install KStack project-scoped and exercise the CLI:

```bash
python scripts/kstack.py inspect-project --project /absolute/disposable/project
python scripts/kstack.py bootstrap --project /absolute/disposable/project --instructions
python scripts/kstack.py bootstrap --project /absolute/disposable/project --instructions --apply
python scripts/kstack.py install --host codex --scope project --project /absolute/disposable/project
python scripts/kstack.py doctor --host codex --scope project --project /absolute/disposable/project
python scripts/kstack.py route 'Fix an API validation bug and run regression tests' --project /absolute/disposable/project --host codex --scope project
python scripts/kstack.py verify-project --project /absolute/disposable/project
python scripts/kstack.py verify-project --project /absolute/disposable/project --run
```

The `--run` step is only appropriate after the **user/trusted project owner** has reviewed the commands in `kstack.json`. Config v2 `verification_targets` add project-relative workspace directories with argument-list commands; KStack validates that paths stay inside the project and runs each command from its target directory. Manifest-derived suggestions remain unapproved until the owner copies reviewed commands into configuration. The runner does not sandbox arbitrary project code.

## Required independent host tests (not yet run)

1. Verify installed KStack skill name/description is exposed by the actual host, not just present on disk.
2. Ask a task explicitly referencing KStack and inspect evidence of actual skill invocation.
3. Ask a representative task without naming KStack; verify appropriate invocation and avoid activating on negative-trigger tasks.
4. Repeat after host restart, update, rollback and uninstall.
5. Test a reviewed, complete Evolve package including its sibling files and required utilities through an actual host session. Local `kstack-package.json` dependency fixtures validate the KStack extension only; do not claim external integration on the basis of catalogue metadata.
6. Run representative Python and React tasks with fresh tests; compare to without-KStack baseline and record actual failures or improvements.
7. Check host permissions, cancellation, fallback and rejection of prompt-injected third-party skills.

## Current environment boundaries

The ChatGPT container has Python and Git for local fixtures, but no authenticated Codex CLI, Claude Code CLI, native Windows/macOS host, live GitHub network from its shell or BreakSwarm browser integration. Connector-based GitHub delivery is separate from the source package's runtime abilities. This environment can run deterministic integration tests, create git repositories locally and push via a connected GitHub tool; it cannot honestly certify real agent host use.

No GitHub Actions tests should be invoked merely to substitute for unavailable local or native tools.
