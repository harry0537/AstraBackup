#!/usr/bin/env bash
set -euo pipefail

# Project Astra NZ - V9 Repo Cleanup Utility
# Safe by default: DRY-RUN unless --apply is given.
#
# Cleans common junk in the v9 folder:
#  - __pycache__/ directories, *.pyc, *.pyo
#  - .DS_Store, editor backups (*~)
#  - *.tmp files within repo
#
# Optional: --deep-tmp also prunes old files in /tmp/vision_v9 except current latest
# (conservative: only *.log and *.old older than 7 days)

APPLY=false
DEEP_TMP=false
for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=true ;;
    --deep-tmp) DEEP_TMP=true ;;
    --help|-h)
      echo "Usage: bash v9/cleanup_v9.sh [--apply] [--deep-tmp]"
      exit 0
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "[cleanup] Scanning repo for junk files (dry-run: $([ "$APPLY" = true ] && echo OFF || echo ON))"

delete_or_echo() {
  local path="$1"
  if [ "$APPLY" = true ]; then
    rm -rf "$path" 2>/dev/null || true
  else
    echo "  would remove: $path"
  fi
}

# 1) __pycache__ directories
while IFS= read -r -d '' d; do
  delete_or_echo "$d"
done < <(find "$SCRIPT_DIR" -type d -name "__pycache__" -print0)

# 2) *.pyc / *.pyo
while IFS= read -r -d '' f; do
  delete_or_echo "$f"
done < <(find "$SCRIPT_DIR" -type f \( -name "*.pyc" -o -name "*.pyo" \) -print0)

# 3) .DS_Store and editor backups *~
while IFS= read -r -d '' f; do
  delete_or_echo "$f"
done < <(find "$SCRIPT_DIR" -type f \( -name ".DS_Store" -o -name "*~" \) -print0)

# 4) *.tmp within repo
while IFS= read -r -d '' f; do
  delete_or_echo "$f"
done < <(find "$SCRIPT_DIR" -type f -name "*.tmp" -print0)

# 5) Optional prune of /tmp/vision_v9 logs (conservative)
if [ "$DEEP_TMP" = true ]; then
  echo "[cleanup] Deep tmp mode: pruning old logs from /tmp/vision_v9 (>=7 days)"
  if [ -d /tmp/vision_v9 ]; then
    # Only remove *.log and *.old older than 7 days
    while IFS= read -r -d '' f; do
      delete_or_echo "$f"
    done < <(find /tmp/vision_v9 -maxdepth 1 -type f \( -name "*.log" -o -name "*.old" \) -mtime +7 -print0)
  fi
fi

if [ "$APPLY" = true ]; then
  echo "[cleanup] Cleanup applied."
else
  echo "[cleanup] DRY-RUN complete. Re-run with --apply to delete."
fi


