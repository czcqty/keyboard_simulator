#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prepare the environment, run all tests, then build if they pass."""

from __future__ import annotations

import re
import subprocess
import sys
import venv
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
VENV_DIR = SCRIPT_DIR / ".venv"
TEST_SCRIPT = SCRIPT_DIR / "test_keyboard_simulator.py"
BUILD_SCRIPT = SCRIPT_DIR / "build.py"
SUMMARY_RE = re.compile(r"Summary:\s+(\d+)/(\d+)\s+OK,\s+(\d+)\s+FAIL")
REQUIRED_PACKAGES = {
    "pynput": "pynput",
    "PyInstaller": "pyinstaller",
}


def in_virtualenv() -> bool:
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix) or hasattr(sys, "real_prefix")


def venv_python() -> Path:
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def ensure_virtualenv() -> None:
    if in_virtualenv():
        return

    python_path = venv_python()
    if not python_path.exists():
        print("=" * 60, flush=True)
        print(f"Creating virtual environment: {VENV_DIR}", flush=True)
        print("=" * 60, flush=True)
        venv.create(VENV_DIR, with_pip=True)

    if not python_path.exists():
        print(f"Virtual environment Python not found: {python_path}", file=sys.stderr)
        raise SystemExit(1)

    print("=" * 60, flush=True)
    print(f"Switching to virtual environment: {python_path}", flush=True)
    print("=" * 60, flush=True)
    result = subprocess.run([str(python_path), str(Path(__file__).resolve()), *sys.argv[1:]], cwd=SCRIPT_DIR)
    raise SystemExit(result.returncode)


def package_installed(import_name: str) -> bool:
    code = f"import importlib.util; raise SystemExit(0 if importlib.util.find_spec({import_name!r}) else 1)"
    return subprocess.run([sys.executable, "-c", code], cwd=SCRIPT_DIR).returncode == 0


def ensure_dependencies() -> None:
    missing = [
        package_name
        for import_name, package_name in REQUIRED_PACKAGES.items()
        if not package_installed(import_name)
    ]
    if not missing:
        print("Required dependencies are already installed.")
        return

    print("=" * 60)
    print(f"Installing dependencies: {', '.join(missing)}")
    print("=" * 60)
    result = subprocess.run([sys.executable, "-m", "pip", "install", *missing], cwd=SCRIPT_DIR)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def run_test_all() -> tuple[bool, subprocess.CompletedProcess[str]]:
    print("=" * 60)
    print("Running tests: test_keyboard_simulator.py -> run --all")
    print("=" * 60)

    result = subprocess.run(
        [sys.executable, str(TEST_SCRIPT)],
        input="run --all\nexit\n",
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
    print("=" * 60)
    print("Running build: build.py")
    print("=" * 60)
    return subprocess.run([sys.executable, str(BUILD_SCRIPT)], cwd=SCRIPT_DIR).returncode


def main() -> int:
    missing = [path.name for path in (TEST_SCRIPT, BUILD_SCRIPT) if not path.exists()]
    if missing:
        print(f"Missing required script(s): {', '.join(missing)}", file=sys.stderr)
        return 1

    ensure_virtualenv()
    ensure_dependencies()

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
