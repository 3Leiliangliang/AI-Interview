"""Docker entrypoint for freeproblemset import.

Environment variables:
    FREEPROBLEMSET_AUTO_SYNC: Run 'sync' command (default: true)
    FREEPROBLEMSET_AUTO_CLASSIFY: Run 'classify' command (default: true)
    FREEPROBLEMSET_AUTO_IMPORT: Run 'import-all' command (default: true)
    FREEPROBLEMSET_CLASSIFIER: Classifier type, 'rule' or 'llm' (default: rule)
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
MANAGER_SCRIPT = SCRIPT_DIR / "freeproblemset_manager.py"


def run_manager(args: list[str]) -> int:
    """Run freeproblemset_manager.py with given arguments."""
    cmd = [sys.executable, str(MANAGER_SCRIPT), *args]
    print(f"[freeproblemset-import] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=False)
    return result.returncode


def main() -> None:
    auto_sync = os.getenv("FREEPROBLEMSET_AUTO_SYNC", "true").strip().lower() in ("true", "1", "yes")
    auto_classify = os.getenv("FREEPROBLEMSET_AUTO_CLASSIFY", "true").strip().lower() in ("true", "1", "yes")
    auto_import = os.getenv("FREEPROBLEMSET_AUTO_IMPORT", "true").strip().lower() in ("true", "1", "yes")
    classifier = os.getenv("FREEPROBLEMSET_CLASSIFIER", "rule").strip().lower()

    if classifier not in ("rule", "llm"):
        print(f"[freeproblemset-import] Invalid classifier: {classifier}, fallback to 'rule'")
        classifier = "rule"

    print(
        f"[freeproblemset-import] Config: auto_sync={auto_sync}, "
        f"auto_classify={auto_classify}, auto_import={auto_import}, classifier={classifier}"
    )

    if auto_sync:
        print("[freeproblemset-import] Step 1: Syncing freeproblemset repository...")
        code = run_manager(["sync"])
        if code != 0:
            print(f"[freeproblemset-import] Sync failed with code {code}")
            sys.exit(code)
        print("[freeproblemset-import] Sync completed.")

    if auto_classify:
        print("[freeproblemset-import] Step 2: Classifying problems...")
        code = run_manager(["classify", "--classifier", classifier])
        if code != 0:
            print(f"[freeproblemset-import] Classify failed with code {code}")
            sys.exit(code)
        print("[freeproblemset-import] Classify completed.")

    if auto_import:
        print("[freeproblemset-import] Step 3: Importing problems to OJ...")
        code = run_manager(["import-all", "--classifier", classifier])
        if code != 0:
            print(f"[freeproblemset-import] Import failed with code {code}")
            sys.exit(code)
        print("[freeproblemset-import] Import completed.")

    print("[freeproblemset-import] All done.")


if __name__ == "__main__":
    main()
