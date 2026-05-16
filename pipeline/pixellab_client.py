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
CREATE_IMAGE_PIXFLUX_URL: str = f"{V2_BASE}/create-image-pixflux"
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

# 429 = Pixellab background-job quota (Tier 1 = 8 concurrent). Background jobs
# take 10–30 min, so a tight retry loop is pointless. Sleep meaningful chunks
# until a slot opens. Caller is expected to be running inside the dashboard's
# subprocess throttle (max 3), so at most 3 of these will sleep concurrently.
_QUOTA_BACKOFF_SECONDS: float = 60.0
_QUOTA_MAX_WAIT_SECONDS: float = 1800.0  # give up after 30 min

# When a polled background job comes back failed-due-to-quota, the only
# remedy is to POST again (Pixellab won't restart a failed job). Each retry
# burns a fresh character_id / object_id, so cap the attempts.
_QUOTA_JOB_MAX_RETRIES: int = 4
_QUOTA_JOB_BACKOFF_SECONDS: float = 60.0


class PixellabQuotaJobError(RuntimeError):
    """Raised when a polled background job comes back failed with a quota /
    rate-limit reason. Caller should sleep and re-submit (this creates a new
    Pixellab job — the failed one cannot be resumed)."""


def _post_submit_with_quota_retry(
    token: str,
    url: str,
    payload: dict[str, Any],
    timeout: float = 60.0,
) -> "requests.Response":
    """POST + tolerate 429 (Pixellab quota) by sleeping and retrying.

    Returns the first non-429 response (caller checks status_code as before).
    Raises RuntimeError if 429 persists past _QUOTA_MAX_WAIT_SECONDS.
    """
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    waited = 0.0
    while True:
        r = requests.post(url, headers=headers, json=payload, timeout=timeout)
        if r.status_code != 429:
            return r
        if waited >= _QUOTA_MAX_WAIT_SECONDS:
            raise RuntimeError(
                f"{url} → still HTTP 429 after waiting {waited:.0f}s "
                f"({_QUOTA_MAX_WAIT_SECONDS:.0f}s budget). Pixellab background "
                f"job quota stuck full — investigate orphan jobs."
            )
        print(
            f"[quota] {url.rsplit('/',1)[-1]} 429: sleeping "
            f"{_QUOTA_BACKOFF_SECONDS:.0f}s (waited {waited:.0f}s so far)",
            flush=True,
        )
        time.sleep(_QUOTA_BACKOFF_SECONDS)
        waited += _QUOTA_BACKOFF_SECONDS


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
            # Distinguish quota failures (transient — Pixellab couldn't queue
            # the render due to internal limits) from real failures. Caller
            # can retry the whole submit on PixellabQuotaJobError.
            last = data.get("last_response") or {}
            err_text = ""
            if isinstance(last, dict):
                err_text = str(last.get("error") or last.get("detail") or "")
            if "429" in err_text or "maximum number of background jobs" in err_text.lower():
                raise PixellabQuotaJobError(
                    f"job {job_id} failed (quota): {err_text or data}"
                )
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
    """把 Pixellab 的單張 image entry 解成 PIL.Image。

    支援三種格式:
      - bare base64 string (PNG encoded)
      - dict with "base64"/"data" + optional "type":"rgba_bytes" + w/h
      - dict (or string) with "url"/"image_url" → HTTP GET 下載
        (tileset endpoint 用這種,storage URL 無需 auth)
    """
    # URL string
    if isinstance(entry, str):
        if entry.startswith("http://") or entry.startswith("https://"):
            try:
                r = requests.get(entry, timeout=60)
                if r.status_code == 200:
                    return Image.open(io.BytesIO(r.content))
            except requests.RequestException:
                return None
            return None
        # bare base64 PNG
        try:
            return Image.open(io.BytesIO(base64.b64decode(entry)))
        except Exception:
            return None
    if not isinstance(entry, dict):
        return None
    # URL inside dict
    url = entry.get("url") or entry.get("image_url")
    if isinstance(url, str) and (url.startswith("http://") or url.startswith("https://")):
        try:
            r = requests.get(url, timeout=60)
            if r.status_code == 200:
                return Image.open(io.BytesIO(r.content))
        except requests.RequestException:
            return None
        return None
    # base64 (inline)
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
    isometric: bool = False,
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
    if isometric:
        payload["isometric"] = True

    last_err: PixellabQuotaJobError | None = None
    for attempt in range(1, _QUOTA_JOB_MAX_RETRIES + 1):
        r = _post_submit_with_quota_retry(token, CREATE_CHAR_8DIR_URL, payload)
        if r.status_code != 200:
            raise RuntimeError(f"create-character-8dir → HTTP {r.status_code}: {r.text[:500]}")
        data = r.json()
        char_id = data.get("character_id", "")
        job_id = data.get("background_job_id") or data.get("job_id")
        if not char_id or not job_id:
            raise RuntimeError(f"POST 回應缺 character_id 或 job_id: {data}")
        try:
            result = poll_background_job(token, job_id)
        except PixellabQuotaJobError as e:
            last_err = e
            print(
                f"[quota] character_8dir background job failed with quota error "
                f"(attempt {attempt}/{_QUOTA_JOB_MAX_RETRIES}, char_id={char_id} "
                f"orphaned). Sleeping {_QUOTA_JOB_BACKOFF_SECONDS:.0f}s before re-POST.",
                flush=True,
            )
            time.sleep(_QUOTA_JOB_BACKOFF_SECONDS)
            continue
        images = _extract_direction_images(result, expected=8)
        return char_id, images
    raise RuntimeError(
        f"submit_character_8dir gave up after {_QUOTA_JOB_MAX_RETRIES} quota retries: {last_err}"
    )


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
    isometric: bool = False,
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
    if isometric:
        payload["isometric"] = True

    last_err: PixellabQuotaJobError | None = None
    for attempt in range(1, _QUOTA_JOB_MAX_RETRIES + 1):
        r = _post_submit_with_quota_retry(token, CREATE_CHAR_4DIR_URL, payload)
        if r.status_code != 200:
            raise RuntimeError(
                f"create-character-4dir → HTTP {r.status_code}: {r.text[:500]}"
            )
        data = r.json()
        char_id = data.get("character_id", "")
        job_id = data.get("background_job_id") or data.get("job_id")
        if not char_id or not job_id:
            raise RuntimeError(f"POST 回應缺 character_id 或 job_id: {data}")
        try:
            result = poll_background_job(token, job_id)
        except PixellabQuotaJobError as e:
            last_err = e
            print(
                f"[quota] character_4dir background job failed with quota error "
                f"(attempt {attempt}/{_QUOTA_JOB_MAX_RETRIES}, char_id={char_id} "
                f"orphaned). Sleeping {_QUOTA_JOB_BACKOFF_SECONDS:.0f}s before re-POST.",
                flush=True,
            )
            time.sleep(_QUOTA_JOB_BACKOFF_SECONDS)
            continue
        images = _extract_direction_images(result, expected=4)
        return char_id, images
    raise RuntimeError(
        f"submit_character_4dir gave up after {_QUOTA_JOB_MAX_RETRIES} quota retries: {last_err}"
    )


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
    action_description: str | None = None,
    directions: list[str] | None = None,
    frame_count: int = 8,
    mode: str | None = None,
    text_guidance_scale: float = 12.0,
    isometric: bool = False,
    template_animation_id: str | None = None,
    ai_freedom: int | None = None,
) -> dict[str, Any]:
    """送出 animate-character；回傳 {job_ids, directions}。

    Two main paths:
      1. **v3 (custom action)**: pass `action_description`. Pixellab generates
         frames from text. text_guidance_scale tunes faithfulness (1-20,
         official default 8, we default 12 for tighter control over creative
         drift like head-turning).
      2. **template (skeleton-based)**: pass `template_animation_id` (e.g.
         "breathing-idle", "walking-4-frames"). Pixellab uses a pre-built
         skeleton, MUCH more stable + cheaper (1 gen/direction). The template
         brings its own motion description — we DO NOT send action_description
         in this mode (sending it would confuse Pixellab into v3 territory
         and re-introduce the very head-turning / arm-flailing the template
         is meant to avoid). ai_freedom (0=strict, 1000=creative) tunes
         template adherence.

    `mode` defaults to auto-pick: "template" if template_animation_id is set,
    otherwise "v3". Override only if you know what you're doing — sending
    mode="v3" alongside a template_animation_id silently downgrades to v3.
    """
    if not template_animation_id and not action_description:
        raise ValueError(
            "must provide either action_description (v3 mode) or "
            "template_animation_id (template mode)"
        )
    effective_mode = mode or ("template" if template_animation_id else "v3")
    payload: dict[str, Any] = {
        "character_id": character_id,
        "mode": effective_mode,
        "frame_count": frame_count,
        "text_guidance_scale": text_guidance_scale,
    }
    if effective_mode == "template":
        if not template_animation_id:
            raise ValueError("mode='template' requires template_animation_id")
        payload["template_animation_id"] = template_animation_id
        if ai_freedom is not None:
            payload["ai_freedom"] = ai_freedom
        # NOTE: action_description deliberately omitted — template provides
        # its own motion. Pre-seeded manifest prompts (long anti-drift text
        # written for v3 mode) become irrelevant under templates.
    else:
        payload["action_description"] = action_description
    if directions:
        payload["directions"] = directions
    if isometric:
        payload["isometric"] = True
    r = _post_submit_with_quota_retry(token, ANIMATE_CHARACTER_URL, payload)
    if r.status_code != 200:
        raise RuntimeError(f"animate-character → HTTP {r.status_code}: {r.text[:500]}")
    data = r.json()
    return {
        "background_job_ids": data.get("background_job_ids", []),
        "directions": data.get("directions", directions or ["south"]),
    }


# === Top-down Tileset ===


VALID_TRANSITION_SIZES: tuple[float, ...] = (0.0, 0.25, 0.5, 1.0)


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

    transition_size 必須是 {0.0, 0.25, 0.5, 1.0} 之一(Pixellab enum 限制)。
    """
    if transition_size not in VALID_TRANSITION_SIZES:
        raise ValueError(
            f"transition_size 必須是 {VALID_TRANSITION_SIZES} 其中一個,收到 {transition_size}"
        )
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

    r = _post_submit_with_quota_retry(token, CREATE_TOPDOWN_TILESET_URL, payload)
    if r.status_code not in (200, 202):
        raise RuntimeError(f"create-tileset → HTTP {r.status_code}: {r.text[:500]}")
    data = r.json()
    tileset_id = data.get("tileset_id") or data.get("id")
    job_id = data.get("background_job_id") or data.get("job_id")
    if not tileset_id or not job_id:
        raise RuntimeError(f"POST 回應缺 tileset_id 或 job_id: {data}")
    # Wait for streaming job to finish; its `image` field is just a per-frame
    # preview, not the final atlas. Fetch the structured tileset record (16
    # Wang tiles, each its own PNG) and assemble the 4×4 atlas ourselves.
    poll_background_job(token, job_id)
    meta = get_topdown_tileset(token, tileset_id)
    img = _assemble_wang_atlas(meta, tile_width, tile_height)
    return tileset_id, img


# TileMapDual `Standard` preset layout — internal Wang ID (bit 1=TL, 2=TR,
# 4=BL, 8=BR) at (col, row) in the 4×4 atlas.
# Pixellab's Wang IDs use the REVERSED bit order (bit 1=BR, 2=BL, 4=TR, 8=TL),
# so we apply _pixellab_to_standard() before lookup.
_WANG_ID_TO_POS: dict[int, tuple[int, int]] = {
    # row 0
     4: (0, 0), 10: (1, 0), 13: (2, 0), 12: (3, 0),
    # row 1
     9: (0, 1), 14: (1, 1), 15: (2, 1),  8: (3, 1),
    # row 2
     2: (0, 2),  3: (1, 2), 11: (2, 2),  5: (3, 2),
    # row 3
     0: (0, 3),  7: (1, 3),  6: (2, 3),  1: (3, 3),
}


def _pixellab_to_standard(wid: int) -> int:
    """Reverse 4-bit Wang ID: Pixellab uses bit0=BR,1=BL,2=TR,3=TL
    but our layout uses bit0=TL,1=TR,2=BL,3=BR."""
    return ((wid & 1) << 3) | ((wid & 2) << 1) | ((wid & 4) >> 1) | ((wid & 8) >> 3)


def _assemble_wang_atlas(
    meta: dict[str, Any], tile_w: int, tile_h: int
) -> Image.Image:
    """Pack the 16 Wang tiles in a `get_topdown_tileset` response into a 4×4
    atlas using the TileMapDual Standard preset layout."""
    tileset = meta.get("tileset") or {}
    tiles = tileset.get("tiles") or []
    if len(tiles) != 16:
        raise RuntimeError(
            f"expected 16 Wang tiles from tileset endpoint, got {len(tiles)}"
        )
    atlas = Image.new("RGBA", (tile_w * 4, tile_h * 4), (0, 0, 0, 0))
    seen: set[int] = set()
    for t in tiles:
        try:
            wid = int(t.get("id"))
        except (TypeError, ValueError):
            raise RuntimeError(f"tile missing numeric id: {t.get('name')!r}")
        std_id = _pixellab_to_standard(wid)
        pos = _WANG_ID_TO_POS.get(std_id)
        if pos is None:
            raise RuntimeError(f"Wang id {wid} (std={std_id}) not in Standard preset layout")
        decoded = _decode_image_entry(t.get("image"))
        if decoded is None:
            raise RuntimeError(f"failed to decode image for Wang tile id={wid}")
        if decoded.mode != "RGBA":
            decoded = decoded.convert("RGBA")
        if decoded.size != (tile_w, tile_h):
            decoded = decoded.resize((tile_w, tile_h), Image.Resampling.NEAREST)
        col, row = pos
        atlas.paste(decoded, (col * tile_w, row * tile_h), decoded)
        seen.add(std_id)
    missing = set(_WANG_ID_TO_POS) - seen
    if missing:
        raise RuntimeError(f"tileset response missing Wang IDs: {sorted(missing)}")
    return atlas


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
    outline: str | None = "single color outline",
    shading: str | None = "medium shading",
    detail: str | None = None,
) -> tuple[str, Image.Image]:
    """同步建 map object(建築物),回傳 (object_id, PIL.Image)。

    Pixellab v2 端點 async:POST 回 202 + background_job_id + object_id。
    本函式 poll + decode 完一次回傳。
    """
    payload: dict[str, Any] = {
        "description": description,
        "image_size": {"width": width, "height": height},
        "view": _wire_view(view),
    }
    # Pixellab v2 enums use space-separated strings (e.g. "single color outline").
    # Send only when caller supplies a value; omit otherwise to avoid 422 on
    # under-documented `detail` enum.
    if outline:
        payload["outline"] = outline
    if shading:
        payload["shading"] = shading
    if detail:
        payload["detail"] = detail
    r = _post_submit_with_quota_retry(token, CREATE_MAP_OBJECT_URL, payload)
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
    r = _post_submit_with_quota_retry(token, CREATE_ISO_TILE_URL, payload)
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


# === Pixflux (general single-image generator) ===


def submit_pixflux_image(
    token: str,
    description: str,
    width: int = 128,
    height: int = 128,
    view: str | None = None,
    isometric: bool = False,
    no_background: bool = True,
    text_guidance_scale: float = 8.0,
    outline: str | None = "single color outline",
    shading: str | None = "medium shading",
    detail: str | None = None,
) -> Image.Image:
    """同步建單張 pixflux 圖,回傳 PIL.Image。

    Pixellab /create-image-pixflux 是**真同步**端點 (200 直接回 base64,無
    background_job 流程)。適合一次性圖像生成,主要用途:**iso 建築**(補
    /map-objects 不支援 isometric 的缺口)。

    限制:
      - image_size 每軸 16-400 px (max 400×400)
      - isometric 是 "weakly guiding" — 也要在 description 帶 "isometric view"
        / "30 degree top-down angle" 等明確字眼
      - view enum: "side" | "low_top_down" | "high_top_down"(內部值,
        _wire_view 轉成 wire format)
    """
    if not (16 <= width <= 400 and 16 <= height <= 400):
        raise ValueError(
            f"pixflux image_size 須 16-400 per axis,收到 {width}x{height}"
        )
    payload: dict[str, Any] = {
        "description": description,
        "image_size": {"width": width, "height": height},
        "text_guidance_scale": text_guidance_scale,
        "isometric": isometric,
        "no_background": no_background,
    }
    if view is not None:
        payload["view"] = _wire_view(view)
    if outline:
        payload["outline"] = outline
    if shading:
        payload["shading"] = shading
    if detail:
        payload["detail"] = detail

    r = _post_submit_with_quota_retry(
        token, CREATE_IMAGE_PIXFLUX_URL, payload, timeout=300.0
    )
    if r.status_code != 200:
        raise RuntimeError(
            f"create-image-pixflux → HTTP {r.status_code}: {r.text[:500]}"
        )
    data = r.json()
    img = _extract_single_image(data)
    if img is None:
        raise RuntimeError(
            f"create-image-pixflux 200 但無 image 可解 (top keys: {list(data.keys())})"
        )
    return img
