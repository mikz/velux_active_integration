#!/usr/bin/env python3
"""Enforce line-and-branch coverage for each integration module, including missing files."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate(report, root: Path) -> list[str]:
    """Validate every installed module against real branch-inclusive totals."""
    if not report["meta"].get("branch_coverage"):
        return ["Branch coverage was not measured"]
    files = report["files"]
    failures = []
    for source in sorted((root / "custom_components/velux_active").rglob("*.py")):
        relative = source.relative_to(root).as_posix()
        if relative not in files:
            failures.append(f"{relative}: absent from coverage")
            continue
        summary = files[relative]["summary"]
        total = summary["num_statements"] + summary["num_branches"]
        covered = summary["covered_lines"] + summary["covered_branches"]
        fraction = covered / total if total else 1
        print(f"{relative}: {fraction:.2%} ({covered}/{total} lines + branches)")
        if source.name == "config_flow.py" and fraction < 1:
            failures.append(f"{relative}: config flow requires 100%")
        elif fraction <= 0.95:
            failures.append(f"{relative}: requires strictly above 95%")
    return failures


def main():
    report = json.loads(Path(sys.argv[1]).read_text())
    if failures := validate(report, ROOT):
        raise SystemExit("\n".join(failures))


if __name__ == "__main__":
    main()
