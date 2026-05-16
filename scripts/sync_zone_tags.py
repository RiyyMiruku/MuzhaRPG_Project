"""Sync zone tags from story/chapters/*/assets.json → art_source/<asset>/asset.json.

`story/chapters/<slug>/assets.json` is the single source of truth for
`zones[]` per asset. This script propagates that to manifest tags so the
dashboard / Godot side can filter by zone.

For each asset listed in the chapter's assets.json:
  1. Drop every existing `zone:*` tag from art_source/<bucket>/<name>/asset.json.
  2. Append one `zone:<slug>` tag per slug in zones[] (preserves order, dedupes).
  3. Preserve all other tags (category:*, chapter:*, free-form, ...).

Validation:
  - Each slug in zones[] must appear in the chapter's zones.json, OR be the
    sentinel '*'. Unknown slugs abort the run with a clear error.
  - Missing asset in art_source is reported but does not abort (other assets
    keep syncing).

Usage:
  uv run python scripts/sync_zone_tags.py                  # all chapters
  uv run python scripts/sync_zone_tags.py --chapter chapter_01_arrival
  uv run python scripts/sync_zone_tags.py --dry-run        # report, don't write
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "pipeline"))
import manifest as pm  # noqa: E402


_BUCKET_FOR_SECTION = {
    "moving_npcs": "characters",
    "static_npcs": "characters",
    "iso_props": "objects",
    "buildings": "objects",
    "tilesets": "tilesets",
}


def _load_zone_vocabulary(zones_json: Path) -> set[str]:
    """Read zones.json and return set of valid zone slugs (+ sentinel '*')."""
    data = json.loads(zones_json.read_text(encoding="utf-8"))
    slugs = {z["slug"] for z in data.get("zones", [])}
    slugs.add("*")
    return slugs


def _sync_one_asset(
    bucket: str, name: str, zones: list[str], *, dry_run: bool
) -> tuple[str, str]:
    """Return (status, detail). status ∈ {'updated','noop','missing'}."""
    entry = pm._read_asset(bucket, name)
    if entry is None:
        return "missing", f"art_source/{bucket}/{name}/asset.json"

    old_tags: list[str] = list(entry.get("tags") or [])
    non_zone = [t for t in old_tags if not t.startswith("zone:")]
    new_zone_tags: list[str] = []
    seen: set[str] = set()
    for z in zones:
        if z not in seen:
            new_zone_tags.append(f"zone:{z}")
            seen.add(z)
    new_tags = non_zone + new_zone_tags

    if new_tags == old_tags:
        return "noop", ""

    if not dry_run:
        entry["tags"] = new_tags
        entry["updated_at"] = pm.now_iso()
        pm._write_asset(bucket, name, entry)
    return "updated", f"{old_tags} -> {new_tags}"


def _sync_chapter(chapter_dir: Path, *, dry_run: bool) -> dict[str, int]:
    """Sync one chapter. Returns counts {updated, noop, missing}."""
    zones_path = chapter_dir / "zones.json"
    assets_path = chapter_dir / "assets.json"
    if not zones_path.is_file():
        raise SystemExit(f"missing {zones_path}")
    if not assets_path.is_file():
        raise SystemExit(f"missing {assets_path}")

    vocabulary = _load_zone_vocabulary(zones_path)
    assets_data = json.loads(assets_path.read_text(encoding="utf-8"))

    print(f"\n=== {chapter_dir.name} ===")
    print(f"  vocabulary: {sorted(s for s in vocabulary if s != '*')} + '*'")

    counts = {"updated": 0, "noop": 0, "missing": 0}
    errors: list[str] = []

    for section, bucket in _BUCKET_FOR_SECTION.items():
        for asset in assets_data.get(section, []) or []:
            name = asset.get("name")
            zones = asset.get("zones") or []
            if not name:
                errors.append(f"[{section}] entry missing 'name'")
                continue
            unknown = [z for z in zones if z not in vocabulary]
            if unknown:
                errors.append(
                    f"[{section}] {name}: unknown zone slug(s) {unknown} "
                    f"(not in {zones_path.name})"
                )
                continue
            status, detail = _sync_one_asset(bucket, name, zones, dry_run=dry_run)
            counts[status] += 1
            marker = {"updated": "+", "noop": "=", "missing": "?"}[status]
            line = f"  {marker} {bucket}/{name}"
            if detail and status == "updated":
                line += f"  ({detail})"
            elif status == "missing":
                line += f"  (no {detail})"
            print(line)

    if errors:
        print("\n  ERRORS:")
        for e in errors:
            print(f"    ! {e}")
        raise SystemExit(1)

    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--chapter", default=None,
                    help="chapter_slug to sync (default: all under story/chapters/)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would change but don't write")
    args = ap.parse_args()

    chapters_dir = REPO_ROOT / "story" / "chapters"
    if args.chapter:
        targets = [chapters_dir / args.chapter]
    else:
        targets = sorted(
            d for d in chapters_dir.iterdir()
            if d.is_dir() and (d / "zones.json").is_file()
        )
    if not targets:
        raise SystemExit("no chapters with zones.json found")

    totals = {"updated": 0, "noop": 0, "missing": 0}
    for t in targets:
        c = _sync_chapter(t, dry_run=args.dry_run)
        for k, v in c.items():
            totals[k] += v

    print(f"\nTOTAL  updated={totals['updated']}  "
          f"noop={totals['noop']}  missing={totals['missing']}"
          + ("  (dry-run, no writes)" if args.dry_run else ""))


if __name__ == "__main__":
    main()
