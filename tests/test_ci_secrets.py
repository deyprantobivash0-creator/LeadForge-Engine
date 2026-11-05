"""Secret-gate detection, execution-error and cleanup contracts; no real secrets."""

import json
from pathlib import Path
import subprocess

import pytest

from scripts import ci


def finding(target):
    return {"RuleID": "generic-api-key", "File": target.as_posix(),
            "StartLine": 1, "EndLine": 1, "Secret": "REDACTED"}


@pytest.mark.parametrize("case,code", [
    ("detected", 42), ("undetected", 0), ("execution_error", 1),
    ("unexpected_exit", 2), ("container_error", 125), ("malformed_report", 42),
    ("wrong_file", 42), ("wrong_rule", 42), ("empty_report", 42),
    ("unredacted_report", 42),
])
def test_negative_control_requires_expected_detection(tmp_path, monkeypatch, capsys, case, code):
    target = tmp_path / "tests/test_auth_migration.py"
    target.parent.mkdir()
    original = b"# original staged source\r\n"
    target.write_bytes(original)
    private_output = "scanner output must stay private"

    def scan(command, **kwargs):
        assert command[-3:] == ["--exit-code=42", "--report-format=json", "--report-path=-"]
        assert kwargs["capture_output"] and kwargs["timeout"] == 120
        assert "api_key" in target.read_text()
        item = finding(target)
        if case == "wrong_file": item["File"] = "unrelated.py"
        if case == "wrong_rule": item["RuleID"] = "unrelated-rule"
        if case == "unredacted_report": item["Secret"] = private_output
        report = [] if case in {"undetected", "empty_report"} else [item]
        stdout = private_output if case == "malformed_report" else json.dumps(report)
        return subprocess.CompletedProcess(command, code, stdout.encode(), private_output.encode())

    monkeypatch.setattr(ci.subprocess, "run", scan)
    if case == "detected":
        ci.secret_negative_probe(tmp_path, ["scanner"])
    else:
        with pytest.raises(RuntimeError, match="expected synthetic finding"):
            ci.secret_negative_probe(tmp_path, ["scanner"])
    assert target.read_bytes() == original
    output = capsys.readouterr()
    assert private_output not in output.out + output.err
    diagnostic = json.loads(output.out.splitlines()[0])
    assert diagnostic["returncode"] == code
    assert ("negative control passed" in output.out) is (case == "detected")


@pytest.mark.parametrize("error", [FileNotFoundError, subprocess.TimeoutExpired])
def test_negative_control_execution_failure_is_private_and_cleans_up(tmp_path, monkeypatch, capsys, error):
    private_output = "private executable or diagnostic"

    def fail(*_args, **_kwargs):
        if error is subprocess.TimeoutExpired:
            raise error(private_output, 120, output=private_output, stderr=private_output)
        raise error(private_output)

    monkeypatch.setattr(ci.subprocess, "run", fail)
    with pytest.raises(RuntimeError, match="could not execute"):
        ci.secret_negative_probe(tmp_path, [private_output])
    assert not (tmp_path / "tests/test_auth_migration.py").exists()
    output = capsys.readouterr()
    assert private_output not in output.out + output.err
    assert json.loads(output.out)["execution_error"] == error.__name__


def test_negative_control_removes_new_fixture_after_container_detection(tmp_path, monkeypatch):
    def scan(command, **_kwargs):
        item = finding(Path("/audit/tests/test_auth_migration.py"))
        return subprocess.CompletedProcess(command, 42, json.dumps([item]).encode(), b"")

    monkeypatch.setattr(ci.subprocess, "run", scan)
    ci.secret_negative_probe(tmp_path, ["container-scanner"])
    assert not (tmp_path / "tests/test_auth_migration.py").exists()


@pytest.mark.parametrize("primary_code", [0, 1, 2])
def test_primary_scan_remains_fail_closed_and_negative_control_mandatory(
    tmp_path, monkeypatch, primary_code,
):
    source = tmp_path / "source.py"
    source.write_text("# clean source\n")
    monkeypatch.setattr(ci, "source_files", lambda: iter([("source.py", source)]))
    monkeypatch.setattr(ci.shutil, "which", lambda _name: "scanner")
    probes, stages = [], []

    def scan(command, **_kwargs):
        if command[1] == "version":
            return subprocess.CompletedProcess(command, 0, "8.30.1\n", "")
        assert "--exit-code=1" in command and "--redact=100" in command
        stage = Path(command[2])
        stages.append(stage)
        report = Path(command[command.index("--report-path") + 1])
        report.write_text("[]")
        return subprocess.CompletedProcess(command, primary_code)

    monkeypatch.setattr(ci.subprocess, "run", scan)
    monkeypatch.setattr(ci, "secret_negative_probe", lambda stage, _command: probes.append(stage))
    if primary_code == 0:
        ci.secrets()
        assert len(probes) == 1
    else:
        with pytest.raises(RuntimeError, match="Gitleaks failed"):
            ci.secrets()
        assert probes == []
    assert stages and all(not stage.exists() for stage in stages)
