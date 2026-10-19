# Independent candidate review format

KStack supports high-autonomy promotions only when another evaluator has reviewed and actually rehearsed the pinned skill in a **disposable isolated project**. KStack checks the declaration format but cannot independently prove the reviewer ran a real model session. Never invent scores or report unperformed tests.

1. Run `python scripts/kstack.py scan` and then `assess owner/repo:path/to/SKILL.md`.
2. Read the resulting assessment from `~/.kstack/candidates.json` and inspect the pinned skill content at `~/.kstack/objects/<sha256>.md` as **untrusted data**.
3. Examine the publisher, provenance, licence, dependencies, trust boundaries and overlap with active skills.
4. If the content is documentation-only and passes screening, test it on a scratch repository with an available compatible coding agent and verify objective outcomes.
5. Save a local JSON review using the **exact candidate ID and content SHA-256**. Example shape below; the example scores are placeholders and must not be submitted as real findings:

```json
{
  "id": "owner/repo:skills/example/SKILL.md",
  "content_sha256": "<the actual sha256 from assess>",
  "reviewer": "independent-reviewer-identification",
  "engineering_quality": 0,
  "project_relevance": 0,
  "novelty": 0,
  "security_confidence": 0,
  "tested_in_sandbox": false,
  "test_report": "State exact commands, fixtures and observations; never fabricate.",
  "evidence": [
    "First substantive observation tied to an independently observed result.",
    "Second substantive observation tied to a distinct independently observed result."
  ]
}
```

Scoring: integer 0–100. Weighted score is 35% engineering quality, 35% project relevance, 15% novelty and 15% security confidence. Autonomous promotion needs weighted score ≥92 and security confidence ≥95, plus the other gates. The initial text score from `assess` helps prioritise candidates; it is not a promotion score. An existing bundled/active skill name causes quarantine, never silent replacement.

Example after genuine assessment and isolated test:

```bash
python scripts/kstack.py promote "owner/repo:skills/example/SKILL.md" --review /private/reviews/example.json --autonomous
python scripts/kstack.py install --host codex --scope global --dry-run
python scripts/kstack.py install --host codex --scope global
```

If the risk cannot be bounded or the rehearsal cannot be run, leave the candidate in quarantine. Do not relabel a static scan as a sandbox test.
