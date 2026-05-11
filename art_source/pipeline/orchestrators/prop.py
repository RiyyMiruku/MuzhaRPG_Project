"""Pipeline 2: Prop orchestrator(building 大建築 + iso_prop 小單格)。

Stages:
  1. generate_object  — building → create-map-object;iso_prop → create-isometric-tile
  2. chroma_key       — PIL 去背(若 API 有殘留底色)

CLI:
  uv run python art_source/pipeline/orchestrators/prop.py \
      --name muzha_shophouse --kind building \
      --description "traditional taiwanese shophouse, red brick" \
      --width 128 --height 128 [--review-mode stage]

  uv run python art_source/pipeline/orchestrators/prop.py \
      --name red_lantern --kind iso_prop \
      --description "red paper lantern with gold tassel" \
      --size 32
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


STAGES: list[str] = ["generate_object", "chroma_key", "import_to_godot"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--name", required=True)
    p.add_argument("--kind", choices=["building", "iso_prop"], required=True)
    p.add_argument("--description", default=None)
    p.add_argument("--width", type=int, default=96)
    p.add_argument("--height", type=int, default=96)
    p.add_argument("--size", type=int, default=32, help="iso_prop 用")
    p.add_argument("--view", default="high_top_down", help="building 用")
    p.add_argument(
        "--review-mode", choices=["none", "stage"], default="stage"
    )
    p.add_argument("--resume-from", default=None)
    p.add_argument("--force-restart-stage", action="append", default=[])
    p.add_argument("--zone", default=None,
                   help=f"所屬 zone (寫入 manifest tags)。valid: {zones.ZONES}")
    p.add_argument("--category", default=None,
                   help="自由形 category tag (e.g. 'vendor', 'decoration')")
    p.add_argument("--chapter", default=None,
                   help="所屬章節 tag (e.g. '1', '2', 'prologue')")
    p.add_argument("--collision", default="bottom_16x16",
                   help='碰撞範圍: none|bottom_16x8|bottom_16x16|full|"WxH"')
    p.add_argument("--no-collision", action="store_true",
                   help="不生成 StaticBody collision (覆蓋 --collision)")
    return p.parse_args()


@stage("generate_object")
def generate_object(ctx: StageContext) -> list[str]:
    args = ctx.args
    assert args is not None
    if not args.description:
        raise SystemExit("首次跑 generate_object 須提供 --description")

    token = plab.load_token()
    out_dir = manifest.object_dir(ctx.name)
    out_dir.mkdir(parents=True, exist_ok=True)
    img_path = out_dir / f"{ctx.name}.png"

    if args.kind == "building":
        object_id, img = plab.submit_map_object(
            token=token,
            description=args.description,
            width=args.width,
            height=args.height,
            view=args.view,
        )
        manifest.upsert_object(
            name=ctx.name,
            fields={
                "object_id": object_id,
                "kind": "building",
                "description": args.description,
                "view": args.view,
                "size": {"width": args.width, "height": args.height},
                "status": "pending",
            },
        )
    else:  # iso_prop
        object_id, img = plab.submit_iso_tile(
            token=token, description=args.description, size=args.size
        )
        manifest.upsert_object(
            name=ctx.name,
            fields={
                "object_id": object_id,
                "kind": "iso_prop",
                "description": args.description,
                "size": {"width": args.size, "height": args.size},
                "status": "pending",
            },
        )

    img.save(img_path)
    return [str(img_path.relative_to(plab.project_root()))]


@stage("chroma_key")
def chroma_key(ctx: StageContext) -> list[str]:
    img_path = manifest.object_dir(ctx.name) / f"{ctx.name}.png"
    pp.chroma_key_file(img_path)
    manifest.upsert_object(
        name=ctx.name,
        fields={
            "status": "completed",
            "local_path": str(img_path.relative_to(plab.project_root())),
        },
    )
    return [str(img_path.relative_to(plab.project_root()))]


@stage("import_to_godot", is_last=True)
def import_to_godot(ctx: StageContext) -> list[str]:
    from orchestrators import _godot_import as gimport
    args = ctx.args
    assert args is not None
    src = manifest.object_dir(ctx.name) / f"{ctx.name}.png"
    has_coll = not args.no_collision
    png_dest, tscn_dest = gimport.import_prop(
        src_png=src,
        name=ctx.name,
        collision=args.collision,
        has_collision=has_coll,
    )
    rel_root = plab.project_root()
    manifest.mark_imported(
        "object",
        ctx.name,
        game_png_path=str(png_dest.relative_to(rel_root)),
        game_tscn_path=str(tscn_dest.relative_to(rel_root)),
        collision=args.collision if has_coll else "none",
    )
    return [
        str(png_dest.relative_to(rel_root)),
        str(tscn_dest.relative_to(rel_root)),
    ]


def main() -> None:
    plab.setup_console()
    args = parse_args()
    manifest.validate_asset_name(args.name)
    zones.validate_zone(args.zone)
    ctx = make_context("object", args, STAGES)

    if not manifest.get_object(ctx.name):
        manifest.upsert_object(name=ctx.name, fields={"status": "init"})

    tags: list[str] = []
    if args.zone:
        tags.append(f"zone:{args.zone}")
    if args.category:
        tags.append(f"category:{args.category}")
    if args.chapter:
        tags.append(f"chapter:{args.chapter}")
    if tags:
        manifest.add_tags(ctx.asset_type, ctx.name, tags)

    generate_object(ctx)
    chroma_key(ctx)
    import_to_godot(ctx)
    print(f"\n[prop:{args.kind}] {ctx.name} 完成。")


if __name__ == "__main__":
    main()
