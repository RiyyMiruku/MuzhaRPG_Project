"""
MuzhaRPG 專屬 Pixellab MCP Server。

定位：讓 Claude Code 能直接用「角色名稱」操作美術資產，背後委派給 Pixellab v2 API。
- 從 .env 讀 token（不需系統環境變數）
- 自動下載、後處理（去背 / iso 投影）、寫 manifest
- 暴露 8 個專案特化工具，比官方 MCP 的 28 個工具精簡

啟動：透過 stdio。.mcp.json:
  {
    "mcpServers": {
      "muzharpg-pixellab": {
        "type": "stdio",
        "command": "uv",
        "args": ["run", "python", "art_source/pipeline/mcp_server.py"]
      }
    }
  }
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

import manifest
import pixellab_client as plab
import post_process as pp


mcp: FastMCP = FastMCP("muzharpg-pixellab")


# === Character ===


@mcp.tool()
def create_character(
    name: str,
    description: str,
    preset: str = "npc",
    size: int = 64,
    view: str = "high_top_down",
    proportions: str = "cartoon",
) -> dict[str, Any]:
    """產生 8 方向角色 sprite（用 Pixellab v2 create-character）。

    完成後自動：(1) 等待 Pixellab 後端生成完成（async, 數分鐘到 30 分）
    (2) 下載 8 張 rotation PNG (3) 寫 manifest (4) 回傳路徑與 character_id。

    參數：
      name: 專案內角色名（如 "chen_ayi"）— 用於資料夾命名與 manifest key
      description: 外觀描述（不必含視角／風格 — server 會補）
      preset: "npc"（4 方向 idle）或 "player"（8 方向 idle+walk，後續用 animate_character 補動畫）
      size: 請求尺寸 hint（mannequin template 可能強制 92×92）
      view: "low_top_down" | "high_top_down" | "side"
      proportions: "default" | "chibi" | "cartoon" | "stylized" | "realistic_male" | "realistic_female" | "heroic"
    """
    if manifest.get_character(name):
        return {
            "status": "exists",
            "message": f"角色 '{name}' 已存在於 manifest；先 delete_asset 才能重建",
            "character": manifest.get_character(name),
        }

    token: str = plab.load_token()
    char_id: str = plab.submit_character_8dir(
        token=token,
        description=description,
        size=size,
        view=view,
        proportions_preset=proportions,
    )

    # 先寫 manifest 記錄 pending 狀態（即使後續失敗也能查回 character_id）
    manifest.upsert_character(
        name=name,
        fields={
            "character_id": char_id,
            "preset": preset,
            "view": view,
            "proportions": proportions,
            "description": description,
            "status": "pending",
        },
    )

    plab.wait_for_character(token, char_id)

    out_dir: Path = manifest.character_dir(name) / "rotations"
    saved: dict[str, Path] = plab.download_character_rotations(token, char_id, out_dir)

    # 後處理：可能有去背問題，補上
    for p in saved.values():
        pp.chroma_key_file(p)

    meta: dict[str, Any] = plab.get_character(token, char_id)
    manifest.upsert_character(
        name=name,
        fields={
            "status": "completed",
            "size": meta.get("size", {}),
            "rotations": list(saved.keys()),
            "local_path": str(manifest.character_dir(name).relative_to(plab.project_root())),
        },
    )

    return {
        "status": "completed",
        "name": name,
        "character_id": char_id,
        "rotations": [str(p.relative_to(plab.project_root())) for p in saved.values()],
        "size": meta.get("size", {}),
    }


@mcp.tool()
def animate_character(
    name: str,
    action: str,
    directions: list[str] | None = None,
    frame_count: int = 8,
) -> dict[str, Any]:
    """為既有角色產生動畫 frames。

    從 manifest 查 character_id，呼叫 Pixellab v2 animate-character (mode=v3)。
    每個 direction 是一個獨立 background job，server 會等全部完成、下載 frames。

    參數：
      name: 既有角色名（必須先 create_character 過）
      action: 動作描述（如 "walk", "idle", "wave hand"）
      directions: 要產生哪些方向（預設 None = 全部 8 向）
      frame_count: 每個方向的 frame 數（4-16）
    """
    char: dict[str, Any] | None = manifest.get_character(name)
    if not char:
        return {"status": "error", "message": f"角色 '{name}' 不存在 — 先用 create_character 建立"}

    char_id: str = char["character_id"]
    token: str = plab.load_token()

    submitted: dict[str, Any] = plab.submit_character_animation(
        token=token,
        character_id=char_id,
        action_description=action,
        directions=directions,
        frame_count=frame_count,
    )
    job_ids: list[str] = submitted["background_job_ids"]
    dirs: list[str] = submitted["directions"]

    # 等待每個方向的 job 完成
    saved_per_dir: dict[str, list[str]] = {}
    for direction, job_id in zip(dirs, job_ids):
        result: dict[str, Any] = plab.poll_background_job(token, job_id)
        images: Any = result.get("images") or []

        anim_dir: Path = manifest.character_dir(name) / "animations" / action / direction
        anim_dir.mkdir(parents=True, exist_ok=True)
        saved_paths: list[str] = []
        for i, item in enumerate(images):
            b64: str = item.get("base64") if isinstance(item, dict) else item
            img = plab.b64_to_img(b64)
            img = pp.chroma_key_bg(img)
            frame_path: Path = anim_dir / f"frame_{i:03d}.png"
            img.save(frame_path)
            saved_paths.append(str(frame_path.relative_to(plab.project_root())))
        saved_per_dir[direction] = saved_paths

    # 更新 manifest
    animations: dict[str, list[str]] = char.get("animations", {})
    animations.setdefault(action, [])
    for d in dirs:
        if d not in animations[action]:
            animations[action].append(d)
    manifest.upsert_character(name=name, fields={"animations": animations})

    return {
        "status": "completed",
        "name": name,
        "action": action,
        "directions": dirs,
        "frame_count": frame_count,
        "saved": saved_per_dir,
    }


@mcp.tool()
def get_character_status(name: str) -> dict[str, Any]:
    """查角色目前狀態（manifest 紀錄，不打 API）。"""
    char: dict[str, Any] | None = manifest.get_character(name)
    if not char:
        return {"status": "not_found", "name": name}
    return {"status": "found", "name": name, **char}


# === Autotile ===


@mcp.tool()
def create_autotile(
    name: str,
    lower_description: str,
    upper_description: str,
    transition_size: float = 0.0,
    transition_description: str | None = None,
    tile_size: int = 16,
    project_to_iso: bool = True,
) -> dict[str, Any]:
    """產生 16-tile Wang autotile（top-down）+ 自動投影成 iso atlas。

    輸出兩個檔案：
      <name>_topdown.png — 4×4 atlas，原始 top-down，給保留 top-down 視角時用
      <name>_iso.png      — 同 atlas 經 PIL 投影成菱形（若 project_to_iso=True）

    參數：
      name: 專案內 tileset 名（如 "market_grass_asphalt"）
      lower_description: 下層地形（例 "green grass texture"）
      upper_description: 上層地形（例 "dark asphalt road"）
      transition_size: 0.0 / 0.25 / 0.5（邊緣過渡寬度）
      transition_description: 邊緣細節（例 "grey concrete curb"）
      tile_size: 每格邊長（預設 16）
      project_to_iso: 是否同時輸出 iso 投影版（預設 True）
    """
    if manifest.get_tileset(name):
        return {
            "status": "exists",
            "message": f"tileset '{name}' 已存在於 manifest",
            "tileset": manifest.get_tileset(name),
        }

    token: str = plab.load_token()
    tileset_id: str = plab.submit_topdown_tileset(
        token=token,
        lower_description=lower_description,
        upper_description=upper_description,
        transition_size=transition_size,
        transition_description=transition_description,
        tile_width=tile_size,
        tile_height=tile_size,
    )

    manifest.upsert_tileset(
        name=name,
        fields={
            "tileset_id": tileset_id,
            "lower": lower_description,
            "upper": upper_description,
            "tile_size": tile_size,
            "status": "pending",
        },
    )

    meta: dict[str, Any] = plab.wait_for_tileset(token, tileset_id)

    out_dir: Path = manifest.tileset_dir(name)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 拿 atlas 圖（API 結構不確定，依 image / image_url / tiles 嘗試）
    atlas_path: Path = out_dir / f"{name}_topdown.png"
    atlas_field: Any = meta.get("image") or meta.get("atlas") or meta.get("image_url")
    if isinstance(atlas_field, dict):
        b64 = atlas_field.get("base64")
        plab.b64_to_img(b64).save(atlas_path)
    elif isinstance(atlas_field, str) and atlas_field.startswith("http"):
        import requests
        r = requests.get(atlas_field, headers={"Authorization": f"Bearer {token}"}, timeout=60)
        atlas_path.write_bytes(r.content)
    else:
        # 無法解析 — 把整個 meta 寫出來方便 debug
        (out_dir / "raw_response.json").write_text(str(meta), encoding="utf-8")
        return {
            "status": "error",
            "message": "無法解析 tileset 圖片欄位 — raw response 已存於 raw_response.json",
            "tileset_id": tileset_id,
        }

    iso_path: Path | None = None
    if project_to_iso:
        iso_path = out_dir / f"{name}_iso.png"
        pp.project_atlas_file(atlas_path, iso_path, cols=4, rows=4)

    manifest.upsert_tileset(
        name=name,
        fields={
            "status": "completed",
            "topdown_path": str(atlas_path.relative_to(plab.project_root())),
            "iso_path": str(iso_path.relative_to(plab.project_root())) if iso_path else None,
        },
    )

    return {
        "status": "completed",
        "name": name,
        "tileset_id": tileset_id,
        "topdown_path": str(atlas_path.relative_to(plab.project_root())),
        "iso_path": str(iso_path.relative_to(plab.project_root())) if iso_path else None,
    }


# === Building / Prop ===


@mcp.tool()
def create_building(
    name: str,
    description: str,
    width: int = 96,
    height: int = 96,
    view: str = "high_top_down",
) -> dict[str, Any]:
    """產生靜態 map object（建築、攤位、燈籠等）。

    使用 Pixellab v2 create-map-object 端點，原生透明背景。

    參數：
      name: 物件名（如 "muzha_shophouse"）
      description: 外觀描述
      width / height: 圖片尺寸（建議 64-128）
      view: "high_top_down"（接近 iso）或 "low_top_down"
    """
    if manifest.get_object(name):
        return {
            "status": "exists",
            "message": f"object '{name}' 已存在",
            "object": manifest.get_object(name),
        }

    token: str = plab.load_token()
    object_id: str = plab.submit_map_object(
        token=token,
        description=description,
        width=width,
        height=height,
        view=view,
    )

    manifest.upsert_object(
        name=name,
        fields={
            "object_id": object_id,
            "description": description,
            "view": view,
            "size": {"width": width, "height": height},
            "status": "pending",
        },
    )

    meta: dict[str, Any] = plab.wait_for_object(token, object_id)

    out_dir: Path = manifest.object_dir(name)
    out_dir.mkdir(parents=True, exist_ok=True)
    img_path: Path = out_dir / f"{name}.png"

    img_field: Any = meta.get("image") or meta.get("image_url")
    if isinstance(img_field, dict):
        plab.b64_to_img(img_field.get("base64", "")).save(img_path)
    elif isinstance(img_field, str) and img_field.startswith("http"):
        import requests
        r = requests.get(img_field, headers={"Authorization": f"Bearer {token}"}, timeout=60)
        img_path.write_bytes(r.content)
    else:
        (out_dir / "raw_response.json").write_text(str(meta), encoding="utf-8")
        return {
            "status": "error",
            "message": "無法解析 object 圖片欄位",
            "object_id": object_id,
        }

    pp.chroma_key_file(img_path)

    manifest.upsert_object(
        name=name,
        fields={
            "status": "completed",
            "local_path": str(img_path.relative_to(plab.project_root())),
        },
    )

    return {
        "status": "completed",
        "name": name,
        "object_id": object_id,
        "local_path": str(img_path.relative_to(plab.project_root())),
    }


# === 管理工具 ===


@mcp.tool()
def list_assets(asset_type: str = "all") -> dict[str, Any]:
    """列出本地 manifest 中所有資產。

    asset_type: "characters" | "tilesets" | "objects" | "all"
    """
    data: dict[str, Any] = manifest.load()
    if asset_type == "all":
        return {
            "characters": list(data["characters"].keys()),
            "tilesets": list(data["tilesets"].keys()),
            "objects": list(data["objects"].keys()),
            "counts": {
                "characters": len(data["characters"]),
                "tilesets": len(data["tilesets"]),
                "objects": len(data["objects"]),
            },
        }
    if asset_type in ("characters", "tilesets", "objects"):
        return {asset_type: data[asset_type]}
    return {"error": f"未知 asset_type: {asset_type}"}


@mcp.tool()
def delete_asset(name: str, asset_type: str) -> dict[str, Any]:
    """從 manifest 移除資產記錄（不刪 Pixellab 後端的，僅本地 index）。

    要徹底刪除遠端，請另外呼叫 Pixellab Web Console。
    本工具會留下本地檔案不刪（避免誤刪），只移除 manifest entry。
    """
    if asset_type == "character":
        ok = manifest.remove_character(name)
    elif asset_type == "tileset":
        ok = manifest.remove_tileset(name)
    elif asset_type == "object":
        ok = manifest.remove_object(name)
    else:
        return {"status": "error", "message": f"未知 asset_type: {asset_type}"}

    return {
        "status": "removed" if ok else "not_found",
        "name": name,
        "asset_type": asset_type,
        "note": "manifest entry 已移除；本地檔案與 Pixellab 後端資產未動",
    }


# === Entry ===

if __name__ == "__main__":
    mcp.run()
