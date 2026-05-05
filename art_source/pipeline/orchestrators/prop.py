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
from orchestrators._common import (
    StageContext,
    make_context,
    stage,
)


STAGES: list[str] = ["generate_object", "chroma_key"]


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
        "--review-mode", choices=["none", "stage", "step"], default="stage"
    )
    p.add_argument("--resume-from", default=None)
    p.add_argument("--force-restart-stage", action="append", default=[])
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
        object_id = plab.submit_map_object(
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
        object_id = plab.submit_iso_tile(
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

    meta = plab.wait_for_object(token, object_id)
    if not plab.download_object_image(token, meta, img_path):
        raise SystemExit(f"無法解析 image 欄位 — 見 {img_path.parent}/raw_response.json")
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


def main() -> None:
    plab.setup_console()
    args = parse_args()
    ctx = make_context("object", args, STAGES)

    if not manifest.get_object(ctx.name):
        manifest.upsert_object(name=ctx.name, fields={"status": "init"})

    generate_object(ctx)
    chroma_key(ctx)
    print(f"\n[prop:{args.kind}] {ctx.name} 完成。")


if __name__ == "__main__":
    main()
