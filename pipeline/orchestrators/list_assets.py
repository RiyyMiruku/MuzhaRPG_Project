"""List / filter art-pipeline assets from manifest.

Usage:
  uv run python pipeline/orchestrators/list_assets.py
  uv run python pipeline/orchestrators/list_assets.py --type character
  uv run python pipeline/orchestrators/list_assets.py --zone market
  uv run python pipeline/orchestrators/list_assets.py --category vendor
  uv run python pipeline/orchestrators/list_assets.py --type tileset --zone market
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import manifest


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--type", choices=["character", "tileset", "object"], default=None)
    p.add_argument("--zone", default=None)
    p.add_argument("--category", default=None)
    p.add_argument("--tag", action="append", default=[],
                   help="自由形 tag 過濾 (可多次,AND 邏輯)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    tags: list[str] = list(args.tag)
    if args.zone:
        tags.append(f"zone:{args.zone}")
    if args.category:
        tags.append(f"category:{args.category}")
    results = manifest.query_assets(asset_type=args.type, tags=tags or None)
    if not results:
        print("(no matches)")
        return
    print(f"{'TYPE':<10} {'NAME':<32} {'STATUS':<12} TAGS")
    print("-" * 80)
    for full_name, entry in sorted(results.items()):
        t, n = full_name.split(":", 1)
        status = entry.get("status", "?")
        tag_str = ",".join(entry.get("tags", []))
        print(f"{t:<10} {n:<32} {status:<12} {tag_str}")


if __name__ == "__main__":
    main()
