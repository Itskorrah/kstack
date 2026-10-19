# Security and trust model

> Security checks here are conservative **screening**, not malware detection or proof that skill instructions are trustworthy.

## Threat boundaries

- Untrusted GitHub repository metadata and `SKILL.md` text may be designed to override the host's instructions, trick an agent into using powerful tools or request credential disclosure.
- A GitHub account can change hands, a pinned commit can contain dangerous instructions, and an apparently harmless Markdown file can carry prompt injection.
- A malicious local manifest can point at unexpected files; all managed skill paths and hashes must be validated.
- User projects may contain personal files or private source code; using a repository-specific profile must not leak them to outside API providers without the user's authorisation.

## Implemented safeguards

- All network endpoints are constructed under `https://api.github.com/`, with short timeouts and redirects disabled. The optional `GITHUB_TOKEN` is only attached to that API request.
- Repository identifiers and skill paths are validated. The source is pinned to a 40-character Git commit SHA; code is never fetched from a mutable branch after assessment.
- GitHub tree truncation fails closed; oversized `SKILL.md` documents are rejected.
- Auto-promotion requires an allowlisted publisher, exactly one `SKILL.md` in its skill folder, no executable/code-fence patterns, a named independent reviewer, sandbox rehearsal and high evaluation thresholds.
- Object files are SHA-256 checked before promotion and installation; local modifications to managed skills block replacement.
- External scripts, hooks, package installers, account privileges and secrets do not pass auto-promotion. No candidate instructions are executed by KStack's CLI.
- Rollback snapshots restore an earlier approved manifest, after which managed hosts must be re-synchronised.

## Residual risks

- No regular expression can detect every prompt injection. There is no machine-verifiable guarantee that a claimed independent reviewer actually ran their stated tests; review attestations are assertions, not signed provenance.
- Text-only skills can still instruct an agent to perform destructive actions. The actual host must enforce tool-level permissions and a sandbox for untrusted instructions.
- Host tools can have stronger privileges than this CLI. Installing KStack does not reduce those privileges.
- The state directory is not encrypted at rest. Use OS account protections and keep it out of shared/public repositories.
- Installed-skill changes are not atomic across all host processes. Reload agents before accepting new behaviour.
- Dependency or repo-owner compromise can invalidate assumptions even when content hashes are intact.

## Maintenance policy

The user selected high autonomy, *not* unrestricted privilege. Safe documentation-only additions that satisfy review and policy gates may be adopted without further approval. Updates introducing executable behaviour, expanded network access, new secrets, deployments, financial expenditure or security bypasses require separate explicit authorisation. On uncertainty, quarantine and continue assessing other candidates.

## Reporting a problem

Do not paste tokens or sensitive contents into public issues. File a sanitised report with reproduction conditions, source commit and expected/observed behaviour. Do not attach private project snapshots.
