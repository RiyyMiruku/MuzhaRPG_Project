"""Pipeline 1: Autotile orchestrator.

Stages:
  1. generate_atlas      — Pixellab create-topdown-tileset(async)
  2. iso_project         — PIL 4×4 affine 投影成菱形 atlas
  3. verify_in_godot     — 印 Godot import 提示(不做事)

CLI:
  uv run python pipeline/orchestrators/autotile.py \\
      --name market_grass_asphalt \\
      --lower "green grass texture" \\
      --upper "dark asphalt road" \\
      [--transition-size 0.25] [--transition-description "grey concrete curb"] \\
      [--tile-size 16] [--review-mode stage]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import manifest
import pixellab_client as plab
import post_process as pp
import zones
from orchestrators._common import (
    StageContext,
    make_context,
    stage,
)


STAGES: list[str] = ["generate_atlas", "iso_project", "verify_in_godot", "import_to_godot"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--lower", help="下層地形描述(首次必填)")
    parser.add_argument("--upper", help="上層地形描述(首次必填)")
    parser.add_argument("--transition-size", type=float, default=0.0)
    parser.add_argument("--transition-description", default=None)
    parser.add_argument("--tile-size", type=int, default=16)
    parser.add_argument(
        "--review-mode", choices=["none", "stage"], default="stage"
    )
    parser.add_argument("--resume-from", default=None)
    parser.add_argument("--force-restart-stage", action="append", default=[])
    parser.add_argument("--zones", default=None,
                        help="逗號分隔的 zone slug list；每個寫成一個 zone:<slug> tag。"
                             "詞彙表是 story/chapters/<slug>/zones.json。'*' 代表跨場景。")
    parser.add_argument("--zone", default=None,
                        help="[deprecated] 單一 zone（保留向下相容；新代碼用 --zones）")
    parser.add_argument("--category", default=None,
                        help="自由形 category tag (e.g. 'vendor', 'decoration')")
    parser.add_argument("--chapter", default=None,
                        help="所屬章節 tag (e.g. '1', '2', 'prologue')")
    return parser.parse_args()


@stage("generate_atlas")
def generate_atlas(ctx: StageContext) -> list[str]:
    args = ctx.args
    assert args is not None
    if not args.lower or not args.upper:
        raise SystemExit("首次跑 generate_atlas 須提供 --lower 與 --upper")

    token = plab.load_token()
    tileset_id, atlas_img = plab.submit_topdown_tileset(
        token=token,
        lower_description=args.lower,
        upper_description=args.upper,
        transition_size=args.transition_size,
        transition_description=args.transition_description,
        tile_width=args.tile_size,
        tile_height=args.tile_size,
    )
    manifest.upsert_tileset(
        name=ctx.name,
        fields={
            "tileset_id": tileset_id,
            "lower": args.lower,
            "upper": args.upper,
            "tile_size": args.tile_size,
            "status": "pending",
        },
    )

    out_dir = manifest.tileset_dir(ctx.name)
    out_dir.mkdir(parents=True, exist_ok=True)
    atlas_path = out_dir / f"{ctx.name}_topdown.png"
    atlas_img.save(atlas_path)

    manifest.upsert_tileset(
        name=ctx.name,
        fields={
            "status": "atlas_ready",
            "topdown_path": str(atlas_path.relative_to(plab.project_root())),
        },
    )
    return [str(atlas_path.relative_to(plab.project_root()))]


@stage("iso_project")
def iso_project(ctx: StageContext) -> list[str]:
    out_dir = manifest.tileset_dir(ctx.name)
    atlas_path = out_dir / f"{ctx.name}_topdown.png"
    iso_path = out_dir / f"{ctx.name}_iso.png"
    pp.project_atlas_file(atlas_path, iso_path, cols=4, rows=4)
    manifest.upsert_tileset(
        name=ctx.name,
        fields={
            "iso_path": str(iso_path.relative_to(plab.project_root())),
            "status": "completed",
        },
    )
    return [str(iso_path.relative_to(plab.project_root()))]


@stage("verify_in_godot", is_last=False)
def verify_in_godot(ctx: StageContext) -> list[str]:
    out_dir = manifest.tileset_dir(ctx.name)
    iso_path = out_dir / f"{ctx.name}_iso.png"
    print(
        f"\n→ 將 {iso_path} import 到 Godot,搭 TileMapDual addon。"
        f"\n  參考 docs/tilemapdual-guide.md"
    )
    return [str(iso_path.relative_to(plab.project_root()))]


@stage("import_to_godot", is_last=True)
def import_to_godot(ctx: StageContext) -> list[str]:
    from orchestrators import _godot_import as gimport
    src = manifest.tileset_dir(ctx.name) / f"{ctx.name}_iso.png"
    if not src.exists():
        # fallback to whatever the previous stage produced
        candidates = sorted(manifest.tileset_dir(ctx.name).glob("*_iso.png"))
        if not candidates:
            raise SystemExit(f"no iso PNG found in {manifest.tileset_dir(ctx.name)}")
        src = candidates[-1]
    dest = gimport.import_tileset(src_png=src, name=ctx.name)
    rel_root = plab.project_root()
    manifest.mark_imported(
        "tileset",
        ctx.name,
        game_png_path=str(dest.relative_to(rel_root)),
    )
    return [str(dest.relative_to(rel_root))]


def main() -> None:
    plab.setup_console()
    args = parse_args()
    manifest.validate_asset_name(args.name)
    ctx = make_context("tileset", args, STAGES)

    # 確保 manifest 條目存在(供 mark_stage 用)
    if not manifest.get_tileset(ctx.name):
        manifest.upsert_tileset(name=ctx.name, fields={"status": "init"})

    tags: list[str] = zones.resolve_zone_tags(args.zones, args.zone)
    if args.category:
        tags.append(f"category:{args.category}")
    if args.chapter:
        tags.append(f"chapter:{args.chapter}")
    if tags:
        manifest.add_tags(ctx.asset_type, ctx.name, tags)

    generate_atlas(ctx)
    iso_project(ctx)
    verify_in_godot(ctx)
    import_to_godot(ctx)
    print(f"\n[autotile] {ctx.name} 完成。")


if __name__ == "__main__":
    main()
