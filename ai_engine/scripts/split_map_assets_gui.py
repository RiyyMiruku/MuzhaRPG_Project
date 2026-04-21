#!/usr/bin/env python3
"""
地圖素材拆解工具（GUI 版）

視覺化介面，美術組可直接用：
1. 批次選擇大圖檔案（支援多選）
2. 自動偵測透明間隔的 prop
3. 進入標記模式：逐一命名、排除不要的物件、全選/全不選切換
4. 匯出前自動驗證檔名合法性、目標資料夾衝突、像素重複
5. 衝突時彈窗讓使用者決定：跳過、覆蓋、改名保留
6. 批次模式：多張圖依序處理，匯出完自動載下一張，最後顯示總計

依賴：Pillow（已在 requirements.txt）、tkinter（Python 內建）
執行：python ai_engine/scripts/split_map_assets_gui.py

暫存區：建議把待處理的大圖放到 game/assets/textures/temp/
（已加入 .gitignore 不會誤推上 GitHub）
"""

import hashlib
import re
import tkinter as tk
from collections import deque
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from PIL import Image, ImageChops, ImageTk

# ── Blob 偵測演算法常數 ──────────────────────────────────────────
# 預設 alpha 門檻：低於此值視為透明背景（可在 UI 覆寫）
DEFAULT_ALPHA_THRESHOLD: int = 16
# 忽略過小的雜訊斑點（< 64 px²）
DEFAULT_MIN_AREA: int = 64

# ── 背景色偵測常數 ──────────────────────────────────────────────
# 縮圖尺寸：加速背景色偵測，夠用不失真
BG_DETECT_SAMPLE_SIZE: int = 256
# 最低占比門檻：占比 > 此值的單一顏色才視為背景色
BG_DETECT_MIN_RATIO: float = 0.25
# 去背容差：RGB 各通道差距 ≤ 此值即視為同色
DEFAULT_BG_TOLERANCE: int = 8

# 合法檔名（不含副檔名）: 僅限 ASCII 英數 + 底線 + 連字號 + 點
# 檔名必須純 ASCII，原因：
#   1. GitHub 跨平台 checkout 時非 ASCII 檔名易亂碼（macOS NFD vs Windows NFC）
#   2. Godot `res://` 路徑對非 ASCII 支援有地雷（import 會失敗）
#   3. Python 在 Windows cp950 / 其他 locale 下讀檔路徑不可靠
VALID_NAME_PATTERN: re.Pattern[str] = re.compile(r"^[a-zA-Z0-9_\-.]+$")

THUMBNAIL_SIZE: tuple[int, int] = (96, 96)

# 專案結構相對路徑（從此腳本位置算）
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
DEFAULT_TEMP_DIR: Path = PROJECT_ROOT / "game" / "assets" / "textures" / "temp"
DEFAULT_PROPS_DIR: Path = PROJECT_ROOT / "game" / "assets" / "textures" / "environment" / "props"


def pixel_hash(img: Image.Image) -> str:
    """對圖片的像素資料計算 SHA-256。相同像素 → 相同 hash，不受 PNG 壓縮差異影響。"""
    normalized: Image.Image = img.convert("RGBA")
    h: hashlib._Hash = hashlib.sha256()
    h.update(f"{normalized.size[0]}x{normalized.size[1]}:".encode())
    h.update(normalized.tobytes())
    return h.hexdigest()


def diagnose_transparency(raw_img: Image.Image) -> dict:
    """分析圖片透明度健康度，判斷是否適合自動拆圖。

    判斷依據：
    - 圖片模式（RGBA 才支援真實 alpha）
    - 完全透明像素比例（背景該占大部分）
    - 半透明像素比例（過高代表邊緣羽化 → 會把 prop 橋接成一塊）

    回傳 dict：
        ok: bool            — 是否通過（無警告）
        severity: str       — "ok" / "warning" / "error"
        mode: str           — 原圖模式
        size: (w, h)
        transparent_pct: float     — alpha = 0 比例 (%)
        semi_pct: float            — 0 < alpha < 255 比例 (%)
        opaque_pct: float          — alpha = 255 比例 (%)
        messages: list[str]        — 警告/錯誤訊息
        suggestions: list[str]     — 建議修正動作
    """
    messages: list[str] = []
    suggestions: list[str] = []
    severity: str = "ok"

    # 1. 模式檢查
    if raw_img.mode not in ("RGBA", "LA", "P"):
        return {
            "ok": False,
            "severity": "error",
            "mode": raw_img.mode,
            "size": raw_img.size,
            "transparent_pct": 0.0,
            "semi_pct": 0.0,
            "opaque_pct": 100.0,
            "messages": [
                f"圖片模式為 {raw_img.mode}，沒有 alpha 通道",
                "所有像素會被視為不透明，整張圖會判成一個 blob",
            ],
            "suggestions": [
                "檢查原始檔是否有透明背景",
                "匯出為 PNG 32-bit（PNG-24 with transparency）而非 JPG/PNG-8",
            ],
        }

    # 轉 RGBA 才能正確取 alpha histogram
    img: Image.Image = raw_img.convert("RGBA")
    alpha: Image.Image = img.split()[3]
    hist: list[int] = alpha.histogram()  # 256 個 bucket
    total: int = img.width * img.height

    fully_transparent: int = hist[0]
    low_alpha: int = sum(hist[:16])       # alpha < 16，含 0（低於偵測門檻）
    semi: int = sum(hist[1:255])          # 0 < alpha < 255
    fully_opaque: int = hist[255]

    transparent_pct: float = fully_transparent / total * 100
    semi_pct: float = semi / total * 100
    opaque_pct: float = fully_opaque / total * 100
    low_alpha_pct: float = low_alpha / total * 100

    # 2. 透明比例檢查：prop 拼貼大圖應至少 20% 以上是背景
    if transparent_pct < 5:
        severity = "error"
        messages.append(
            f"完全透明像素只有 {transparent_pct:.1f}%（正常應 ≥ 30%）"
        )
        messages.append("整張圖幾乎沒透明背景 → 會被判成一個 blob")
        suggestions.append("匯出時確認有勾「透明背景」選項")
        suggestions.append("確認原檔背景圖層是隱藏或刪除的")
    elif transparent_pct < 20:
        severity = "warning" if severity == "ok" else severity
        messages.append(
            f"完全透明比例偏低（{transparent_pct:.1f}%，建議 ≥ 30%）"
        )

    # 3. 半透明比例檢查：> 8% 通常是邊緣羽化或陰影
    if semi_pct > 15:
        severity = "error"
        messages.append(
            f"半透明像素占 {semi_pct:.1f}%（正常應 < 5%）"
        )
        messages.append("邊緣可能有羽化/外發光/陰影 → 會把多個 prop 橋接起來")
        suggestions.append("移除圖層的 Outer Glow / Feather / Drop Shadow 效果")
        suggestions.append("像素風建議邊緣使用硬邊（無抗鋸齒）")
    elif semi_pct > 5:
        severity = "warning" if severity == "ok" else severity
        messages.append(
            f"半透明像素偏多（{semi_pct:.1f}%），可能影響拆圖準確度"
        )
        suggestions.append("若拆圖結果異常，嘗試把 Alpha 門檻從 16 調高到 32 或 64")

    if severity == "ok":
        messages.append("透明度檢查通過 ✓")

    return {
        "ok": severity == "ok",
        "severity": severity,
        "mode": raw_img.mode,
        "size": raw_img.size,
        "transparent_pct": transparent_pct,
        "semi_pct": semi_pct,
        "opaque_pct": opaque_pct,
        "low_alpha_pct": low_alpha_pct,
        "messages": messages,
        "suggestions": suggestions,
    }


def save_alpha_preview(img: Image.Image, output_path: Path) -> None:
    """把 alpha 通道單獨存成灰階圖，方便視覺檢查。

    白色 = 完全不透明，黑色 = 完全透明，灰色 = 半透明（問題點）。
    """
    alpha: Image.Image = img.convert("RGBA").split()[3]
    alpha.save(output_path)


# ── 背景色偵測與去背（for 沒勾透明匯出的大圖） ───────────────────

def detect_background_color(
    img: Image.Image,
    sample_size: int = BG_DETECT_SAMPLE_SIZE,
    min_ratio: float = BG_DETECT_MIN_RATIO,
    alpha_min: int = 32,
) -> Optional[tuple[tuple[int, int, int], float]]:
    """偵測圖片中占比最高的單一顏色，判斷是否為背景色。

    演算法：
    1. 縮圖到 sample_size × sample_size（加速，保留色彩分布）
    2. 用 getcolors 精確計數每種顏色（僅計算 alpha ≥ alpha_min 的不透明像素）
    3. 若最常見顏色 > min_ratio 占比 → 判定為背景色

    Returns:
        ((r, g, b), ratio) — 若偵測到背景色
        None — 若沒有單一顏色占主導地位
    """
    rgba: Image.Image = img.convert("RGBA")
    thumb: Image.Image = rgba.copy()
    thumb.thumbnail((sample_size, sample_size), Image.Resampling.NEAREST)

    max_colors: int = thumb.width * thumb.height
    colors: Optional[list[tuple[int, tuple[int, int, int, int]]]] = thumb.getcolors(maxcolors=max_colors)
    if not colors:
        return None

    # 只看不透明像素（避免已透明的 alpha=0 佔分母）
    opaque: list[tuple[int, tuple[int, int, int, int]]] = [
        (cnt, rgba_tuple) for cnt, rgba_tuple in colors if rgba_tuple[3] >= alpha_min
    ]
    if not opaque:
        return None

    total_opaque: int = sum(cnt for cnt, _ in opaque)
    top_cnt, top_rgba = max(opaque, key=lambda x: x[0])
    ratio: float = top_cnt / total_opaque

    if ratio >= min_ratio:
        return ((top_rgba[0], top_rgba[1], top_rgba[2]), ratio)
    return None


def remove_color_background(
    img: Image.Image,
    bg_color: tuple[int, int, int],
    tolerance: int = DEFAULT_BG_TOLERANCE,
) -> Image.Image:
    """將接近 bg_color 的像素設為透明，回傳新的 RGBA 圖。

    實作：用 Pillow ImageChops 向量化操作（C 實作），比純 Python pixel loop 快 100×。
    對 4.2M 像素圖 < 1 秒。

    Args:
        bg_color: 要去除的 RGB 色
        tolerance: 各通道容差（<= 此值視為同色）。0 = 嚴格相同，8 = 小量抗鋸齒，32 = 寬鬆
    """
    rgba: Image.Image = img.convert("RGBA")
    r, g, b, a = rgba.split()
    solid: Image.Image = Image.new("RGB", rgba.size, bg_color)
    rgb: Image.Image = Image.merge("RGB", (r, g, b))

    # 逐通道差異
    diff: Image.Image = ImageChops.difference(rgb, solid)
    dr, dg, db = diff.split()
    # 三通道差異取 max（只要任一通道超過容差就算不同色）
    max_diff: Image.Image = ImageChops.lighter(ImageChops.lighter(dr, dg), db)
    # 建立保留遮罩：diff > tolerance → 255（保留），否則 0（去除）
    keep_mask: Image.Image = max_diff.point(lambda v: 255 if v > tolerance else 0)
    # 新 alpha = min(原 alpha, keep_mask)：原本透明保持透明，匹配背景色的變透明
    new_alpha: Image.Image = ImageChops.darker(a, keep_mask)
    return Image.merge("RGBA", (r, g, b, new_alpha))


# ── Blob 偵測（4-connected Connected Component Labeling via BFS flood-fill） ──

def find_blobs(
    img: Image.Image,
    min_area: int,
    alpha_threshold: int = DEFAULT_ALPHA_THRESHOLD,
) -> list[tuple[int, int, int, int]]:
    """找出圖中所有連通的非透明區域（blob），回傳每個 blob 的 bbox。

    Args:
        img: RGBA Image
        min_area: 小於此面積的 blob 會被忽略（雜訊過濾）
        alpha_threshold: 低於此 alpha 值視為背景（透明）

    Returns:
        list of (x1, y1, x2, y2) 其中 x2/y2 為 exclusive
    """
    w, h = img.size
    alpha: bytes = img.split()[3].tobytes()
    visited: bytearray = bytearray(w * h)

    bboxes: list[tuple[int, int, int, int]] = []

    for start_y in range(h):
        for start_x in range(w):
            start_idx: int = start_y * w + start_x
            if visited[start_idx]:
                continue
            if alpha[start_idx] < alpha_threshold:
                visited[start_idx] = 1
                continue

            # BFS flood-fill
            queue: deque[tuple[int, int]] = deque()
            queue.append((start_x, start_y))
            visited[start_idx] = 1
            min_x: int = start_x
            min_y: int = start_y
            max_x: int = start_x
            max_y: int = start_y
            pixel_count: int = 0

            while queue:
                cx, cy = queue.popleft()
                pixel_count += 1
                if cx < min_x:
                    min_x = cx
                elif cx > max_x:
                    max_x = cx
                if cy < min_y:
                    min_y = cy
                elif cy > max_y:
                    max_y = cy

                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nx: int = cx + dx
                    ny: int = cy + dy
                    if 0 <= nx < w and 0 <= ny < h:
                        nidx: int = ny * w + nx
                        if not visited[nidx] and alpha[nidx] >= alpha_threshold:
                            visited[nidx] = 1
                            queue.append((nx, ny))

            if pixel_count >= min_area:
                bboxes.append((min_x, min_y, max_x + 1, max_y + 1))

    return bboxes


def sort_reading_order(
    bboxes: list[tuple[int, int, int, int]],
    row_tolerance: int = 50,
) -> list[tuple[int, int, int, int]]:
    """依閱讀順序（由上到下、由左到右）排序 bbox。同列容忍度為 row_tolerance 像素。"""
    return sorted(bboxes, key=lambda b: (b[1] // row_tolerance, b[0]))


def validate_filename(name: str) -> Optional[str]:
    """檢查檔名是否合法。回傳錯誤訊息或 None。

    規則：必須純 ASCII（不可含中文、日文、韓文、emoji、全形符號等），
    只允許英數、底線、連字號、點。
    """
    if not name or not name.strip():
        return "檔名不可為空"
    if not name.isascii():
        non_ascii: str = "".join(sorted(set(c for c in name if not c.isascii())))
        return f"檔名僅可用純 ASCII，不可含：{non_ascii}"
    if not VALID_NAME_PATTERN.match(name):
        return "檔名僅可含英數、底線、連字號、點（不可有空白或 /\\:*?\"<>|）"
    if name.startswith(".") or name.startswith("-"):
        return "檔名不可以 . 或 - 開頭"
    return None


class PropEntry:
    """單一偵測到的 prop 狀態。"""

    def __init__(self, index: int, bbox: tuple[int, int, int, int], cropped: Image.Image) -> None:
        self.index: int = index
        self.bbox: tuple[int, int, int, int] = bbox
        self.cropped: Image.Image = cropped
        self.pixel_hash: str = pixel_hash(cropped)
        self.include_var: Optional[tk.BooleanVar] = None
        self.name_var: Optional[tk.StringVar] = None
        self.thumbnail: Optional[ImageTk.PhotoImage] = None
        self.error_label: Optional[ttk.Label] = None


class SplitterApp:
    """主應用程式（tkinter 單視窗多狀態）。"""

    def __init__(self, root: tk.Tk) -> None:
        self.root: tk.Tk = root
        self.root.title("地圖素材拆解工具")
        self.root.geometry("1100x780")
        self.root.minsize(900, 600)

        # 批次狀態
        self.input_paths: list[Path] = []      # 待處理的大圖清單
        self.current_index: int = 0             # 當前處理到第幾張
        self.dest_dir: Optional[Path] = None
        self.mega_image: Optional[Image.Image] = None
        self.prop_entries: list[PropEntry] = []

        # 批次累計統計（跨多張大圖）
        self.batch_stats: dict[str, int] = {"saved": 0, "skipped": 0, "deleted": 0}

        # tkinter 變數（在 setup 畫面用）
        self.input_listbox: Optional[tk.Listbox] = None  # 在 _build_setup_ui 建立
        self.dest_var: tk.StringVar = tk.StringVar()
        self.min_area_var: tk.StringVar = tk.StringVar(value=str(DEFAULT_MIN_AREA))
        self.alpha_thresh_var: tk.StringVar = tk.StringVar(value=str(DEFAULT_ALPHA_THRESHOLD))
        # 背景色自動去除（救援沒勾透明匯出的大圖）
        self.auto_remove_bg_var: tk.BooleanVar = tk.BooleanVar(value=True)
        self.bg_tolerance_var: tk.StringVar = tk.StringVar(value=str(DEFAULT_BG_TOLERANCE))

        # 框架容器
        self.main_frame: ttk.Frame = ttk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 鍵盤快捷鍵
        self.root.bind("<Control-a>", lambda _e: self._toggle_all(True))
        self.root.bind("<Control-A>", lambda _e: self._toggle_all(True))
        self.root.bind("<Control-d>", lambda _e: self._toggle_all(False))
        self.root.bind("<Control-D>", lambda _e: self._toggle_all(False))
        self.root.bind("<Control-i>", lambda _e: self._invert_selection())
        self.root.bind("<Control-I>", lambda _e: self._invert_selection())

        self._build_setup_ui()

    # ── 切換畫面 ──────────────────────────────────────────────────
    def _clear_main(self) -> None:
        for widget in self.main_frame.winfo_children():
            widget.destroy()

    # ── Setup 畫面 ────────────────────────────────────────────────
    def _build_setup_ui(self) -> None:
        self._clear_main()
        frame: ttk.Frame = self.main_frame

        ttk.Label(frame, text="地圖素材拆解工具", font=("TkDefaultFont", 16, "bold")).pack(
            anchor=tk.W, pady=(0, 16)
        )

        # Step 1: 大圖清單（支援批次）
        step1: ttk.LabelFrame = ttk.LabelFrame(frame, text="1. 選擇待處理大圖（可一次多張）", padding=10)
        step1.pack(fill=tk.BOTH, expand=True, pady=6)

        list_row: ttk.Frame = ttk.Frame(step1)
        list_row.pack(fill=tk.BOTH, expand=True)
        self.input_listbox = tk.Listbox(list_row, selectmode=tk.EXTENDED, height=6, activestyle="dotbox")
        self.input_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        lb_scroll: ttk.Scrollbar = ttk.Scrollbar(list_row, orient=tk.VERTICAL, command=self.input_listbox.yview)
        lb_scroll.pack(side=tk.LEFT, fill=tk.Y)
        self.input_listbox.config(yscrollcommand=lb_scroll.set)
        self._refresh_input_listbox()

        btn_row: ttk.Frame = ttk.Frame(step1)
        btn_row.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(btn_row, text="➕ 加入檔案...", command=self._on_browse_input).pack(side=tk.LEFT)
        ttk.Button(btn_row, text="➖ 移除所選", command=self._remove_selected_inputs).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        ttk.Button(btn_row, text="🗑 清空清單", command=self._clear_inputs).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Separator(btn_row, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Button(btn_row, text="🔍 檢查透明度", command=self._on_diagnose).pack(side=tk.LEFT)
        ttk.Label(
            btn_row,
            text="（拆圖結果異常時先按這個排查）",
            foreground="#666",
        ).pack(side=tk.LEFT, padx=(6, 0))

        # Step 2: 目標資料夾
        step2: ttk.LabelFrame = ttk.LabelFrame(frame, text="2. 選擇目標資料夾", padding=10)
        step2.pack(fill=tk.X, pady=6)
        row2: ttk.Frame = ttk.Frame(step2)
        row2.pack(fill=tk.X)
        ttk.Entry(row2, textvariable=self.dest_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row2, text="瀏覽...", command=self._on_browse_dest).pack(side=tk.LEFT, padx=(6, 0))
        hint: ttk.Label = ttk.Label(
            step2,
            text="建議：game/assets/textures/environment/props/nature 或 .../urban",
            foreground="#666",
        )
        hint.pack(anchor=tk.W, pady=(4, 0))

        # Step 3: 進階
        adv: ttk.LabelFrame = ttk.LabelFrame(frame, text="3. 進階選項（通常用預設即可）", padding=10)
        adv.pack(fill=tk.X, pady=6)
        grid: ttk.Frame = ttk.Frame(adv)
        grid.pack(fill=tk.X)
        ttk.Label(grid, text="最小 blob 面積 (px²)：").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(grid, textvariable=self.min_area_var, width=10).grid(row=0, column=1, sticky=tk.W, pady=2)
        ttk.Label(grid, text="（小於此值視為雜訊）", foreground="#666").grid(
            row=0, column=2, sticky=tk.W, padx=(8, 0)
        )
        ttk.Label(grid, text="Alpha 門檻 (0-255)：").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(grid, textvariable=self.alpha_thresh_var, width=10).grid(row=1, column=1, sticky=tk.W, pady=2)
        ttk.Label(grid, text="（低於此值視為背景）", foreground="#666").grid(
            row=1, column=2, sticky=tk.W, padx=(8, 0)
        )

        # 自動去除背景色（美術忘了勾透明時的救援）
        ttk.Separator(adv, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
        bg_row: ttk.Frame = ttk.Frame(adv)
        bg_row.pack(fill=tk.X)
        ttk.Checkbutton(
            bg_row,
            text="自動偵測並去除主要背景色（美術忘了勾透明匯出時用）",
            variable=self.auto_remove_bg_var,
        ).pack(side=tk.LEFT)
        ttk.Label(bg_row, text="容差：", foreground="#666").pack(side=tk.LEFT, padx=(12, 0))
        ttk.Entry(bg_row, textvariable=self.bg_tolerance_var, width=6).pack(side=tk.LEFT)
        ttk.Label(
            bg_row,
            text="（0=嚴格同色、8=抗鋸齒容忍、32=寬鬆）",
            foreground="#666",
        ).pack(side=tk.LEFT, padx=(4, 0))

        # 偵測按鈕
        bottom: ttk.Frame = ttk.Frame(frame)
        bottom.pack(fill=tk.X, pady=(16, 0))
        ttk.Button(bottom, text="偵測並進入標記 →", command=self._on_detect).pack(side=tk.RIGHT)

    def _refresh_input_listbox(self) -> None:
        """將 self.input_paths 同步到 Listbox 顯示。"""
        if self.input_listbox is None:
            return
        self.input_listbox.delete(0, tk.END)
        for p in self.input_paths:
            # 顯示相對於專案根的路徑（較短），失敗則顯示完整路徑
            try:
                display: str = str(p.relative_to(PROJECT_ROOT))
            except ValueError:
                display = str(p)
            self.input_listbox.insert(tk.END, display)

    def _on_browse_input(self) -> None:
        """多選檔案加入清單。初始目錄設為 temp/。"""
        initial: Path = DEFAULT_TEMP_DIR if DEFAULT_TEMP_DIR.exists() else PROJECT_ROOT
        paths: tuple[str, ...] = filedialog.askopenfilenames(
            title="選擇大圖（可按住 Ctrl 或 Shift 多選）",
            initialdir=str(initial),
            filetypes=[
                ("PNG 圖片", "*.png"),
                ("所有圖片", "*.png *.jpg *.jpeg *.webp"),
                ("全部", "*.*"),
            ],
        )
        if not paths:
            return
        # 去重加入
        existing: set[Path] = set(self.input_paths)
        for p in paths:
            path_obj: Path = Path(p)
            if path_obj not in existing:
                self.input_paths.append(path_obj)
                existing.add(path_obj)
        self._refresh_input_listbox()

    def _remove_selected_inputs(self) -> None:
        """從清單移除選取項。"""
        if self.input_listbox is None:
            return
        selected: tuple[int, ...] = self.input_listbox.curselection()
        if not selected:
            return
        # 倒序刪除避免 index 位移
        for idx in sorted(selected, reverse=True):
            del self.input_paths[idx]
        self._refresh_input_listbox()

    def _clear_inputs(self) -> None:
        self.input_paths.clear()
        self._refresh_input_listbox()

    # ── 透明度診斷 ────────────────────────────────────────────────
    def _on_diagnose(self) -> None:
        """對清單中選取的檔案（或全部）執行透明度診斷。"""
        if not self.input_paths:
            messagebox.showinfo("無檔案", "請先加入至少一張大圖")
            return
        # 若 listbox 有選取項就只檢查選取的，否則檢查全部
        if self.input_listbox is not None:
            selected_indices: tuple[int, ...] = self.input_listbox.curselection()
        else:
            selected_indices = ()
        targets: list[Path] = (
            [self.input_paths[i] for i in selected_indices]
            if selected_indices
            else list(self.input_paths)
        )
        self._show_diagnosis_dialog(targets)

    def _show_diagnosis_dialog(self, paths: list[Path]) -> None:
        """顯示透明度診斷結果視窗（每個檔案一個區塊）。"""
        dlg: tk.Toplevel = tk.Toplevel(self.root)
        dlg.title(f"透明度檢查結果 ({len(paths)} 個檔案)")
        dlg.geometry("760x620")
        dlg.transient(self.root)
        dlg.grab_set()

        header: ttk.Frame = ttk.Frame(dlg, padding=10)
        header.pack(fill=tk.X)
        ttk.Label(
            header,
            text="檢查重點：背景是否真透明、邊緣是否有軟化",
            font=("TkDefaultFont", 10, "bold"),
        ).pack(anchor=tk.W)
        ttk.Label(
            header,
            text="理想：完全透明 ≥ 30%，半透明 < 5%",
            foreground="#666",
        ).pack(anchor=tk.W)

        # 捲動容器
        list_frame: ttk.Frame = ttk.Frame(dlg)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10)
        canvas: tk.Canvas = tk.Canvas(list_frame, highlightthickness=0)
        sb: ttk.Scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=canvas.yview)
        inner: ttk.Frame = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor=tk.NW)
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        for path in paths:
            self._build_diagnosis_block(inner, path)

        btns: ttk.Frame = ttk.Frame(dlg, padding=10)
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="關閉", command=dlg.destroy).pack(side=tk.RIGHT)

    def _build_diagnosis_block(self, parent: ttk.Frame, path: Path) -> None:
        """建立單一檔案的診斷區塊。"""
        try:
            raw_img: Image.Image = Image.open(path)
            diag: dict = diagnose_transparency(raw_img)
        except Exception as e:
            fail_frame: ttk.LabelFrame = ttk.LabelFrame(parent, text=path.name, padding=8)
            fail_frame.pack(fill=tk.X, pady=4)
            ttk.Label(fail_frame, text=f"✗ 無法讀取：{e}", foreground="#c0392b").pack(anchor=tk.W)
            return

        # 標題加狀態圖示
        icon: str = {"ok": "✓", "warning": "⚠", "error": "✗"}[diag["severity"]]
        color: str = {"ok": "#27ae60", "warning": "#d68910", "error": "#c0392b"}[
            diag["severity"]
        ]
        block: ttk.LabelFrame = ttk.LabelFrame(
            parent, text=f"{icon}  {path.name}", padding=10
        )
        block.pack(fill=tk.X, pady=4)

        # 基本資訊
        info: ttk.Frame = ttk.Frame(block)
        info.pack(fill=tk.X)
        w, h = diag["size"]
        ttk.Label(
            info,
            text=f"模式：{diag['mode']}   尺寸：{w} × {h}",
            foreground="#444",
        ).pack(anchor=tk.W)

        # Alpha 分布條
        dist: ttk.Frame = ttk.Frame(block)
        dist.pack(fill=tk.X, pady=(6, 0))

        self._add_alpha_bar(
            dist, "完全透明 (α=0)", diag["transparent_pct"],
            ideal_min=30, color="#95a5a6",
        )
        self._add_alpha_bar(
            dist, "半透明 (軟邊)", diag["semi_pct"],
            ideal_max=5, color="#e67e22",
        )
        self._add_alpha_bar(
            dist, "完全不透明 (α=255)", diag["opaque_pct"],
            color="#2c3e50",
        )

        # 訊息
        if diag["messages"]:
            msg_frame: ttk.Frame = ttk.Frame(block)
            msg_frame.pack(fill=tk.X, pady=(8, 0))
            for msg in diag["messages"]:
                ttk.Label(msg_frame, text=f"  {icon} {msg}", foreground=color).pack(anchor=tk.W)

        # 建議
        if diag["suggestions"]:
            sug_frame: ttk.Frame = ttk.Frame(block)
            sug_frame.pack(fill=tk.X, pady=(4, 0))
            ttk.Label(sug_frame, text="建議：", font=("TkDefaultFont", 9, "bold")).pack(anchor=tk.W)
            for sug in diag["suggestions"]:
                ttk.Label(sug_frame, text=f"  • {sug}", foreground="#555").pack(anchor=tk.W)

        # 背景色偵測（若透明度不足時特別有用）
        if diag["transparent_pct"] < 20:
            bg_result: Optional[tuple[tuple[int, int, int], float]] = detect_background_color(raw_img)
            bg_frame: ttk.Frame = ttk.Frame(block)
            bg_frame.pack(fill=tk.X, pady=(6, 0))
            if bg_result is not None:
                (br, bgc, bb), ratio = bg_result
                hex_color: str = f"#{br:02x}{bgc:02x}{bb:02x}"
                info_row: ttk.Frame = ttk.Frame(bg_frame)
                info_row.pack(fill=tk.X)
                ttk.Label(
                    info_row,
                    text="🎨 偵測到主要顏色（可視為背景去除）：",
                    font=("TkDefaultFont", 9, "bold"),
                ).pack(side=tk.LEFT)
                # 顏色色塊預覽
                swatch: tk.Label = tk.Label(
                    info_row, bg=hex_color, width=4, height=1, bd=1, relief=tk.SOLID
                )
                swatch.pack(side=tk.LEFT, padx=(4, 4))
                ttk.Label(
                    info_row,
                    text=f"RGB({br}, {bgc}, {bb})   占比 {ratio * 100:.1f}%",
                    foreground="#555",
                ).pack(side=tk.LEFT)
                ttk.Label(
                    bg_frame,
                    text="→ Setup 勾「自動去除主要背景色」後偵測，會自動把此色轉透明",
                    foreground="#2980b9",
                ).pack(anchor=tk.W, pady=(2, 0))
            else:
                ttk.Label(
                    bg_frame,
                    text="🎨 沒偵測到單一主色（可能是漸層/雜色背景，自動去背無法救援）",
                    foreground="#666",
                ).pack(anchor=tk.W)

        # 匯出 alpha 預覽按鈕
        action_frame: ttk.Frame = ttk.Frame(block)
        action_frame.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(
            action_frame,
            text="💾 匯出 alpha 預覽圖",
            command=lambda p=path, img=raw_img: self._export_alpha_preview(p, img),
        ).pack(side=tk.LEFT)
        ttk.Label(
            action_frame,
            text="（存成灰階圖：白=實體、黑=透明、灰=軟邊）",
            foreground="#666",
        ).pack(side=tk.LEFT, padx=(6, 0))

    def _add_alpha_bar(
        self,
        parent: ttk.Frame,
        label: str,
        pct: float,
        ideal_min: Optional[float] = None,
        ideal_max: Optional[float] = None,
        color: str = "#444",
    ) -> None:
        """單一 alpha 類別的進度條行。"""
        row: ttk.Frame = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=1)
        ttk.Label(row, text=label, width=22).pack(side=tk.LEFT)
        bar: ttk.Progressbar = ttk.Progressbar(row, length=260, maximum=100, value=pct)
        bar.pack(side=tk.LEFT, padx=(0, 6))

        # 判斷是否在理想區間
        in_ideal: bool = True
        hint: str = ""
        if ideal_min is not None and pct < ideal_min:
            in_ideal = False
            hint = f"（應 ≥ {ideal_min:.0f}%）"
        if ideal_max is not None and pct > ideal_max:
            in_ideal = False
            hint = f"（應 < {ideal_max:.0f}%）"
        value_color: str = "#27ae60" if in_ideal else "#c0392b"
        ttk.Label(
            row,
            text=f"{pct:5.1f}%  {hint}",
            foreground=value_color,
            font=("TkDefaultFont", 9),
        ).pack(side=tk.LEFT)

    def _export_alpha_preview(self, path: Path, img: Image.Image) -> None:
        """把 alpha 通道存成灰階圖，方便用圖片檢視器看哪裡有軟邊「橋」。"""
        output: Path = path.parent / f"{path.stem}_alpha_preview.png"
        try:
            save_alpha_preview(img, output)
            messagebox.showinfo(
                "已匯出",
                f"Alpha 預覽圖已存到：\n{output}\n\n"
                "解讀：\n"
                "• 白色區域 = 實體像素（會被偵測成 prop）\n"
                "• 黑色區域 = 透明背景\n"
                "• 灰色區域 = 半透明（問題點）— 若不同 prop 之間有灰色「橋」連接，就是拆圖失敗的原因",
            )
        except Exception as e:
            messagebox.showerror("匯出失敗", str(e))

    def _on_browse_dest(self) -> None:
        initial: Path = DEFAULT_PROPS_DIR if DEFAULT_PROPS_DIR.exists() else PROJECT_ROOT
        path: str = filedialog.askdirectory(title="選擇目標資料夾", initialdir=str(initial))
        if path:
            self.dest_var.set(path)

    def _on_detect(self) -> None:
        """驗證輸入並啟動批次處理。"""
        if not self.input_paths:
            messagebox.showerror("錯誤", "請至少加入一張大圖")
            return
        dest_str: str = self.dest_var.get().strip()
        if not dest_str:
            messagebox.showerror("錯誤", "請選擇目標資料夾")
            return
        dest_dir: Path = Path(dest_str)
        if not dest_dir.exists():
            if messagebox.askyesno("目標資料夾不存在", f"{dest_dir}\n\n要建立此資料夾嗎？"):
                dest_dir.mkdir(parents=True, exist_ok=True)
            else:
                return

        # 驗證所有輸入檔都存在
        missing: list[Path] = [p for p in self.input_paths if not p.exists()]
        if missing:
            messagebox.showerror("錯誤", "以下檔案不存在：\n" + "\n".join(str(p) for p in missing))
            return

        try:
            int(self.min_area_var.get())
            alpha_thresh: int = int(self.alpha_thresh_var.get())
        except ValueError:
            messagebox.showerror("錯誤", "最小面積與 alpha 門檻必須是整數")
            return
        if not 0 <= alpha_thresh <= 255:
            messagebox.showerror("錯誤", "Alpha 門檻須在 0-255 之間")
            return

        # 啟動批次
        self.dest_dir = dest_dir
        self.current_index = 0
        self.batch_stats = {"saved": 0, "skipped": 0, "deleted": 0}
        self._process_current_file()

    def _process_current_file(self) -> None:
        """處理當前索引的大圖：載入 + 透明度預檢 + 偵測 blob + 切換到標記畫面。"""
        assert 0 <= self.current_index < len(self.input_paths)
        input_path: Path = self.input_paths[self.current_index]

        try:
            min_area: int = int(self.min_area_var.get())
            alpha_thresh: int = int(self.alpha_thresh_var.get())
            bg_tolerance: int = int(self.bg_tolerance_var.get())
        except ValueError:
            messagebox.showerror("錯誤", "最小面積、alpha 門檻與容差必須是整數")
            self._build_setup_ui()
            return

        # 預檢透明度（快速，不用跑整個 BFS）
        try:
            raw_img: Image.Image = Image.open(input_path).convert("RGBA")
            diag: dict = diagnose_transparency(raw_img)
        except Exception as e:
            messagebox.showerror("讀取失敗", f"{input_path.name}：{e}")
            self._advance_or_finish()
            return

        # 準備實際要送去偵測的圖（可能經過去背處理）
        working_img: Image.Image = raw_img
        bg_removed_info: Optional[str] = None  # 記錄去背摘要顯示給使用者

        # 若透明度不足且啟用自動去背 → 嘗試找主要背景色並去除
        needs_rescue: bool = diag["severity"] == "error" and diag["transparent_pct"] < 20
        if needs_rescue and self.auto_remove_bg_var.get():
            bg_result: Optional[tuple[tuple[int, int, int], float]] = detect_background_color(raw_img)
            if bg_result is not None:
                (br, bgc, bb), ratio = bg_result
                confirm: bool = messagebox.askyesno(
                    "偵測到背景色",
                    f"{input_path.name} 透明背景只有 {diag['transparent_pct']:.1f}%\n\n"
                    f"偵測到主要顏色：RGB({br}, {bgc}, {bb})  占 {ratio * 100:.1f}%\n\n"
                    f"要將此色視為背景並去背（alpha 設 0）再偵測嗎？\n"
                    f"（容差 = {bg_tolerance}）",
                )
                if confirm:
                    working_img = remove_color_background(raw_img, (br, bgc, bb), bg_tolerance)
                    bg_removed_info = f"已將 RGB({br},{bgc},{bb}) 視為背景去除"
                    # 去背後重跑診斷，確認問題解除
                    diag = diagnose_transparency(working_img)
                    needs_rescue = diag["severity"] == "error" and diag["transparent_pct"] < 20

        # 若仍有透明度問題（未啟用去背、未偵測到主色、或去背後仍不夠）→ 警告
        if diag["severity"] == "error":
            msg: str = (
                f"{input_path.name} 透明度檢查未通過\n\n"
                + "\n".join(f"• {m}" for m in diag["messages"])
                + "\n\n建議：\n"
                + "\n".join(f"• {s}" for s in diag["suggestions"])
                + "\n\n仍要繼續偵測嗎？（可能會得到一個巨大 blob）"
            )
            if not messagebox.askyesno("透明度有問題", msg, icon="warning"):
                self._advance_or_finish()
                return

        # Progress 視窗
        progress_msg: str = (
            f"正在偵測 prop…\n"
            f"第 {self.current_index + 1}/{len(self.input_paths)} 張：{input_path.name}\n"
            f"（大圖約需 10-30 秒）"
        )
        if bg_removed_info:
            progress_msg += f"\n{bg_removed_info}"

        progress: tk.Toplevel = tk.Toplevel(self.root)
        progress.title("處理中")
        progress.geometry("420x120")
        progress.transient(self.root)
        ttk.Label(progress, text=progress_msg, padding=10).pack(pady=10)
        progress.update()

        try:
            self.mega_image = working_img
            bboxes: list[tuple[int, int, int, int]] = find_blobs(
                self.mega_image, min_area, alpha_threshold=alpha_thresh
            )
            bboxes = sort_reading_order(bboxes)
        except Exception as e:
            progress.destroy()
            messagebox.showerror("偵測失敗", f"{input_path.name}：{e}")
            self._advance_or_finish()
            return
        finally:
            progress.destroy()

        if not bboxes:
            skip: bool = messagebox.askyesno(
                "沒找到 prop",
                f"{input_path.name} 沒偵測到 prop\n（可能是沒有透明背景或全部連在一起）\n\n跳過這張繼續下一張？",
            )
            if skip:
                self._advance_or_finish()
            else:
                self._build_setup_ui()
            return

        # 建立 PropEntry
        self.prop_entries = []
        for i, bbox in enumerate(bboxes, 1):
            cropped: Image.Image = self.mega_image.crop(bbox)
            entry: PropEntry = PropEntry(i, bbox, cropped)
            self.prop_entries.append(entry)

        self._build_labeling_ui()

    def _advance_or_finish(self) -> None:
        """前進到批次中的下一張，若已處理完則顯示總計並回到 setup。"""
        self.current_index += 1
        if self.current_index < len(self.input_paths):
            self._process_current_file()
            return

        # 全部處理完
        s: dict[str, int] = self.batch_stats
        msg: str = (
            f"批次處理完成！\n\n"
            f"共處理 {len(self.input_paths)} 張大圖\n"
            f"成功匯出：{s['saved']}\n"
            f"跳過：{s['skipped']}"
        )
        if s["deleted"] > 0:
            msg += f"\n刪除舊重複檔：{s['deleted']}"
        messagebox.showinfo("批次完成", msg)
        # 重置並回 setup
        self.input_paths.clear()
        self.current_index = 0
        self.batch_stats = {"saved": 0, "skipped": 0, "deleted": 0}
        self._build_setup_ui()

    # ── Labeling 畫面 ─────────────────────────────────────────────
    def _build_labeling_ui(self) -> None:
        self._clear_main()
        frame: ttk.Frame = self.main_frame

        # 頂部狀態列
        top: ttk.Frame = ttk.Frame(frame)
        top.pack(fill=tk.X)

        # 批次進度 + 當前檔名
        current_file: Path = self.input_paths[self.current_index]
        batch_label: str = (
            f"第 {self.current_index + 1}/{len(self.input_paths)} 張：{current_file.name}"
        )
        ttk.Label(top, text=batch_label, font=("TkDefaultFont", 11, "bold"), foreground="#2980b9").pack(
            anchor=tk.W
        )

        status_row: ttk.Frame = ttk.Frame(top)
        status_row.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(
            status_row,
            text=f"找到 {len(self.prop_entries)} 個 prop",
            font=("TkDefaultFont", 12, "bold"),
        ).pack(side=tk.LEFT)
        ttk.Label(status_row, text=f"  目標：{self.dest_dir}", foreground="#666").pack(side=tk.LEFT)
        ttk.Button(status_row, text="← 取消批次", command=self._cancel_batch).pack(side=tk.RIGHT)

        # 工具列
        toolbar: ttk.Frame = ttk.Frame(frame, padding=(0, 8))
        toolbar.pack(fill=tk.X)
        ttk.Button(toolbar, text="全選 (Ctrl+A)", command=lambda: self._toggle_all(True)).pack(
            side=tk.LEFT, padx=(0, 4)
        )
        ttk.Button(toolbar, text="全不選 (Ctrl+D)", command=lambda: self._toggle_all(False)).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(toolbar, text="反選 (Ctrl+I)", command=self._invert_selection).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Label(toolbar, text="批次前綴：").pack(side=tk.LEFT)
        self.prefix_var: tk.StringVar = tk.StringVar()
        ttk.Entry(toolbar, textvariable=self.prefix_var, width=16).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(toolbar, text="套用到全部", command=self._apply_prefix).pack(side=tk.LEFT)

        # 捲動容器（Canvas + 內嵌 Frame）
        list_frame: ttk.Frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        canvas: tk.Canvas = tk.Canvas(list_frame, highlightthickness=0)
        scrollbar: ttk.Scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=canvas.yview)
        inner: ttk.Frame = ttk.Frame(canvas)
        inner.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=inner, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 滑鼠滾輪（Windows）
        def _on_mousewheel(event: tk.Event) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # 每個 prop 一列
        for entry in self.prop_entries:
            self._build_prop_row(inner, entry)

        # 底部操作
        bottom: ttk.Frame = ttk.Frame(frame, padding=(0, 8, 0, 0))
        bottom.pack(fill=tk.X)
        is_last: bool = self.current_index >= len(self.input_paths) - 1
        next_btn_text: str = "驗證並匯出（最後一張）" if is_last else "驗證並匯出 → 下一張"
        ttk.Button(bottom, text="跳過此張", command=self._skip_current).pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(bottom, text=next_btn_text, command=self._validate_and_export).pack(side=tk.RIGHT)

    def _cancel_batch(self) -> None:
        if messagebox.askyesno("取消批次", "確定要取消整個批次？已處理的結果仍會保留。"):
            # 顯示目前統計
            s: dict[str, int] = self.batch_stats
            if s["saved"] + s["skipped"] + s["deleted"] > 0:
                msg: str = (
                    f"已中止批次\n\n"
                    f"目前已處理 {self.current_index}/{len(self.input_paths)} 張\n"
                    f"成功匯出：{s['saved']}\n"
                    f"跳過：{s['skipped']}"
                )
                if s["deleted"] > 0:
                    msg += f"\n刪除舊重複檔：{s['deleted']}"
                messagebox.showinfo("批次中止", msg)
            self.input_paths.clear()
            self.current_index = 0
            self.batch_stats = {"saved": 0, "skipped": 0, "deleted": 0}
            self._build_setup_ui()

    def _skip_current(self) -> None:
        """跳過當前這張大圖不匯出，進下一張。"""
        self._advance_or_finish()

    def _build_prop_row(self, parent: ttk.Frame, entry: PropEntry) -> None:
        row: ttk.Frame = ttk.Frame(parent, padding=(6, 6))
        row.pack(fill=tk.X, pady=2)

        # 勾選框
        entry.include_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row, variable=entry.include_var).pack(side=tk.LEFT, padx=(0, 4))

        # 縮圖（用 Label 加邊框讓像素風縮圖更清楚）
        thumb: Image.Image = entry.cropped.copy()
        thumb.thumbnail(THUMBNAIL_SIZE, Image.Resampling.NEAREST)  # 像素風要用 NEAREST
        entry.thumbnail = ImageTk.PhotoImage(thumb)
        thumb_label: tk.Label = tk.Label(row, image=entry.thumbnail, bd=1, relief=tk.SOLID, bg="#e0e0e0")
        thumb_label.pack(side=tk.LEFT, padx=6)

        # 編號
        ttk.Label(row, text=f"#{entry.index:03d}", width=6, font=("TkDefaultFont", 10, "bold")).pack(
            side=tk.LEFT
        )

        # 名稱輸入
        ttk.Label(row, text="名稱：").pack(side=tk.LEFT)
        entry.name_var = tk.StringVar(value=f"prop_{entry.index:03d}")
        name_entry: ttk.Entry = ttk.Entry(row, textvariable=entry.name_var, width=36, font=("TkDefaultFont", 10))
        name_entry.pack(side=tk.LEFT, padx=(0, 6))

        # 尺寸資訊
        x1, y1, x2, y2 = entry.bbox
        size_text: str = f"{x2 - x1}×{y2 - y1}"
        ttk.Label(row, text=size_text, foreground="#666", width=12).pack(side=tk.LEFT)

        # .png 後綴提示
        ttk.Label(row, text=".png", foreground="#888").pack(side=tk.LEFT)

    # ── 勾選操作 ─────────────────────────────────────────────────
    def _toggle_all(self, include: bool) -> None:
        if not self.prop_entries:
            return
        for entry in self.prop_entries:
            if entry.include_var is not None:
                entry.include_var.set(include)

    def _invert_selection(self) -> None:
        if not self.prop_entries:
            return
        for entry in self.prop_entries:
            if entry.include_var is not None:
                entry.include_var.set(not entry.include_var.get())

    def _apply_prefix(self) -> None:
        prefix: str = self.prefix_var.get().strip()
        if not prefix:
            return
        for entry in self.prop_entries:
            if entry.include_var is None or entry.name_var is None:
                continue
            if entry.include_var.get():
                entry.name_var.set(f"{prefix}_{entry.index:03d}")

    # ── 驗證與匯出 ────────────────────────────────────────────────
    def _validate_and_export(self) -> None:
        assert self.dest_dir is not None

        selected: list[PropEntry] = [
            e for e in self.prop_entries
            if e.include_var is not None and e.include_var.get()
        ]
        if not selected:
            messagebox.showwarning("沒有選取項目", "請至少勾選一個 prop 再匯出")
            return

        # 1. 檢查檔名合法性 + 自身重複
        issues: list[dict] = []
        name_map: dict[str, list[PropEntry]] = {}
        for entry in selected:
            if entry.name_var is None:
                continue
            name: str = entry.name_var.get().strip()
            err: Optional[str] = validate_filename(name)
            if err:
                issues.append({
                    "type": "invalid",
                    "entry": entry,
                    "name": name,
                    "reason": err,
                })
            name_map.setdefault(name, []).append(entry)

        for name, entries in name_map.items():
            if len(entries) > 1:
                for e in entries:
                    issues.append({
                        "type": "internal_dup",
                        "entry": e,
                        "name": name,
                        "reason": f"此次匯出中有 {len(entries)} 個項目用了同名「{name}」",
                    })

        # 2. 檢查目標資料夾現有檔案：檔名衝突 + 像素重複
        existing_files: list[Path] = list(self.dest_dir.glob("*.png"))
        existing_hashes: dict[str, Path] = {}
        for f in existing_files:
            try:
                with Image.open(f) as img:
                    h: str = pixel_hash(img)
                existing_hashes[h] = f
            except Exception:
                continue

        for entry in selected:
            if entry.name_var is None:
                continue
            name = entry.name_var.get().strip()
            if validate_filename(name) is not None:
                continue  # 已在上面標為 invalid
            target: Path = self.dest_dir / f"{name}.png"
            if target.exists():
                issues.append({
                    "type": "name_collision",
                    "entry": entry,
                    "name": name,
                    "reason": f"目標資料夾已有同名檔案：{target.name}",
                    "existing_path": target,
                })
            if entry.pixel_hash in existing_hashes:
                dup_path: Path = existing_hashes[entry.pixel_hash]
                if dup_path != target:  # 避免和 name_collision 重複報（若不同名才報 hash 衝突）
                    issues.append({
                        "type": "hash_dup",
                        "entry": entry,
                        "name": name,
                        "reason": f"像素完全相同的檔案已存在：{dup_path.name}",
                        "existing_path": dup_path,
                    })

        if not issues:
            self._do_export(selected, resolutions={})
            return

        self._show_conflicts_dialog(selected, issues)

    def _show_conflicts_dialog(
        self,
        selected: list[PropEntry],
        issues: list[dict],
    ) -> None:
        """顯示衝突解決對話框。"""
        dlg: tk.Toplevel = tk.Toplevel(self.root)
        dlg.title("發現衝突，請選擇處理方式")
        dlg.geometry("720x500")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(
            dlg,
            text=f"共 {len(issues)} 項需要處理",
            font=("TkDefaultFont", 11, "bold"),
            padding=10,
        ).pack(anchor=tk.W)

        # 捲動列表
        list_frame: ttk.Frame = ttk.Frame(dlg)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10)
        canvas: tk.Canvas = tk.Canvas(list_frame, highlightthickness=0)
        sb: ttk.Scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=canvas.yview)
        inner: ttk.Frame = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor=tk.NW)
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        # key = id(issue_dict), value = StringVar 存處理選擇
        resolutions: dict[int, tk.StringVar] = {}
        has_invalid: bool = False

        for issue in issues:
            row: ttk.LabelFrame = ttk.LabelFrame(
                inner,
                text=f"#{issue['entry'].index:03d}  {issue['name']}.png",
                padding=8,
            )
            row.pack(fill=tk.X, pady=4)

            icon: str = "✗" if issue["type"] == "invalid" else "⚠"
            color: str = "#c0392b" if issue["type"] == "invalid" else "#d68910"
            ttk.Label(row, text=f"{icon} {issue['reason']}", foreground=color).pack(anchor=tk.W)

            if issue["type"] == "invalid" or issue["type"] == "internal_dup":
                has_invalid = True
                ttk.Label(
                    row,
                    text="必須回到標記畫面修正檔名（關閉此視窗後修正）",
                    foreground="#666",
                ).pack(anchor=tk.W, pady=(4, 0))
                continue

            # name_collision / hash_dup：提供處理選項
            var: tk.StringVar = tk.StringVar(value="skip")
            resolutions[id(issue)] = var
            radios: ttk.Frame = ttk.Frame(row)
            radios.pack(anchor=tk.W, pady=(4, 0))
            ttk.Radiobutton(radios, text="跳過此項（保留舊檔）", variable=var, value="skip").pack(
                anchor=tk.W
            )
            ttk.Radiobutton(radios, text="覆蓋舊檔", variable=var, value="overwrite").pack(
                anchor=tk.W
            )
            if issue["type"] == "hash_dup":
                ttk.Radiobutton(
                    radios,
                    text="兩者都保留（將此新檔自動加後綴 _dup）",
                    variable=var,
                    value="keep_both",
                ).pack(anchor=tk.W)
                ttk.Radiobutton(
                    radios,
                    text="刪除目標資料夾中的重複檔案（保留新的此項）",
                    variable=var,
                    value="delete_existing",
                ).pack(anchor=tk.W)
            else:  # name_collision
                ttk.Radiobutton(
                    radios,
                    text="兩者都保留（將此新檔自動加後綴 _2）",
                    variable=var,
                    value="keep_both",
                ).pack(anchor=tk.W)

        # 底部按鈕
        btns: ttk.Frame = ttk.Frame(dlg, padding=10)
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="取消", command=dlg.destroy).pack(side=tk.RIGHT, padx=(4, 0))

        def on_apply() -> None:
            if has_invalid:
                messagebox.showerror(
                    "仍有非法檔名",
                    "有項目的檔名不合法，請關閉此視窗回到標記畫面修正後再試",
                    parent=dlg,
                )
                return
            # 組成每個 entry 的解決方案 map
            per_entry_res: dict[int, tuple[str, str]] = {}
            for issue in issues:
                if issue["type"] in ("name_collision", "hash_dup"):
                    choice: str = resolutions[id(issue)].get()
                    per_entry_res[id(issue["entry"])] = (issue["type"], choice)
            dlg.destroy()
            self._do_export(selected, per_entry_res)

        ttk.Button(btns, text="套用並匯出", command=on_apply).pack(side=tk.RIGHT)

    def _do_export(
        self,
        selected: list[PropEntry],
        resolutions: dict[int, tuple[str, str]],
    ) -> None:
        """實際寫檔。resolutions: entry id → (issue_type, action)。"""
        assert self.dest_dir is not None
        self.dest_dir.mkdir(parents=True, exist_ok=True)

        saved: int = 0
        skipped: int = 0
        deleted: int = 0
        errors: list[str] = []

        for entry in selected:
            if entry.name_var is None:
                continue
            name: str = entry.name_var.get().strip()
            target: Path = self.dest_dir / f"{name}.png"

            action: Optional[str] = None
            issue_type: Optional[str] = None
            if id(entry) in resolutions:
                issue_type, action = resolutions[id(entry)]

            if action == "skip":
                skipped += 1
                continue

            if action == "keep_both":
                if issue_type == "name_collision":
                    counter: int = 2
                    while True:
                        candidate: Path = self.dest_dir / f"{name}_{counter}.png"
                        if not candidate.exists():
                            target = candidate
                            break
                        counter += 1
                else:  # hash_dup
                    candidate = self.dest_dir / f"{name}_dup.png"
                    counter = 2
                    while candidate.exists():
                        candidate = self.dest_dir / f"{name}_dup_{counter}.png"
                        counter += 1
                    target = candidate

            if action == "delete_existing":
                # 刪除目標資料夾裡那個 hash 相同的舊檔
                assert issue_type == "hash_dup"
                # 重新掃一次找 hash 相同的檔（可能因先前處理已變）
                for f in self.dest_dir.glob("*.png"):
                    try:
                        with Image.open(f) as img:
                            if pixel_hash(img) == entry.pixel_hash and f != target:
                                f.unlink()
                                deleted += 1
                                break
                    except Exception:
                        continue

            # 覆蓋、delete_existing、keep_both 都走一般寫檔流程
            try:
                entry.cropped.save(target)
                saved += 1
            except Exception as e:
                errors.append(f"{target.name}: {e}")

        # 累計到批次統計
        self.batch_stats["saved"] += saved
        self.batch_stats["skipped"] += skipped
        self.batch_stats["deleted"] += deleted

        # 若有錯誤或這張是最後一張，顯示當下結果；否則靜默進下一張
        current_file: Path = self.input_paths[self.current_index]
        if errors:
            msg: str = (
                f"{current_file.name} 完成\n\n"
                f"成功匯出：{saved}\n跳過：{skipped}"
            )
            if deleted > 0:
                msg += f"\n刪除舊重複檔：{deleted}"
            msg += f"\n\n錯誤 {len(errors)} 項：\n" + "\n".join(errors[:5])
            messagebox.showwarning("匯出有錯誤", msg)

        self._advance_or_finish()


def main() -> int:
    root: tk.Tk = tk.Tk()
    try:
        # Windows 高 DPI 適配
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    SplitterApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
