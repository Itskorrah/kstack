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
    def test_digest(self):
        self.assertEqual(len(digest("abc")), 64)
