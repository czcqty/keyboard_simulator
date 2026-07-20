#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Keyboard Simulator Test Program

Tests:
1. Direct Mode Test - Verify clipboard paste functionality
2. Simulation Mode Test - Verify character-by-character input
3. Auto Repair Test - Verify text repair functionality
"""

import sys
import time
import types
from pathlib import Path

# ──────────────────────────────────────────────
# Fake pynput module (for capturing keyboard events)
# ──────────────────────────────────────────────

class FakeKey:
    enter = "ENTER"
    tab = "TAB"
    space = "SPACE"
    f6 = "F6"
    f7 = "F7"
    f8 = "F8"
    end = "END"
    home = "HOME"
    left = "LEFT"
    right = "RIGHT"
    down = "DOWN"
    shift = "SHIFT"
    backspace = "BACKSPACE"
    delete = "DELETE"
    cmd = "CMD"
    ctrl = "CTRL"


class FakeController:
    def __init__(self):
        self.events = []

    def press(self, key):
        self.events.append(("press", key))

    def release(self, key):
        self.events.append(("release", key))

    def type(self, text):
        self.events.append(("type", text))


class FakeListener:
    def __init__(self, on_press=None):
        self.on_press = on_press
        self.daemon = False
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


def install_fake_pynput():
    """Inject fake pynput module"""
    pynput_module = types.ModuleType("pynput")
    keyboard_module = types.ModuleType("pynput.keyboard")
    keyboard_module.Controller = FakeController
    keyboard_module.Key = FakeKey
    keyboard_module.Listener = FakeListener
    pynput_module.keyboard = keyboard_module
    sys.modules["pynput"] = pynput_module
    sys.modules["pynput.keyboard"] = keyboard_module


def import_target_module(target_path):
    """Import main program module"""
    import importlib.util
    import re

    install_fake_pynput()
    target_path = Path(target_path).resolve()
    module_name = "keyboard_simulator_under_test_" + re.sub(r"\W+", "_", str(target_path))
    sys.modules.pop(module_name, None)

    spec = importlib.util.spec_from_file_location(module_name, target_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import target file: {target_path}")

    module = importlib.util.module_from_spec(spec)
    original_base_prefix = getattr(sys, "base_prefix", sys.prefix)
    try:
        sys.base_prefix = "__keyboard_simulator_test_base__"
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.base_prefix = original_base_prefix


# ──────────────────────────────────────────────
# Helper functions
# ──────────────────────────────────────────────

def events_to_text(events):
    """Convert keyboard events to text"""
    output = []
    special_keys = {
        FakeKey.enter: "\n",
        FakeKey.tab: "\t",
        FakeKey.space: " ",
    }
    for action, value in events:
        if action == "type":
            output.append(value)
        elif action == "press" and value in special_keys:
            output.append(special_keys[value])
    return "".join(output)


def has_paste_event(events):
    """Check if there is a paste event (Ctrl+V / Cmd+V) in the event sequence"""
    ctrl_pressed = False
    for action, value in events:
        if action == "press" and value in (FakeKey.ctrl, FakeKey.cmd):
            ctrl_pressed = True
        elif action == "press" and value == "v" and ctrl_pressed:
            return True
        elif action == "release" and value in (FakeKey.ctrl, FakeKey.cmd):
            ctrl_pressed = False
    return False


def apply_events_to_text(initial_text, events, clipboard_text=""):
    """Simulate text editor behavior"""
    text = list(initial_text.replace("\r\n", "\n").replace("\r", "\n"))
    cursor = len(text)
    selection = None
    pressed = set()
    selection_anchor = None

    def delete_selection():
        nonlocal cursor, selection, selection_anchor
        if selection is None:
            return False
        start, end = sorted(selection)
        del text[start:end]
        cursor = start
        selection = None
        selection_anchor = None
        return True

    def insert(value):
        nonlocal cursor
        delete_selection()
        chars = list(value.replace("\r\n", "\n").replace("\r", "\n"))
        text[cursor:cursor] = chars
        cursor += len(chars)

    def move_cursor(new_pos, selecting=False):
        nonlocal cursor, selection, selection_anchor
        new_pos = max(0, min(new_pos, len(text)))
        if selecting:
            if selection_anchor is None:
                selection_anchor = cursor
            cursor = new_pos
            selection = (selection_anchor, cursor)
        else:
            cursor = new_pos
            selection = None
            selection_anchor = None

    for action, value in events:
        if action == "clipboard":
            clipboard_text = value
        elif action == "press":
            if value in (FakeKey.ctrl, FakeKey.cmd, FakeKey.shift):
                pressed.add(value)
                continue
            modifier_down = FakeKey.ctrl in pressed or FakeKey.cmd in pressed
            shift_down = FakeKey.shift in pressed
            if modifier_down and value == "a":
                selection = (0, len(text))
                selection_anchor = 0
                cursor = len(text)
                continue
            if modifier_down and value == "c":
                continue
            if modifier_down and value == FakeKey.home:
                move_cursor(0, selecting=shift_down)
                continue
            if modifier_down and value == FakeKey.end:
                move_cursor(len(text), selecting=shift_down)
                continue
            if value == FakeKey.left:
                move_cursor(cursor - 1, selecting=shift_down)
                continue
            if value == FakeKey.right:
                move_cursor(cursor + 1, selecting=shift_down)
                continue
            if value == FakeKey.delete:
                if not delete_selection() and cursor < len(text):
                    del text[cursor]
                continue
            if value == FakeKey.backspace:
                if not delete_selection() and cursor > 0:
                    cursor -= 1
                    del text[cursor]
                continue
            if value == FakeKey.enter:
                insert("\n")
                continue
            if value == FakeKey.tab:
                insert("\t")
                continue
            if value == FakeKey.space:
                insert(" ")
                continue
        elif action == "release":
            pressed.discard(value)
        elif action == "type":
            insert(value)
    return "".join(text)


def text_preview(text, limit=90):
    """Preview text (truncate if too long)"""
    escaped = text.encode("unicode_escape").decode("ascii")
    if len(escaped) > limit:
        return escaped[: limit - 3] + "..."
    return escaped


def wait_for_engine(engine, timeout=2.0):
    """Wait for engine to complete"""
    deadline = time.monotonic() + timeout
    while getattr(engine, "running", False) and time.monotonic() < deadline:
        time.sleep(0.001)

    thread = getattr(engine, "_thread", None)
    if thread is not None:
        thread.join(timeout=max(0.0, deadline - time.monotonic()))

    if getattr(engine, "running", False):
        raise AssertionError("KeyboardEngine worker did not finish before timeout")


def new_engine(module):
    """Create engine instance"""
    if not hasattr(module, "KeyboardEngine"):
        raise AssertionError("Target module does not define KeyboardEngine")
    return module.KeyboardEngine()


def read_file(file_path):
    """Read text file"""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def normalize_text(text):
    """Normalize text (unify line endings)"""
    return text.replace("\r\n", "\n").replace("\r", "\n")


# ──────────────────────────────────────────────
# Test functions
# ──────────────────────────────────────────────

def test_direct_mode(module, data_dir):
    """
    Direct mode test

    Verify: Direct mode pastes text via clipboard
    Flow:
    1. Read test data file
    2. Call direct mode
    3. Verify paste event (Ctrl+V) was sent
    """
    input_file = data_dir / "direct_input.txt"
    if not input_file.exists():
        return {
            "ok": False,
            "name": "Direct Mode Test",
            "detail": f"Test data file does not exist: {input_file}"
        }

    input_text = read_file(input_file)
    if not input_text:
        return {
            "ok": False,
            "name": "Direct Mode Test",
            "detail": "Test data file is empty"
        }

    try:
        engine = new_engine(module)
        done = []

        # Call direct mode
        engine.type_text(
            input_text,
            delay_ms=0,
            loops=1,
            direct_mode=True,
            on_done=lambda status: done.append(status)
        )
        wait_for_engine(engine, timeout=10.0)

        # Check if paste event was sent
        events = engine.kb.events
        if has_paste_event(events):
            return {
                "ok": True,
                "name": "Direct Mode Test",
                "detail": "Paste event detected (Ctrl+V)"
            }
        else:
            return {
                "ok": False,
                "name": "Direct Mode Test",
                "detail": "No paste event detected"
            }

    except Exception as e:
        return {
            "ok": False,
            "name": "Direct Mode Test",
            "detail": f"Test exception: {e}"
        }


def test_simulation_mode(module, data_dir):
    """
    Simulation mode test

    Verify: Simulation mode inputs text character by character
    Flow:
    1. Read test data file
    2. Call simulation mode
    3. Verify output text matches input text
    """
    input_file = data_dir / "simulation_input.txt"
    if not input_file.exists():
        return {
            "ok": False,
            "name": "Simulation Mode Test",
            "detail": f"Test data file does not exist: {input_file}"
        }

    input_text = read_file(input_file)
    if not input_text:
        return {
            "ok": False,
            "name": "Simulation Mode Test",
            "detail": "Test data file is empty"
        }

    try:
        engine = new_engine(module)
        done = []

        # Call simulation mode
        engine.type_text(
            input_text,
            delay_ms=0,
            loops=1,
            direct_mode=False,
            on_done=lambda status: done.append(status)
        )
        wait_for_engine(engine, timeout=10.0)

        # Get output text
        output = events_to_text(engine.kb.events)
        norm_output = normalize_text(output)
        norm_input = normalize_text(input_text)

        # Verify output
        if norm_output == norm_input:
            return {
                "ok": True,
                "name": "Simulation Mode Test",
                "detail": "Output text matches input text"
            }
        else:
            return {
                "ok": False,
                "name": "Simulation Mode Test",
                "detail": "Output text does not match input text",
                "output": text_preview(output),
                "expected": text_preview(input_text)
            }

    except Exception as e:
        return {
            "ok": False,
            "name": "Simulation Mode Test",
            "detail": f"Test exception: {e}"
        }


def test_repair_mode(module, data_dir):
    """
    Auto repair test

    Verify: Auto repair functionality can fix text differences
    Flow:
    1. Read expected text file and error text file
    2. Use _repair_diff method to fix differences
    3. Multiple repairs until text matches
    4. Verify repaired text matches expected text
    """
    expected_file = data_dir / "repair_expected.txt"
    input_file = data_dir / "repair_input.txt"

    if not expected_file.exists():
        return {
            "ok": False,
            "name": "Auto Repair Test",
            "detail": f"Expected text file does not exist: {expected_file}"
        }

    if not input_file.exists():
        return {
            "ok": False,
            "name": "Auto Repair Test",
            "detail": f"Error text file does not exist: {input_file}"
        }

    expected_text = read_file(expected_file)
    error_text = read_file(input_file)

    if not expected_text:
        return {
            "ok": False,
            "name": "Auto Repair Test",
            "detail": "Expected text file is empty"
        }

    if not error_text:
        return {
            "ok": False,
            "name": "Auto Repair Test",
            "detail": "Error text file is empty"
        }

    try:
        engine = new_engine(module)
        norm_expected = normalize_text(expected_text)
        repaired = normalize_text(error_text)

        # Multiple repairs until text matches
        max_repairs = 20
        for i in range(max_repairs):
            if repaired == norm_expected:
                return {
                    "ok": True,
                    "name": "Auto Repair Test",
                    "detail": f"Text repair successful after {i} rounds"
                }

            # Call _repair_diff method
            changed = engine._repair_diff(repaired, norm_expected, delay_ms=0, use_sendinput=False)
            if not changed:
                # No more differences to repair
                break

            # Apply events to text
            repaired = apply_events_to_text(repaired, engine.kb.events)

        # Final verification
        if repaired == norm_expected:
            return {
                "ok": True,
                "name": "Auto Repair Test",
                "detail": f"Text repair successful after {max_repairs} rounds"
            }
        else:
            return {
                "ok": False,
                "name": "Auto Repair Test",
                "detail": "Text repair failed, still has differences",
                "output": text_preview(repaired[:200]),
                "expected": text_preview(norm_expected[:200])
            }

    except Exception as e:
        return {
            "ok": False,
            "name": "Auto Repair Test",
            "detail": f"Test exception: {e}"
        }


# ──────────────────────────────────────────────
# Test runner
# ──────────────────────────────────────────────

def run_all_tests(data_dir):
    """Run all tests"""
    base_dir = Path(__file__).resolve().parent
    target_path = base_dir / "keyboard_simulator.py"

    if not target_path.exists():
        print(f"[FAIL] Main program does not exist: {target_path}")
        return 1

    print(f"Target program: {target_path}")
    print(f"Test data directory: {data_dir}")
    print()

    try:
        module = import_target_module(target_path)
    except Exception as e:
        print(f"[FAIL] Failed to import main program: {e}")
        return 1

    tests = [
        ("direct", test_direct_mode),
        ("simulation", test_simulation_mode),
        ("repair", test_repair_mode),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"Running test: {test_name}...")
        result = test_func(module, data_dir)
        results.append(result)

        status = "OK" if result["ok"] else "FAIL"
        print(f"[{status}] {result['name']}")
        if result.get("detail"):
            print(f"      Detail: {result['detail']}")
        if result.get("output"):
            print(f"      Output: {result['output']}")
        if result.get("expected"):
            print(f"      Expected: {result['expected']}")
        print()

    # Summary
    passed = sum(1 for r in results if r["ok"])
    total = len(results)
    failed = total - passed

    print(f"Summary: {passed}/{total} OK, {failed} FAIL")

    return 0 if failed == 0 else 1


# ──────────────────────────────────────────────
# Command line argument handling
# ──────────────────────────────────────────────

def print_help():
    """Print help information"""
    print("Keyboard Simulator Test Program")
    print()
    print("Usage:")
    print("  python test_keyboard_simulator.py [options]")
    print()
    print("Options:")
    print("  run --all           Run all tests")
    print("  run --direct        Run direct mode test")
    print("  run --simulation    Run simulation mode test")
    print("  run --repair        Run auto repair test")
    print("  run --help          Show help information")
    print()
    print("Examples:")
    print("  python test_keyboard_simulator.py run --all")
    print("  python test_keyboard_simulator.py run --direct")
    print("  python test_keyboard_simulator.py run --simulation")
    print("  python test_keyboard_simulator.py run --repair")


def main():
    """Main function"""
    if len(sys.argv) < 2:
        print_help()
        return 1

    command = sys.argv[1]

    if command == "run":
        if len(sys.argv) < 3:
            print("Error: Missing argument")
            print_help()
            return 1

        option = sys.argv[2]
        base_dir = Path(__file__).resolve().parent
        data_dir = base_dir / "test_data"

        if option == "--all":
            return run_all_tests(data_dir)
        elif option == "--direct":
            # Only run direct mode test
            module = import_target_module(base_dir / "keyboard_simulator.py")
            result = test_direct_mode(module, data_dir)
            status = "OK" if result["ok"] else "FAIL"
            print(f"[{status}] {result['name']}")
            if result.get("detail"):
                print(f"      Detail: {result['detail']}")
            return 0 if result["ok"] else 1
        elif option == "--simulation":
            # Only run simulation mode test
            module = import_target_module(base_dir / "keyboard_simulator.py")
            result = test_simulation_mode(module, data_dir)
            status = "OK" if result["ok"] else "FAIL"
            print(f"[{status}] {result['name']}")
            if result.get("detail"):
                print(f"      Detail: {result['detail']}")
            return 0 if result["ok"] else 1
        elif option == "--repair":
            # Only run auto repair test
            module = import_target_module(base_dir / "keyboard_simulator.py")
            result = test_repair_mode(module, data_dir)
            status = "OK" if result["ok"] else "FAIL"
            print(f"[{status}] {result['name']}")
            if result.get("detail"):
                print(f"      Detail: {result['detail']}")
            return 0 if result["ok"] else 1
        elif option == "--help":
            print_help()
            return 0
        else:
            print(f"Error: Unknown option {option}")
            print_help()
            return 1
    elif command == "--help" or command == "-h":
        print_help()
        return 0
    else:
        print(f"Error: Unknown command {command}")
        print_help()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
