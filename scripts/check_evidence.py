"""Fail the build when the test evidence is missing, empty, failing, or too small.

  python scripts/check_evidence.py reports/junit.xml --require tests.ui:8 --require tests.rag:20
  python scripts/check_evidence.py java-app/target/surefire-reports/TEST-*.xml --require :30

Several report files may be given (their test cases are added together).
--require PREFIX:N means at least N tests whose class name starts with PREFIX must have PASSED
(an empty PREFIX, written ":N", matches every test).
Skipped tests do not count as passed. Any failure or error fails the check. A missing or unreadable report fails it.
"""
from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def summarise(path: Path) -> list[dict]:
    root = ET.parse(path).getroot()
    cases = []
    for case in root.iter("testcase"):
        outcome = "passed"
        for child in case:
            if child.tag in ("failure", "error"):
                outcome = "failed"
                break
            if child.tag == "skipped":
                outcome = "skipped"
        cases.append({"classname": case.get("classname", ""), "name": case.get("name", ""), "outcome": outcome})
    return cases


def check(paths, requirements: dict[str, int]) -> list[str]:
    paths = [Path(paths)] if isinstance(paths, (str, Path)) else [Path(p) for p in paths]
    if not paths:
        return ["no evidence files were given"]
    cases: list[dict] = []
    for path in paths:
        if not path.is_file():
            return [f"evidence file missing: {path}"]
        try:
            cases += summarise(path)
        except ET.ParseError as error:
            return [f"evidence file unreadable: {path}: {error}"]
    problems = []
    if not cases:
        problems.append("the report contains no test cases")
    failed = [f"{c['classname']}::{c['name']}" for c in cases if c["outcome"] == "failed"]
    problems += [f"failed: {name}" for name in failed]
    for prefix, minimum in requirements.items():
        passed = sum(1 for c in cases if c["outcome"] == "passed" and c["classname"].startswith(prefix))
        if passed < minimum:
            problems.append(f"expected at least {minimum} passed tests under {prefix or 'all'}, found {passed}")
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--require", action="append", default=[], metavar="PREFIX:N")
    args = parser.parse_args(argv)
    requirements = {}
    for item in args.require:
        prefix, _, count = item.rpartition(":")
        requirements[prefix] = int(count)
    problems = check(args.reports, requirements)
    if problems:
        print("Evidence check failed:")
        for problem in problems:
            print("  " + problem)
        return 1
    cases = [c for report in args.reports for c in summarise(report)]
    print(f"Evidence OK: {sum(c['outcome'] == 'passed' for c in cases)} passed, "
          f"{sum(c['outcome'] == 'skipped' for c in cases)} skipped, 0 failed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
