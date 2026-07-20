#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build keyboard_simulator into a standalone binary."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SOURCE_FILE = SCRIPT_DIR / "keyboard_simulator.py"
APP_NAME = "keyboard_simulator"
VENV_DIR = SCRIPT_DIR / ".venv"


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
        print(f"[错误] 未检测到本地虚拟环境: {VENV_DIR}", file=sys.stderr)
        print("请先运行 'python init.py' 进行初始化！", file=sys.stderr)
        raise SystemExit(1)

    print("=" * 60, flush=True)
    print(f"Switching to virtual environment: {python_path}", flush=True)
    print("=" * 60, flush=True)
    result = subprocess.run([str(python_path), str(Path(__file__).resolve()), *sys.argv[1:]], cwd=SCRIPT_DIR)
    raise SystemExit(result.returncode)


def run(cmd: list[str]) -> None:
    print(f"  > {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=SCRIPT_DIR)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def build() -> Path:
    system = platform.system()
    print(f"[build] Target platform: {system}")
    print(f"[build] Source file: {SOURCE_FILE}")

    if not SOURCE_FILE.exists():
        print(f"[error] Source file not found: {SOURCE_FILE}", file=sys.stderr)
        raise SystemExit(1)

    run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--onefile",
            "--windowed",
            "--name",
            APP_NAME,
            str(SOURCE_FILE),
        ]
    )

    built_name = APP_NAME + ".exe" if system == "Windows" else APP_NAME
    dist_path = SCRIPT_DIR / "dist" / built_name
    final_path = SCRIPT_DIR / built_name

    if not dist_path.exists():
        print(f"[error] Built file not found: {dist_path}", file=sys.stderr)
        raise SystemExit(1)

    if final_path.exists():
        os.remove(final_path)
    shutil.move(str(dist_path), str(final_path))
    print(f"[build] Binary generated: {final_path}")

    for cleanup_dir in ("build", "dist"):
        path = SCRIPT_DIR / cleanup_dir
        if path.is_dir():
            shutil.rmtree(path)

    spec_path = SCRIPT_DIR / f"{APP_NAME}.spec"
    if spec_path.exists():
        os.remove(spec_path)

    print("[build] Temporary files removed: build/, dist/, .spec")
    return final_path


def main() -> int:
    ensure_virtualenv()
    build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

