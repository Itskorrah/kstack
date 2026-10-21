"""Measure deterministic routing against synthetic routing regression contracts."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from kstack.router import route

FIXTURE = ROOT / "tests" / "fixtures" / "routing_regression.json"


def evaluate() -> dict:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("format") != 1 or not isinstance(data.get("cases"), list):
        raise ValueError("Invalid router regression fixture")
    results = []
    workflow_total = workflow_hits = specialist_total = specialist_hits = 0
    candidate_total = candidate_allowed = 0
    with tempfile.TemporaryDirectory(prefix="kstack-route-benchmark-") as temporary:
        base = Path(temporary)
        state = base / "state"
        for case in data["cases"]:
            if not isinstance(case, dict) or not isinstance(case.get("id"), str):
                raise ValueError("Invalid router regression case")
            project = base / case["id"]
            project.mkdir()
            if case["profile"] == "web":
                (project / "package.json").write_text(
                    '{"dependencies":{"react":"19.0.0"}}', encoding="utf-8")
            elif case["profile"] == "python":
                (project / "pyproject.toml").write_text(
                    '[project]\nname="routing-fixture"\n', encoding="utf-8")
            actual = route(case["task"], ROOT, state, project=project,
                           host="codex", scope="project")
            workflows = {item["name"] for item in actual["workflow_suggestions"]}
            specialists = {item["id"] for item in actual["external_candidates"]}
            required_workflows = set(case["required_workflows"])
            required_specialists = set(case["required_specialists"])
            allowed_specialists = set(case["allowed_specialists"])
            missing_workflows = sorted(required_workflows - workflows)
            missing_specialists = sorted(required_specialists - specialists)
            unexpected_specialists = sorted(specialists - allowed_specialists)
            workflow_total += len(required_workflows)
            workflow_hits += len(required_workflows & workflows)
            specialist_total += len(required_specialists)
            specialist_hits += len(required_specialists & specialists)
            candidate_total += len(specialists)
            candidate_allowed += len(specialists & allowed_specialists)
            passed = (not missing_workflows and not missing_specialists and not unexpected_specialists
                      and actual["profile"] == case["profile"] and actual["risk"] == case["risk"]
                      and actual["complexity"] == case["complexity"])
            results.append({"id": case["id"], "passed": passed,
                            "profile": actual["profile"], "risk": actual["risk"],
                            "complexity": actual["complexity"],
                            "workflows": sorted(workflows), "specialists": sorted(specialists),
                            "missing_workflows": missing_workflows,
                            "missing_specialists": missing_specialists,
                            "unexpected_specialists": unexpected_specialists})
    return {
        "passed": bool(results) and all(item["passed"] for item in results),
        "cases_passed": sum(item["passed"] for item in results),
        "case_count": len(results),
        "workflow_recall": workflow_hits / workflow_total if workflow_total else 1.0,
        "required_specialist_recall": specialist_hits / specialist_total if specialist_total else 1.0,
        "candidate_precision": candidate_allowed / candidate_total if candidate_total else 1.0,
        "host_invocation_verified": False,
        "cases": results,
    }


def main() -> int:
    result = evaluate()
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
