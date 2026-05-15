#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨平台键盘输入模拟器
支持 Windows / macOS / Linux
使用 pynput 进行键盘模拟，tkinter 构建 GUI
"""
import os
import sys
import subprocess
import platform

# 自动切换到虚拟环境
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
        print("[环境] 自动转入虚拟环境...")
        sys.exit(subprocess.run([venv_python, __file__] + sys.argv[1:], cwd=script_dir).returncode)

_auto_switch_venv()

import time
import threading


# ──────────────────────────────────────────────
# Windows 高 DPI 适配 (在导入 tkinter 之前执行)
# 支持 1080p / 2K / 4K 等高分辨率屏幕，避免界面模糊
# ──────────────────────────────────────────────
if platform.system() == "Windows":
    try:
        import ctypes
        # 2 = PROCESS_PER_MONITOR_DPI_AWARE_V2，最佳 DPI 支持
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
# 依赖检查
# ──────────────────────────────────────────────
try:
    from pynput.keyboard import Controller as KBController, Key, Listener as KBListener
except ImportError:
    print("缺少依赖: pynput")
    print("请运行: pip install pynput")
    sys.exit(1)


# ──────────────────────────────────────────────
# Windows SendInput 备用模式 (仅 Windows)
# ──────────────────────────────────────────────
SENDINIPUT_AVAILABLE = False
if platform.system() == "Windows":
    try:
        import ctypes
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
# 键盘模拟引擎
# ──────────────────────────────────────────────
class KeyboardEngine:
    """键盘模拟核心引擎"""

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
        """按输入顺序产出字符单元，兼容 \r\n / \r / \n 换行格式。"""
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            # 将 CRLF 视作单个换行，避免重复发送两次回车
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
        """发送单个字符单元，尽量保持输入格式。"""
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

    def type_text(self, text, delay_ms=50, loops=1, use_sendinput=False, on_progress=None, on_done=None):
        """在新线程中模拟输入文本"""
        self._stop_flag.clear()
        self._running = True

        units = list(self._iter_output_units(text))
        total_units = len(units)

        if total_units == 0:
            self._running = False
            if on_done:
                on_done()
            return

        def worker():
            try:
                for loop_i in range(loops):
                    if self._should_stop():
                        break
                    for unit_i, unit in enumerate(units):
                        if self._should_stop():
                            break
                        self._emit_unit(unit, use_sendinput=use_sendinput)
                        if on_progress:
                            pct = ((loop_i * total_units + unit_i + 1) / (loops * total_units)) * 100
                            on_progress(f"执行中... 第 {loop_i+1}/{loops} 轮，进度 {pct:.0f}%")
                        time.sleep(delay_ms / 1000.0)
            except Exception as e:
                if on_progress:
                    on_progress(f"错误: {e}")
            finally:
                self._running = False
                if on_done:
                    on_done()

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()




# ──────────────────────────────────────────────
# GUI 应用
# ──────────────────────────────────────────────
class KeyboardSimulatorApp:
    """键盘模拟器 GUI"""

    HOTKEY_START = Key.f6
    HOTKEY_STOP = Key.f7

    def __init__(self):
        self.engine = KeyboardEngine()
        self.hotkey_listener = None

        # ── 主窗口 ──
        self.root = Tk()
        self.root.title("键盘输入模拟器")
        self.root.geometry("520x480")
        self.root.resizable(True, True)
        self.root.minsize(420, 380)

        # 样式
        style = ttk.Style()
        style.configure("Title.TLabel", font=("", 14, "bold"))
        style.configure("Status.TLabel", font=("", 10))

        self._build_ui()
        self._start_hotkey_listener()

    # ──────────── UI 构建 ────────────

    def _build_ui(self):
        root = self.root

        # 标题
        title_frame = Frame(root, padx=12, pady=8)
        title_frame.pack(fill=X)
        ttk.Label(title_frame, text="⌨ 键盘输入模拟器", style="Title.TLabel").pack(side=LEFT)
        sys_label = "Windows" if platform.system() == "Windows" else platform.system()
        ttk.Label(title_frame, text=f"平台: {sys_label}").pack(side=RIGHT)

        # 文本输入区域
        text_frame = ttk.LabelFrame(root, text="📝 输入要模拟的文本内容", padding=8)
        text_frame.pack(fill=BOTH, expand=True, padx=12, pady=(0, 4))
        self._build_text_area(text_frame)

        # 通用设置区域
        settings_frame = ttk.LabelFrame(root, text="设置", padding=8)
        settings_frame.pack(fill=X, padx=12, pady=4)
        self._build_settings(settings_frame)

        # 按钮区域
        btn_frame = Frame(root, padx=12, pady=6)
        btn_frame.pack(fill=X)
        self._build_buttons(btn_frame)

        # 状态栏
        status_frame = Frame(root, padx=12, pady=6)
        status_frame.pack(fill=X, side="bottom")
        self.status_var = StringVar(value="就绪  |  F6 启动 · F7 停止")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, style="Status.TLabel")
        self.status_label.pack(side=LEFT)

    def _build_text_area(self, parent):
        # 使用 NONE wrap 以保留原始格式（空格、缩进、换行）
        self.text_input = Text(parent, height=12, wrap="none", font=("Consolas", 11))
        # 添加水平滚动条以支持长行
        h_scroll = ttk.Scrollbar(parent, orient="horizontal", command=self.text_input.xview)
        self.text_input.configure(xscrollcommand=h_scroll.set)
        self.text_input.pack(fill=BOTH, expand=True)
        h_scroll.pack(fill=X)

        # Windows SendInput 选项
        if SENDINIPUT_AVAILABLE:
            self.use_sendinput_var = IntVar(value=1)
            si_frame = Frame(parent)
            si_frame.pack(anchor=W, pady=(6, 0))
            ttk.Checkbutton(
                si_frame, text="使用 SendInput 模式（更强的绕过能力，仅 Windows）",
                variable=self.use_sendinput_var
            ).pack()

    def _build_settings(self, parent):
        row1 = Frame(parent)
        row1.pack(fill=X, pady=2)

        ttk.Label(row1, text="按键间隔:").pack(side=LEFT)
        self.delay_var = StringVar(value="50")
        delay_entry = ttk.Entry(row1, textvariable=self.delay_var, width=6, justify="center")
        delay_entry.pack(side=LEFT, padx=(4, 0))
        ttk.Label(row1, text="ms").pack(side=LEFT, padx=(2, 16))

        ttk.Label(row1, text="循环次数:").pack(side=LEFT)
        self.loops_var = StringVar(value="1")
        loops_entry = ttk.Entry(row1, textvariable=self.loops_var, width=6, justify="center")
        loops_entry.pack(side=LEFT, padx=(4, 0))
        ttk.Label(row1, text="次").pack(side=LEFT, padx=(2, 16))

        ttk.Label(row1, text="启动延迟:").pack(side=LEFT)
        self.start_delay_var = StringVar(value="3")
        sd_entry = ttk.Entry(row1, textvariable=self.start_delay_var, width=6, justify="center")
        sd_entry.pack(side=LEFT, padx=(4, 0))
        ttk.Label(row1, text="秒").pack(side=LEFT, padx=(2, 0))

    def _build_buttons(self, parent):
        self.start_btn = ttk.Button(parent, text="▶  开始 (F6)", command=self._on_start, width=16)
        self.start_btn.pack(side=LEFT, padx=(0, 8))

        self.stop_btn = ttk.Button(parent, text="⏹  停止 (F7)", command=self._on_stop, width=16, state=DISABLED)
        self.stop_btn.pack(side=LEFT)

    # ──────────── 热键监听 ────────────

    def _start_hotkey_listener(self):
        def on_press(key):
            if key == self.HOTKEY_START:
                self.root.after(0, self._on_start)
            elif key == self.HOTKEY_STOP:
                self.root.after(0, self._on_stop)

        self.hotkey_listener = KBListener(on_press=on_press)
        self.hotkey_listener.daemon = True
        self.hotkey_listener.start()

    # ──────────── 控制逻辑 ────────────

    def _on_start(self):
        if self.engine.running:
            return

        # 清除上次的停止标志，确保新一轮可以正常启动
        self.engine._stop_flag.clear()

        # 读取参数
        try:
            delay_ms = max(1, int(self.delay_var.get()))
        except ValueError:
            messagebox.showwarning("参数错误", "按键间隔必须是正整数")
            return
        try:
            loops = max(1, int(self.loops_var.get()))
        except ValueError:
            messagebox.showwarning("参数错误", "循环次数必须是正整数")
            return
        try:
            start_delay = max(0, float(self.start_delay_var.get()))
        except ValueError:
            messagebox.showwarning("参数错误", "启动延迟必须是数字")
            return

        # 文本输入模式
        # tkinter Text 控件在末尾总会自动附加一个 \n，只去掉这一个
        text = self.text_input.get("1.0", "end-1c")
        if not text:
            messagebox.showwarning("内容为空", "请输入要模拟的文本")
            return
        use_si = SENDINIPUT_AVAILABLE and hasattr(self, "use_sendinput_var") and self.use_sendinput_var.get()

        self._set_running_state(True)
        self._countdown_then_run(
            start_delay,
            lambda: self.engine.type_text(
                text, delay_ms, loops,
                use_sendinput=use_si,
                on_progress=lambda msg: self.root.after(0, self._update_status, msg),
                on_done=lambda: self.root.after(0, self._on_done),
            )
        )

    def _countdown_then_run(self, delay_seconds, run_func):
        """启动延迟倒计时，然后执行"""
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
            self._update_status(f"启动倒计时: {remaining:.1f} 秒... (F7 取消)")
            self.root.after(100, countdown, remaining - 0.1)

        countdown(delay_seconds)

    def _on_stop(self):
        self.engine.stop()
        self._update_status("已停止")
        self._set_running_state(False)

    def _on_done(self):
        self._update_status("完成  |  F6 启动 · F7 停止")
        self._set_running_state(False)

    def _set_running_state(self, is_running):
        self.start_btn.config(state=DISABLED if is_running else NORMAL)
        self.stop_btn.config(state=NORMAL if is_running else DISABLED)

    def _update_status(self, msg):
        self.status_var.set(msg)

    # ──────────── 启动 ────────────

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self):
        self.engine.stop()
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        self.root.destroy()


# ──────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────
if __name__ == "__main__":
    app = KeyboardSimulatorApp()
    app.run()
