import base64
import json
import tempfile
import unittest
from pathlib import Path
from kstack.engine import discover, assess, promote, rollback, candidate_id, report, analyse
from kstack.github_api import GitHubAPI, GitHubError
from kstack.installer import available_skills
from kstack.cli import ROOT
from kstack.state import read_json, write_json

SHA = "a" * 40
CONTENT = "---\nname: high-value-audit\ndescription: Audit Python code and test coverage when improving developer projects with security and performance concerns.\n---\n" + "# Audit\n\n## Steps\n\n1. Review interfaces and architecture.\n2. Check correctness, security, code quality, performance and user-facing design.\n3. Verify actual test results with negative cases.\n4. Respect scope and approval boundaries.\n\n## Validation\n\nTest against an isolated fixture and attach actual evidence.\n"
PATH = "skills/high-value-audit/SKILL.md"
REPO = "Itskorrah/sample-skills"
ID = REPO + ":" + PATH

class FakeGitHub:
    def repository(self, repo): return {"default_branch": "main", "archived": False, "disabled": False}
    def head(self, repo, branch): return SHA
    def tree(self, repo, sha): return [{"path": PATH, "type": "blob"}]
    def skill(self, repo, path, sha): return CONTENT

class EngineTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.state = Path(temp.name)
        self.api = FakeGitHub()
        self.policy = {"high_autonomy": True, "auto_promote_min_review": 92,
            "trusted_owners": ["Itskorrah"], "max_package_files": 12,
            "interests": ["coding", "developer", "code", "review", "security", "performance", "design", "testing"]}
        self.watch = {"sources": [{"repository": REPO, "paths": ["skills/"]}]}
    def prepare(self):
        self.assertEqual(discover(self.api, self.watch, self.state)["changed"], [ID])
        return assess(self.api, self.policy, self.state, ID, set(available_skills(ROOT, self.state)))
    def review(self, item):
        return {"id": ID, "content_sha256": item["content_sha256"], "engineering_quality": 98,
                "project_relevance": 99, "novelty": 96, "security_confidence": 99,
                "reviewer": "independent-agent-qa-1", "tested_in_sandbox": True,
                "test_report": "Fixture ran with no side effects and met every acceptance criterion.",
                "evidence": ["The audit finds incorrect validation through repository fixtures.",
                             "Independent review confirmed it adds distinct Python testing value."]}
    def test_full_lifecycle(self):
        item = self.prepare()
        self.assertEqual(item["status"], "assessed")
        self.assertFalse(item["blockers"])
        self.assertEqual(discover(self.api, self.watch, self.state)["changed"], [])
        promoted = promote(self.state, self.policy, ID, self.review(item), autonomous=True)
        self.assertEqual(promoted["name"], "high-value-audit")
        self.assertIn("high-value-audit", available_skills(ROOT, self.state))
        self.assertIn(ID, report(self.state)["active_external"])
        result = rollback(self.state, 1)
        self.assertEqual(result, {})
    def test_review_mismatched_hash(self):
        item = self.prepare()
        r = self.review(item)
        r["content_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "not bound"):
            promote(self.state, self.policy, ID, r, autonomous=True)
    def test_review_requires_rehearsal(self):
        item = self.prepare()
        r = self.review(item)
        r["tested_in_sandbox"] = False
        with self.assertRaisesRegex(ValueError, "rehearsal"):
            promote(self.state, self.policy, ID, r, autonomous=True)
    def test_review_low_ratings(self):
        item = self.prepare()
        r = self.review(item)
        r["engineering_quality"] = 50
        with self.assertRaisesRegex(ValueError, "below"):
            promote(self.state, self.policy, ID, r, autonomous=True)
    def test_fails_on_executable_payload(self):
        self.api.skill = lambda *args: CONTENT + "\n```bash\necho dangerous\n```\n"
        item = self.prepare()
        self.assertEqual(item["status"], "quarantined")
        with self.assertRaisesRegex(ValueError, "Promotion blocked"):
            promote(self.state, self.policy, ID, self.review(item), autonomous=True)
    def test_unknown_owner_quarantine(self):
        item = analyse(CONTENT, self.policy, "unknownowner/test", PATH,
                      [{"path": PATH, "type": "blob"}], set())
        self.assertTrue(any("publisher" in x for x in item["blockers"]))
    def test_non_markdown_dependency_quarantine(self):
        item = analyse(CONTENT, self.policy, REPO, PATH,
                      [{"path": PATH, "type": "blob"}, {"path": "skills/high-value-audit/script.py", "type": "blob"}], set())
        self.assertTrue(item["blockers"])
    def test_truncated_tree(self):
        class Bad(FakeGitHub):
            def tree(self, repo, sha): raise GitHubError("truncated")
        outcome = discover(Bad(), self.watch, self.state)
        self.assertEqual(len(outcome["errors"]), 1)
    def test_stale_object_rejected(self):
        item = self.prepare()
        (self.state / "objects" / (item["content_sha256"] + ".md")).write_text("tamper")
        with self.assertRaisesRegex(ValueError, "modified"):
            promote(self.state, self.policy, ID, self.review(item), autonomous=True)
    def test_candidate_id_blocks_traversal(self):
        with self.assertRaises(ValueError): candidate_id(REPO, "../SKILL.md")
    def test_github_api_stays_on_expected_host(self):
        data = {}
        def transport(req):
            data["url"] = req.full_url
            return {"sha": SHA}
        api = GitHubAPI(token="test-secret", transport=transport)
        api.head(REPO, "main")
        self.assertTrue(data["url"].startswith("https://api.github.com/repos/"))
        self.assertNotIn("test-secret", data["url"])
    def test_same_source_revision_can_replace_itself(self):
        item = self.prepare()
        promote(self.state, self.policy, ID, self.review(item), autonomous=True)
        # Simulate a changed upstream revision of exactly this pinned skill.
        next_commit = "b" * 40
        self.api.head = lambda repo, branch: next_commit
        changed = discover(self.api, self.watch, self.state)
        self.assertEqual(changed["changed"], [ID])
        # The CLI excludes the same active ID from its duplicate-name check.
        names = set(available_skills(ROOT, self.state))
        names.discard(read_json(self.state / "active.json")[ID]["name"])
        updated = assess(self.api, self.policy, self.state, ID, names)
        self.assertFalse(updated["blockers"])
        self.assertEqual(updated["commit"], next_commit)
        promote(self.state, self.policy, ID, self.review(updated), autonomous=True)
        self.assertEqual(read_json(self.state / "active.json")[ID]["commit"], next_commit)
        rollback(self.state, 2)
        self.assertEqual(read_json(self.state / "active.json")[ID]["commit"], SHA)
    def test_bad_repo_name(self):
        with self.assertRaises(ValueError): GitHubAPI(transport=lambda req: {}).repository("https://evil.invalid/")
