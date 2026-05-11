"""
Pixellab HTTP 客戶端（純底層）。

職責：把 Pixellab API 端點包成純函式，自動處理：
  - .env / 環境變數讀 token
  - 5xx 重試 + exp backoff
  - async job 投遞 + 輪詢
  - base64 ↔ PIL Image 轉換

不做：
  - 業務邏輯（manifest 寫入、檔案命名 — 由 orchestrator 負責）
  - PIL 後處理（chroma_key, iso 投影 — 由 post_process 負責）
"""

from __future__ import annotations

import base64
import io
import json
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

BACKGROUND_JOBS_URL: str = f"{V2_BASE}/background-jobs"

CREATE_CHAR_8DIR_URL: str = f"{V2_BASE}/create-character-with-8-directions"
CREATE_CHAR_4DIR_URL: str = f"{V2_BASE}/create-character-with-4-directions"
ANIMATE_CHARACTER_URL: str = f"{V2_BASE}/animate-character"
CREATE_TOPDOWN_TILESET_URL: str = f"{V2_BASE}/create-tileset"
CREATE_MAP_OBJECT_URL: str = f"{V2_BASE}/map-objects"
CREATE_ISO_TILE_URL: str = f"{V2_BASE}/create-isometric-tile"
CHARACTERS_URL: str = f"{V2_BASE}/characters"
TILESETS_URL: str = f"{V2_BASE}/tilesets"
OBJECTS_URL: str = f"{V2_BASE}/objects"


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


def download_object_image(
    token: str,
    meta: dict[str, Any],
    out_path: Path,
    extra_keys: tuple[str, ...] = (),
) -> bool:
    """Download generated image from a Pixellab object meta response.

    Tries `meta["image"]` then any `extra_keys` then `meta["image_url"]`.
    Handles base64 dicts and HTTP URLs. On unparseable shape, writes
    raw_response.json next to out_path and returns False; otherwise saves
    to out_path and returns True.

    extra_keys: 額外要嘗試的 meta keys(在 image / image_url 之外),
                例如 tileset 端點會回 'atlas'。順序依優先度。
    """
    candidates: list[str] = ["image", *extra_keys, "image_url"]
    img_field: Any = None
    for k in candidates:
        v = meta.get(k)
        if v:
            img_field = v
            break
    if isinstance(img_field, dict):
        b64_to_img(img_field.get("base64", "")).save(out_path)
        return True
    if isinstance(img_field, str) and img_field.startswith("http"):
        r = requests.get(
            img_field, headers={"Authorization": f"Bearer {token}"}, timeout=60
        )
        out_path.write_bytes(r.content)
        return True
    out_path.parent.mkdir(parents=True, exist_ok=True)
    (out_path.parent / "raw_response.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return False


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


_VIEW_WIRE: dict[str, str] = {
    "low_top_down": "low top-down",
    "high_top_down": "high top-down",
    "side": "side",
    "none": "none",
}


def _wire_view(view: str) -> str:
    """轉換內部用的 view 字串 (`high_top_down`) 成 Pixellab v2 API 要求的
    wire format (`"high top-down"`)。讓 caller 端不用改,只在 HTTP boundary
    做一次轉換。未知值原樣回傳,讓 API 自己回錯。"""
    return _VIEW_WIRE.get(view, view)


def _extract_direction_images(result: dict[str, Any], expected: int) -> dict[str, Image.Image]:
    """從 background-job 完成結果中抽出 {direction: PIL.Image}。

    Pixellab v2 character endpoints 的 result["images"] 形如:
        {"south": {"type": "rgba_bytes", "width": 92, "height": 92,
                   "base64": "<base64 of W*H*4 raw RGBA bytes>"},
         "east":  {...}, ...}

    "rgba_bytes" 不是 PNG-encoded — 是 raw RGBA pixel bytes,要用
    Image.frombytes 重組,不能 Image.open。本函式統一在 client 層
    decode,caller 拿到的就是現成 PIL.Image。
    """
    candidates: list[dict[str, Any]] = [result]
    if isinstance(result.get("response"), dict):
        candidates.append(result["response"])
    if isinstance(result.get("last_response"), dict):
        candidates.append(result["last_response"])

    for source in candidates:
        raw = source.get("images")
        if not isinstance(raw, dict) or not raw:
            continue
        out: dict[str, Image.Image] = {}
        for direction, entry in raw.items():
            img = _decode_image_entry(entry)
            if img is not None:
                out[direction] = img
        if len(out) >= expected:
            return out

    raise RuntimeError(
        f"job result 無 images 欄位或不完整 (expected {expected} dirs); "
        f"top keys: {list(result.keys())}"
    )


def _decode_image_entry(entry: Any) -> Image.Image | None:
    """把 Pixellab 的單張 image entry 解成 PIL.Image。支援 rgba_bytes 與 base64 PNG。"""
    if isinstance(entry, str):
        # bare base64; assume PNG-encoded
        try:
            return Image.open(io.BytesIO(base64.b64decode(entry)))
        except Exception:
            return None
    if not isinstance(entry, dict):
        return None
    b64 = entry.get("base64") or entry.get("data") or ""
    if not b64:
        return None
    raw_bytes = base64.b64decode(b64)
    kind = entry.get("type") or ""
    if kind == "rgba_bytes":
        w = int(entry.get("width") or 0)
        h = int(entry.get("height") or 0)
        if w <= 0 or h <= 0 or len(raw_bytes) != w * h * 4:
            return None
        return Image.frombytes("RGBA", (w, h), raw_bytes)
    # default: assume PNG/JPEG file bytes
    try:
        return Image.open(io.BytesIO(raw_bytes))
    except Exception:
        return None


def _extract_single_image(result: dict[str, Any]) -> Image.Image | None:
    """Extract a single PIL.Image from a Pixellab background-job result.

    Tries several shapes:
      - {"image": {type, base64, ...}}
      - {"image": "base64..."}
      - {"images": {<single key>: {...}}}  (rare; pick first)
      - {"images": [{...}]}                  (rare; pick first)
      - nested in {"response": {...}} or {"last_response": {...}}
    Returns None if nothing decodable.
    """
    candidates: list[dict[str, Any]] = [result]
    for key in ("response", "last_response"):
        nested = result.get(key)
        if isinstance(nested, dict):
            candidates.append(nested)

    for source in candidates:
        # Singular "image"
        img_entry = source.get("image")
        if img_entry is not None:
            decoded = _decode_image_entry(img_entry)
            if decoded is not None:
                return decoded

        # Plural "images" — may be dict or list
        imgs = source.get("images")
        if isinstance(imgs, dict) and imgs:
            first_entry = next(iter(imgs.values()))
            decoded = _decode_image_entry(first_entry)
            if decoded is not None:
                return decoded
        if isinstance(imgs, list) and imgs:
            decoded = _decode_image_entry(imgs[0])
            if decoded is not None:
                return decoded

    return None


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
) -> tuple[str, dict[str, Image.Image]]:
    """同步建 8 方向角色,回傳 (character_id, {direction: base64_png})。

    Pixellab 的 /create-character-with-8-directions 是同步端點 — POST 一次
    回傳 8 張完整渲染的 base64 PNG。**不是**先回 character_id 再 poll。
    所以 caller 應該直接用回傳的 images 存檔,不要用 wait_for_character /
    download_character_rotations 走 storage URL 路徑(URL 是預測路徑,常常
    永遠不會上傳)。
    """
    if view not in ("low_top_down", "high_top_down", "side"):
        raise ValueError(f"view 必須 low_top_down/high_top_down/side,收到 {view}")
    payload: dict[str, Any] = {
        "description": description,
        "image_size": {"width": size, "height": size},
        "view": _wire_view(view),
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
    data = r.json()
    char_id = data.get("character_id", "")
    job_id = data.get("background_job_id") or data.get("job_id")
    if not char_id or not job_id:
        raise RuntimeError(f"POST 回應缺 character_id 或 job_id: {data}")
    result = poll_background_job(token, job_id)
    images = _extract_direction_images(result, expected=8)
    return char_id, images


def submit_character_4dir(
    token: str,
    description: str,
    size: int = 64,
    view: str = "high_top_down",
    proportions_preset: str = "cartoon",
    outline: str | None = "single_color_outline",
    shading: str | None = "medium_shading",
    detail: str | None = "detailed",
    text_guidance_scale: float = 8.0,
) -> tuple[str, dict[str, Image.Image]]:
    """同步建 4 方向角色,回傳 (character_id, {direction: base64_png})。

    與 submit_character_8dir 同樣是同步端點,POST 直接回 4 張 N/S/E/W base64。
    Pixellab credit ~50% 較便宜。注意:character_id 與 8-dir 端點不通用,
    日後升級成移動 NPC 需重新 create_character。
    """
    if view not in ("low_top_down", "high_top_down", "side"):
        raise ValueError(f"view 必須 low_top_down/high_top_down/side,收到 {view}")
    payload: dict[str, Any] = {
        "description": description,
        "image_size": {"width": size, "height": size},
        "view": _wire_view(view),
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
    r = requests.post(CREATE_CHAR_4DIR_URL, headers=headers, json=payload, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(
            f"create-character-4dir → HTTP {r.status_code}: {r.text[:500]}"
        )
    data = r.json()
    char_id = data.get("character_id", "")
    job_id = data.get("background_job_id") or data.get("job_id")
    if not char_id or not job_id:
        raise RuntimeError(f"POST 回應缺 character_id 或 job_id: {data}")
    result = poll_background_job(token, job_id)
    images = _extract_direction_images(result, expected=4)
    return char_id, images


def wait_for_character(
    token: str, character_id: str, timeout_sec: float = 1800.0, poll_interval: float = 15.0
) -> None:
    """輪詢直到所有 rotation 圖檔實際上傳到 storage。

    Pixellab 的 rotation_urls 是「預測路徑」,在檔案實際渲染並上傳到
    Backblaze 之前就會出現在 GET /characters/{id} 回應中。所以「URL 非空」
    不等於「圖可下載」— 必須對每個 URL 實際 HEAD 一次,200 才算 ready。

    過去版本(已修)輪詢 /zip endpoint 等 200,但 zip 是 rotations + 所有
    animations 都好才解鎖,stage 1 還沒提交 animations 就 poll zip 必然
    deadlock。
    """
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        meta = get_character(token, character_id)
        urls = meta.get("rotation_urls") or {}
        if urls and all(urls.values()):
            ready = True
            for direction, url in urls.items():
                try:
                    h = requests.head(url, timeout=15)
                except requests.RequestException:
                    ready = False
                    break
                if h.status_code != 200:
                    ready = False
                    break
            if ready:
                return
        time.sleep(poll_interval)
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
    # rotation_urls are public Supabase storage URLs, not Pixellab API endpoints.
    # Sending the Pixellab Bearer token causes Supabase to 401.
    for direction, url in urls.items():
        fname = direction.replace("-", "_") + ".png"
        out = output_dir / fname
        r = requests.get(url, timeout=60)
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
) -> tuple[str, Image.Image]:
    """同步建 4×4 top-down tileset atlas,回傳 (tileset_id, PIL.Image)。

    Pixellab v2 端點 async:POST 回 202 + background_job_id + tileset_id。
    本函式 poll + decode 完一次回傳。
    """
    payload: dict[str, Any] = {
        "lower_description": lower_description,
        "upper_description": upper_description,
        "transition_size": transition_size,
        "tile_size": {"width": tile_width, "height": tile_height},
        "view": _wire_view(view),
        "text_guidance_scale": text_guidance_scale,
    }
    if transition_description:
        payload["transition_description"] = transition_description

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.post(CREATE_TOPDOWN_TILESET_URL, headers=headers, json=payload, timeout=60)
    if r.status_code not in (200, 202):
        raise RuntimeError(f"create-topdown-tileset → HTTP {r.status_code}: {r.text[:500]}")
    data = r.json()
    tileset_id = data.get("tileset_id") or data.get("id")
    job_id = data.get("background_job_id") or data.get("job_id")
    if not tileset_id or not job_id:
        raise RuntimeError(f"POST 回應缺 tileset_id 或 job_id: {data}")
    result = poll_background_job(token, job_id)
    img = _extract_single_image(result)
    if img is None:
        raise RuntimeError(
            f"create-topdown-tileset job 完成但無 image 可解 (top keys: {list(result.keys())})"
        )
    return tileset_id, img


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
) -> tuple[str, Image.Image]:
    """同步建 map object(建築物),回傳 (object_id, PIL.Image)。

    Pixellab v2 端點 async:POST 回 202 + background_job_id + object_id。
    本函式 poll + decode 完一次回傳。
    """
    payload: dict[str, Any] = {
        "description": description,
        "image_size": {"width": width, "height": height},
        "view": _wire_view(view),
        "outline": outline,
        "shading": shading,
        "detail": detail,
    }
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.post(CREATE_MAP_OBJECT_URL, headers=headers, json=payload, timeout=60)
    if r.status_code not in (200, 202):
        raise RuntimeError(f"map-objects → HTTP {r.status_code}: {r.text[:500]}")
    data = r.json()
    object_id = data.get("object_id") or data.get("id")
    job_id = data.get("background_job_id") or data.get("job_id")
    if not object_id or not job_id:
        raise RuntimeError(f"POST 回應缺 object_id 或 job_id: {data}")
    result = poll_background_job(token, job_id)
    img = _extract_single_image(result)
    if img is None:
        raise RuntimeError(
            f"create-map-object job 完成但無 image 可解 (top keys: {list(result.keys())})"
        )
    return object_id, img


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


# === Isometric Tile ===


def submit_iso_tile(
    token: str,
    description: str,
    size: int = 32,
    text_guidance_scale: float = 8.0,
) -> tuple[str, Image.Image]:
    """同步建單格 isometric tile,回傳 (tile_id, PIL.Image)。

    Pixellab v2 端點是 async:POST 回 202 + background_job_id + tile_id。
    本函式內部完成 poll_background_job + image decode,caller 拿到已 decode 的圖。
    """
    payload: dict[str, Any] = {
        "description": description,
        "image_size": {"width": size, "height": size},
        "text_guidance_scale": text_guidance_scale,
    }
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.post(CREATE_ISO_TILE_URL, headers=headers, json=payload, timeout=60)
    if r.status_code not in (200, 202):
        raise RuntimeError(
            f"create-isometric-tile → HTTP {r.status_code}: {r.text[:500]}"
        )
    data = r.json()
    tile_id = data.get("tile_id") or data.get("object_id") or data.get("id")
    job_id = data.get("background_job_id") or data.get("job_id")
    if not tile_id or not job_id:
        raise RuntimeError(f"POST 回應缺 tile_id 或 job_id: {data}")
    result = poll_background_job(token, job_id)
    img = _extract_single_image(result)
    if img is None:
        raise RuntimeError(
            f"create-isometric-tile job 完成但無 image 可解 (top keys: {list(result.keys())})"
        )
    return tile_id, img
