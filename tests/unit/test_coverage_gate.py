"""The release gate must reject misleading aggregate or line-only coverage."""

import pytest

from scripts.check_coverage import validate


@pytest.mark.parametrize(
    "filename,covered,expected",
    [
        ("api.py", 95, "strictly above 95%"),
        ("config_flow.py", 99, "requires 100%"),
        ("subpackage/new.py", None, "absent from coverage"),
    ],
)
def test_per_module_coverage_failures(tmp_path, filename, covered, expected):
    path = tmp_path / "custom_components/velux_active" / filename
    path.parent.mkdir(parents=True)
    path.write_text("# fixture")
    report = {"meta": {"branch_coverage": True}, "files": {}}
    if covered is not None:
        report["files"][path.relative_to(tmp_path).as_posix()] = {
            "summary": {
                "num_statements": 50,
                "num_branches": 50,
                "covered_lines": 50,
                "covered_branches": covered - 50,
            }
        }
    assert expected in validate(report, tmp_path)[0]


def test_line_only_report_rejected_before_branch_fields_are_read(tmp_path):
    path = tmp_path / "custom_components/velux_active/config_flow.py"
    path.parent.mkdir(parents=True)
    path.write_text("# fixture")
    assert validate({"meta": {"branch_coverage": False}, "files": {}}, tmp_path) == [
        "Branch coverage was not measured"
    ]
