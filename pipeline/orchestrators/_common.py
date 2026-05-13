"""Shared stage framework for art pipeline orchestrators.

提供:
  - @stage 裝飾器:自動讀已完成 stage、寫入完成記錄、按 review-mode 暫停
  - parse_common_args:統一 CLI 介面
  - StageContext:跨 stage 傳遞狀態的 dataclass
  - compute_skip_set:把 --resume-from 轉成要跳過的 stage 集合
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Literal

import manifest


ReviewMode = Literal["none", "stage"]


@dataclass
class StageContext:
    asset_type: str  # "character" | "tileset" | "object"
    name: str
    review_mode: ReviewMode
    resume_from: str | None
    skip_set: set[str]
    force_restart: set[str]
    args: argparse.Namespace | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def stage(
    stage_name: str, *, is_last: bool = False
) -> Callable[[Callable[..., list[str]]], Callable[..., None]]:
    """裝飾器:把一個函式登錄為 pipeline stage。

    被裝飾函式:
      - 接受 ctx: StageContext
      - 回傳 list[str](該 stage 產出的檔案路徑)

    參數:
      - is_last: 標記此 stage 為 pipeline 最後一個。review_mode=="stage"
        時,最後一個 stage 跑完不暫停也不印 resume 提示(因無下一階段)。

    框架負責:
      - skip_set 中的 stage 直接跳過(已 resume;優先於 force_restart)
      - 已在 manifest 完成且不在 force_restart 的 stage 直接跳過
      - 跑完寫入 manifest.mark_stage
      - review_mode == "stage" 且非最後一階段:跑完印路徑後 sys.exit(0)
    """
    def decorator(fn: Callable[..., list[str]]) -> Callable[..., None]:
        @wraps(fn)
        def wrapper(ctx: StageContext) -> None:
            if stage_name in ctx.skip_set:
                print(f"[skip] {stage_name}(resume-from)")
                return
            completed = manifest.get_completed_stages(ctx.asset_type, ctx.name)
            if stage_name in completed and stage_name not in ctx.force_restart:
                print(f"[skip] {stage_name}(已完成於 manifest)")
                return

            print(f"[run]  {stage_name} ...")
            paths = fn(ctx)
            manifest.mark_stage(ctx.asset_type, ctx.name, stage_name, paths)
            print(f"[done] {stage_name} → {paths}")

            if ctx.review_mode == "stage" and not is_last:
                print(
                    f"\n--- review-mode=stage:於 {stage_name} 暫停 ---\n"
                    f"檢視產出後,以 --resume-from <next-stage> 繼續。"
                )
                sys.exit(0)
        return wrapper
    return decorator


def compute_skip_set(all_stages: list[str], resume_from: str | None) -> set[str]:
    """把 --resume-from 轉成要跳過的 stage 集合。

    resume_from=None → 空集合
    resume_from="b" with all_stages=["a","b","c"] → {"a"}
    """
    if resume_from is None:
        return set()
    if resume_from not in all_stages:
        raise ValueError(
            f"unknown stage '{resume_from}';available: {all_stages}"
        )
    idx = all_stages.index(resume_from)
    return set(all_stages[:idx])


def parse_common_args(argv: list[str] | None = None) -> argparse.Namespace:
    """共用 CLI 參數解析。Pipeline 自身可在呼叫前先 add_argument 自家專屬。"""
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--name", required=True, help="資產名(manifest key)")
    parser.add_argument(
        "--review-mode",
        choices=["none", "stage"],
        default="stage",
        help="none=一路到底;stage=每階段停",
    )
    parser.add_argument(
        "--resume-from", default=None, help="從指定 stage 起跑,前面 stage 跳過"
    )
    parser.add_argument(
        "--force-restart-stage",
        action="append",
        default=[],
        help="強制重跑某 stage(可多次指定)",
    )
    return parser.parse_args(argv)


def make_context(
    asset_type: str,
    args: argparse.Namespace,
    all_stages: list[str],
) -> StageContext:
    """從 parsed args 建 StageContext。"""
    return StageContext(
        asset_type=asset_type,
        name=args.name,
        review_mode=args.review_mode,
        resume_from=args.resume_from,
        skip_set=compute_skip_set(all_stages, args.resume_from),
        force_restart=set(args.force_restart_stage),
        args=args,
    )


CARDINAL_DIRECTIONS: list[str] = ["south", "east", "north", "west"]
ALL_8_DIRECTIONS: list[str] = [
    "south", "south-east", "east", "north-east",
    "north", "north-west", "west", "south-west",
]


def run_character_animation_template(
    ctx: StageContext,
    action: str,
    *,
    override_template_id: str | None = None,
    only_directions: list[str] | None = None,
    isometric: bool = False,
) -> list[str]:
    """Run an animation stage in TEMPLATE mode (Pixellab skeleton-driven).

    This is the **preferred** entry point for stock actions like idle/walk/
    running — it always sends `mode=template` + `template_animation_id`,
    never v3 + prompt. Stable, predictable, 1 gen/direction (cheap).

    `action`: key into pipeline.animation_templates.DEFAULT_TEMPLATES.
    `override_template_id`: swap the default template (e.g., user passed
        --walk-template-id walking-4-frames). Directions/frame_count stay
        from registry.
    """
    # Lazy import: animation_templates is light, but keeping import surface
    # consistent with the other lazy imports in run_character_animation.
    import animation_templates as at
    cfg = at.get_template(action, override_template_id=override_template_id)
    return run_character_animation(
        ctx, action, cfg.directions, cfg.frame_count,
        stage_name=f"add_{action}_animation",
        only_directions=only_directions,
        isometric=isometric,
        template_animation_id=cfg.template_id,
    )


def run_character_animation(
    ctx: StageContext,
    action: str,
    directions: list[str],
    frame_count: int,
    *,
    stage_name: str | None = None,
    only_directions: list[str] | None = None,
    isometric: bool = False,
    template_animation_id: str | None = None,
) -> list[str]:
    """執行 character animation:submit job → poll 每方向 → 存 frame → 寫 manifest。

    Two paths:
      - **v3 (default)**: action_description from manifest prompt or `action` arg
      - **template**: pass `template_animation_id` (e.g. "breathing-idle"). Skeleton-
        based, more stable than v3 for stock motions, 1 gen/direction (cheaper).
        action_description still sent (some templates accept it as flavoring).
    """
    # Lazy import: pixellab_client 拉很多 transitive deps,放 module 頂層
    # 會讓 _common 的 import 變重;且 post_process 也是業務模組。
    import pixellab_client as plab
    import post_process as pp

    char = manifest.get_character(ctx.name)
    assert char is not None
    char_id: str = char["character_id"]
    token = plab.load_token()

    # Template mode: skeleton brings its own motion description. Skip ALL
    # action_description plumbing including pre-seeded manifest prompts —
    # those are written for v3's anti-drift workaround and Pixellab will
    # silently downgrade to v3 if action_description sneaks in.
    action_description: str | None = None
    if not template_animation_id:
        action_description = action
        if stage_name is not None:
            from_manifest = manifest.get_prompt(ctx.asset_type, ctx.name, stage_name)
            if from_manifest:
                action_description = from_manifest

    effective_directions = list(directions)
    if only_directions:
        wanted = set(only_directions)
        effective_directions = [d for d in directions if d in wanted]
        if not effective_directions:
            raise SystemExit(
                f"--only-directions {sorted(wanted)} 與此 stage 預設方向 "
                f"{directions} 沒交集,沒事可做"
            )
        print(f"[partial] regenerating only directions: {effective_directions}")

    submitted = plab.submit_character_animation(
        token=token,
        character_id=char_id,
        action_description=action_description,
        directions=effective_directions,
        frame_count=frame_count,
        isometric=isometric,
        template_animation_id=template_animation_id,
    )

    # New flow: paste frames directly into the per-character spritesheet
    # (no `frame_NNN.png` sprawl). The sheet + atlas JSON is the source of
    # truth; `compile_spritesheet` is now a no-op verification step.
    import spritesheet  # local: keep top-level deps light
    char_dir = manifest.character_dir(ctx.name)
    sheet, atlas = spritesheet.load_or_init_sheet(char_dir)

    for direction, job_id in zip(submitted["directions"], submitted["background_job_ids"]):
        result = plab.poll_background_job(token, job_id)
        items = result.get("images") or []
        frames: list = []
        for i, item in enumerate(items):
            img = plab._decode_image_entry(item)
            if img is None:
                raise RuntimeError(
                    f"animation frame {direction}/{i} failed to decode "
                    f"(item type={type(item).__name__}, keys={list(item.keys()) if isinstance(item, dict) else 'n/a'})"
                )
            frames.append(pp.chroma_key_bg(img))
        sheet, atlas = spritesheet.write_animation_frames(
            sheet, atlas, action, direction, frames,
        )

    sheet_png, sheet_json = spritesheet.save_sheet(char_dir, sheet, atlas)

    animations = char.get("animations", {})
    animations.setdefault(action, [])
    for d in submitted["directions"]:
        if d not in animations[action]:
            animations[action].append(d)
    manifest.upsert_character(name=ctx.name, fields={"animations": animations})

    root = plab.project_root()
    return [
        str(sheet_png.relative_to(root)),
        str(sheet_json.relative_to(root)),
    ]
