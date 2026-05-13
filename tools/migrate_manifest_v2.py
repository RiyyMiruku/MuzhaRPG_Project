#!/usr/bin/env python3
"""Migrate art_source/manifest.json (v1, single aggregate file) to v2
file-per-asset layout (art_source/<type>/<name>/asset.json).

Idempotent: running multiple times is safe. Existing per-asset asset.json
files are NOT overwritten unless --force is passed (in which case the
aggregate manifest.json wins, last write).

Usage:
    uv run python tools/migrate_manifest_v2.py            # dry run + report
    uv run python tools/migrate_manifest_v2.py --apply    # actually write
    uv run python tools/migrate_manifest_v2.py --apply --force
                                                          # overwrite existing

Output:
    - art_source/<type>/<name>/asset.json  (one per asset)
    - art_source/manifest.json.bak-v1-to-v2  (backup of original)
    - art_source/manifest.json              (left in place; remove only after
                                             verifying everything reads OK)
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ART_ROOT = REPO_ROOT / "art_source"
MANIFEST_FILE = ART_ROOT / "manifest.json"
BACKUP_FILE = ART_ROOT / "manifest.json.bak-v1-to-v2"

_BUCKET_TO_TYPE = {
    "characters": "character",
    "tilesets": "tileset",
    "objects": "object",
}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply", action="store_true",
                   help="Actually write files. Without this, dry-run only.")
    p.add_argument("--force", action="store_true",
                   help="Overwrite existing per-asset asset.json files.")
    args = p.parse_args()

    if not MANIFEST_FILE.exists():
        print(f"!! No source manifest found at {MANIFEST_FILE}")
        print("   Nothing to migrate.")
        return 1

    raw = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    version = raw.get("version", "?")
    print(f"== Source: {MANIFEST_FILE} (version={version}) ==")

    plan: list[tuple[str, str, Path, str]] = []  # (action, bucket/name, target, reason)
    for bucket, asset_type in _BUCKET_TO_TYPE.items():
        section = raw.get(bucket) or {}
        for name, entry in section.items():
            target = ART_ROOT / bucket / name / "asset.json"
            if target.exists():
                if args.force:
                    plan.append(("OVERWRITE", f"{asset_type}/{name}", target,
                                 "force-overwrite existing"))
                else:
                    plan.append(("SKIP", f"{asset_type}/{name}", target,
                                 "already exists; use --force to overwrite"))
            else:
                plan.append(("CREATE", f"{asset_type}/{name}", target,
                             ""))

    counts: dict[str, int] = {}
    for action, _, _, _ in plan:
        counts[action] = counts.get(action, 0) + 1

    print(f"\n== Plan: {sum(counts.values())} entries ==")
    for action, count in sorted(counts.items()):
        print(f"  {action:10} {count}")
    print()
    for action, label, target, reason in plan:
        rel = target.relative_to(REPO_ROOT)
        suffix = f" ({reason})" if reason else ""
        print(f"  [{action:10}] {label:40} -> {rel}{suffix}")

    if not args.apply:
        print("\n(dry run; pass --apply to actually write)")
        return 0

    print(f"\n== Backing up original ==")
    if BACKUP_FILE.exists():
        print(f"  backup already exists at {BACKUP_FILE}, leaving as-is")
    else:
        shutil.copy2(MANIFEST_FILE, BACKUP_FILE)
        print(f"  copied {MANIFEST_FILE.name} -> {BACKUP_FILE.name}")

    print(f"\n== Writing per-asset files ==")
    written = 0
    skipped = 0
    for action, label, target, _ in plan:
        if action == "SKIP":
            skipped += 1
            continue
        bucket, name = label.split("/", 1)
        # Map back from asset_type to bucket name
        bucket_dir = {v: k for k, v in _BUCKET_TO_TYPE.items()}[bucket]
        entry = raw[bucket_dir][name]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(entry, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        written += 1
    print(f"  wrote {written}, skipped {skipped}")

    print(f"\n== Done ==")
    print(f"  Original {MANIFEST_FILE.name} left in place — remove only after")
    print(f"  verifying dashboard + pipeline still read correctly via per-asset files.")
    print(f"  Backup at {BACKUP_FILE.relative_to(REPO_ROOT)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
