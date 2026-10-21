"""Synthetic routing regression contracts; no agent host is invoked."""
import importlib.util
import unittest
from pathlib import Path

from kstack.cli import ROOT


SPEC = importlib.util.spec_from_file_location("route_benchmark", ROOT / "scripts" / "route_benchmark.py")
BENCHMARK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BENCHMARK)


class RouterRegressionTests(unittest.TestCase):
    def test_synthetic_task_contracts(self):
        result = BENCHMARK.evaluate()
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["cases_passed"], 6)
        self.assertEqual(result["case_count"], 6)
        self.assertEqual(result["workflow_recall"], 1.0)
        self.assertEqual(result["required_specialist_recall"], 1.0)
        self.assertEqual(result["candidate_precision"], 1.0)
        self.assertFalse(result["host_invocation_verified"])


if __name__ == "__main__":
    unittest.main()
