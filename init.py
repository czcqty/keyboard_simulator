#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
键盘模拟器 - 独立的开发环境初始化脚本
检测并创建本地 .venv 虚拟环境，并使用 pip 安装所有必需依赖项。
"""
import sys
import subprocess
import venv
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
VENV_DIR = SCRIPT_DIR / ".venv"


def venv_python() -> Path:
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def main():
    print("=" * 60)
    print("[环境] 正在初始化键盘模拟器开发环境...")
    print("=" * 60)

    # 1. 检测并创建本地 .venv 虚拟环境
    python_path = venv_python()
    if not python_path.exists():
        print(f"[环境] 正在创建本地虚拟环境: {VENV_DIR} ...", flush=True)
        try:
            venv.create(VENV_DIR, with_pip=True)
            print("[环境] 虚拟环境创建成功。")
        except Exception as e:
            print(f"[错误] 创建虚拟环境失败: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("[环境] 本地虚拟环境已存在，跳过创建。")

    if not python_path.exists():
        print(f"[错误] 未找到虚拟环境的 Python 解释器: {python_path}", file=sys.stderr)
        sys.exit(1)

    # 2. 自动使用 pip 安装核心依赖与打包依赖
    print("[依赖] 正在检查并安装/更新项目依赖 (pynput, pyinstaller)...", flush=True)
    requirements_file = SCRIPT_DIR / "requirements.txt"
    if requirements_file.exists():
        cmd = [str(python_path), "-m", "pip", "install", "-r", str(requirements_file)]
    else:
        cmd = [str(python_path), "-m", "pip", "install", "pynput", "pyinstaller"]

    print(f"[执行] {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=SCRIPT_DIR)
    
    if result.returncode == 0:
        print("环境初始化成功！")
        print("您现在可以运行以下脚本进行开发或测试：")
        print("  - 运行测试与构建: python automation.py")
        print("  - 独立运行构建  : python build.py")
        print("  - 启动模拟器 GUI: python keyboard_simulator.py")
    else:
        print(f"\n[错误] 依赖安装失败，退出码: {result.returncode}", file=sys.stderr)
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
