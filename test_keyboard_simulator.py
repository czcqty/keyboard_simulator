#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Interactive contract tester for keyboard_simulator versions.

The tester injects a fake pynput module, captures the text that would be typed,
and prints OK/FAIL for every tested text. It never sends real keyboard input.
"""

import glob
import importlib.util
import re
import shlex
import sys
import time
import types
from pathlib import Path


class FakeKey:
    enter = "ENTER"
    tab = "TAB"
    space = "SPACE"
    f6 = "F6"
    f7 = "F7"


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


BUILTIN_TEXTS = [
    ("empty", ""),
    ("lowercase", "abcdefghijklmnopqrstuvwxyz"),
    ("uppercase", "ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    ("digits", "0123456789"),
    ("ascii_mixed", "abcXYZ123"),
    ("single_space", " "),
    ("many_spaces", "    "),
    ("leading_trailing_spaces", "  leading and trailing  "),
    ("tab", "\t"),
    ("tabs_between_columns", "col1\tcol2\tcol3"),
    ("lf_newlines", "line1\nline2\nline3"),
    ("crlf_newlines", "line1\r\nline2\r\nline3"),
    ("cr_newlines", "line1\rline2\rline3"),
    ("mixed_whitespace", " A\tB \n C\r\nD\rE "),
    ("ascii_punctuation", r"""!@#$%^&*()_+-=[]{};:'",.<>/?\|`~"""),
    ("quotes", "\"double\" 'single' `backtick`"),
    ("brackets", "() [] {} <>"),
    ("math_symbols", "+ - * / = % ^ < >"),
    ("chinese", "\u4e2d\u6587\u6d4b\u8bd5"),
    ("mixed_chinese_ascii", "\u4e2d\u6587 ABC 123"),
    ("full_width", "\uff21\uff22\uff23\uff11\uff12\uff13\uff0c\u3002\uff01\uff1f"),
    ("emoji", "\U0001f600\U0001f680\u2728"),
    ("combining_marks", "e\u0301 a\u0308 n\u0303"),
    ("long_text", ("abc123 \u4e2d\u6587\tline\n" * 10).rstrip("\n")),
]


def install_fake_pynput():
    pynput_module = types.ModuleType("pynput")
    keyboard_module = types.ModuleType("pynput.keyboard")
    keyboard_module.Controller = FakeController
    keyboard_module.Key = FakeKey
    keyboard_module.Listener = FakeListener
    pynput_module.keyboard = keyboard_module
    sys.modules["pynput"] = pynput_module
    sys.modules["pynput.keyboard"] = keyboard_module


def import_target_module(target_path):
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
        # Some versions auto-relaunch into .venv when they think they are
        # running globally. Make import look like an active virtualenv.
        sys.base_prefix = "__keyboard_simulator_test_base__"
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.base_prefix = original_base_prefix


def events_to_text(events):
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


def text_preview(text, limit=90):
    escaped = text.encode("unicode_escape").decode("ascii")
    if len(escaped) > limit:
        return escaped[: limit - 3] + "..."
    return escaped


def wait_for_engine(engine, timeout=2.0):
    deadline = time.monotonic() + timeout
    while getattr(engine, "running", False) and time.monotonic() < deadline:
        time.sleep(0.001)

    thread = getattr(engine, "_thread", None)
    if thread is not None:
        thread.join(timeout=max(0.0, deadline - time.monotonic()))

    if getattr(engine, "running", False):
        raise AssertionError("KeyboardEngine worker did not finish before timeout")


def new_engine(module):
    if not hasattr(module, "KeyboardEngine"):
        raise AssertionError("Target module does not define KeyboardEngine")
    return module.KeyboardEngine()


def type_and_capture(module, text, loops=1, use_sendinput=False, on_progress=None):
    engine = new_engine(module)
    done = []
    engine.type_text(
        text,
        delay_ms=0,
        loops=loops,
        use_sendinput=use_sendinput,
        on_progress=on_progress,
        on_done=lambda: done.append(True),
    )
    wait_for_engine(engine)
    return engine, done


def pass_result(behavior, name, text, output="", expected="", detail=""):
    return {
        "ok": True,
        "behavior": behavior,
        "name": name,
        "input": text,
        "output": output,
        "expected": expected,
        "detail": detail,
    }


def fail_result(behavior, name, text, output="", expected="", detail=""):
    return {
        "ok": False,
        "behavior": behavior,
        "name": name,
        "input": text,
        "output": output,
        "expected": expected,
        "detail": detail,
    }


def test_exact(module, name, text):
    try:
        engine, done = type_and_capture(module, text)
        output = events_to_text(engine.kb.events)
        if output != text:
            return fail_result("exact", name, text, output, text, "output text differs from input text")
        if done != [True]:
            return fail_result("exact", name, text, output, text, f"on_done calls = {len(done)}")
        return pass_result("exact", name, text, output, text, "input == output")
    except Exception as exc:
        return fail_result("exact", name, text, detail=str(exc))


def test_loops(module, name, text):
    try:
        loops = 2
        engine, done = type_and_capture(module, text, loops=loops)
        output = events_to_text(engine.kb.events)
        expected = text * loops
        if output != expected:
            return fail_result("loops", name, text, output, expected, f"output differs from input * {loops}")
        if done != [True]:
            return fail_result("loops", name, text, output, expected, f"on_done calls = {len(done)}")
        return pass_result("loops", name, text, output, expected, f"input repeated {loops} times")
    except Exception as exc:
        return fail_result("loops", name, text, detail=str(exc))


def test_callbacks(module, name, text):
    try:
        progress = []
        engine, done = type_and_capture(module, text, loops=2, on_progress=progress.append)
        output = events_to_text(engine.kb.events)
        expected = text * 2
        if output != expected:
            return fail_result("callbacks", name, text, output, expected, "typed output differs")
        if done != [True]:
            return fail_result("callbacks", name, text, output, expected, f"on_done calls = {len(done)}")
        if text and not progress:
            return fail_result("callbacks", name, text, output, expected, "on_progress was not called")
        if progress and not progress[-1].endswith("100%"):
            return fail_result("callbacks", name, text, output, expected, "last progress is not 100%")
        return pass_result("callbacks", name, text, output, expected, f"progress calls = {len(progress)}")
    except Exception as exc:
        return fail_result("callbacks", name, text, detail=str(exc))


def test_stop(module, name, text):
    try:
        engine = new_engine(module)
        if not text:
            engine.type_text(text, delay_ms=0)
            wait_for_engine(engine)
            output = events_to_text(engine.kb.events)
            if output == "":
                return pass_result("stop", name, text, output, "", "empty text finishes without output")
            return fail_result("stop", name, text, output, "", "empty text produced output")

        original_press = engine.kb.press
        original_type = engine.kb.type

        def press_and_stop(key):
            original_press(key)
            engine.stop()

        def type_and_stop(value):
            original_type(value)
            engine.stop()

        engine.kb.press = press_and_stop
        engine.kb.type = type_and_stop
        engine.type_text(text, delay_ms=0)
        wait_for_engine(engine)
        output = events_to_text(engine.kb.events)
        if output and text.startswith(output):
            return pass_result("stop", name, text, output, "prefix of input", "stopped after first emitted unit")
        return fail_result("stop", name, text, output, "prefix of input", "stop did not preserve prefix behavior")
    except Exception as exc:
        return fail_result("stop", name, text, detail=str(exc))


def test_sendinput(module, name, text):
    original_available = getattr(module, "SENDINIPUT_AVAILABLE", False)
    original_sender = getattr(module, "send_unicode_char", None)
    calls = []
    try:
        module.SENDINIPUT_AVAILABLE = True
        module.send_unicode_char = calls.append
        engine, done = type_and_capture(module, text, use_sendinput=True)
        fake_keyboard_output = events_to_text(engine.kb.events)
        output = "".join(calls)
        if fake_keyboard_output:
            return fail_result("sendinput", name, text, fake_keyboard_output, "", "fallback keyboard path was used")
        if output != text:
            return fail_result("sendinput", name, text, output, text, "SendInput output differs from input")
        if done != [True]:
            return fail_result("sendinput", name, text, output, text, f"on_done calls = {len(done)}")
        return pass_result("sendinput", name, text, output, text, "SendInput captured input == output")
    except Exception as exc:
        return fail_result("sendinput", name, text, detail=str(exc))
    finally:
        module.SENDINIPUT_AVAILABLE = original_available
        if original_sender is None:
            try:
                delattr(module, "send_unicode_char")
            except AttributeError:
                pass
        else:
            module.send_unicode_char = original_sender


BEHAVIOR_TESTS = {
    "exact": test_exact,
    "loops": test_loops,
    "callbacks": test_callbacks,
    "stop": test_stop,
    "sendinput": test_sendinput,
}

BEHAVIOR_SAMPLES = {
    "loops": ("loop_behavior", "Loop sample\n\tABC123"),
    "callbacks": ("callback_behavior", "AB"),
    "stop": ("stop_behavior", "ABCDE"),
    "sendinput": ("sendinput_behavior", "A \n\t\u4e2d"),
}


HELP_TEXT = {
    "help": """help usage:
  help --list          list first-level commands
  help --tab           toggle tab completion on/off
  help --help          show this help""",
    "case": """case usage:
  case --list          show selected test behaviors
  case --exact         select exact input/output test
  case --loops         select loop-repeat test
  case --callbacks     select progress/done callback test
  case --stop          select stop behavior test
  case --sendinput     select SendInput behavior test
  case --all           select all behaviors
  case --exact,--loops select multiple behaviors
  case --help          show this help
""",
    "target": """target usage:
  target --list                show selected target files
  target --add <file.py>       add one target file
  target --set <file.py>       replace targets with one file
  target --glob <pattern>      add targets matched by a glob pattern
  target --clear               remove all targets
  target --default             reset to keyboard_simulator.py
  target --help                show this help
""",
    "text": """text usage:
  text --list                  show currently selected test texts
  text --builtins              toggle built-in full coverage texts on/off
  text --add <text>            add custom text to the selected test text list
  text --help                  show this help
""",
    "run": """run usage:
  run --status        run selected cases; text list applies only to exact
  run --all           run all cases against all built-ins plus custom texts
  run --custom <text> run exact input/output test against one custom text
  run --help          show this help""",
    "status": """status usage:
  status --list   show current targets, cases, and text configuration
  status --help   show this help""",
    "exit": """exit usage:
  exit            leave the tester
  quit            same as exit
  exit --help     show this help""",
}

FIRST_LEVEL_COMMANDS = ["case", "target", "text", "run", "status", "help", "exit", "quit"]


class TesterShell:
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent
        self.targets = [self.base_dir / "keyboard_simulator.py"]
        self.behaviors = ["exact"]
        self.use_builtins = True
        self.custom_texts = []
        self.custom_index = 1
        self.tab_completion_enabled = False
        self.readline = None

    def resolve_path(self, value):
        path = Path(value)
        if not path.is_absolute():
            path = self.base_dir / path
        return path.resolve()

    def unique_targets(self, paths):
        seen = set()
        result = []
        for path in paths:
            resolved = Path(path).resolve()
            if resolved not in seen:
                seen.add(resolved)
                result.append(resolved)
        return result

    def active_texts(self):
        texts = []
        if self.use_builtins:
            texts.extend(BUILTIN_TEXTS)
        texts.extend(self.custom_texts)
        return texts

    def all_texts(self):
        return list(BUILTIN_TEXTS) + list(self.custom_texts)

    def parse_behaviors(self, raw_value):
        raw_value = raw_value.strip().lower()
        if not raw_value:
            return self.behaviors

        aliases = {
            "--1": "exact",
            "--2": "loops",
            "--3": "callbacks",
            "--4": "stop",
            "--5": "sendinput",
            "--6": "all",
            "--a": "all",
            "--callback": "callbacks",
            "--send_input": "sendinput",
            "--send-input": "sendinput",
        }

        behaviors = []
        for token in re.split(r"[,，\s]+", raw_value):
            if not token:
                continue
            if not token.startswith("--"):
                raise ValueError(f"parameter {token!r} must start with --")
            behavior = aliases.get(token, token)
            if behavior.startswith("--"):
                behavior = behavior[2:]
            if behavior == "all":
                return list(BEHAVIOR_TESTS)
            if behavior not in BEHAVIOR_TESTS:
                raise ValueError(f"unknown case {token!r}")
            behaviors.append(behavior)
        return list(dict.fromkeys(behaviors)) or self.behaviors

    def print_result(self, result):
        status = "OK" if result["ok"] else "FAIL"
        print(f"[{status}] {result['behavior']:<9} {result['name']}")
        print(f"      input   : {text_preview(result['input'])}")
        if result["output"] != "" or not result["ok"]:
            print(f"      output  : {text_preview(result['output'])}")
        if result["expected"] != "" and result["expected"] != result["output"]:
            print(f"      expected: {text_preview(result['expected'])}")
        if result["detail"]:
            print(f"      detail  : {result['detail']}")

    def print_status(self):
        print("Current status:")
        print(f"  cases   : {', '.join(self.behaviors)}")
        print("  targets :")
        for target in self.targets:
            print(f"    - {target}")
        print(f"  builtins: {'on' if self.use_builtins else 'off'}")
        print(f"  texts   : {len(self.active_texts())} selected")
        print(f"  tab     : {'on' if self.tab_completion_enabled else 'off'}")

    def print_texts(self):
        texts = self.active_texts()
        print(f"Active test texts: {len(texts)}")
        for name, text in texts:
            print(f"- {name}: {text_preview(text)}")

    def print_targets(self):
        print("Selected target files:")
        if not self.targets:
            print("  (none)")
            return
        for target in self.targets:
            print(f"  - {target}")

    def print_cases(self):
        print(f"Selected cases: {', '.join(self.behaviors)}")

    def handle_help(self, args):
        if not args:
            print(HELP_TEXT["help"])
            return
        option = args[0]
        if option == "--list":
            print("First-level commands:")
            for command in FIRST_LEVEL_COMMANDS:
                print(f"  {command}")
            return
        if option == "--tab":
            self.toggle_tab_completion()
            return
        if option == "--help":
            print(HELP_TEXT["help"])
            return
        self.invalid_parameter("help")

    def handle_case(self, args):
        if not args:
            self.invalid_parameter("case")
            return
        if args[0] == "--help":
            print(HELP_TEXT["case"])
            return
        if args[0] == "--list":
            self.print_cases()
            return
        try:
            self.behaviors = self.parse_behaviors(" ".join(args))
        except ValueError as exc:
            print(f"Invalid case parameter: {exc}. Use `case --help`.")
            return
        self.print_cases()

    def handle_target(self, args):
        if not args:
            self.invalid_parameter("target")
            return
        if args[0] == "--help":
            print(HELP_TEXT["target"])
            return
        if args[0] == "--list":
            self.print_targets()
            return

        action = args[0]
        if action == "--add" and len(args) >= 2:
            self.targets = self.unique_targets(self.targets + [self.resolve_path(" ".join(args[1:]))])
            self.print_targets()
            return
        if action == "--set" and len(args) >= 2:
            self.targets = [self.resolve_path(" ".join(args[1:]))]
            self.print_targets()
            return
        if action == "--glob" and len(args) >= 2:
            pattern = " ".join(args[1:])
            matched = [Path(path) for path in glob.glob(str(self.base_dir / pattern))]
            self.targets = self.unique_targets(self.targets + matched)
            print(f"Matched {len(matched)} target(s).")
            self.print_targets()
            return
        if action == "--clear":
            self.targets = []
            self.print_targets()
            return
        if action == "--default":
            self.targets = [self.base_dir / "keyboard_simulator.py"]
            self.print_targets()
            return
        print("Invalid target parameter. Use `target --help`.")

    def handle_text(self, args):
        if not args:
            self.invalid_parameter("text")
            return
        if args[0] == "--help":
            print(HELP_TEXT["text"])
            return
        if args[0] == "--list":
            self.print_texts()
            return
        if args[0] == "--builtins" and len(args) == 1:
            self.use_builtins = not self.use_builtins
            print(f"Built-in texts: {'on' if self.use_builtins else 'off'}")
            return
        if args[0] == "--add" and len(args) >= 2:
            text = " ".join(args[1:])
            self.custom_texts.append((f"custom_text_{self.custom_index}", text))
            self.custom_index += 1
            print(f"Added selected text: {text_preview(text)}")
            return
        print("Invalid text parameter. Use `text --help`.")

    def run_tests(self, texts=None, behaviors=None):
        if texts is None:
            texts = self.active_texts()
        if behaviors is None:
            behaviors = self.behaviors
        if not self.targets:
            print("[FAIL] no target selected. Use `target --help`.")
            return 1
        if "exact" in behaviors and not texts:
            print("[FAIL] no test text selected. Use `text --help`.")
            return 1

        total = 0
        failed = 0

        for target_path in self.targets:
            print()
            print(f"Target: {target_path}")
            try:
                module = import_target_module(target_path)
            except Exception as exc:
                print(f"[FAIL] import target: {exc}")
                total += 1
                failed += 1
                continue

            for behavior in behaviors:
                test_func = BEHAVIOR_TESTS[behavior]
                behavior_texts = texts
                if behavior != "exact":
                    behavior_texts = [BEHAVIOR_SAMPLES[behavior]]
                for name, text in behavior_texts:
                    result = test_func(module, name, text)
                    total += 1
                    failed += 0 if result["ok"] else 1
                    self.print_result(result)

        passed = total - failed
        print()
        print(f"Summary: {passed}/{total} OK, {failed} FAIL")
        return 0 if failed == 0 else 1

    def handle_run(self, args):
        if args and args[0] == "--help":
            print(HELP_TEXT["run"])
            return
        if not args:
            print("Invalid run parameter. Use `run --help`.")
            return
        if args[0] == "--status" and len(args) == 1:
            self.run_tests()
            return
        if args[0] == "--all" and len(args) == 1:
            self.run_tests(texts=self.all_texts(), behaviors=list(BEHAVIOR_TESTS))
            return
        if args[0] == "--custom" and len(args) >= 2:
            self.run_tests(texts=[("custom_text", " ".join(args[1:]))], behaviors=["exact"])
            return
        print("Invalid run parameter. Use `run --help`.")

    def invalid_parameter(self, command):
        print(f"Invalid {command} parameter. Use `{command} --help`.")

    def handle_command(self, raw_line):
        try:
            parts = shlex.split(raw_line)
        except ValueError as exc:
            print(f"Invalid input: {exc}. Use `help --list`.")
            return True

        if not parts:
            return True

        command = parts[0].lower()
        args = parts[1:]

        if command == "help":
            self.handle_help(args)
        elif command == "case":
            self.handle_case(args)
        elif command == "target":
            self.handle_target(args)
        elif command == "text":
            self.handle_text(args)
        elif command == "run":
            self.handle_run(args)
        elif command == "status":
            if args and args[0] == "--help":
                print(HELP_TEXT["status"])
            elif args and args[0] == "--list" and len(args) == 1:
                self.print_status()
            elif args:
                self.invalid_parameter("status")
            else:
                self.invalid_parameter("status")
        elif command in ("exit", "quit"):
            if args and args[0] == "--help":
                print(HELP_TEXT["exit"])
            elif args:
                self.invalid_parameter(command)
            else:
                return False
        else:
            print("Unknown command. Use `help --list` to list first-level commands.")
        return True

    def completer(self, text, state):
        options = FIRST_LEVEL_COMMANDS[:]
        options.extend(
            [
                "help --list",
                "help --tab",
                "help --help",
                "case --list",
                "case --exact",
                "case --loops",
                "case --callbacks",
                "case --stop",
                "case --sendinput",
                "case --all",
                "case --help",
                "target --list",
                "target --add ",
                "target --set ",
                "target --glob ",
                "target --clear",
                "target --default",
                "target --help",
                "text --list",
                "text --builtins",
                "text --add ",
                "text --help",
                "run --status",
                "run --all",
                "run --custom ",
                "run --help",
                "status --list",
                "status --help",
                "exit --help",
                "quit --help",
            ]
        )
        matches = [option for option in options if option.startswith(text)]
        try:
            return matches[state]
        except IndexError:
            return None

    def toggle_tab_completion(self):
        if self.readline is None:
            try:
                import readline
            except ImportError:
                print("Tab completion is not available in this Python environment.")
                return
            self.readline = readline

        self.tab_completion_enabled = not self.tab_completion_enabled
        if self.tab_completion_enabled:
            self.readline.set_completer(self.completer)
            self.readline.parse_and_bind("tab: complete")
        else:
            self.readline.set_completer(None)
        print(f"Tab completion: {'on' if self.tab_completion_enabled else 'off'}")

    def run(self):
        print("Keyboard simulator test console")
        while True:
            try:
                raw_line = input("tester> ")
            except EOFError:
                print()
                return 0
            except KeyboardInterrupt:
                print()
                continue
            if not self.handle_command(raw_line):
                return 0


def main():
    if len(sys.argv) > 1:
        print("Startup parameters are ignored. Configure tests after the console starts.")
    return TesterShell().run()


if __name__ == "__main__":
    raise SystemExit(main())
