---
name: kstack-setup
description: Guide a developer through the one-time KStack installation, verification, project-profile selection and optional review-based high-autonomy configuration.
---

# Set up KStack

This is an interactive onboarding workflow; installation of a plugin does not silently grant OS filesystem or GitHub permissions.

1. Identify the user's coding host (Codex, Claude Code or another agent), OS, available repositories and intended installation scope.
2. Check if KStack files and local terminal access are genuinely available. An enabled ChatGPT plugin does not imply the Python CLI runs in ChatGPT's hosted session.
3. Use the checkout's `python scripts/kstack.py install --host codex|claude --scope global|project` when local permission and a checkout exist; show the dry-run and preserve local changes.
4. Run `python scripts/kstack.py doctor --host ...`; then start a fresh agent session and ask it to enumerate `kstack-router` and `kstack-verify` to test real host discovery.
5. Explain that external integrations remain separately installed and require their own host compatibility checks. Set a project profile where beneficial.
6. Describe the high-autonomy gate: trusted, pinned Markdown, strict screening, independent sandbox rehearsal and review. No automatic execution of GitHub-sourced code or host permission escalation.
7. Offer only the minimal necessary setup steps and report exactly which checks completed.
