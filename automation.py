#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prepare the environment, run all tests, then build if they pass."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TEST_SCRIPT = SCRIPT_DIR / "test_keyboard_simulator.py"
BUILD_SCRIPT = SCRIPT_DIR / "build.py"
SUMMARY_RE = re.compile(r"Summary:\s+(\d+)/(\d+)\s+OK,\s+(\d+)\s+FAIL")


def run_test_all() -> tuple[bool, subprocess.CompletedProcess[str]]:
    print("=" * 60)
    print("Running tests: test_keyboard_simulator.py run --all")
    print("=" * 60)

    result = subprocess.run(
        [sys.executable, str(TEST_SCRIPT), "run", "--all"],
        cwd=SCRIPT_DIR,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )

    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)

    summary = SUMMARY_RE.search(result.stdout)
    tests_ok = (
        result.returncode == 0
        and summary is not None
        and int(summary.group(2)) > 0
        and int(summary.group(3)) == 0
    )
    return tests_ok, result


def ask_continue() -> bool:
    if not sys.stdin.isatty():
        print("Tests did not all pass, and stdin is not interactive. Build skipped.")
        return False

    answer = input("Tests did not all pass. Continue with build anyway? [y/N] ").strip().lower()
    return answer in {"y", "yes"}


def run_build() -> int:
    print("Running build: build.py")
    return subprocess.run([sys.executable, str(BUILD_SCRIPT)], cwd=SCRIPT_DIR).returncode


def main() -> int:
    missing = [path.name for path in (TEST_SCRIPT, BUILD_SCRIPT) if not path.exists()]
    if missing:
        print(f"Missing required script(s): {', '.join(missing)}", file=sys.stderr)
        return 1

    tests_ok, test_result = run_test_all()
    if tests_ok:
        print("All tests passed. Starting build automatically.")
        return run_build()

    print(f"Tests are not fully OK. Test process exit code: {test_result.returncode}")
    if ask_continue():
        return run_build()

    print("Build skipped.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
