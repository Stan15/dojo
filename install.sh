#!/bin/bash
# Dojo Zero-Dependency Installer
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Stan15/dojo/main/install.sh | sh

set -euo pipefail

# Style helpers
info() { echo -e "\033[1;32m=>\033[0m $*"; }
warn() { echo -e "\033[1;33m=> WARNING:\033[0m $*"; }
error() { echo -e "\033[1;31m=> ERROR:\033[0m $*"; exit 1; }

# Dojo Doctor Safety Gate Helper
check_dojo_doctor() {
    local bin_path="$1"
    local install_type="$2"
    
    info "Running Dojo Doctor sanity check..."
    if ! "$bin_path" doctor; then
        warn "Dojo Doctor check failed. The target repository folder contains unexpected or non-compliant files."
        warn "Aborting installation to prevent conflicts."
        
        # Clean up based on install type
        if [ "$install_type" = "pipx" ]; then
            info "Rolling back: Uninstalling Dojo via pipx..."
            pipx uninstall dojo >/dev/null 2>&1 || true
        elif [ "$install_type" = "venv" ]; then
            info "Rolling back: Removing virtual environment and symlinks..."
            rm -rf "$INSTALL_DIR"
            rm -f "$BIN_DIR/dojo"
        elif [ "$install_type" = "binary" ]; then
            info "Rolling back: Removing downloaded binary..."
            rm -f "$INSTALL_DIR/dojo"
        fi
        
        error "Installation aborted because the Dojo repository directory contains unexpected or non-compliant files."
    fi
}

# Determine package source: default to github remote URL
PKG_SRC="git+https://github.com/Stan15/dojo.git"

# Resolve script directory to check if it's run from inside a cloned repository
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
if [ -f "$SCRIPT_DIR/src/dojo/cli.py" ]; then
    info "Detected local repository source. Installing from: $SCRIPT_DIR"
    PKG_SRC="$SCRIPT_DIR"
fi

info "Starting Dojo installation..."

# Step 1: Try pipx (Gold Standard for Python CLIs)
if command -v pipx >/dev/null 2>&1; then
    info "Found pipx. Installing/Updating Dojo in an isolated environment..."
    if pipx install "$PKG_SRC" --force 2>&1; then
        # Find the installed binary to run doctor
        DOJO_BIN=""
        if command -v dojo >/dev/null 2>&1; then
            DOJO_BIN=$(command -v dojo)
        fi
        if [ -z "$DOJO_BIN" ] || [ ! -x "$DOJO_BIN" ]; then
            for loc in "$HOME/.local/bin/dojo" "$HOME/.pipx/bin/dojo" "/usr/local/bin/dojo"; do
                if [ -x "$loc" ]; then
                    DOJO_BIN="$loc"
                    break
                fi
            done
        fi
        if [ -z "$DOJO_BIN" ]; then
            DOJO_BIN="dojo"
        fi
        
        check_dojo_doctor "$DOJO_BIN" "pipx"
        
        info "Dojo successfully installed!"
        info "You can now run: dojo --help"
        exit 0
    else
        warn "pipx installation failed. Retrying with alternative methods..."
    fi
fi

# Step 2: Try python3 virtual environment (Fallback for machines with Python but no pipx)
PYTHON_BIN=""
for cmd in python3 python3.13 python3.12 python3.11; do
    if command -v "$cmd" >/dev/null 2>&1; then
        if "$cmd" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >/dev/null 2>&1; then
            PYTHON_BIN="$cmd"
            break
        fi
    fi
done

if [ -n "$PYTHON_BIN" ]; then
    info "Found compatible Python executable: $PYTHON_BIN"
    info "pipx not found. Installing into an isolated home directory virtual environment..."
    
    INSTALL_DIR="$HOME/.dojo"
    BIN_DIR="$HOME/.local/bin"
    
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$BIN_DIR"
    
    # Clean old virtualenv if exists
    if [ -d "$INSTALL_DIR/venv" ]; then
        rm -rf "$INSTALL_DIR/venv"
    fi
    
    "$PYTHON_BIN" -m venv "$INSTALL_DIR/venv"
    info "Upgrading pip in virtual environment..."
    "$INSTALL_DIR/venv/bin/python" -m pip install --quiet --upgrade pip
    
    info "Installing package and dependencies..."
    "$INSTALL_DIR/venv/bin/pip" install --quiet "$PKG_SRC"
    
    # Create symlink
    ln -sf "$INSTALL_DIR/venv/bin/dojo" "$BIN_DIR/dojo"
    
    check_dojo_doctor "$INSTALL_DIR/venv/bin/dojo" "venv"
    
    info "Dojo successfully installed to $BIN_DIR/dojo!"
    
    # Check if BIN_DIR is in PATH
    if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
        warn "$BIN_DIR is not in your PATH. Add the following line to your shell configuration (.zshrc or .bashrc):"
        echo -e "  \033[1;36mexport PATH=\"\$HOME/.local/bin:\$PATH\"\033[0m"
    fi
    exit 0
else
    if command -v python3 >/dev/null 2>&1; then
        DETECTED_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
        warn "Found python3 ($DETECTED_VER) but it is older than the required 3.11+."
    fi
fi

# Step 3: Standalone Precompiled Binary Fallback (For environments without Python installed)
OS_TYPE=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH_TYPE=$(uname -m)

info "Python not found or incompatible. Attempting to install precompiled binary for $OS_TYPE-$ARCH_TYPE..."

INSTALL_DIR="/usr/local/bin"
if [ ! -w "$INSTALL_DIR" ]; then
    INSTALL_DIR="$HOME/.local/bin"
    mkdir -p "$INSTALL_DIR"
fi

# Map architecture names
case "$ARCH_TYPE" in
    x86_64) ARCH="amd64" ;;
    arm64|aarch64) ARCH="arm64" ;;
    *) error "Unsupported CPU architecture: $ARCH_TYPE" ;;
esac

BINARY_URL="https://github.com/Stan15/dojo/releases/latest/download/dojo-${OS_TYPE}-${ARCH}"

info "Downloading standalone binary from: $BINARY_URL"
DOWNLOAD_SUCCESS=0

if command -v curl >/dev/null 2>&1; then
    if curl -fsSL "$BINARY_URL" -o "$INSTALL_DIR/dojo" 2>/dev/null; then
        DOWNLOAD_SUCCESS=1
    fi
elif command -v wget >/dev/null 2>&1; then
    if wget -qO "$INSTALL_DIR/dojo" "$BINARY_URL" 2>/dev/null; then
        DOWNLOAD_SUCCESS=1
    fi
fi

if [ "$DOWNLOAD_SUCCESS" -eq 1 ]; then
    chmod +x "$INSTALL_DIR/dojo"
    
    check_dojo_doctor "$INSTALL_DIR/dojo" "binary"
    
    info "Dojo standalone binary successfully installed to $INSTALL_DIR/dojo!"
    exit 0
else
    warn "Could not fetch precompiled binary from GitHub Releases (repository may be private or release not yet published)."
    warn "Please install Python 3.11+ to run the automated source installer, or build the binary locally using PyInstaller:"
    echo -e "  \033[1;36mpip install pyinstaller && pyinstaller --onefile --name dojo --paths src --add-data \"skills/dojo:skills/dojo\" run_dojo.py\033[0m"
    exit 1
fi
