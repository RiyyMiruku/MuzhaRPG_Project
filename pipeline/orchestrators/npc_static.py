"""Pipeline 3: Static NPC orchestrator(劇情背景 NPC,4 向 idle)。

Stages:
  1. generate_4dir_base   — create-character(4-dir 或 8-dir,看 --directions)
  2. add_idle_animation   — animate-character 4 向 idle(可 --no-idle 關)
  3. compile_spritesheet  — pipeline/spritesheet.py compile_character()

CLI:
  uv run python pipeline/orchestrators/npc_static.py \\
      --name shopkeeper_li \\
      --description "elderly taiwanese male shopkeeper, blue shirt" \\
      [--directions 4] [--no-idle] [--review-mode stage]
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
    CARDINAL_DIRECTIONS,
    StageContext,
    make_context,
    run_character_animation,
    stage,
)


STAGES: list[str] = ["generate_4dir_base", "add_idle_animation", "compile_spritesheet", "import_to_godot"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--name", required=True)
    p.add_argument("--description", default=None)
    p.add_argument("--directions", type=int, choices=[4, 8], default=8)
    p.add_argument("--view", default="high_top_down")
    p.add_argument("--proportions", default="cartoon")
    p.add_argument("--no-idle", action="store_true")
    p.add_argument("--idle-frame-count", type=int, default=4)
    p.add_argument(
        "--review-mode", choices=["none", "stage"], default="stage"
    )
    p.add_argument("--resume-from", default=None)
    p.add_argument("--force-restart-stage", action="append", default=[])
    p.add_argument("--zone", default=None,
                   help=f"所屬 zone (寫入 manifest tags)。valid: {zones.ZONES}")
    p.add_argument("--category", default=None,
                   help="自由形 category tag (e.g. 'vendor', 'student')")
    p.add_argument("--chapter", default=None,
                   help="所屬章節 tag (e.g. '1', '2', 'prologue')")
    return p.parse_args()


@stage("generate_4dir_base")
def generate_4dir_base(ctx: StageContext) -> list[str]:
    args = ctx.args
    assert args is not None
    if not args.description:
        raise SystemExit("首次跑須提供 --description")

    token = plab.load_token()
    if args.directions == 4:
        char_id, images = plab.submit_character_4dir(
            token=token, description=args.description,
            view=args.view, proportions_preset=args.proportions,
        )
    else:
        char_id, images = plab.submit_character_8dir(
            token=token, description=args.description,
            view=args.view, proportions_preset=args.proportions,
        )
    manifest.upsert_character(
        name=ctx.name,
        fields={
            "character_id": char_id,
            "preset": "npc",
            "directions": args.directions,
            "view": args.view,
            "proportions": args.proportions,
            "description": args.description,
            "status": "pending",
        },
    )
    out_dir = manifest.character_dir(ctx.name) / "rotations"
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: dict[str, Path] = {}
    for direction, img in images.items():
        img = pp.chroma_key_bg(img)
        fname = direction.replace("-", "_") + ".png"
        out = out_dir / fname
        img.save(out)
        saved[direction] = out
    manifest.upsert_character(
        name=ctx.name,
        fields={
            "status": "base_ready",
            "rotations": list(saved.keys()),
            "local_path": str(
                manifest.character_dir(ctx.name).relative_to(plab.project_root())
            ),
        },
    )
    return [str(p.relative_to(plab.project_root())) for p in saved.values()]


@stage("add_idle_animation")
def add_idle_animation(ctx: StageContext) -> list[str]:
    args = ctx.args
    assert args is not None
    if args.no_idle:
        print("--no-idle 指定,略過 idle 動畫")
        return []
    return run_character_animation(
        ctx, "idle", CARDINAL_DIRECTIONS, args.idle_frame_count,
        stage_name="add_idle_animation",
    )


@stage("compile_spritesheet", is_last=False)
def compile_spritesheet(ctx: StageContext) -> list[str]:
    char_dir = manifest.character_dir(ctx.name)
    # Local import — keeps top-level import surface light.
    import spritesheet
    spritesheet.compile_character(char_dir)
    return [str(char_dir.relative_to(plab.project_root()))]


@stage("import_to_godot", is_last=True)
def import_to_godot(ctx: StageContext) -> list[str]:
    from orchestrators import _godot_import as gimport
    char_dir = manifest.character_dir(ctx.name)
    sheet_dir = char_dir / "spritesheet"
    src_png = sheet_dir / f"{ctx.name}.png"
    src_json = sheet_dir / f"{ctx.name}.json"
    if not src_png.exists() or not src_json.exists():
        raise SystemExit(
            f"spritesheet not found in {sheet_dir} — did compile_spritesheet succeed?"
        )
    png_dest, json_dest = gimport.import_character_spritesheet(
        src_png=src_png, src_atlas_json=src_json, name=ctx.name
    )
    rel_root = plab.project_root()
    manifest.mark_imported(
        "character",
        ctx.name,
        game_png_path=str(png_dest.relative_to(rel_root)),
        game_json_path=str(json_dest.relative_to(rel_root)),
    )
    return [
        str(png_dest.relative_to(rel_root)),
        str(json_dest.relative_to(rel_root)),
    ]


def main() -> None:
    plab.setup_console()
    args = parse_args()
    manifest.validate_asset_name(args.name)
    zones.validate_zone(args.zone)
    ctx = make_context("character", args, STAGES)

    if not manifest.get_character(ctx.name):
        manifest.upsert_character(name=ctx.name, fields={"status": "init"})

    tags: list[str] = []
    if args.zone:
        tags.append(f"zone:{args.zone}")
    if args.category:
        tags.append(f"category:{args.category}")
    if args.chapter:
        tags.append(f"chapter:{args.chapter}")
    if tags:
        manifest.add_tags(ctx.asset_type, ctx.name, tags)

    generate_4dir_base(ctx)
    add_idle_animation(ctx)
    compile_spritesheet(ctx)
    import_to_godot(ctx)
    print(f"\n[npc_static] {ctx.name} 完成。")


if __name__ == "__main__":
    main()
