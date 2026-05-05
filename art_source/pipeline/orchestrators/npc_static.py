"""Pipeline 3: Static NPC orchestrator(劇情背景 NPC,4 向 idle)。

Stages:
  1. generate_4dir_base   — create-character(4-dir 或 8-dir,看 --directions)
  2. add_idle_animation   — animate-character 4 向 idle(可 --no-idle 關)
  3. compile_spritesheet  — 呼叫 scripts/generate_spritesheet.py

CLI:
  uv run python art_source/pipeline/orchestrators/npc_static.py \\
      --name shopkeeper_li \\
      --description "elderly taiwanese male shopkeeper, blue shirt" \\
      [--directions 4] [--no-idle] [--review-mode stage]
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
from orchestrators._common import StageContext, make_context, stage


CARDINAL_DIRECTIONS: list[str] = ["south", "east", "north", "west"]
STAGES: list[str] = ["generate_4dir_base", "add_idle_animation", "compile_spritesheet"]


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
        "--review-mode", choices=["none", "stage", "step"], default="stage"
    )
    p.add_argument("--resume-from", default=None)
    p.add_argument("--force-restart-stage", action="append", default=[])
    return p.parse_args()


@stage("generate_4dir_base")
def generate_4dir_base(ctx: StageContext) -> list[str]:
    args = ctx.args
    assert args is not None
    if not args.description:
        raise SystemExit("首次跑須提供 --description")

    token = plab.load_token()
    if args.directions == 4:
        char_id = plab.submit_character_4dir(
            token=token, description=args.description,
            view=args.view, proportions_preset=args.proportions,
        )
    else:
        char_id = plab.submit_character_8dir(
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
    if args.no_idle:
        print("--no-idle 指定,略過 idle 動畫")
        return []

    char = manifest.get_character(ctx.name)
    assert char is not None
    char_id: str = char["character_id"]
    token = plab.load_token()

    submitted = plab.submit_character_animation(
        token=token,
        character_id=char_id,
        action_description="idle",
        directions=CARDINAL_DIRECTIONS,
        frame_count=args.idle_frame_count,
    )
    saved_paths: list[str] = []
    for direction, job_id in zip(submitted["directions"], submitted["background_job_ids"]):
        result = plab.poll_background_job(token, job_id)
        images = result.get("images") or []
        anim_dir = manifest.character_dir(ctx.name) / "animations" / "idle" / direction
        anim_dir.mkdir(parents=True, exist_ok=True)
        for i, item in enumerate(images):
            b64 = item.get("base64") if isinstance(item, dict) else item
            img = plab.b64_to_img(b64)
            img = pp.chroma_key_bg(img)
            frame_path = anim_dir / f"frame_{i:03d}.png"
            img.save(frame_path)
            saved_paths.append(str(frame_path.relative_to(plab.project_root())))

    animations = char.get("animations", {})
    animations.setdefault("idle", [])
    for d in submitted["directions"]:
        if d not in animations["idle"]:
            animations["idle"].append(d)
    manifest.upsert_character(name=ctx.name, fields={"animations": animations})
    return saved_paths


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

    generate_4dir_base(ctx)
    add_idle_animation(ctx)
    compile_spritesheet(ctx)
    print(f"\n[npc_static] {ctx.name} 完成。")


if __name__ == "__main__":
    main()
