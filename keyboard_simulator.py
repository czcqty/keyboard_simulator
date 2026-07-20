#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cross-platform keyboard input simulator
Supports Windows / macOS / Linux
Uses pynput for keyboard simulation, tkinter for GUI
Supports direct mode (clipboard paste) and simulation mode (character-by-character input)
"""
import os
import sys
import subprocess
import platform
import ctypes

# Auto-switch to virtual environment
def _auto_switch_venv():
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix) or hasattr(sys, "real_prefix")
    if in_venv:
        return
    script_dir = os.path.dirname(os.path.abspath(__file__))
    venv_dir = os.path.join(script_dir, ".venv")
    system = platform.system()
    if system == "Windows":
        venv_python = os.path.join(venv_dir, "Scripts", "python.exe")
    else:
        venv_python = os.path.join(venv_dir, "bin", "python3")
        if not os.path.exists(venv_python):
            venv_python = os.path.join(venv_dir, "bin", "python")

    if os.path.exists(venv_python):
        print("[Environment] Auto-switching to virtual environment...")
        sys.exit(subprocess.run([venv_python, __file__] + sys.argv[1:], cwd=script_dir).returncode)

_auto_switch_venv()

import time
import threading
import difflib

# Try to import clipboard library
try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
except ImportError:
    PYPERCLIP_AVAILABLE = False


FAST_INPUT_DELAY_MS = 5
REPAIR_NAV_DELAY_SECONDS = 0.005
VERIFY_SETTLE_SECONDS = 0.05
COPY_SETTLE_SECONDS = 0.05


# ──────────────────────────────────────────────
# Windows high DPI adaptation (execute before importing tkinter)
# Supports 1080p / 2K / 4K high resolution screens, avoids blurry interface
# ──────────────────────────────────────────────
if platform.system() == "Windows":
    try:
        # 2 = PROCESS_PER_MONITOR_DPI_AWARE_V2, best DPI support
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

from tkinter import (
    Tk, Frame, Label, Entry, Text, Button, StringVar, IntVar,
    ttk, messagebox, END, WORD, DISABLED, NORMAL, LEFT, RIGHT, BOTH, X, Y, W, E, N, S
)

# ──────────────────────────────────────────────
# Dependency check
# ──────────────────────────────────────────────
try:
    from pynput.keyboard import Controller as KBController, Key, Listener as KBListener
except ImportError:
    print("Missing required third-party dependency: pynput", file=sys.stderr)
    print("Please run 'python init.py' to initialize local virtual environment first.", file=sys.stderr)
    sys.exit(1)


# ──────────────────────────────────────────────
# Windows SendInput fallback mode (Windows only)
# ──────────────────────────────────────────────
SENDINIPUT_AVAILABLE = False
if platform.system() == "Windows":
    try:
        from ctypes import wintypes

        user32 = ctypes.windll.user32

        INPUT_KEYBOARD = 1
        KEYEVENTF_UNICODE = 0x0004
        KEYEVENTF_KEYUP = 0x0002

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [
                ("dx", wintypes.LONG),
                ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
            ]

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
            ]

        class HARDWAREINPUT(ctypes.Structure):
            _fields_ = [
                ("uMsg", wintypes.DWORD),
                ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD),
            ]

        class INPUT(ctypes.Structure):
            class _INPUT_UNION(ctypes.Union):
                _fields_ = [
                    ("mi", MOUSEINPUT),
                    ("ki", KEYBDINPUT),
                    ("hi", HARDWAREINPUT),
                ]
            _fields_ = [
                ("type", wintypes.DWORD),
                ("union", _INPUT_UNION),
            ]

        VK_RETURN = 0x0D
        VK_TAB = 0x09

        def _send_vk_key(vk_code):
            """通过 SendInput 发送单个虚拟键码"""
            inp_down = INPUT()
            inp_down.type = INPUT_KEYBOARD
            inp_down.union.ki.wVk = vk_code
            inp_down.union.ki.wScan = 0
            inp_down.union.ki.dwFlags = 0
            inp_down.union.ki.time = 0
            inp_down.union.ki.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))

            inp_up = INPUT()
            inp_up.type = INPUT_KEYBOARD
            inp_up.union.ki.wVk = vk_code
            inp_up.union.ki.wScan = 0
            inp_up.union.ki.dwFlags = KEYEVENTF_KEYUP
            inp_up.union.ki.time = 0
            inp_up.union.ki.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))

            user32.SendInput(2, (INPUT * 2)(inp_down, inp_up), ctypes.sizeof(INPUT))

        def send_unicode_char(char):
            """通过 SendInput 发送单个字符（Windows 专用）"""
            # 换行和 Tab 需要通过虚拟键码发送
            if char == "\n" or char == "\r":
                _send_vk_key(VK_RETURN)
                return
            if char == "\t":
                _send_vk_key(VK_TAB)
                return

            code = ord(char)
            # Key down
            inp_down = INPUT()
            inp_down.type = INPUT_KEYBOARD
            inp_down.union.ki.wVk = 0
            inp_down.union.ki.wScan = code
            inp_down.union.ki.dwFlags = KEYEVENTF_UNICODE
            inp_down.union.ki.time = 0
            inp_down.union.ki.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))
            # Key up
            inp_up = INPUT()
            inp_up.type = INPUT_KEYBOARD
            inp_up.union.ki.wVk = 0
            inp_up.union.ki.wScan = code
            inp_up.union.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
            inp_up.union.ki.time = 0
            inp_up.union.ki.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))


            user32.SendInput(2, (INPUT * 2)(inp_down, inp_up), ctypes.sizeof(INPUT))

        SENDINIPUT_AVAILABLE = True
    except Exception:
        pass





# ──────────────────────────────────────────────
# Keyboard simulation engine
# ──────────────────────────────────────────────
class KeyboardEngine:
    """Keyboard simulation core engine"""

    def __init__(self):
        self.kb = KBController()
        self._stop_flag = threading.Event()
        self._running = False
        self._thread = None

    @property
    def running(self):
        return self._running

    def stop(self):
        self._stop_flag.set()

    def _should_stop(self):
        return self._stop_flag.is_set()

    def _iter_output_units(self, text):
        """Yield character units in input order, compatible with \r\n / \r / \n line endings."""
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            # Treat CRLF as single newline, avoid sending enter twice
            if ch == "\r" and i + 1 < n and text[i + 1] == "\n":
                yield "\n"
                i += 2
                continue
            if ch == "\r":
                yield "\n"
            else:
                yield ch
            i += 1

    def _emit_unit(self, unit, use_sendinput=False):
        """Send a single character unit, preserving input format."""
        if use_sendinput and SENDINIPUT_AVAILABLE:
            send_unicode_char(unit)
            return

        if unit == "\n":
            self.kb.press(Key.enter)
            self.kb.release(Key.enter)
        elif unit == "\t":
            self.kb.press(Key.tab)
            self.kb.release(Key.tab)
        elif unit == " ":
            self.kb.press(Key.space)
            self.kb.release(Key.space)
        else:
            self.kb.type(unit)

    def _tap_key(self, key):
        self.kb.press(key)
        self.kb.release(key)

    def _hotkey(self, modifier, key):
        self.kb.press(modifier)
        self.kb.press(key)
        self.kb.release(key)
        self.kb.release(modifier)

    def _select_all_and_copy(self):
        """Send select-all (Ctrl+A / Cmd+A) and copy (Ctrl+C / Cmd+C) shortcuts"""
        system = platform.system()
        modifier = Key.cmd if system == "Darwin" else Key.ctrl

        self._select_all(modifier)

        if COPY_SETTLE_SECONDS > 0:
            time.sleep(COPY_SETTLE_SECONDS)

        # Copy
        self.kb.press(modifier)
        self.kb.press('c')
        self.kb.release('c')
        self.kb.release(modifier)

    def _paste_from_clipboard(self):
        """Send paste shortcut (Ctrl+V / Cmd+V)"""
        system = platform.system()
        modifier = Key.cmd if system == "Darwin" else Key.ctrl

        self.kb.press(modifier)
        self.kb.press('v')
        self.kb.release('v')
        self.kb.release(modifier)

    def _select_all(self, modifier=None):
        """Send select-all shortcut, allowing caller to reuse determined platform modifier."""
        if modifier is None:
            system = platform.system()
            modifier = Key.cmd if system == "Darwin" else Key.ctrl

        self.kb.press(modifier)
        self.kb.press('a')
        self.kb.release('a')
        self.kb.release(modifier)

    def _move_to_pos(self, pos, text_len, modifier, nav_delay):
        """Navigate from document endpoint to logical character position, avoiding Down affected by soft line breaks."""
        pos = max(0, min(pos, text_len))
        from_start = pos
        from_end = text_len - pos

        if from_start <= from_end:
            self._hotkey(modifier, Key.home)
            steps = from_start
            key = Key.right
        else:
            self._hotkey(modifier, Key.end)
            steps = from_end
            key = Key.left

        if nav_delay > 0:
            time.sleep(nav_delay)
        for _ in range(steps):
            if self._should_stop():
                break
            self._tap_key(key)
            if nav_delay > 0:
                time.sleep(nav_delay)

    def _select_forward(self, count, nav_delay):
        if count <= 0:
            return
        self.kb.press(Key.shift)
        try:
            for _ in range(count):
                if self._should_stop():
                    break
                self._tap_key(Key.right)
                if nav_delay > 0:
                    time.sleep(nav_delay)
        finally:
            self.kb.release(Key.shift)

    def _direct_paste_text(self, text, delay_ms, on_progress, get_clipboard_func,
                          enable_repair, max_detections, paste_by_line=False):
        """Direct mode: paste text via clipboard, bypassing website/software keyboard restrictions

        Args:
            paste_by_line: If True, paste line by line with Enter key; if False, paste all at once
        """
        system = platform.system()
        modifier = Key.cmd if system == "Darwin" else Key.ctrl

        def normalize(t):
            return t.replace("\r\n", "\n").replace("\r", "\n")

        # Try pyperclip, fallback to system commands if unavailable
        def set_clipboard(text_content):
            if PYPERCLIP_AVAILABLE:
                try:
                    pyperclip.copy(text_content)
                    return True
                except Exception:
                    pass
            # Fallback: use subprocess to call system commands
            try:
                if system == "Windows":
                    # Windows: use clip command
                    process = subprocess.Popen(['clip'], stdin=subprocess.PIPE, shell=True)
                    process.communicate(text_content.encode('utf-16-le'))
                    return True
                elif system == "Darwin":
                    # macOS: use pbcopy
                    process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
                    process.communicate(text_content.encode('utf-8'))
                    return True
                else:
                    # Linux: use xclip or xsel
                    try:
                        process = subprocess.Popen(['xclip', '-selection', 'clipboard'],
                                                 stdin=subprocess.PIPE)
                        process.communicate(text_content.encode('utf-8'))
                        return True
                    except FileNotFoundError:
                        process = subprocess.Popen(['xsel', '--clipboard', '--input'],
                                                 stdin=subprocess.PIPE)
                        process.communicate(text_content.encode('utf-8'))
                        return True
            except Exception:
                return False

        if paste_by_line:
            # Line-by-line paste mode
            lines = text.split('\n')
            total_lines = len(lines)

            if on_progress:
                on_progress(f"Direct mode: preparing to paste {total_lines} lines...")

            for i, line in enumerate(lines):
                if self._should_stop():
                    return False

                if on_progress:
                    pct = ((i + 1) / total_lines) * 100
                    on_progress(f"Direct mode: pasting line {i+1}/{total_lines} ({pct:.0f}%)")

                # Copy current line to clipboard
                if not set_clipboard(line):
                    if on_progress:
                        on_progress("Error: cannot set clipboard content")
                    return False

                # Short delay to ensure clipboard content is set
                time.sleep(0.05)

                # Send paste shortcut
                self._paste_from_clipboard()

                # If not last line, send enter key for newline
                if i < total_lines - 1:
                    time.sleep(0.05)
                    self.kb.press(Key.enter)
                    self.kb.release(Key.enter)

                # Inter-line delay
                if delay_ms > 0:
                    time.sleep(delay_ms / 1000.0)
        else:
            # All-at-once paste mode
            if on_progress:
                on_progress("Direct mode: preparing to paste all text...")

            # Copy entire text to clipboard
            if not set_clipboard(text):
                if on_progress:
                    on_progress("Error: cannot set clipboard content")
                return False

            # Short delay to ensure clipboard content is set
            time.sleep(0.05)

            # Send paste shortcut
            self._paste_from_clipboard()

            if on_progress:
                on_progress("Direct mode: text pasted successfully")

        # Paste line by line
        for i, line in enumerate(lines):
            if self._should_stop():
                return False

            if on_progress:
                pct = ((i + 1) / total_lines) * 100
                on_progress(f"Direct mode: pasting line {i+1}/{total_lines} ({pct:.0f}%)")

            # Copy current line to clipboard
            if not set_clipboard(line):
                if on_progress:
                    on_progress("Error: cannot set clipboard content")
                return False

            # Short delay to ensure clipboard content is set
            time.sleep(0.05)

            # Send paste shortcut
            self._paste_from_clipboard()

            # If not last line, send enter key for newline
            if i < total_lines - 1:
                time.sleep(0.05)
                self.kb.press(Key.enter)
                self.kb.release(Key.enter)

            # Inter-line delay
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)

        # If auto-repair is enabled, perform verification and repair
        if enable_repair and get_clipboard_func:
            if on_progress:
                on_progress("Direct mode: starting text verification...")

            expected_text = text
            for repair_round in range(max_detections + 1):
                if self._should_stop():
                    return False

                if on_progress:
                    on_progress(f"Verifying text... repaired {repair_round}/{max_detections} rounds")

                # Wait for text to stabilize
                if VERIFY_SETTLE_SECONDS > 0:
                    time.sleep(VERIFY_SETTLE_SECONDS)

                # Select all and copy
                self._select_all_and_copy()
                if COPY_SETTLE_SECONDS > 0:
                    time.sleep(COPY_SETTLE_SECONDS)

                # Get clipboard content
                clipboard_text = get_clipboard_func()

                # Compare text
                if normalize(clipboard_text) == normalize(expected_text):
                    if on_progress:
                        on_progress("Success (text matches)")
                    return True

                if repair_round >= max_detections:
                    if on_progress:
                        on_progress("Failed (text does not match)")
                    return False

                # Execute repair
                if on_progress:
                    on_progress(f"Text mismatch, performing repair {repair_round + 1}/{max_detections}...")
                repaired = self._repair_diff(clipboard_text, expected_text, delay_ms, use_sendinput=False)
                if self._should_stop():
                    return False
                if not repaired:
                    if on_progress:
                        on_progress("Failed (no repairable differences found)")
                    return False

        return True

    def _insert_repair_text(self, text, delay_ms, use_sendinput):
        for char in text:
            if self._should_stop():
                break
            self._emit_unit(char, use_sendinput=use_sendinput)
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)

    def _repair_diff(self, current_str, target_str, delay_ms, use_sendinput):
        """Repair a difference block.

        Each time only repairs one difference based on the just-copied text, then outer layer re-checks.
        This avoids using stale coordinates to modify subsequent difference blocks in the same round.
        """
        current_norm = current_str.replace("\r\n", "\n").replace("\r", "\n")
        target_norm = target_str.replace("\r\n", "\n").replace("\r", "\n")
        opcodes = difflib.SequenceMatcher(None, current_norm, target_norm).get_opcodes()
        system = platform.system()
        modifier = Key.cmd if system == "Darwin" else Key.ctrl
        nav_delay = REPAIR_NAV_DELAY_SECONDS
        for tag, i1, i2, j1, j2 in reversed(opcodes):
            if self._should_stop():
                return False
            if tag == "equal":
                continue

            delete_count = i2 - i1
            insert_text = target_norm[j1:j2]

            self._move_to_pos(i1, len(current_norm), modifier, nav_delay)
            if self._should_stop():
                return False

            if delete_count:
                self._select_forward(delete_count, nav_delay)
                if self._should_stop():
                    return False
                self._tap_key(Key.delete)
                if nav_delay > 0:
                    time.sleep(nav_delay)

            self._insert_repair_text(insert_text, delay_ms, use_sendinput)
            return True
        return False

    def type_text(self, text, delay_ms=50, loops=1, use_sendinput=False,
                  enable_repair=False, max_detections=20, get_clipboard_func=None,
                  only_repair=False, on_progress=None, on_done=None, direct_mode=False,
                  paste_by_line=False):
        """Simulate text input in new thread or auto-verify with manual error correction repair

        Args:
            direct_mode: Whether to use direct mode (clipboard paste)
            paste_by_line: If True, paste line by line; if False, paste all at once (direct mode only)
        """
        self._stop_flag.clear()
        self._running = True

        units = list(self._iter_output_units(text))
        total_units = len(units)

        if not only_repair and total_units == 0:
            self._running = False
            if on_done:
                on_done()
            return

        def do_typing():
            # If direct mode, use clipboard paste
            if direct_mode and not only_repair:
                success = self._direct_paste_text(
                    text, delay_ms, on_progress, get_clipboard_func,
                    enable_repair, max_detections, paste_by_line
                )
                return success

            # Simulation mode: character-by-character input
            for loop_i in range(loops):
                if self._should_stop():
                    return False
                for unit_i, unit in enumerate(units):
                    if self._should_stop():
                        return False
                    self._emit_unit(unit, use_sendinput=use_sendinput)
                    if on_progress:
                        pct = ((loop_i * total_units + unit_i + 1) / (loops * total_units)) * 100
                        on_progress(f"Simulation mode: round {loop_i+1}/{loops}, progress {pct:.0f}%")
                    if delay_ms > 0:
                        time.sleep(delay_ms / 1000.0)
            return True

        def worker():
            final_status = None
            try:
                expected_text = text * loops

                # If not "repair only", execute typing first
                if not only_repair:
                    success = do_typing()
                    if not success or self._should_stop():
                        return

                # If direct mode, verification is handled in _direct_paste_text
                if direct_mode:
                    return

                # If repair is not enabled or no clipboard function provided, end directly
                if not enable_repair or not get_clipboard_func:
                    return

                def normalize(t):
                    return t.replace("\r\n", "\n").replace("\r", "\n")

                for repair_round in range(max_detections + 1):
                    if self._should_stop():
                        return

                    if on_progress:
                        on_progress(f"Verifying text... repaired {repair_round}/{max_detections} rounds")

                    if VERIFY_SETTLE_SECONDS > 0:
                        time.sleep(VERIFY_SETTLE_SECONDS)
                    self._select_all_and_copy()
                    if COPY_SETTLE_SECONDS > 0:
                        time.sleep(COPY_SETTLE_SECONDS)
                    clipboard_text = get_clipboard_func()

                    if normalize(clipboard_text) == normalize(expected_text):
                        if on_progress:
                            on_progress("Success (text matches)")
                        final_status = "Success (text matches)"
                        return

                    if repair_round >= max_detections:
                        if on_progress:
                            on_progress("Failed (text does not match)")
                        final_status = "Failed (text does not match)"
                        return

                    if on_progress:
                        on_progress(f"Text mismatch, performing repair {repair_round + 1}/{max_detections}...")
                    repaired = self._repair_diff(clipboard_text, expected_text, delay_ms, use_sendinput)
                    if self._should_stop():
                        return
                    if not repaired:
                        if on_progress:
                            on_progress("Failed (no repairable differences found)")
                        final_status = "Failed (no repairable differences found)"
                        return
            except Exception as e:
                if on_progress:
                    on_progress(f"Error: {e}")
                final_status = f"Error: {e}"
            finally:
                self._running = False
                if on_done:
                    try:
                        on_done(final_status)
                    except TypeError:
                        on_done()

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()




# ──────────────────────────────────────────────
# GUI Application
# ──────────────────────────────────────────────
class KeyboardSimulatorApp:
    """Keyboard simulator GUI"""

    HOTKEY_START = Key.f6
    HOTKEY_STOP = Key.f7
    HOTKEY_CORRECT = Key.f8

    def __init__(self):
        self.engine = KeyboardEngine()
        self.hotkey_listener = None

        # ── Main window ──
        self.root = Tk()
        self.root.title("Keyboard Input Simulator")
        self.root.geometry("520x580")
        self.root.resizable(True, True)
        self.root.minsize(420, 480)

        # Styles
        style = ttk.Style()
        style.configure("Title.TLabel", font=("", 14, "bold"))
        style.configure("Status.TLabel", font=("", 10))
        style.configure("Mode.TLabel", font=("", 10, "bold"))

        self._build_ui()
        self._start_hotkey_listener()

    # ──────────── UI Construction ────────────

    def _build_ui(self):
        root = self.root

        # Title
        title_frame = Frame(root, padx=12, pady=8)
        title_frame.pack(fill=X)
        ttk.Label(title_frame, text="Keyboard Input Simulator", style="Title.TLabel").pack(side=LEFT)
        sys_label = "Windows" if platform.system() == "Windows" else platform.system()
        ttk.Label(title_frame, text=f"Platform: {sys_label}").pack(side=RIGHT)

        # Mode selection area
        mode_frame = ttk.LabelFrame(root, text="Input Mode", padding=8)
        mode_frame.pack(fill=X, padx=12, pady=(0, 4))
        self._build_mode_selector(mode_frame)

        # Text input area
        text_frame = ttk.LabelFrame(root, text="Text Box", padding=8)
        text_frame.pack(fill=BOTH, expand=True, padx=12, pady=(0, 4))
        self._build_text_area(text_frame)

        # Direct mode options (auto repair only)
        self.direct_options_frame = ttk.LabelFrame(root, text="Direct Mode Options", padding=8)
        self.direct_options_frame.pack(fill=X, padx=12, pady=4)
        self._build_direct_options(self.direct_options_frame)

        # Simulation mode options (SendInput, settings)
        self.sim_options_frame = ttk.LabelFrame(root, text="Simulation Mode Options", padding=8)
        self.sim_options_frame.pack(fill=X, padx=12, pady=4)
        self._build_sim_options(self.sim_options_frame)

        # Initially hide simulation options
        self.sim_options_frame.pack_forget()

        # Button area
        btn_frame = Frame(root, padx=12, pady=6)
        btn_frame.pack(fill=X)
        self._build_buttons(btn_frame)

        # Status bar
        status_frame = Frame(root, padx=12, pady=6)
        status_frame.pack(fill=X, side="bottom")
        self.status_var = StringVar(value="Ready  |  F6 Start · F7 Stop · F8 Auto Repair")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, style="Status.TLabel")
        self.status_label.pack(side=LEFT)

    def _build_mode_selector(self, parent):
        """Build mode selection area"""
        # Mode variable, default to direct mode (value=1)
        self.direct_mode_var = IntVar(value=1)

        # Mode description
        desc_frame = Frame(parent)
        desc_frame.pack(fill=X, pady=(0, 6))

        ttk.Label(desc_frame, text="Select input mode:", style="Mode.TLabel").pack(side=LEFT)

        # Radio buttons
        radio_frame = Frame(parent)
        radio_frame.pack(fill=X)

        # Direct mode radio button
        direct_radio = ttk.Radiobutton(
            radio_frame,
            text="Direct Mode (default)",
            variable=self.direct_mode_var,
            value=1,
            command=lambda: self._on_mode_change(1)
        )
        direct_radio.pack(side=LEFT, padx=(0, 20))

        # Simulation mode radio button
        sim_radio = ttk.Radiobutton(
            radio_frame,
            text="Simulation Mode",
            variable=self.direct_mode_var,
            value=0,
            command=lambda: self._on_mode_change(0)
        )
        sim_radio.pack(side=LEFT)

        # Mode description label
        info_frame = Frame(parent)
        info_frame.pack(fill=X, pady=(6, 0))

        self.mode_info_var = StringVar(value="Direct: Paste via clipboard, bypass keyboard restrictions")
        ttk.Label(info_frame, textvariable=self.mode_info_var, foreground="gray").pack(side=LEFT)

    def _on_mode_change(self, mode):
        """Handle mode switch"""
        if mode == 1:
            # Direct mode: show direct options, hide simulation options
            self.mode_info_var.set("Direct: Paste via clipboard, bypass keyboard restrictions")
            self.direct_options_frame.pack(fill=X, padx=12, pady=4, after=self.text_input.master)
            self.sim_options_frame.pack_forget()
        else:
            # Simulation mode: hide direct options, show simulation options
            self.mode_info_var.set("Simulation: Character-by-character input, better compatibility")
            self.direct_options_frame.pack_forget()
            self.sim_options_frame.pack(fill=X, padx=12, pady=4, after=self.text_input.master)

    def _build_text_area(self, parent):
        # Use NONE wrap to preserve original format (spaces, indentation, line breaks)
        self.text_input = Text(parent, height=12, wrap="none", font=("Consolas", 11))
        # Add horizontal scrollbar for long lines
        h_scroll = ttk.Scrollbar(parent, orient="horizontal", command=self.text_input.xview)
        self.text_input.configure(xscrollcommand=h_scroll.set)
        self.text_input.pack(fill=BOTH, expand=True)
        h_scroll.pack(fill=X)

    def _build_direct_options(self, parent):
        """Build direct mode options"""
        # Paste mode selection
        paste_mode_frame = Frame(parent)
        paste_mode_frame.pack(fill=X, pady=(0, 4))

        ttk.Label(paste_mode_frame, text="Paste mode:").pack(side=LEFT)
        self.paste_by_line_var = IntVar(value=0)  # 0=all at once, 1=line by line

        all_at_once_radio = ttk.Radiobutton(
            paste_mode_frame,
            text="All at once",
            variable=self.paste_by_line_var,
            value=0
        )
        all_at_once_radio.pack(side=LEFT, padx=(8, 16))

        line_by_line_radio = ttk.Radiobutton(
            paste_mode_frame,
            text="Line by line",
            variable=self.paste_by_line_var,
            value=1
        )
        line_by_line_radio.pack(side=LEFT)

        # Auto repair and detection count
        repair_frame = Frame(parent)
        repair_frame.pack(fill=X, pady=(4, 0))

        self.enable_repair_var = IntVar(value=1)
        self.repair_chk = ttk.Checkbutton(
            repair_frame, text="Auto repair after completion",
            variable=self.enable_repair_var
        )
        self.repair_chk.pack(side=LEFT, padx=(0, 16))

        ttk.Label(repair_frame, text="Auto repair count:").pack(side=LEFT)
        self.max_detections_var = StringVar(value="5")
        md_entry = ttk.Entry(repair_frame, textvariable=self.max_detections_var, width=6, justify="center")
        md_entry.pack(side=LEFT, padx=(4, 0))
        ttk.Label(repair_frame, text="times").pack(side=LEFT, padx=(2, 0))

    def _build_sim_options(self, parent):
        """Build simulation mode options (SendInput, settings)"""
        # Windows SendInput option
        if SENDINIPUT_AVAILABLE:
            self.use_sendinput_var = IntVar(value=1)
            si_frame = Frame(parent)
            si_frame.pack(anchor=W, pady=(0, 4))
            ttk.Checkbutton(
                si_frame, text="SendInput mode (stronger bypass, Windows only)",
                variable=self.use_sendinput_var
            ).pack()

        # Auto repair and detection count (same layout as direct mode)
        repair_frame = Frame(parent)
        repair_frame.pack(fill=X, pady=(4, 0))

        self.enable_repair_sim_var = IntVar(value=1)
        repair_chk = ttk.Checkbutton(
            repair_frame, text="Auto repair after completion",
            variable=self.enable_repair_sim_var
        )
        repair_chk.pack(side=LEFT, padx=(0, 16))

        ttk.Label(repair_frame, text="Auto repair count:").pack(side=LEFT)
        self.max_detections_sim_var = StringVar(value="5")
        md_entry = ttk.Entry(repair_frame, textvariable=self.max_detections_sim_var, width=6, justify="center")
        md_entry.pack(side=LEFT, padx=(4, 0))
        ttk.Label(repair_frame, text="times").pack(side=LEFT, padx=(2, 0))

    def _build_buttons(self, parent):
        self.start_btn = ttk.Button(parent, text="Start (F6)", command=self._on_start, width=12)
        self.start_btn.pack(side=LEFT, padx=(0, 8))

        self.stop_btn = ttk.Button(parent, text="Stop (F7)", command=self._on_stop, width=12, state=DISABLED)
        self.stop_btn.pack(side=LEFT, padx=(0, 8))

        self.correct_btn = ttk.Button(parent, text="Auto Repair (F8)", command=self._on_correct, width=16)
        self.correct_btn.pack(side=LEFT)

    # ──────────── Hotkey Listener ────────────

    def _start_hotkey_listener(self):
        def on_press(key):
            if key == self.HOTKEY_START:
                self.root.after(0, self._on_start)
            elif key == self.HOTKEY_STOP:
                self.root.after(0, self._on_stop)
            elif key == self.HOTKEY_CORRECT:
                self.root.after(0, self._on_correct)

        self.hotkey_listener = KBListener(on_press=on_press)
        self.hotkey_listener.daemon = True
        self.hotkey_listener.start()

    # ──────────── Control Logic ────────────

    def _on_start(self):
        if self.engine.running:
            return

        # Clear last stop flag to ensure new round can start normally
        self.engine._stop_flag.clear()

        delay_ms = FAST_INPUT_DELAY_MS
        direct_mode = bool(self.direct_mode_var.get())

        # Get parameters based on current mode
        if direct_mode:
            # Direct mode: only need detection count for repair
            try:
                max_detections = max(1, int(self.max_detections_var.get()))
            except ValueError:
                messagebox.showwarning("Parameter Error", "Detection count must be a positive integer")
                return
            enable_repair = bool(self.enable_repair_var.get())
            paste_by_line = bool(self.paste_by_line_var.get())
            loops = 1
            start_delay = 5  # Default start delay for direct mode
            use_si = False
        else:
            # Simulation mode: use fixed defaults
            try:
                max_detections = max(1, int(self.max_detections_sim_var.get()))
            except ValueError:
                messagebox.showwarning("Parameter Error", "Detection count must be a positive integer")
                return
            use_si = SENDINIPUT_AVAILABLE and hasattr(self, "use_sendinput_var") and self.use_sendinput_var.get()
            enable_repair = bool(self.enable_repair_sim_var.get())
            loops = 1
            start_delay = 5

        # Text input mode
        # tkinter Text control always appends a \n at the end, only remove this one
        text = self.text_input.get("1.0", "end-1c")
        if not text:
            messagebox.showwarning("Empty Content", "Please enter text to simulate")
            return

        def get_clipboard_text():
            try:
                return self.root.clipboard_get()
            except Exception:
                return ""

        self._set_running_state(True)
        self._countdown_then_run(
            start_delay,
            lambda: self.engine.type_text(
                text, delay_ms, loops,
                use_sendinput=use_si,
                enable_repair=enable_repair,
                max_detections=max_detections,
                get_clipboard_func=get_clipboard_text,
                on_progress=lambda msg: self.root.after(0, self._update_status, msg),
                on_done=lambda status_msg=None: self.root.after(0, self._on_done, status_msg),
                direct_mode=direct_mode,
                paste_by_line=paste_by_line if direct_mode else False,
            )
        )

    def _on_correct(self):
        if self.engine.running:
            return

        # Clear last stop flag to ensure new round can start normally
        self.engine._stop_flag.clear()

        delay_ms = FAST_INPUT_DELAY_MS
        direct_mode = bool(self.direct_mode_var.get())

        # Get parameters based on current mode
        if direct_mode:
            try:
                max_detections = max(1, int(self.max_detections_var.get()))
            except ValueError:
                messagebox.showwarning("Parameter Error", "Detection count must be a positive integer")
                return
            loops = 1
            start_delay = 5
            use_si = False
        else:
            try:
                max_detections = max(1, int(self.max_detections_sim_var.get()))
            except ValueError:
                messagebox.showwarning("Parameter Error", "Detection count must be a positive integer")
                return
            use_si = SENDINIPUT_AVAILABLE and hasattr(self, "use_sendinput_var") and self.use_sendinput_var.get()
            loops = 1
            start_delay = 5

        # Text input mode
        text = self.text_input.get("1.0", "end-1c")
        if not text:
            messagebox.showwarning("Empty Content", "Please enter text to simulate")
            return

        def get_clipboard_text():
            try:
                return self.root.clipboard_get()
            except Exception:
                return ""

        self._set_running_state(True)
        self._countdown_then_run(
            start_delay,
            lambda: self.engine.type_text(
                text, delay_ms, loops,
                use_sendinput=use_si,
                enable_repair=True,
                max_detections=max_detections,
                get_clipboard_func=get_clipboard_text,
                only_repair=True,
                on_progress=lambda msg: self.root.after(0, self._update_status, msg),
                on_done=lambda status_msg=None: self.root.after(0, self._on_done, status_msg),
            )
        )

    def _countdown_then_run(self, delay_seconds, run_func):
        """Start delay countdown, then execute"""
        if delay_seconds <= 0:
            run_func()
            return

        def countdown(remaining):
            if self.engine._stop_flag.is_set():
                self._on_done()
                return
            if remaining <= 0:
                run_func()
                return
            self._update_status(f"Starting in: {remaining:.1f}s... (F7 to cancel)")
            self.root.after(100, countdown, remaining - 0.1)

        countdown(delay_seconds)

    def _on_stop(self):
        self.engine.stop()
        self._update_status("Stopped")
        self._set_running_state(False)

    def _on_done(self, status_msg=None):
        if status_msg:
            self._update_status(f"{status_msg}  |  F6 Start · F7 Stop · F8 Auto Repair")
            if status_msg == "Success (text matches)":
                messagebox.showinfo("Success", "Success: Input text matches perfectly!")
            elif status_msg == "Failed (text does not match)":
                messagebox.showerror("Failed", "Failed: Input text does not match!")
        else:
            self._update_status("Done  |  F6 Start · F7 Stop · F8 Auto Repair")
        self._set_running_state(False)

    def _set_running_state(self, is_running):
        self.start_btn.config(state=DISABLED if is_running else NORMAL)
        self.correct_btn.config(state=DISABLED if is_running else NORMAL)
        self.stop_btn.config(state=NORMAL if is_running else DISABLED)

    def _update_status(self, msg):
        self.status_var.set(msg)

    # ──────────── Launch ────────────

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self):
        self.engine.stop()
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        self.root.destroy()


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────
if __name__ == "__main__":
    app = KeyboardSimulatorApp()
    app.run()
