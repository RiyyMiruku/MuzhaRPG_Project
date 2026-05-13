"""Async Pixellab v2 client (httpx-based) for the v2 stage runner.

Wraps the same endpoints as pipeline.pixellab_client (sync, requests-based)
but suitable for asyncio worker loops:
  - One httpx.AsyncClient shared across calls (HTTP/2 + connection pooling)
  - Two retry paths preserved from sync client:
      * POST 429 (rate limit at request) → sleep + same-request retry
      * Polled job comes back failed with internal "429"-class error
        → re-POST (creates new ID), bounded attempts
  - poll_background_job uses asyncio.sleep, not blocking time.sleep,
    so N concurrent character renderings don't stall each other.

Only includes the endpoints v2 stages need today:
  - submit_character_8dir / submit_character_4dir
  - submit_character_animation (template + v3)
  - poll_background_job
  - low-level _post / _get

Object/tileset endpoints (submit_iso_tile, submit_map_object, ...) come
later when those stages are ported.

Token loading + image decoding helpers are imported from the existing sync
`pixellab_client` module (unchanged code).
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
from PIL import Image

# Reuse non-HTTP helpers from sync client.
import pixellab_client as _sync


# === URLs (same as sync) ===

V2_BASE = _sync.V2_BASE
BACKGROUND_JOBS_URL = _sync.BACKGROUND_JOBS_URL
CREATE_CHAR_8DIR_URL = _sync.CREATE_CHAR_8DIR_URL
CREATE_CHAR_4DIR_URL = _sync.CREATE_CHAR_4DIR_URL
ANIMATE_CHARACTER_URL = _sync.ANIMATE_CHARACTER_URL
CHARACTERS_URL = _sync.CHARACTERS_URL


# === Retry config (mirrors sync) ===

_QUOTA_BACKOFF_SECONDS = 60.0
_QUOTA_MAX_WAIT_SECONDS = 1800.0   # 30 min budget for POST-side 429
_QUOTA_JOB_MAX_RETRIES = 4         # cap re-POSTs after polled-job 429-failure
_QUOTA_JOB_BACKOFF_SECONDS = 60.0
_POLL_INTERVAL = 5.0
_POLL_MAX_WAIT = 1800.0


# Re-export the exception type so callers can `except` against the same class.
PixellabQuotaJobError = _sync.PixellabQuotaJobError


# === Module-level client ===

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, read=180.0),
            http2=False,  # Pixellab API doesn't advertise; keep simple
        )
    return _client


async def aclose() -> None:
    """Close the shared client. Backend should call on shutdown."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None


# === Low-level HTTP ===


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


async def _post(token: str, url: str, payload: dict[str, Any]) -> httpx.Response:
    """POST + tolerate POST-side 429 (Pixellab quota). Returns first non-429
    response. Caller checks status_code as before.
    """
    client = _get_client()
    waited = 0.0
    while True:
        r = await client.post(url, headers=_auth_headers(token), json=payload)
        if r.status_code != 429:
            return r
        if waited >= _QUOTA_MAX_WAIT_SECONDS:
            raise RuntimeError(
                f"{url} → still 429 after {waited:.0f}s wait. "
                f"Pixellab quota stuck; investigate orphan jobs."
            )
        print(
            f"[quota] {url.rsplit('/', 1)[-1]} 429: sleeping "
            f"{_QUOTA_BACKOFF_SECONDS:.0f}s (waited {waited:.0f}s)",
            flush=True,
        )
        await asyncio.sleep(_QUOTA_BACKOFF_SECONDS)
        waited += _QUOTA_BACKOFF_SECONDS


async def _get(token: str, url: str) -> httpx.Response:
    client = _get_client()
    return await client.get(url, headers={"Authorization": f"Bearer {token}"})


async def _download(url: str) -> bytes:
    """Anonymous fetch (used for storage URLs that 401 with our bearer token)."""
    client = _get_client()
    r = await client.get(url, timeout=60.0)
    r.raise_for_status()
    return r.content


# === Background job polling ===


async def poll_background_job(
    token: str,
    job_id: str,
    poll_interval: float = _POLL_INTERVAL,
    max_wait: float = _POLL_MAX_WAIT,
) -> dict[str, Any]:
    """Poll a Pixellab background job until terminal state.

    On status='completed' returns the `last_response` dict.
    On status='failed' raises:
      - PixellabQuotaJobError if the failure mentions an internal 429 /
        "Maximum N background jobs" — caller should re-POST.
      - RuntimeError otherwise (true failure; no point retrying same job).
    """
    poll_url = f"{BACKGROUND_JOBS_URL}/{job_id}"
    deadline = time.time() + max_wait
    while time.time() < deadline:
        await asyncio.sleep(poll_interval)
        try:
            r = await _get(token, poll_url)
        except httpx.RequestError:
            continue
        if r.status_code != 200:
            raise RuntimeError(f"poll {job_id} → HTTP {r.status_code}: {r.text[:200]}")
        data = r.json()
        status = data.get("status", "unknown")
        if status == "completed":
            return data.get("last_response") or data.get("response") or data
        if status == "failed":
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


# === Character creation (8-dir + 4-dir) ===


async def submit_character_8dir(
    token: str,
    description: str,
    *,
    size: int = 64,
    view: str = "high_top_down",
    proportions_preset: str = "cartoon",
    outline: str | None = "single_color_outline",
    shading: str | None = "medium_shading",
    detail: str | None = "detailed",
    text_guidance_scale: float = 8.0,
    isometric: bool = False,
) -> tuple[str, dict[str, Image.Image]]:
    """Async equivalent of pixellab_client.submit_character_8dir."""
    if view not in ("low_top_down", "high_top_down", "side"):
        raise ValueError(f"view must be low_top_down/high_top_down/side, got {view}")
    payload: dict[str, Any] = {
        "description": description,
        "image_size": {"width": size, "height": size},
        "view": _sync._wire_view(view),
        "mode": "standard",
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
        r = await _post(token, CREATE_CHAR_8DIR_URL, payload)
        if r.status_code != 200:
            raise RuntimeError(f"create-character-8dir → HTTP {r.status_code}: {r.text[:500]}")
        data = r.json()
        char_id = data.get("character_id", "")
        job_id = data.get("background_job_id") or data.get("job_id")
        if not char_id or not job_id:
            raise RuntimeError(f"POST 回應缺 character_id/job_id: {data}")
        try:
            result = await poll_background_job(token, job_id)
        except PixellabQuotaJobError as e:
            last_err = e
            print(
                f"[quota] character_8dir poll failed (attempt {attempt}/{_QUOTA_JOB_MAX_RETRIES}, "
                f"char_id={char_id} orphaned). Sleep {_QUOTA_JOB_BACKOFF_SECONDS:.0f}s then re-POST.",
                flush=True,
            )
            await asyncio.sleep(_QUOTA_JOB_BACKOFF_SECONDS)
            continue
        images = _sync._extract_direction_images(result, expected=8)
        return char_id, images
    raise RuntimeError(
        f"submit_character_8dir gave up after {_QUOTA_JOB_MAX_RETRIES} retries: {last_err}"
    )


async def submit_character_4dir(
    token: str,
    description: str,
    *,
    size: int = 64,
    view: str = "high_top_down",
    proportions_preset: str = "cartoon",
    outline: str | None = "single_color_outline",
    shading: str | None = "medium_shading",
    detail: str | None = "detailed",
    text_guidance_scale: float = 8.0,
    isometric: bool = False,
) -> tuple[str, dict[str, Image.Image]]:
    if view not in ("low_top_down", "high_top_down", "side"):
        raise ValueError(f"view must be low_top_down/high_top_down/side, got {view}")
    payload: dict[str, Any] = {
        "description": description,
        "image_size": {"width": size, "height": size},
        "view": _sync._wire_view(view),
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
        r = await _post(token, CREATE_CHAR_4DIR_URL, payload)
        if r.status_code != 200:
            raise RuntimeError(f"create-character-4dir → HTTP {r.status_code}: {r.text[:500]}")
        data = r.json()
        char_id = data.get("character_id", "")
        job_id = data.get("background_job_id") or data.get("job_id")
        if not char_id or not job_id:
            raise RuntimeError(f"POST 回應缺 character_id/job_id: {data}")
        try:
            result = await poll_background_job(token, job_id)
        except PixellabQuotaJobError as e:
            last_err = e
            print(
                f"[quota] character_4dir poll failed (attempt {attempt}/{_QUOTA_JOB_MAX_RETRIES}, "
                f"char_id={char_id} orphaned). Sleep {_QUOTA_JOB_BACKOFF_SECONDS:.0f}s then re-POST.",
                flush=True,
            )
            await asyncio.sleep(_QUOTA_JOB_BACKOFF_SECONDS)
            continue
        images = _sync._extract_direction_images(result, expected=4)
        return char_id, images
    raise RuntimeError(
        f"submit_character_4dir gave up after {_QUOTA_JOB_MAX_RETRIES} retries: {last_err}"
    )


# === Animation ===


async def submit_character_animation(
    token: str,
    character_id: str,
    *,
    action_description: str | None = None,
    directions: list[str] | None = None,
    frame_count: int = 8,
    mode: str | None = None,
    text_guidance_scale: float = 12.0,
    isometric: bool = False,
    template_animation_id: str | None = None,
    ai_freedom: int | None = None,
) -> dict[str, Any]:
    """Submit animation job. Returns {background_job_ids, directions}.
    Caller polls each job_id with poll_background_job."""
    if not template_animation_id and not action_description:
        raise ValueError("provide action_description (v3) or template_animation_id (template)")
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
    else:
        payload["action_description"] = action_description
    if directions:
        payload["directions"] = directions
    if isometric:
        payload["isometric"] = True
    r = await _post(token, ANIMATE_CHARACTER_URL, payload)
    if r.status_code != 200:
        raise RuntimeError(f"animate-character → HTTP {r.status_code}: {r.text[:500]}")
    data = r.json()
    return {
        "background_job_ids": data.get("background_job_ids", []),
        "directions": data.get("directions", directions or ["south"]),
    }


__all__ = [
    "PixellabQuotaJobError",
    "submit_character_8dir",
    "submit_character_4dir",
    "submit_character_animation",
    "poll_background_job",
    "_post",
    "_get",
    "_download",
    "aclose",
]
