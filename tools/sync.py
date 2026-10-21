#!/usr/bin/env python3
"""Copy the canonical scanner (re-arch-scan/scripts) into the skills that vendor it.

Usage: python3 tools/sync.py          copy
       python3 tools/sync.py --check  exit 1 if a vendored copy drifted (CI)
"""
import filecmp
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, "skills", "re-arch-scan", "scripts")
FILES = ["scan.py", "precise.py", "di.py", "insights.py", "ts_resolve.js", "php_refs.php"]
TARGET_DIRS = [os.path.join(ROOT, "skills", "re-arch-guardrails", "scripts")]

check = "--check" in sys.argv
drift = []
for d in TARGET_DIRS:
    for f in FILES:
        src, dst = os.path.join(SRC_DIR, f), os.path.join(d, f)
        if check:
            if not os.path.exists(dst) or not filecmp.cmp(src, dst, shallow=False):
                drift.append(os.path.relpath(dst, ROOT))
        else:
            shutil.copyfile(src, dst)
if check:
    if drift:
        print("vendored scanner out of date: " + ", ".join(drift) + " (run python3 tools/sync.py)")
        sys.exit(1)
    print("vendored scanner in sync")
else:
    print(f"synced {len(FILES)} files into {len(TARGET_DIRS)} skill(s)")
