"""
PIL 後處理工具集。

職責：
  - chroma_key_bg: 把純色背景換成透明（Pixellab v2/v3 不去背時補救）
  - project_to_iso_atlas: 把方形 Wang autotile 投影成 iso 菱形 atlas
  - resize_pixel: 像素風格安全縮放（NEAREST）

不做 HTTP 呼叫；不依賴 Pixellab。純粹本地圖像處理。
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image


# Pixellab v2 端點（animate-with-text-v3, create-character-with-8-directions 等）
# 在 no_background 失效時的固定底色
DEFAULT_BG_COLOR_RGB: tuple[int, int, int] = (128, 128, 128)


def resize_pixel(img: Image.Image, size: int) -> Image.Image:
    """像素風格安全縮放（NEAREST，不平滑）。"""
    if img.size == (size, size):
        return img
    return img.resize((size, size), resample=Image.Resampling.NEAREST)


def chroma_key_bg(
    img: Image.Image,
    bg_rgb: tuple[int, int, int] = DEFAULT_BG_COLOR_RGB,
) -> Image.Image:
    """把純色背景換成透明，僅在「整張不透明 + 四角是該背景色」時觸發。

    精確匹配 RGB（不做容差），不會誤刪角色身上的同色像素。
    若圖片已有透明像素或四角不是預期背景色，原樣回傳（冗餘安全）。
    """
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    alpha = img.split()[-1]
    if min(alpha.getextrema()) == 0:
        return img  # 已有透明，不處理

    w, h = img.size
    corner_colors: set[tuple[int, int, int]] = {
        img.getpixel(p)[:3] for p in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    }
    if bg_rgb not in corner_colors:
        return img  # 不是預期 bg，可能 API 已處理

    pixels = img.load()
    for y in range(h):
        for x in range(w):
            r, g, b, _ = pixels[x, y]
            if (r, g, b) == bg_rgb:
                pixels[x, y] = (0, 0, 0, 0)
    return img


# === Iso 投影 ===
#
# orthographic 2:1 isometric 投影：
#     screen_x = world_x - world_y + H
#     screen_y = (world_x + world_y) / 2
# 反向（PIL.AFFINE 需要）:
#     world_x = 0.5*screen_x + 1*screen_y - H/2
#     world_y = -0.5*screen_x + 1*screen_y + H/2


def _iso_affine_coeffs(width: int, height: int) -> tuple[float, ...]:
    h_half: float = height / 2.0
    return (0.5, 1.0, -h_half, -0.5, 1.0, h_half)


def project_to_iso(img: Image.Image) -> Image.Image:
    """整張方形圖投影成 iso 菱形（單格用）。"""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    w, h = img.size
    out_w: int = w + h
    out_h: int = (w + h) // 2
    return img.transform(
        (out_w, out_h),
        Image.Transform.AFFINE,
        _iso_affine_coeffs(w, h),
        resample=Image.Resampling.NEAREST,
        fillcolor=(0, 0, 0, 0),
    )


def project_to_iso_atlas(
    img: Image.Image, cols: int, rows: int
) -> Image.Image:
    """切成 cols×rows 格 → 各自投影成菱形 → 拼成 iso atlas。

    用於 Wang autotile（top-down 16-cell atlas → iso 16-菱形 atlas）。
    """
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    src_w, src_h = img.size
    if src_w % cols != 0 or src_h % rows != 0:
        raise ValueError(f"圖片尺寸 {src_w}x{src_h} 無法整除 {cols}x{rows}")

    cell_w: int = src_w // cols
    cell_h: int = src_h // rows
    proj_w: int = cell_w + cell_h
    proj_h: int = (cell_w + cell_h) // 2

    atlas: Image.Image = Image.new(
        "RGBA", (proj_w * cols, proj_h * rows), (0, 0, 0, 0)
    )
    for r in range(rows):
        for c in range(cols):
            box = (c * cell_w, r * cell_h, (c + 1) * cell_w, (r + 1) * cell_h)
            cell = img.crop(box)
            projected = project_to_iso(cell)
            atlas.paste(projected, (c * proj_w, r * proj_h), projected)
    return atlas


# === 便利函式（檔案 in/out）===


def chroma_key_file(path: Path, bg_rgb: tuple[int, int, int] = DEFAULT_BG_COLOR_RGB) -> bool:
    """對檔案做 chroma_key（in-place）。回傳是否實際修改。"""
    img: Image.Image = Image.open(path).convert("RGBA")
    a = img.split()[-1]
    if min(a.getextrema()) == 0:
        return False
    new = chroma_key_bg(img, bg_rgb)
    new.save(path)
    return True


def project_atlas_file(
    src: Path, dst: Path, cols: int = 4, rows: int = 4
) -> tuple[int, int]:
    """讀檔投影、寫檔。回傳輸出尺寸。"""
    img: Image.Image = Image.open(src).convert("RGBA")
    out: Image.Image = project_to_iso_atlas(img, cols, rows)
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst)
    return out.size
