# Dojo Installation Guide

This guide details alternative ways to install, run, and compile Dojo locally.

---

## Isolated Installation via `pipx`

If you have `pipx` installed and want to install Dojo globally in an isolated Python environment:

```bash
pipx install git+https://github.com/Stan15/dojo.git
```

To update an existing installation:

```bash
pipx upgrade dojo
```

---

## Manual Source Installation (Developer / Editable Mode)

If you are developing Dojo or want to run it directly from source:

1. Clone the repository:
   ```bash
   git clone https://github.com/Stan15/dojo.git
   cd dojo
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install in editable mode along with development dependencies:
   ```bash
   pip install -e .
   ```

You can now run `dojo` directly in your shell while editing the source files.

---

## Compiling a Standalone Binary Locally

Dojo uses `PyInstaller` to build standalone, single-file executables that do not require Python to run.

To compile the binary yourself:

1. Activate your virtual environment and install PyInstaller:
   ```bash
   pip install pyinstaller
   ```

2. Run the compilation script:
   ```bash
   pyinstaller --onefile --name dojo --paths src --add-data "skills/dojo:skills/dojo" run_dojo.py
   ```

The compiled standalone executable will be saved in `dist/dojo`. You can copy this executable to `/usr/local/bin/` or `~/.local/bin/` to use it globally.
