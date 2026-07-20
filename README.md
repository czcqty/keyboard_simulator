# Keyboard Simulator

A Python tool for simulating keyboard input. It is useful for entering text into applications or web pages where regular paste/copy shortcuts are unavailable, restricted, or unreliable.

## Features

- Cross-platform GUI built with `tkinter`
- **Two input modes:**
  - **Direct Mode (default):** Uses clipboard paste to bypass keyboard restrictions on websites/software
  - **Simulation Mode:** Character-by-character keyboard simulation for better compatibility
- Keyboard simulation powered by `pynput`
- Preserves spaces, tabs, and line breaks while typing
- Global hotkeys:
  - `F6`: start 
  - `F7`: stop 
  - `F8`: auto repair
- Windows-only `SendInput` mode for stronger Unicode input compatibility
- Automatic text verification and repair after input
- Two paste modes for Direct Mode:
  - **All at once:** Paste entire text at once (faster, preserves format)
  - **Line by line:** Paste line by line with Enter key (for apps that don't support multi-line paste)
- One-click setup script (`init.py`) for virtualenv and dependency installation
- PyInstaller build script (`build.py`) for generating a standalone executable

## Requirements

- Python 3.10 or newer recommended
- `pynput` for keyboard simulation
- `pyperclip` for clipboard operations (Direct Mode)
- `pyinstaller` for building standalone executable

## Installation & Setup

We provide an independent, one-click initialization script `init.py` that automatically detects or creates a local `.venv` virtual environment and installs all required dependencies.

To initialize the project:

```bash
python init.py
```

This ensures a 100% reproducible and clean environment sandbox.

## Usage

### Run the GUI

Run the simulator directly:

```bash
python keyboard_simulator.py
```

*Note: If `.venv` exists, the script will automatically switch to the virtual environment and launch.*

Then:
1. Select input mode (Direct Mode or Simulation Mode)
2. Paste or type the text you want to simulate into the text box
3. Configure options for the selected mode
4. Move focus to the target input field
5. Press `F6` or click the Start button
6. Press `F7` to stop early

### Input Modes

#### Direct Mode (Default)
- Copies text to clipboard and sends `Ctrl+V` (or `Cmd+V` on macOS) to paste
- Bypasses most website/software keyboard input restrictions
- Works with applications that block simulated keyboard events
- Supports automatic text verification and repair
- Two paste modes:
  - **All at once:** Paste entire text at once (faster, preserves format)
  - **Line by line:** Paste line by line with Enter key (for apps that don't support multi-line paste)

#### Simulation Mode
- Types each character individually using keyboard simulation
- Better compatibility with applications that don't accept paste events
- Uses `pynput` for cross-platform keyboard control
- Optional Windows `SendInput` mode for enhanced Unicode support
- Supports automatic text verification and repair


Use this project only in environments where automated input is allowed.

## Script Overview

### `init.py`

One-click development environment initializer.

- Checks for local `.venv` and creates it if missing.
- Installs or updates dependencies declared in `requirements.txt` using the virtual environment's pip.
- Highly compatible with various terminal encodings (GBK, UTF-8, etc.).

### `keyboard_simulator.py`

Main application entry point.

- Automatic virtual environment relaunch logic when a local `.venv` exists.
- Windows DPI awareness setup for sharper GUI rendering.
- **Two input modes:** Direct Mode (clipboard paste) and Simulation Mode (keyboard simulation).
- Optional Windows `SendInput` support for Unicode character emission.
- `KeyboardEngine`, the core typing engine with direct paste and simulation capabilities.
- `KeyboardSimulatorApp`, the `tkinter` GUI wrapper with mode selection interface.
- Global hotkey listener for `F6` start, `F7` stop, and `F8` auto-correct.
- Automatic text verification and repair functionality.
- Friendly prompts directing developers to run `init.py` if dependencies are missing.

### `test_keyboard_simulator.py`

Test program for verifying the main simulator's functionality.

- Injects a fake `pynput` module, captures typed text events, and verifies behavior without sending real keyboard input.
- Fully independent of `.venv` and requires no third-party libraries (runs anywhere instantly using Python standard library).
- **Three test modes:**
  - **Direct Mode Test:** Verifies clipboard paste functionality
  - **Simulation Mode Test:** Verifies character-by-character input
  - **Auto Repair Test:** Verifies text repair functionality
- Uses test data files from `test_data/` directory

Run the tests:

```bash
# Run all tests
python test_keyboard_simulator.py run --all

# Run specific test
python test_keyboard_simulator.py run --direct
python test_keyboard_simulator.py run --simulation
python test_keyboard_simulator.py run --repair
```

### `build.py`

Builds `keyboard_simulator.py` into a standalone binary with PyInstaller.

- Automatically detects and switches to `.venv` on launch to utilize isolated dependencies.
- Runs PyInstaller with `--onefile` and `--windowed`.
- Moves the generated binary from `dist/` to the project root and cleans up build folders (`build/`, `dist/`, `.spec`).
- Alerts and directs developers to run `init.py` first if `.venv` is missing.

Run:

```bash
python build.py
```

### `automation.py`

Convenience pipeline automation script.

- Runs the full test suite through `test_keyboard_simulator.py` in a pure and lightweight global environment.
- Invokes `build.py` automatically if tests pass (where `build.py` will safely redirect to `.venv` to complete packaging).

Run:

```bash
python automation.py
```

## Repository Files

```text
init.py                     One-click environment initializer
keyboard_simulator.py       Main GUI application and typing engine
test_keyboard_simulator.py  Test program for verifying simulator functionality
test_data/                  Test data directory
├── direct_input.txt        Test data for direct mode test
├── simulation_input.txt    Test data for simulation mode test
├── repair_expected.txt     Expected text for auto repair test
└── repair_input.txt        Error text for auto repair test
build.py                    PyInstaller build script
automation.py               Pipeline automation script
requirements.txt            Python dependency list
LICENSE                     MIT License
.gitignore                  Git ignore rules for local/build artifacts
```

## License

This project is licensed under the MIT License. See `LICENSE` for details.
