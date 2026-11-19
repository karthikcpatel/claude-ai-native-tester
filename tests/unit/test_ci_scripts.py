"""Unit tests for the CI gate scripts. They are the guard rails, so the guard rails are tested too."""
import importlib.util
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


secrets = _load("check_secrets")
evidence = _load("check_evidence")

FAKE_ANTHROPIC = "sk-ant-" + "api03-" + "A1b2C3d4E5f6G7h8I9j0K1l2"  # assembled so this file holds no literal key
FAKE_AWS = "AKIA" + "ABCDEFGHIJKLMNOP"


@pytest.mark.parametrize("line,label", [
    (f"key = {FAKE_ANTHROPIC}", "Anthropic API key"),
    (f"aws {FAKE_AWS}", "AWS access key id"),
    ("-----BEGIN " + "PRIVATE KEY-----", "Private key block"),
    ('ANTHROPIC_API_KEY="' + "x" * 40 + '"', "Key assigned in config"),
], ids=["anthropic-key", "aws-key-id", "private-key-block", "key-assigned-in-config"])  # ids must not echo the values
def test_secret_patterns_are_detected(line, label):
    findings = secrets.scan_text("f.txt", line)
    assert findings and label in findings[0]


def test_findings_never_contain_the_secret_value():
    findings = secrets.scan_text("f.txt", f"token {FAKE_ANTHROPIC}")
    assert findings and FAKE_ANTHROPIC not in " ".join(findings)


@pytest.mark.parametrize("line", [
    "ANTHROPIC_API_KEY is read from the environment",
    "forbid_regex: sk-ant-[A-Za-z0-9_-]{8,}",
    "api_key = os.environ['ANTHROPIC_API_KEY']",
    "synthetic card 9999 0000 0000 0000",
])
def test_ordinary_text_and_regex_definitions_are_not_flagged(line):
    assert secrets.scan_text("f.txt", line) == []


def test_allow_marker_skips_a_deliberate_fixture_line():
    assert secrets.scan_text("f.txt", f"{FAKE_ANTHROPIC}  # secret-scan: allow") == []


def test_paths_mode_scans_a_folder_and_fails_on_a_planted_secret(tmp_path, capsys):
    (tmp_path / "clean.txt").write_text("hello", encoding="utf-8")
    assert secrets.main(["--paths", str(tmp_path)]) == 0
    (tmp_path / "leak.jsonl").write_text(f'{{"answer": "{FAKE_ANTHROPIC}"}}', encoding="utf-8")
    assert secrets.main(["--paths", str(tmp_path)]) == 1
    output = capsys.readouterr().out
    assert "leak.jsonl:1" in output and FAKE_ANTHROPIC not in output


def test_binary_files_are_skipped(tmp_path):
    binary = tmp_path / "trace.zip"
    binary.write_bytes(b"PK\x03\x04\x00\x00" + FAKE_ANTHROPIC.encode())
    assert secrets.scan_file(binary) == []


def _junit(path, cases):
    body = "".join(
        f'<testcase classname="{c}" name="{n}">' + {"passed": "", "failed": "<failure message='x'/>",
                                                      "skipped": "<skipped/>"}[o] + "</testcase>"
        for c, n, o in cases)
    path.write_text(f'<?xml version="1.0"?><testsuites><testsuite>{body}</testsuite></testsuites>', encoding="utf-8")


def test_evidence_passes_when_enough_tests_passed(tmp_path):
    report = tmp_path / "junit.xml"
    _junit(report, [("tests.ui.test_a", f"t{i}", "passed") for i in range(8)])
    assert evidence.check(report, {"tests.ui": 8}) == []


def test_evidence_fails_on_a_missing_report(tmp_path):
    assert "missing" in evidence.check(tmp_path / "nope.xml", {})[0]


def test_evidence_fails_on_an_empty_report(tmp_path):
    report = tmp_path / "junit.xml"
    _junit(report, [])
    assert "no test cases" in " ".join(evidence.check(report, {}))


def test_evidence_fails_on_any_failure_even_when_the_minimum_is_met(tmp_path):
    report = tmp_path / "junit.xml"
    _junit(report, [("tests.ui.x", f"t{i}", "passed") for i in range(9)] + [("tests.ui.x", "bad", "failed")])
    problems = evidence.check(report, {"tests.ui": 8})
    assert any("failed: tests.ui.x::bad" in p for p in problems)


def test_skipped_tests_do_not_count_toward_the_minimum(tmp_path):
    report = tmp_path / "junit.xml"
    _junit(report, [("tests.ui.x", f"t{i}", "skipped") for i in range(10)])
    assert any("found 0" in p for p in evidence.check(report, {"tests.ui": 8}))


def test_evidence_fails_on_an_unreadable_report(tmp_path):
    report = tmp_path / "junit.xml"
    report.write_text("<not xml", encoding="utf-8")
    assert "unreadable" in evidence.check(report, {})[0]


def test_several_reports_are_added_together_and_an_empty_prefix_matches_everything(tmp_path):
    first, second = tmp_path / "a.xml", tmp_path / "b.xml"
    _junit(first, [("com.x.A", f"t{i}", "passed") for i in range(3)])
    _junit(second, [("com.x.B", f"t{i}", "passed") for i in range(3)])
    assert evidence.check([first, second], {"": 6}) == []
    assert any("found 6" in p for p in evidence.check([first, second], {"": 7}))


def test_one_missing_report_among_several_fails_the_check(tmp_path):
    first = tmp_path / "a.xml"
    _junit(first, [("com.x.A", "t", "passed")])
    assert "missing" in evidence.check([first, tmp_path / "gone.xml"], {})[0]
