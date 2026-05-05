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


ReviewMode = Literal["none", "stage", "step"]


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


def stage(stage_name: str) -> Callable[[Callable[..., list[str]]], Callable[..., None]]:
    """裝飾器:把一個函式登錄為 pipeline stage。

    被裝飾函式:
      - 接受 ctx: StageContext
      - 回傳 list[str](該 stage 產出的檔案路徑)

    框架負責:
      - skip_set 中的 stage 直接跳過(已 resume)
      - 已在 manifest 完成且不在 force_restart 的 stage 直接跳過
      - 跑完寫入 manifest.mark_stage
      - review_mode == "stage" 跑完印路徑後 sys.exit(0)
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

            if ctx.review_mode == "stage":
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
        choices=["none", "stage", "step"],
        default="stage",
        help="none=一路到底;stage=每階段停;step=每 API 呼叫停",
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
