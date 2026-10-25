#!/usr/bin/env bash
# Docker Janitor — Automated Installer
# https://github.com/raminmz66/docker-janitor
# MIT License

set -euo pipefail

GITHUB_RAW_URL="https://raw.githubusercontent.com/raminmz66/docker-janitor/main"

# Default directories
PREFIX="${PREFIX:-$HOME/.local}"
BIN_DIR="${BIN_DIR:-$PREFIX/bin}"
XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
APP_SHARE_DIR="$XDG_DATA_HOME/docker-janitor"
ICONS_DIR="$XDG_DATA_HOME/icons/hicolor/scalable/apps"
APPS_DIR="$XDG_DATA_HOME/applications"
AUTOSTART_DIR="$XDG_CONFIG_HOME/autostart"

DRY_RUN=false
ENABLE_AUTOSTART=true
INTERACTIVE=true

# Locate local repository root if running from a git clone
SCRIPT_SOURCE="${BASH_SOURCE[0]:-}"
REPO_ROOT=""
if [[ -n "$SCRIPT_SOURCE" && "$SCRIPT_SOURCE" != "-" ]]; then
    SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_SOURCE")" && pwd)"
    if [[ -f "$SCRIPT_DIR/docker_janitor.py" ]]; then
        REPO_ROOT="$SCRIPT_DIR"
    fi
fi

# Print usage instructions
print_help() {
    cat <<EOF
Docker Janitor — Automated Installer

Usage:
  ./install.sh [OPTIONS]

Options:
  --dry-run             Preview installation actions without making any changes
  --no-autostart        Do not register Docker Janitor for automatic login startup
  -y, --non-interactive Run non-interactively, accepting all defaults
  --prefix=<DIR>        Custom installation prefix (default: \$HOME/.local)
  -h, --help            Show this help message and exit

Description:
  Installs Docker Janitor into user space ($PREFIX), registers the application
  menu entry and desktop icon, checks for required system dependencies,
  and configures login autostart.
EOF
}

# Parse command line arguments
for arg in "$@"; do
    case "$arg" in
        --dry-run)
            DRY_RUN=true
            ;;
        --no-autostart)
            ENABLE_AUTOSTART=false
            ;;
        -y|--non-interactive|--yes)
            INTERACTIVE=false
            ;;
        --prefix=*)
            PREFIX="${arg#*=}"
            BIN_DIR="$PREFIX/bin"
            ;;
        -h|--help)
            print_help
            exit 0
            ;;
        *)
            echo "Error: Unknown argument: $arg" >&2
            echo "Run './install.sh --help' for usage." >&2
            exit 1
            ;;
    esac
done

echo "=== Docker Janitor Installer ==="
if [[ "$DRY_RUN" == true ]]; then
    echo "[DRY RUN MODE: No files will be modified or created]"
fi

# 1. Check Python installation
if ! command -v python3 &>/dev/null; then
    echo "Error: Python 3 is required but not installed." >&2
    exit 1
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)

if (( PY_MAJOR < 3 || (PY_MAJOR == 3 && PY_MINOR < 8) )); then
    echo "Error: Python 3.8 or higher is required (found $PY_VER)." >&2
    exit 1
fi
echo "✓ Python $PY_VER detected"

# 2. Check Docker CLI
if ! command -v docker &>/dev/null; then
    echo "Notice: 'docker' CLI not found on PATH. Docker Janitor requires Docker to run cleanup."
else
    echo "✓ Docker CLI detected"
fi

# 3. Check GObject / GTK / Ayatana AppIndicator dependencies
has_gobject_deps() {
    python3 -c "import gi; gi.require_version('Gtk', '3.0'); gi.require_version('AyatanaAppIndicator3', '0.1'); from gi.repository import Gtk, AyatanaAppIndicator3" &>/dev/null
}

if has_gobject_deps; then
    echo "✓ System GUI dependencies detected (PyGObject, GTK 3, Ayatana AppIndicator)"
else
    echo "! Missing required system GUI libraries (PyGObject, GTK 3, Ayatana AppIndicator)."
    
    # Identify package manager
    PKG_MGR=""
    INSTALL_CMD=""
    if command -v apt-get &>/dev/null; then
        PKG_MGR="apt"
        INSTALL_CMD="sudo apt-get update && sudo apt-get install -y python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1"
    elif command -v dnf &>/dev/null; then
        PKG_MGR="dnf"
        INSTALL_CMD="sudo dnf install -y python3-gobject gtk3 libayatana-appindicator-gtk3"
    elif command -v pacman &>/dev/null; then
        PKG_MGR="pacman"
        INSTALL_CMD="sudo pacman -S --needed --noconfirm python python-gobject gtk3 libayatana-appindicator"
    fi

    if [[ -n "$INSTALL_CMD" ]]; then
        if [[ "$DRY_RUN" == true ]]; then
            echo "[dry-run] Would execute: $INSTALL_CMD"
        else
            DO_INSTALL=false
            if [[ "$INTERACTIVE" == true ]]; then
                read -r -p "Would you like to install them now with sudo using $PKG_MGR? [Y/n] " response || response="n"
                if [[ -z "$response" || "$response" =~ ^[Yy]$ ]]; then
                    DO_INSTALL=true
                fi
            else
                DO_INSTALL=true
            fi

            if [[ "$DO_INSTALL" == true ]]; then
                echo "Installing dependencies..."
                eval "$INSTALL_CMD"
            else
                echo "Please install dependencies manually using:"
                echo "  $INSTALL_CMD"
            fi
        fi
    else
        echo "Please install PyGObject, GTK 3, and Ayatana AppIndicator using your system's package manager."
    fi
fi

# 4. Prepare target directories
echo "Installing files to prefix: $PREFIX"
if [[ "$DRY_RUN" == true ]]; then
    echo "[dry-run] Would create directory: $BIN_DIR"
    echo "[dry-run] Would create directory: $APP_SHARE_DIR/icons"
    echo "[dry-run] Would create directory: $ICONS_DIR"
    echo "[dry-run] Would create directory: $APPS_DIR"
    if [[ "$ENABLE_AUTOSTART" == true ]]; then
        echo "[dry-run] Would create directory: $AUTOSTART_DIR"
    fi
else
    mkdir -p "$BIN_DIR"
    mkdir -p "$APP_SHARE_DIR/icons"
    mkdir -p "$ICONS_DIR"
    mkdir -p "$APPS_DIR"
    if [[ "$ENABLE_AUTOSTART" == true ]]; then
        mkdir -p "$AUTOSTART_DIR"
    fi
fi

# 5. Install application files
if [[ -n "$REPO_ROOT" ]]; then
    if [[ "$DRY_RUN" == true ]]; then
        echo "[dry-run] Would copy $REPO_ROOT/docker_janitor.py -> $APP_SHARE_DIR/docker_janitor.py"
        echo "[dry-run] Would copy $REPO_ROOT/icons/docker-janitor.svg -> $APP_SHARE_DIR/icons/docker-janitor.svg"
        echo "[dry-run] Would copy $REPO_ROOT/icons/docker-janitor.svg -> $ICONS_DIR/docker-janitor.svg"
    else
        cp -f "$REPO_ROOT/docker_janitor.py" "$APP_SHARE_DIR/docker_janitor.py"
        cp -f "$REPO_ROOT/icons/docker-janitor.svg" "$APP_SHARE_DIR/icons/docker-janitor.svg"
        cp -f "$REPO_ROOT/icons/docker-janitor.svg" "$ICONS_DIR/docker-janitor.svg"
        chmod +x "$APP_SHARE_DIR/docker_janitor.py"
    fi
else
    # Piped / standalone curl installation
    if [[ "$DRY_RUN" == true ]]; then
        echo "[dry-run] Would download docker_janitor.py from $GITHUB_RAW_URL/docker_janitor.py"
        echo "[dry-run] Would download docker-janitor.svg from $GITHUB_RAW_URL/icons/docker-janitor.svg"
    else
        echo "Downloading Docker Janitor files from GitHub..."
        curl -fsSL "$GITHUB_RAW_URL/docker_janitor.py" -o "$APP_SHARE_DIR/docker_janitor.py"
        curl -fsSL "$GITHUB_RAW_URL/icons/docker-janitor.svg" -o "$APP_SHARE_DIR/icons/docker-janitor.svg"
        cp -f "$APP_SHARE_DIR/icons/docker-janitor.svg" "$ICONS_DIR/docker-janitor.svg"
        chmod +x "$APP_SHARE_DIR/docker_janitor.py"
    fi
fi

# 6. Create binary launcher wrapper in $BIN_DIR/docker-janitor
LAUNCHER_PATH="$BIN_DIR/docker-janitor"
if [[ "$DRY_RUN" == true ]]; then
    echo "[dry-run] Would write executable launcher to $LAUNCHER_PATH"
else
    cat <<EOF > "$LAUNCHER_PATH"
#!/usr/bin/env bash
exec python3 "$APP_SHARE_DIR/docker_janitor.py" "\$@"
EOF
    chmod +x "$LAUNCHER_PATH"
    echo "✓ Installed launcher: $LAUNCHER_PATH"
fi

# 7. Create desktop application launcher
DESKTOP_PATH="$APPS_DIR/docker-janitor.desktop"
if [[ "$DRY_RUN" == true ]]; then
    echo "[dry-run] Would write desktop launcher to $DESKTOP_PATH"
else
    cat <<EOF > "$DESKTOP_PATH"
[Desktop Entry]
Type=Application
Name=Docker Janitor
GenericName=Docker Storage Cleaner
Comment=Preview Docker cleanup and prune safely
Exec=$LAUNCHER_PATH
Icon=docker-janitor
Terminal=false
Categories=Utility;System;
StartupNotify=false
X-GNOME-Autostart-enabled=true
EOF
    chmod 644 "$DESKTOP_PATH"
    echo "✓ Installed desktop entry: $DESKTOP_PATH"
fi

# 8. Create autostart entry if requested
if [[ "$ENABLE_AUTOSTART" == true ]]; then
    AUTOSTART_PATH="$AUTOSTART_DIR/docker-janitor.desktop"
    if [[ "$DRY_RUN" == true ]]; then
        echo "[dry-run] Would create autostart entry at $AUTOSTART_PATH"
    else
        cp -f "$DESKTOP_PATH" "$AUTOSTART_PATH"
        echo "✓ Configured autostart: $AUTOSTART_PATH"
    fi
fi

# 9. Optional desktop database refresh
if [[ "$DRY_RUN" != true ]]; then
    if command -v update-desktop-database &>/dev/null; then
        update-desktop-database "$APPS_DIR" 2>/dev/null || true
    fi
    if command -v gtk-update-icon-cache &>/dev/null; then
        gtk-update-icon-cache -f -t "$XDG_DATA_HOME/icons/hicolor" 2>/dev/null || true
    fi
fi

# 10. PATH verification notice
echo ""
echo "=== Installation Complete ==="
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo "Notice: $BIN_DIR is not currently in your \$PATH."
    echo "To run 'docker-janitor' directly from any terminal, add this to your ~/.bashrc or ~/.profile:"
    echo "  export PATH=\"\$PATH:$BIN_DIR\""
    echo ""
fi

echo "You can start Docker Janitor by:"
echo "  1. Launching it from your application menu ('Docker Janitor')"
echo "  2. Running: $LAUNCHER_PATH &"
if [[ "$ENABLE_AUTOSTART" == true ]]; then
    echo "  3. Logging into your desktop session (autostarts automatically)"
fi
echo ""
echo "To uninstall later, run './uninstall.sh'."
