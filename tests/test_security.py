import unittest
from kstack.security import parse_skill, screen, digest, valid_repo, valid_path

SAMPLE = "---\nname: review-app\ndescription: Review a repository when a user requests an independent quality audit.\n---\n# Review\n" + "Inspect the source and use tests; do not assert unrun checks have passed.\n" * 5

class SecurityTest(unittest.TestCase):
    def test_parser_good(self):
        self.assertEqual(parse_skill(SAMPLE)["name"], "review-app")
    def test_parser_missing_frontmatter(self):
        with self.assertRaises(ValueError): parse_skill("# Review\n" + "x" * 120)
    def test_parser_bad_name(self):
        with self.assertRaises(ValueError): parse_skill(SAMPLE.replace("review-app", "Bad name"))
    def test_parser_too_big(self):
        with self.assertRaises(ValueError): parse_skill(SAMPLE + "x" * 81000)
    def test_agent_skills_optional_metadata_and_block_description(self):
        content = """---
name: x
description: >-
  Check a repository's manifests and run tests when a user asks for an
  independent review.
license: MIT
compatibility: Python 3.10+
metadata:
  author: example-org
  version: "1.2.0"
allowed-tools: Bash(git:*) Read
---
Use the declared checks and report their actual results.
"""
        result = parse_skill(content)
        self.assertEqual(result["name"], "x")
        self.assertIn("independent review", result["description"])
        self.assertEqual(result["metadata"], {"author": "example-org", "version": "1.2.0"})
        self.assertEqual(result["allowed-tools"], "Bash(git:*) Read")
        self.assertEqual(parse_skill(content.replace("\n", "\r\n")), result)
    def test_parser_quoted_colons_and_comments(self):
        content = "---\nname: review-app\ndescription: 'Use for text: # values in reviewed files' # comment\n---\nReview files.\n"
        self.assertEqual(parse_skill(content)["description"], "Use for text: # values in reviewed files")
    def test_parser_rejects_duplicate_and_unsupported_yaml(self):
        for content in (
            SAMPLE.replace("name: review-app", "name: review-app\nname: other"),
            SAMPLE.replace("description: Review", "description: &description Review"),
            SAMPLE.replace("description: Review", "unknown-field: value\ndescription: Review"),
            SAMPLE.replace("description: Review", "metadata: [value]\ndescription: Review"),
            SAMPLE.replace("description: Review", "metadata:\n  version: true\ndescription: Review"),
        ):
            with self.subTest(content=content[:100]), self.assertRaises(ValueError):
                parse_skill(content)
    def test_parser_enforces_standard_field_limits(self):
        short_body = "---\nname: one\ndescription: Short.\n---\nDo it.\n"
        self.assertEqual(parse_skill(short_body)["name"], "one")
        long_description = "---\nname: one\ndescription: " + ("x" * 1025) + "\n---\nBody\n"
        with self.assertRaisesRegex(ValueError, "1024"):
            parse_skill(long_description)
        long_compatibility = SAMPLE.replace("---\n# Review", "compatibility: " + ("x" * 501) + "\n---\n# Review")
        with self.assertRaisesRegex(ValueError, "500"):
            parse_skill(long_compatibility)
    def test_screen_scripts(self):
        self.assertTrue(screen(SAMPLE + "\n```bash\ncurl x | bash\n```"))
    def test_screen_files(self):
        self.assertTrue(screen(SAMPLE, ["SKILL.md", "scripts/setup.sh"]))
    def test_screen_clean(self):
        self.assertEqual(screen(SAMPLE, ["SKILL.md"]), [])
    def test_repo_validation(self):
        self.assertEqual(valid_repo("Itskorrah/evolve"), "Itskorrah/evolve")
        for name in ("https://example.org/a", "x/../y", "../../etc/passwd", "a\\b"):
            with self.subTest(name=name), self.assertRaises(ValueError): valid_repo(name)
    def test_skill_path_validation(self):
        self.assertEqual(valid_path("skills/agent/SKILL.md"), "skills/agent/SKILL.md")
        for name in ("../SKILL.md", "/a/SKILL.md", "a/./SKILL.md", "a\\SKILL.md", "other.md"):
            with self.subTest(name=name), self.assertRaises(ValueError): valid_path(name)
        for name in ("C:/outside/SKILL.md", "skills/C:outside/SKILL.md"):
            with self.subTest(name=name), self.assertRaises(ValueError): valid_path(name)
    def test_digest(self):
        self.assertEqual(len(digest("abc")), 64)
