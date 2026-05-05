"""Pipeline 4: Moving NPC orchestrator(player + 移動 NPC)。

Stages:
  1. generate_8dir_base   — create-character-with-8-directions
  2. add_idle_animation   — animate-character 4 向 idle
  3. add_walk_animation   — animate-character 8 向 walk
  4. compile_spritesheet  — 呼叫 scripts/generate_spritesheet.py

CLI:
  uv run python art_source/pipeline/orchestrators/npc_moving.py \
      --name chen_ayi \
      --description "middle-aged taiwanese market vendor woman, red floral shirt" \
      [--review-mode stage]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import manifest
import pixellab_client as plab
import post_process as pp
from orchestrators._common import (
    ALL_8_DIRECTIONS,
    CARDINAL_DIRECTIONS,
    StageContext,
    make_context,
    run_character_animation,
    stage,
)


STAGES: list[str] = [
    "generate_8dir_base",
    "add_idle_animation",
    "add_walk_animation",
    "compile_spritesheet",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--name", required=True)
    p.add_argument("--description", default=None)
    p.add_argument("--view", default="high_top_down")
    p.add_argument("--proportions", default="cartoon")
    p.add_argument("--idle-frame-count", type=int, default=4)
    p.add_argument("--walk-frame-count", type=int, default=8)
    p.add_argument(
        "--review-mode", choices=["none", "stage", "step"], default="stage"
    )
    p.add_argument("--resume-from", default=None)
    p.add_argument("--force-restart-stage", action="append", default=[])
    return p.parse_args()


@stage("generate_8dir_base")
def generate_8dir_base(ctx: StageContext) -> list[str]:
    args = ctx.args
    assert args is not None
    if not args.description:
        raise SystemExit("首次跑須提供 --description")

    token = plab.load_token()
    char_id = plab.submit_character_8dir(
        token=token, description=args.description,
        view=args.view, proportions_preset=args.proportions,
    )
    manifest.upsert_character(
        name=ctx.name,
        fields={
            "character_id": char_id,
            "preset": "player",
            "directions": 8,
            "view": args.view,
            "proportions": args.proportions,
            "description": args.description,
            "status": "pending",
        },
    )
    plab.wait_for_character(token, char_id)
    out_dir = manifest.character_dir(ctx.name) / "rotations"
    saved = plab.download_character_rotations(token, char_id, out_dir)
    for p in saved.values():
        pp.chroma_key_file(p)
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
    return run_character_animation(ctx, "idle", CARDINAL_DIRECTIONS, args.idle_frame_count)


@stage("add_walk_animation")
def add_walk_animation(ctx: StageContext) -> list[str]:
    args = ctx.args
    assert args is not None
    return run_character_animation(ctx, "walk", ALL_8_DIRECTIONS, args.walk_frame_count)


@stage("compile_spritesheet")
def compile_spritesheet(ctx: StageContext) -> list[str]:
    char_dir = manifest.character_dir(ctx.name)
    script = plab.project_root() / "scripts" / "generate_spritesheet.py"
    if not script.exists():
        print(f"[warn] {script} 不存在,略過 spritesheet 編譯")
        return []
    cmd = ["uv", "run", "python", str(script), "--character-dir", str(char_dir)]
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    return [str(char_dir.relative_to(plab.project_root()))]


def main() -> None:
    plab.setup_console()
    args = parse_args()
    ctx = make_context("character", args, STAGES)

    if not manifest.get_character(ctx.name):
        manifest.upsert_character(name=ctx.name, fields={"status": "init"})

    generate_8dir_base(ctx)
    add_idle_animation(ctx)
    add_walk_animation(ctx)
    compile_spritesheet(ctx)
    print(f"\n[npc_moving] {ctx.name} 完成。")


if __name__ == "__main__":
    main()
