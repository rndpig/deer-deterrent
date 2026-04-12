#!/usr/bin/env python3
"""
Rollback the production model to a previous backup.

Lists available model backups and restores a selected one,
then rebuilds and restarts the ml-detector container.

Usage:
    python3 scripts/rollback_model.py --list
    python3 scripts/rollback_model.py --to 20260411
    python3 scripts/rollback_model.py --to best.pt.bak_20260411_092300
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRODUCTION_DIR = PROJECT_ROOT / "dell-deployment" / "models" / "production"
PRODUCTION_MODEL = PRODUCTION_DIR / "best.pt"
VERSION_FILE = PRODUCTION_DIR / "VERSION"


def list_backups():
    """List all available model backups with size and date."""
    backups = sorted(PRODUCTION_DIR.glob("best.pt.bak_*"), reverse=True)
    # Also include named backups like best.pt.backup_*
    backups += sorted(PRODUCTION_DIR.glob("best.pt.backup_*"), reverse=True)

    if not backups:
        print("  No backups found in", PRODUCTION_DIR)
        return []

    print(f"  {'Backup':<50} {'Size':>10} {'Modified'}")
    print(f"  {'-'*50} {'-'*10} {'-'*20}")
    for b in backups:
        size_mb = b.stat().st_size / 1e6
        mtime = b.stat().st_mtime
        from datetime import datetime
        modified = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        print(f"  {b.name:<50} {size_mb:>8.1f}MB {modified}")

    if PRODUCTION_MODEL.exists():
        size_mb = PRODUCTION_MODEL.stat().st_size / 1e6
        version = VERSION_FILE.read_text().strip() if VERSION_FILE.exists() else "unknown"
        print(f"\n  Current production: best.pt ({size_mb:.1f}MB, {version})")

    return backups


def rollback(target: str, restart: bool = True):
    """Restore a backup to production."""
    # Find matching backup
    candidates = list(PRODUCTION_DIR.glob(f"*{target}*"))
    candidates = [c for c in candidates if c.name != "best.pt"]

    if not candidates:
        print(f"  ERROR: No backup matching '{target}' found")
        list_backups()
        sys.exit(1)

    if len(candidates) > 1:
        print(f"  Multiple backups match '{target}':")
        for c in candidates:
            print(f"    {c.name}")
        print("  Be more specific.")
        sys.exit(1)

    backup = candidates[0]
    print(f"  Restoring: {backup.name}")

    # Backup current model before overwriting
    if PRODUCTION_MODEL.exists():
        from datetime import datetime
        rollback_backup = PRODUCTION_MODEL.with_suffix(
            f".pt.pre_rollback_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        PRODUCTION_MODEL.rename(rollback_backup)
        print(f"  Saved current as: {rollback_backup.name}")

    # Copy backup to production
    import shutil
    shutil.copy2(backup, PRODUCTION_MODEL)
    print(f"  Restored to: {PRODUCTION_MODEL}")

    # Try to determine version from backup filename
    # e.g., best.pt.backup_yolo26s_v3.0_20260411 → "YOLO26s v3.0"
    import re
    match = re.search(r'v(\d+\.\d+)', backup.name)
    if match:
        version_label = f"YOLO26s v{match.group(1)} (rollback)"
        VERSION_FILE.write_text(version_label)
        print(f"  Updated VERSION: {version_label}")

    if restart:
        print("\n  Restarting ml-detector container...")
        result = subprocess.run(
            ["docker", "compose", "restart", "ml-detector"],
            cwd=str(PROJECT_ROOT),
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print("  ml-detector restarted.")
        else:
            print(f"  WARNING: Restart failed: {result.stderr}")
            print("  Run manually: docker compose restart ml-detector")
    else:
        print("\n  Skipped container restart (--no-restart)")
        print("  Run manually: docker compose restart ml-detector")

    print("\n  Rollback complete.")


def main():
    parser = argparse.ArgumentParser(description="Rollback production model to a backup")
    parser.add_argument("--list", action="store_true", help="List available backups")
    parser.add_argument("--to", dest="target", help="Backup to restore (partial match on filename or date)")
    parser.add_argument("--no-restart", action="store_true", help="Don't restart ml-detector after rollback")
    args = parser.parse_args()

    if args.list or (not args.target):
        list_backups()
        if not args.target:
            print("\n  Usage: python3 scripts/rollback_model.py --to <backup_date_or_name>")
    elif args.target:
        rollback(args.target, restart=not args.no_restart)


if __name__ == "__main__":
    main()
