"""Tests for orchestrator stage framework."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "art_source" / "pipeline")
)

import manifest
from orchestrators import _common as oc


def _ctx(tmp_path: Path) -> oc.StageContext:
    return oc.StageContext(
        asset_type="character",
        name="test_npc",
        review_mode="none",
        resume_from=None,
        skip_set=set(),
        force_restart=set(),
    )


def test_stage_runs_when_review_mode_none(
    isolated_manifest: Path, tmp_path: Path
) -> None:
    manifest.upsert_character("test_npc", {"character_id": "id"})
    calls: list[str] = []

    @oc.stage("first")
    def first_stage(ctx: oc.StageContext) -> list[str]:
        calls.append("first")
        return ["p1"]

    ctx = _ctx(tmp_path)
    first_stage(ctx)
    assert calls == ["first"]
    assert "first" in manifest.get_completed_stages("character", "test_npc")


def test_stage_skips_when_completed_and_no_force(
    isolated_manifest: Path, tmp_path: Path
) -> None:
    manifest.upsert_character("test_npc", {"character_id": "id"})
    manifest.mark_stage("character", "test_npc", "first", ["existing"])

    calls: list[str] = []

    @oc.stage("first")
    def first_stage(ctx: oc.StageContext) -> list[str]:
        calls.append("first")
        return ["new"]

    ctx = _ctx(tmp_path)
    first_stage(ctx)
    assert calls == [], "已完成 stage 不應重跑"


def test_stage_reruns_when_in_force_restart(
    isolated_manifest: Path, tmp_path: Path
) -> None:
    manifest.upsert_character("test_npc", {"character_id": "id"})
    manifest.mark_stage("character", "test_npc", "first", ["old"])

    calls: list[str] = []

    @oc.stage("first")
    def first_stage(ctx: oc.StageContext) -> list[str]:
        calls.append("first")
        return ["new"]

    ctx = _ctx(tmp_path)
    ctx.force_restart = {"first"}
    first_stage(ctx)
    assert calls == ["first"]


def test_stage_exits_after_run_when_review_mode_stage(
    isolated_manifest: Path, tmp_path: Path
) -> None:
    manifest.upsert_character("test_npc", {"character_id": "id"})

    @oc.stage("only")
    def only_stage(ctx: oc.StageContext) -> list[str]:
        return ["p"]

    ctx = _ctx(tmp_path)
    ctx.review_mode = "stage"
    with pytest.raises(SystemExit) as exc:
        only_stage(ctx)
    assert exc.value.code == 0


def test_resume_from_skips_earlier_stages(
    isolated_manifest: Path, tmp_path: Path
) -> None:
    manifest.upsert_character("test_npc", {"character_id": "id"})
    calls: list[str] = []

    @oc.stage("a")
    def a(ctx: oc.StageContext) -> list[str]:
        calls.append("a"); return []

    @oc.stage("b")
    def b(ctx: oc.StageContext) -> list[str]:
        calls.append("b"); return []

    ctx = _ctx(tmp_path)
    ctx.skip_set = {"a"}  # resume_from=b 解析後的結果
    a(ctx)
    b(ctx)
    assert calls == ["b"]


def test_compute_skip_set_from_resume_from() -> None:
    skip = oc.compute_skip_set(
        all_stages=["a", "b", "c"], resume_from="b"
    )
    assert skip == {"a"}


def test_compute_skip_set_unknown_resume_raises() -> None:
    with pytest.raises(ValueError, match="unknown stage"):
        oc.compute_skip_set(all_stages=["a", "b"], resume_from="zzz")


def test_parse_common_args_defaults() -> None:
    ns = oc.parse_common_args(["--name", "alice"])
    assert ns.name == "alice"
    assert ns.review_mode == "stage"
    assert ns.resume_from is None
    assert ns.force_restart_stage == []
