import json
import tempfile
import unittest
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from kstack.cli import main
from kstack.router import route
from kstack.cli import ROOT

class CliTest(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.state = t.name
    def test_list(self):
        out = StringIO()
        with redirect_stdout(out):
            result = main(["--state", self.state, "list"])
        self.assertEqual(result, 0)
        self.assertGreaterEqual(len(json.loads(out.getvalue())["bundled"]), 4)
    def test_route(self):
        answer = route("test the browser and push a release", ROOT, Path(self.state), "web")
        self.assertIn("kstack-verify", answer["installed_skill_suggestions"])
        self.assertIn("kstack-ship", answer["installed_skill_suggestions"])
        self.assertTrue(answer["conditional_guidance"])
    def test_unknown_profile(self):
        with self.assertRaises(ValueError): route("fix", ROOT, Path(self.state), "nonexistent")
    def test_doctor(self):
        out = StringIO()
        with redirect_stdout(out):
            code = main(["--state", self.state, "doctor"])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out.getvalue())["ok"])
    def test_unknown_candidate_returns_error(self):
        stderr = StringIO()
        with redirect_stderr(stderr):
            code = main(["--state", self.state, "assess", "Itskorrah/none:skills/test/SKILL.md"])
        self.assertEqual(code, 1)
        self.assertIn("Unknown candidate", stderr.getvalue())
