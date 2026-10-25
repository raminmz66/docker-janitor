#!/usr/bin/env bash
# Docker Janitor — Uninstaller
# https://github.com/raminmz66/docker-janitor
# MIT License

set -euo pipefail

PREFIX="${PREFIX:-$HOME/.local}"
BIN_DIR="${BIN_DIR:-$PREFIX/bin}"
XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
XDG_STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"

APP_SHARE_DIR="$XDG_DATA_HOME/docker-janitor"
ICONS_DIR="$XDG_DATA_HOME/icons/hicolor/scalable/apps"
APPS_DIR="$XDG_DATA_HOME/applications"
AUTOSTART_DIR="$XDG_CONFIG_HOME/autostart"

CONFIG_DIR="$XDG_CONFIG_HOME/docker-janitor"
LOG_FILE="$XDG_STATE_HOME/docker-janitor.log"

DRY_RUN=false
PURGE=false

print_help() {
    cat <<EOF
Docker Janitor — Uninstaller

Usage:
  ./uninstall.sh [OPTIONS]

Options:
  --dry-run             Preview removal actions without deleting any files
  --purge               Also remove configuration files and activity logs
  --prefix=<DIR>        Custom installation prefix (default: \$HOME/.local)
  -h, --help            Show this help message and exit

Description:
  Removes the Docker Janitor executable launcher, application menu entry,
  autostart configuration, and installed desktop icons.
EOF
}

# Parse command line arguments
for arg in "$@"; do
    case "$arg" in
        --dry-run)
            DRY_RUN=true
            ;;
        --purge)
            PURGE=true
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
            echo "Run './uninstall.sh --help' for usage." >&2
            exit 1
            ;;
    esac
done

echo "=== Docker Janitor Uninstaller ==="
if [[ "$DRY_RUN" == true ]]; then
    echo "[DRY RUN MODE: No files will be deleted]"
fi

remove_file() {
    local target="$1"
    if [[ -f "$target" || -L "$target" ]]; then
        if [[ "$DRY_RUN" == true ]]; then
            echo "[dry-run] Would remove file: $target"
        else
            rm -f "$target"
            echo "✓ Removed: $target"
        fi
    fi
}

remove_dir() {
    local target="$1"
    if [[ -d "$target" ]]; then
        if [[ "$DRY_RUN" == true ]]; then
            echo "[dry-run] Would remove directory: $target"
        else
            rm -rf "$target"
            echo "✓ Removed directory: $target"
        fi
    fi
}

# Remove binary launcher
remove_file "$BIN_DIR/docker-janitor"

# Remove application desktop launcher and autostart
remove_file "$APPS_DIR/docker-janitor.desktop"
remove_file "$AUTOSTART_DIR/docker-janitor.desktop"

# Remove installed icons
remove_file "$ICONS_DIR/docker-janitor.svg"

# Remove app share directory
remove_dir "$APP_SHARE_DIR"

# Purge configuration and log files if requested
if [[ "$PURGE" == true ]]; then
    remove_dir "$CONFIG_DIR"
    remove_file "$LOG_FILE"
    echo "✓ Purged configuration and state logs"
else
    if [[ -d "$CONFIG_DIR" || -f "$LOG_FILE" ]]; then
        echo "Note: Configuration ($CONFIG_DIR) and logs ($LOG_FILE) were kept."
        echo "Run './uninstall.sh --purge' if you wish to remove them as well."
    fi
fi

# Refresh desktop databases
if [[ "$DRY_RUN" != true ]]; then
    if command -v update-desktop-database &>/dev/null; then
        update-desktop-database "$APPS_DIR" 2>/dev/null || true
    fi
    if command -v gtk-update-icon-cache &>/dev/null; then
        gtk-update-icon-cache -f -t "$XDG_DATA_HOME/icons/hicolor" 2>/dev/null || true
    fi
fi

echo ""
echo "=== Uninstallation Complete ==="
