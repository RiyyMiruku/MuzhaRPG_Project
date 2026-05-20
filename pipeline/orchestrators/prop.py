"""Pipeline 2: Prop orchestrator(building / iso_building 大物件 + iso_prop 小單格)。

Stages:
  1. generate_object  —
       building      → create-map-object      (top-down 立面;沒有 iso 參數)
       iso_building  → create-image-pixflux   (sync,isometric:true 弱引導;需在
                        description 帶 "isometric view, 30-degree angle" 字眼)
       iso_prop      → create-isometric-tile  (專屬 iso 端點;max 64×64)
  2. chroma_key       — PIL 去背(若 API 有殘留底色)
  3. import_to_godot  — 複製 PNG + 生成 .tscn + 更新 manifest

CLI:
  uv run python pipeline/orchestrators/prop.py \
      --name muzha_shophouse --kind iso_building \
      --description "isometric pixel art, 30-degree top-down angled view, full \
building visible with roof and two side walls — traditional taiwanese \
shophouse, red brick" \
      --width 128 --height 128 [--review-mode stage]

  uv run python pipeline/orchestrators/prop.py \
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
    p.add_argument(
        "--kind",
        choices=["building", "iso_building", "iso_prop"],
        required=True,
    )
    p.add_argument("--description", default=None)
    p.add_argument("--width", type=int, default=96,
                   help="building / iso_building 用 (16-400 for iso_building)")
    p.add_argument("--height", type=int, default=96,
                   help="building / iso_building 用 (16-400 for iso_building)")
    p.add_argument("--size", type=int, default=32, help="iso_prop 用")
    p.add_argument("--view", default="high_top_down",
                   help="building / iso_building 用 (iso_building 預設一律 high_top_down)")
    p.add_argument(
        "--review-mode", choices=["none", "stage"], default="stage"
    )
    p.add_argument("--resume-from", default=None)
    p.add_argument("--force-restart-stage", action="append", default=[])
    p.add_argument("--zones", default=None,
                   help="逗號分隔的 zone slug list；每個寫成一個 zone:<slug> tag。"
                        "詞彙表是 story/chapters/<slug>/zones.json。'*' 代表跨場景。")
    p.add_argument("--zone", default=None,
                   help="[deprecated] 單一 zone（保留向下相容；新代碼用 --zones）")
    p.add_argument("--category", default=None,
                   help="自由形 category tag (e.g. 'vendor', 'decoration')")
    p.add_argument("--chapter", default=None,
                   help="所屬章節 tag (e.g. '1', '2', 'prologue')")
    p.add_argument("--collision", default="bottom_16x16",
                   help='碰撞範圍: none|bottom_16x8|bottom_16x16|full|"WxH"')
    p.add_argument("--no-collision", action="store_true",
                   help="不生成 StaticBody collision (覆蓋 --collision)")
    p.add_argument(
        "--flip-h",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="水平翻轉 Sprite2D（解光照方向不一致）；不指定 = 沿用 manifest 既有值",
    )
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
    elif args.kind == "iso_building":
        # pixflux is sync (no background job, no object_id from Pixellab side).
        # Synthesize a local id so manifest stays uniform across kinds.
        img = plab.submit_pixflux_image(
            token=token,
            description=args.description,
            width=args.width,
            height=args.height,
            view=args.view,
            isometric=True,
            no_background=True,
        )
        manifest.upsert_object(
            name=ctx.name,
            fields={
                "object_id": f"pixflux:{ctx.name}",
                "kind": "iso_building",
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
    entry = manifest.get_object(ctx.name) or {}
    flip_h = bool(entry.get("flip_h", False))
    has_coll = not args.no_collision
    png_dest, tscn_dest = gimport.import_prop(
        src_png=src,
        name=ctx.name,
        collision=args.collision,
        has_collision=has_coll,
        flip_h=flip_h,
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
    ctx = make_context("object", args, STAGES)

    if not manifest.get_object(ctx.name):
        manifest.upsert_object(name=ctx.name, fields={"status": "init"})

    # Persist explicit flip_h into manifest (None = caller didn't specify; leave entry alone).
    if args.flip_h is not None:
        if manifest.get_object(ctx.name) is None:
            manifest.upsert_object(name=ctx.name, fields={"status": "init"})
        manifest.upsert_object(name=ctx.name, fields={"flip_h": bool(args.flip_h)})

    tags: list[str] = zones.resolve_zone_tags(args.zones, args.zone)
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
