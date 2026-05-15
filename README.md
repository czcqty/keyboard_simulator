# keyboard_simulator

A Python tool for simulating keyboard input. It is useful for entering text into applications or web pages where regular paste/copy shortcuts are unavailable, restricted, or unreliable.

## Features

- Cross-platform GUI built with `tkinter`
- Keyboard simulation powered by `pynput`
- Preserves spaces, tabs, and line breaks while typing
- Configurable key interval, loop count, and start delay
- Global hotkeys:
  - `F6`: start typing
  - `F7`: stop typing
- Windows-only `SendInput` mode for stronger Unicode input compatibility
- Contract-style test console that verifies typing behavior without sending real keyboard events
- PyInstaller build script for generating a standalone executable

## Requirements

- Python 3.9 or newer recommended
- `pynput`
- `PyInstaller` only if you want to build a standalone binary

Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run the GUI:

```bash
python keyboard_simulator.py
```

Then:

1. Paste or type the text you want to simulate into the text area.
2. Set the key interval, loop count, and start delay.
3. Move focus to the target input field.
4. Press `F6` or click the start button.
5. Press `F7` to stop early.

Use this project only in environments where automated input is allowed.

## Script Overview

### `keyboard_simulator.py`

Main application entry point.

It contains:

- Automatic virtual environment relaunch logic when a local `.venv` exists
- Windows DPI awareness setup for sharper GUI rendering
- Dependency check for `pynput`
- Optional Windows `SendInput` support for Unicode character emission
- `KeyboardEngine`, the core typing engine
- `KeyboardSimulatorApp`, the `tkinter` GUI wrapper
- Global hotkey listener for `F6` start and `F7` stop

Core behavior:

- Converts text into output units while normalizing `CRLF`, `CR`, and `LF` line endings
- Emits spaces, tabs, and newlines as explicit key presses
- Emits other characters through `pynput.Controller.type`
- Runs typing in a background thread so the GUI remains responsive
- Supports progress and completion callbacks

### `test_keyboard_simulator.py`

Interactive contract tester for the main simulator.

This script injects a fake `pynput` module, captures the text that would be typed, and verifies behavior without sending real keyboard input.

It can test:

- Exact input/output preservation
- Loop repeat behavior
- Progress and completion callbacks
- Stop behavior
- Windows `SendInput` routing behavior

Start the tester:

```bash
python test_keyboard_simulator.py
```

Common commands inside the tester:

```text
help --list
status --list
case --all
run --all
exit
```

### `build.py`

Builds `keyboard_simulator.py` into a standalone binary with PyInstaller.

Behavior:

- Uses the current Python interpreter
- Runs PyInstaller with `--onefile` and `--windowed`
- Moves the generated binary from `dist/` to the project root
- Removes temporary `build/`, `dist/`, and `.spec` files after a successful build

Run:

```bash
python build.py
```

On Windows, the output file is:

```text
keyboard_simulator.exe
```

The generated executable is intentionally ignored by Git. Release binaries should be uploaded through GitHub Releases instead of being committed to the source repository.

### `automation.py`

Convenience automation script for preparing the environment, running tests, and building the application.

Behavior:

- Creates a local `.venv` if needed
- Relaunches itself inside the virtual environment
- Installs required packages:
  - `pynput`
  - `pyinstaller`
- Runs the full test suite through `test_keyboard_simulator.py`
- Starts `build.py` automatically only if tests pass
- If tests fail in an interactive terminal, asks whether to continue building anyway

Run:

```bash
python automation.py
```

## Repository Files

```text
keyboard_simulator.py       Main GUI application and typing engine
test_keyboard_simulator.py  Interactive behavior tester
build.py                    PyInstaller build script
automation.py               Test-and-build automation script
requirements.txt            Python dependency list
LICENSE                     MIT License
.gitignore                  Git ignore rules for local/build artifacts
```

## License

This project is licensed under the MIT License. See `LICENSE` for details.
