#!/usr/bin/env python3
"""Fail qualification when essential pytest cases were skipped or under-run.

Used by the opt-in Windows Qt qualification job after PySide6 is installed.
Generic developer suites may still skip when Qt is absent; that path must not
be treated as PASS in qualification.
"""
from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET


def evaluate(junit: str, *, min_passed: int) -> list[str]:
    failures: list[str] = []
    root = ET.parse(junit).getroot()
    suites = [root] if root.tag == 'testsuite' else list(root.findall('testsuite'))
    if not suites:
        return ['junit xml contained no testsuites']
    passed = skipped = failed = errors = 0
    skipped_names: list[str] = []
    for suite in suites:
        passed += int(suite.attrib.get('tests', 0)) - int(suite.attrib.get('skipped', 0)) \
            - int(suite.attrib.get('failures', 0)) - int(suite.attrib.get('errors', 0))
        skipped += int(suite.attrib.get('skipped', 0))
        failed += int(suite.attrib.get('failures', 0))
        errors += int(suite.attrib.get('errors', 0))
        for case in suite.findall('testcase'):
            if case.find('skipped') is not None:
                skipped_names.append(f"{case.attrib.get('classname', '?')}::{case.attrib.get('name', '?')}")
    if failed or errors:
        failures.append(f'junit reported failures={failed} errors={errors}')
    if skipped:
        failures.append('essential qualification tests were skipped: ' + ', '.join(skipped_names[:12]))
    if passed < min_passed:
        failures.append(f'passed={passed} below required minimum {min_passed}')
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('junit')
    parser.add_argument('--min-passed', type=int, default=5)
    args = parser.parse_args()
    try:
        problems = evaluate(args.junit, min_passed=args.min_passed)
    except (OSError, ET.ParseError) as exc:
        print(f'FAIL: unreadable junit ({exc})', file=sys.stderr)
        return 2
    if problems:
        for item in problems:
            print('FAIL:', item)
        return 1
    print(f'PASS: qualification junit has no skips and meets min_passed={args.min_passed}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
