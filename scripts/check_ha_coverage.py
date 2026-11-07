"""Require >95% lines and branches in every shipped integration module."""
import json
from pathlib import Path

ROOT = Path("custom_components/solem_woobee")


def check(report):
    if not report.get("meta", {}).get("branch_coverage"):
        raise ValueError("Branch coverage measurement is required")
    expected = {path.as_posix() for path in ROOT.rglob("*.py")}
    files = report["files"]
    failures = []
    for name in sorted(expected):
        if name not in files:
            failures.append(f"{name}: absent from coverage report")
            continue
        summary = files[name]["summary"]
        lines = summary["num_statements"]
        branches = summary["num_branches"]
        line_pct = 100 * summary["covered_lines"] / lines if lines else 100
        branch_pct = 100 * summary["covered_branches"] / branches if branches else 100
        print(f"{name}: lines {summary['covered_lines']}/{lines} ({line_pct:.4f}%), "
              f"branches {summary['covered_branches']}/{branches} ({branch_pct:.4f}%)")
        if line_pct <= 95 or branch_pct <= 95:
            failures.append(f"{name}: requires >95% lines AND branches")
        if (name == f"{ROOT}/config_flow.py" or name.startswith(f"{ROOT}/config_flow_handler/")) and (line_pct < 100 or branch_pct < 100):
            failures.append(f"{name}: config flow requires 100% lines AND branches")
    if not expected:
        failures.append("No shipped modules found")
    if failures:
        raise ValueError("\n".join(failures))
    print(f"Coverage passed for all {len(expected)} shipped modules")


if __name__ == "__main__":
    try:
        check(json.loads(Path("coverage.json").read_text()))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
