"""
Pixellab HTTP 客戶端（純底層）。

職責：把 Pixellab API 端點包成純函式，自動處理：
  - .env / 環境變數讀 token
  - 5xx 重試 + exp backoff
  - async job 投遞 + 輪詢
  - base64 ↔ PIL Image 轉換

不做：
  - 業務邏輯（manifest 寫入、檔案命名 — 由 mcp_server 負責）
  - PIL 後處理（chroma_key, iso 投影 — 由 post_process 負責）
"""

from __future__ import annotations

import base64
import io
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from PIL import Image


# === 端點 ===

V1_BASE: str = "https://api.pixellab.ai/v1"
V2_BASE: str = "https://api.pixellab.ai/v2"

PIXFLUX_URL: str = f"{V1_BASE}/generate-image-pixflux"
ROTATE_URL: str = f"{V1_BASE}/rotate"
ANIMATE_TEXT_V3_URL: str = f"{V2_BASE}/animate-with-text-v3"
BACKGROUND_JOBS_URL: str = f"{V2_BASE}/background-jobs"

CREATE_CHAR_8DIR_URL: str = f"{V2_BASE}/create-character-with-8-directions"
CREATE_CHAR_4DIR_URL: str = f"{V2_BASE}/create-character-with-4-directions"
ANIMATE_CHARACTER_URL: str = f"{V2_BASE}/animate-character"
CREATE_TOPDOWN_TILESET_URL: str = f"{V2_BASE}/create-topdown-tileset"
CREATE_MAP_OBJECT_URL: str = f"{V2_BASE}/create-map-object"
CHARACTERS_URL: str = f"{V2_BASE}/characters"
TILESETS_URL: str = f"{V2_BASE}/topdown-tilesets"
OBJECTS_URL: str = f"{V2_BASE}/objects"


# === 端點限制 ===

ROTATE_VALID_SIZES: tuple[int, ...] = (16, 32, 64, 128)
ANIMATE_V3_PIXEL_BUDGET: int = 524_288


# === Token / 路徑 ===


def project_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("找不到 pyproject.toml")


def load_token() -> str:
    """從 .env（透過 python-dotenv）或 process env 讀 PIXELLAB_API_TOKEN。"""
    load_dotenv(project_root() / ".env")
    token: str | None = os.getenv("PIXELLAB_API_TOKEN")
    if not token or token == "your_token_here":
        raise RuntimeError(
            "找不到 PIXELLAB_API_TOKEN — 請設定專案根目錄 .env 或系統環境變數"
        )
    return token


def setup_console() -> None:
    """Windows console UTF-8 修正。"""
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]


# === Image codec ===


def img_to_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def b64_to_img(b64: str) -> Image.Image:
    if b64.startswith("data:"):
        b64 = b64.split(",", 1)[1]
    return Image.open(io.BytesIO(base64.b64decode(b64)))


# === Response 封裝 ===


@dataclass
class PixellabResponse:
    image_field: Any
    metadata: dict[str, Any]
    raw: dict[str, Any]

    def to_image(self) -> Image.Image:
        b64: str
        if isinstance(self.image_field, dict):
            b64 = self.image_field.get("base64") or self.image_field.get("data") or ""
        else:
            b64 = str(self.image_field)
        if not b64:
            raise RuntimeError(f"無法解析單張圖: {self.raw}")
        return b64_to_img(b64)

    def to_frames(self) -> list[Image.Image]:
        if not isinstance(self.image_field, list):
            raise RuntimeError(f"預期多 frame 但收到單張: {type(self.image_field)}")
        out: list[Image.Image] = []
        for item in self.image_field:
            b64 = item.get("base64") if isinstance(item, dict) else item
            out.append(b64_to_img(b64))
        return out


# === HTTP 共用 ===

_RETRY_STATUS: tuple[int, ...] = (500, 502, 503, 504)
_MAX_RETRIES: int = 4
_BACKOFF_BASE: float = 5.0


def _post(token: str, url: str, payload: dict[str, Any]) -> PixellabResponse:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    last_error = ""
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=180)
        except requests.RequestException as e:
            last_error = f"連線錯誤: {e}"
            time.sleep(_BACKOFF_BASE * attempt)
            continue

        if r.status_code == 200:
            data = r.json()
            image_field = data.get("image") or data.get("images")
            metadata = {k: v for k, v in data.items() if k not in ("image", "images")}
            return PixellabResponse(image_field=image_field, metadata=metadata, raw=data)

        if r.status_code in _RETRY_STATUS:
            last_error = f"HTTP {r.status_code}: {r.text[:200]}"
            time.sleep(_BACKOFF_BASE * attempt)
            continue

        raise RuntimeError(f"{url} → HTTP {r.status_code}: {r.text[:500]}")

    raise RuntimeError(f"{url} 重試 {_MAX_RETRIES} 次仍失敗：{last_error}")


def _get(token: str, url: str) -> requests.Response:
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers, timeout=30)
    return r


# === 同步 v1 端點 ===


def call_pixflux(
    token: str,
    description: str,
    width: int,
    height: int,
    seed: int | None = None,
    negative_description: str = "",
    no_background: bool = True,
) -> PixellabResponse:
    payload: dict[str, Any] = {
        "description": description,
        "image_size": {"width": width, "height": height},
        "negative_description": negative_description,
        "no_background": no_background,
        "text_guidance_scale": 8.0,
    }
    if seed is not None:
        payload["seed"] = seed
    return _post(token, PIXFLUX_URL, payload)


def call_rotate(
    token: str,
    from_image: Image.Image,
    from_direction: str,
    to_direction: str,
    size: int = 64,
) -> PixellabResponse:
    if size not in ROTATE_VALID_SIZES:
        raise ValueError(f"rotate size 必須 ∈ {ROTATE_VALID_SIZES}，收到 {size}")
    img = from_image
    if img.size != (size, size):
        img = img.resize((size, size), resample=Image.Resampling.NEAREST)
    payload = {
        "from_image": {"type": "base64", "base64": img_to_b64(img)},
        "image_size": {"width": size, "height": size},
        "from_direction": from_direction,
        "to_direction": to_direction,
    }
    return _post(token, ROTATE_URL, payload)


# === Async (v2) ===

_POLL_INTERVAL: float = 5.0
_POLL_MAX_WAIT: float = 1800.0  # 30 分鐘


def poll_background_job(
    token: str,
    job_id: str,
    poll_interval: float = _POLL_INTERVAL,
    max_wait: float = _POLL_MAX_WAIT,
    on_status: Any = None,
) -> dict[str, Any]:
    """輪詢直到完成；回傳 last_response。on_status(elapsed, status) 可作 callback。"""
    poll_url = f"{BACKGROUND_JOBS_URL}/{job_id}"
    deadline = time.time() + max_wait
    last_status = ""
    started = time.time()
    while time.time() < deadline:
        time.sleep(poll_interval)
        try:
            r = _get(token, poll_url)
        except requests.RequestException:
            continue
        if r.status_code != 200:
            raise RuntimeError(f"poll {job_id} → HTTP {r.status_code}: {r.text[:200]}")
        data = r.json()
        status = data.get("status", "unknown")
        if status != last_status:
            elapsed = time.time() - started
            if on_status:
                on_status(elapsed, status)
            last_status = status
        if status == "completed":
            return data.get("last_response") or data.get("response") or data
        if status == "failed":
            raise RuntimeError(f"job {job_id} 失敗: {data}")
    raise TimeoutError(f"job {job_id} 超過 {max_wait}s 未完成")


def _post_async(
    token: str, url: str, payload: dict[str, Any]
) -> PixellabResponse:
    """投遞 + 輪詢直到完成。回傳 PixellabResponse。"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"submit {url} → HTTP {r.status_code}: {r.text[:500]}")
    data = r.json()
    job_id = data.get("background_job_id") or data.get("job_id") or data.get("id")
    if not job_id:
        raise RuntimeError(f"submit 回應無 job id: {data}")
    result = poll_background_job(token, job_id)
    image_field = result.get("images") or result.get("image")
    metadata = {k: v for k, v in result.items() if k not in ("images", "image")}
    metadata["job_id"] = job_id
    return PixellabResponse(image_field=image_field, metadata=metadata, raw=result)


def call_animate_with_text_v3(
    token: str,
    first_frame: Image.Image,
    action: str,
    frame_count: int = 8,
    size: int = 64,
    no_background: bool = True,
) -> PixellabResponse:
    if not (4 <= frame_count <= 16):
        raise ValueError(f"frame_count 必須 4-16，收到 {frame_count}")
    if size * size * frame_count > ANIMATE_V3_PIXEL_BUDGET:
        raise ValueError(f"像素預算超過 {ANIMATE_V3_PIXEL_BUDGET}")
    img = first_frame
    if img.size != (size, size):
        img = img.resize((size, size), resample=Image.Resampling.NEAREST)
    payload = {
        "first_frame": {"type": "base64", "base64": img_to_b64(img)},
        "action": action,
        "frame_count": frame_count,
        "no_background": no_background,
    }
    return _post_async(token, ANIMATE_TEXT_V3_URL, payload)


# === Character Creator ===


def submit_character_8dir(
    token: str,
    description: str,
    size: int = 64,
    view: str = "high_top_down",
    mode: str = "standard",
    proportions_preset: str = "cartoon",
    outline: str | None = "single_color_outline",
    shading: str | None = "medium_shading",
    detail: str | None = "detailed",
    text_guidance_scale: float = 8.0,
) -> str:
    """提交建角色，回傳 character_id；不等完成（需另外 poll）。"""
    if view not in ("low_top_down", "high_top_down", "side"):
        raise ValueError(f"view 必須 low_top_down/high_top_down/side，收到 {view}")
    payload: dict[str, Any] = {
        "description": description,
        "image_size": {"width": size, "height": size},
        "view": view,
        "mode": mode,
        "proportions": {"type": "preset", "name": proportions_preset},
        "text_guidance_scale": text_guidance_scale,
    }
    if outline:
        payload["outline"] = outline
    if shading:
        payload["shading"] = shading
    if detail:
        payload["detail"] = detail

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.post(CREATE_CHAR_8DIR_URL, headers=headers, json=payload, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"create-character-8dir → HTTP {r.status_code}: {r.text[:500]}")
    char_id = r.json().get("character_id", "")
    if not char_id:
        raise RuntimeError(f"回應無 character_id: {r.json()}")
    return char_id


def wait_for_character(
    token: str, character_id: str, timeout_sec: float = 1800.0, poll_interval: float = 15.0
) -> None:
    """輪詢 /characters/{id}/zip 直到 200。"""
    url = f"{CHARACTERS_URL}/{character_id}/zip"
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        r = _get(token, url)
        if r.status_code == 200:
            return
        if r.status_code == 423:
            time.sleep(poll_interval)
            continue
        raise RuntimeError(f"wait_for_character → HTTP {r.status_code}: {r.text[:200]}")
    raise TimeoutError(f"character {character_id} 等 {timeout_sec}s 未完成")


def get_character(token: str, character_id: str) -> dict[str, Any]:
    r = _get(token, f"{CHARACTERS_URL}/{character_id}")
    if r.status_code != 200:
        raise RuntimeError(f"get character → HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


def download_character_rotations(
    token: str, character_id: str, output_dir: Path
) -> dict[str, Path]:
    """下載 rotation_urls 中所有方向 PNG。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    meta = get_character(token, character_id)
    urls: dict[str, str] = meta.get("rotation_urls", {})
    if not urls:
        raise RuntimeError(f"character {character_id} 無 rotation_urls")
    saved: dict[str, Path] = {}
    headers = {"Authorization": f"Bearer {token}"}
    for direction, url in urls.items():
        fname = direction.replace("-", "_") + ".png"
        out = output_dir / fname
        r = requests.get(url, headers=headers, timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"下載 {direction} → HTTP {r.status_code}")
        out.write_bytes(r.content)
        saved[direction] = out
    return saved


def submit_character_animation(
    token: str,
    character_id: str,
    action_description: str,
    directions: list[str] | None = None,
    frame_count: int = 8,
    mode: str = "v3",
) -> dict[str, Any]:
    """送出 animate-character；回傳 {job_ids, directions}。"""
    payload: dict[str, Any] = {
        "character_id": character_id,
        "action_description": action_description,
        "mode": mode,
        "frame_count": frame_count,
    }
    if directions:
        payload["directions"] = directions
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.post(ANIMATE_CHARACTER_URL, headers=headers, json=payload, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"animate-character → HTTP {r.status_code}: {r.text[:500]}")
    data = r.json()
    return {
        "background_job_ids": data.get("background_job_ids", []),
        "directions": data.get("directions", directions or ["south"]),
    }


# === Top-down Tileset ===


def submit_topdown_tileset(
    token: str,
    lower_description: str,
    upper_description: str,
    transition_size: float = 0.0,
    transition_description: str | None = None,
    tile_width: int = 16,
    tile_height: int = 16,
    view: str = "high_top_down",
    text_guidance_scale: float = 8.0,
) -> str:
    payload: dict[str, Any] = {
        "lower_description": lower_description,
        "upper_description": upper_description,
        "transition_size": transition_size,
        "tile_size": {"width": tile_width, "height": tile_height},
        "view": view,
        "text_guidance_scale": text_guidance_scale,
    }
    if transition_description:
        payload["transition_description"] = transition_description

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.post(CREATE_TOPDOWN_TILESET_URL, headers=headers, json=payload, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"create-topdown-tileset → HTTP {r.status_code}: {r.text[:500]}")
    tileset_id = r.json().get("tileset_id") or r.json().get("id", "")
    if not tileset_id:
        raise RuntimeError(f"回應無 tileset_id: {r.json()}")
    return tileset_id


def get_topdown_tileset(token: str, tileset_id: str) -> dict[str, Any]:
    r = _get(token, f"{TILESETS_URL}/{tileset_id}")
    if r.status_code != 200:
        raise RuntimeError(f"get tileset → HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


def wait_for_tileset(token: str, tileset_id: str, timeout_sec: float = 1800.0, poll_interval: float = 15.0) -> dict[str, Any]:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        meta = get_topdown_tileset(token, tileset_id)
        status = meta.get("status", "")
        if status == "completed":
            return meta
        if status == "failed":
            raise RuntimeError(f"tileset {tileset_id} 失敗: {meta}")
        time.sleep(poll_interval)
    raise TimeoutError(f"tileset {tileset_id} 超時")


# === Map Object ===


def submit_map_object(
    token: str,
    description: str,
    width: int = 64,
    height: int = 64,
    view: str = "high_top_down",
    outline: str = "single_color_outline",
    shading: str = "medium_shading",
    detail: str = "medium_detail",
) -> str:
    payload: dict[str, Any] = {
        "description": description,
        "width": width,
        "height": height,
        "view": view,
        "outline": outline,
        "shading": shading,
        "detail": detail,
    }
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.post(CREATE_MAP_OBJECT_URL, headers=headers, json=payload, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"create-map-object → HTTP {r.status_code}: {r.text[:500]}")
    object_id = r.json().get("object_id") or r.json().get("id", "")
    if not object_id:
        raise RuntimeError(f"回應無 object_id: {r.json()}")
    return object_id


def get_map_object(token: str, object_id: str) -> dict[str, Any]:
    r = _get(token, f"{OBJECTS_URL}/{object_id}")
    if r.status_code != 200:
        raise RuntimeError(f"get object → HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


def wait_for_object(token: str, object_id: str, timeout_sec: float = 1800.0, poll_interval: float = 15.0) -> dict[str, Any]:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        meta = get_map_object(token, object_id)
        status = meta.get("status", "")
        if status == "completed":
            return meta
        if status == "failed":
            raise RuntimeError(f"object {object_id} 失敗: {meta}")
        time.sleep(poll_interval)
    raise TimeoutError(f"object {object_id} 超時")
