---
name: kstack-ship
description: Prepare accurate documentation, commit, push and merge independently verified coding changes after explicit delivery authorisation and required checks.
---

# KStack shipping

Use only when the task authorises GitHub delivery. Don't interpret using KStack as a standing grant to deploy, spend money or change external accounts.

1. Inspect current branch, changed files, user edits, licence constraints and secret scanning results.
2. Ensure tests are fresh relative to the changes. Identify blockers, missing cross-platform acceptance and unrun checks.
3. Update README with reproducible setup, real functionality, limitations, maintenance and user-facing examples. Don't invent screenshots or release badges.
4. Commit narrowly scoped changes, push to a development branch and create a descriptive PR when supported.
5. Merge only when the user's task authorises merging, the relevant checks pass and branch-protection/security requirements are satisfied. Never bypass those safeguards to create a green badge.
6. Independently confirm the target branch contains the intended commit. A locally committed change is not a pushed or merged change.
7. Report commit/PR URL, tests, unverified paths, blockers, residual risks and next work.

When execution is blocked, preserve a reviewable patch or branch and continue other authorised work rather than claiming completion.
