# ① 角色素材製作（給生圖人）

本文涵蓋如何**從零產出一個新角色**的所有素材。完成後丟進對應資料夾即可，**不需要操作 Godot**。

> 後續流程：素材 → spritesheet 編譯（[② 2-spritesheet-workflow.md](2-spritesheet-workflow.md)）→ 角色實裝（[③ 3-asset-usage.md](3-asset-usage.md)）。

---

## 0. 一頁總覽

| 素材 | 用途 | 規格 | 存放位置 |
| --- | --- | --- | --- |
| 角色 spritesheet 序列圖 | 走動/idle 動畫 | 92×92 px / 幀，4 方向 | `art_source/characters/<id>/` |
| 對話立繪 | 對話框中的頭像 | 96×96 px | `game/assets/textures/portraits/<id>.png` |

**每個角色一個 ID**（小寫底線，貫穿整個系統）— 例：`chen_ayi`、`master_guang`、`player`。

---

## 1. 通用風格 (General Style)

```
pixel art, top-down RPG, 2.5D perspective, 16-bit style,
warm color palette, Taiwanese urban setting
```

---

## 2. 角色序列圖（spritesheet 來源）

### 2.1 規格（嚴格）

```
規格               值
─────────────────────────────────
每幀尺寸           92×92 px
方向               4（east / west / south / north）
idle 動畫          每方向 4 幀（呼吸/微擺動）
walk 動畫          每方向 6 幀（走路循環）
背景               真正的透明 alpha（不是灰白格子）
檔案格式           PNG（RGBA）
視角               Low Top-down（微俯視）
```

> 每幀大小**必須一致**、角色**置中**、idle 與 walk **明顯區別**（idle 不能有走路動作）。

### 2.2 用 Pixellab AI 生圖（推薦工作流程）

**通用 Prompt**（貼給 AI 用的結構描述，再接角色描述）：

```
Generate a single PNG sprite sheet for a top-down 2.5D pixel art RPG character.

LAYOUT — strict 6-column × 4-row uniform grid, 24 cells total, no gaps, no borders between cells:
  • Row 1 (top):    character facing DOWN  (toward the viewer)
  • Row 2:          character facing RIGHT
  • Row 3:          character facing LEFT
  • Row 4 (bottom): character facing UP    (away from the viewer)

ANIMATION per row — read left to right:
  • Cell 1:     IDLE pose — standing completely still, arms relaxed at sides, feet together, weight centered
  • Cells 2-6:  WALK CYCLE — 5 frames of a smooth looping walk animation for that direction

CRITICAL RULES:
  1. Every cell must be the exact same pixel width and height (uniform grid)
  2. The character must be centered in every cell, same vertical baseline
  3. The idle pose (cell 1) must look clearly different from the walk frames — no mid-step legs
  4. Background must be fully transparent (alpha channel), not a checkerboard pattern
  5. Consistent lighting, proportions, and color palette across all 24 frames
  6. Pixel art style, no anti-aliasing, clean sharp pixels
```

> Pixellab 會把每幀切成獨立 PNG 並放進 `idle/<dir>/frame_*.png` 與 `walk/<dir>/frame_*.png` 結構，並產出 `metadata.json`。

### 2.3 既有角色 Prompt 範例

#### Player Character

```
Young male Taiwanese college student, early 20s.
Brown short hair, blue casual button shirt, dark navy pants, white sneakers.
Slim average build, neutral relaxed expression.
Style: 16-bit pixel art, top-down 2.5D RPG, warm color palette.
```

#### 陳阿姨 (Chen Ayi - Market Vendor)

```
Middle-aged Taiwanese woman, late 40s, market vendor.
Short permed black hair, floral blouse under a beige market apron.
Slightly stout friendly build, warm smile.
Style: 16-bit pixel art, top-down 2.5D RPG, warm color palette.
```

#### 王伯伯 (Wang Bobo - Noodle Shop Owner)

```
Elderly Taiwanese man, late 60s, noodle shop owner.
Thin build, white sleeveless undershirt, grey towel draped over right shoulder.
Calm expression, slightly hunched posture.
Style: 16-bit pixel art, top-down 2.5D RPG, warm color palette.
```

#### 廣師父 (Master Guang - Temple Keeper)

```
Elderly temple keeper / monk figure, age 70+.
Shaved head, long grey traditional Chinese robe, wooden prayer beads around neck.
Serene mysterious expression, upright dignified posture.
Style: 16-bit pixel art, top-down 2.5D RPG, green and warm tones.
```

#### 釣魚老人 (Old Fisherman)

```
Old riverside fisherman, age 60+.
Woven straw sun hat, loose beige linen shirt, dark pants rolled up to calves.
Holding a bamboo fishing rod in right hand.
Relaxed cheerful grin, tanned weathered skin.
Style: 16-bit pixel art, top-down 2.5D RPG, warm golden-hour tones.
```

### 2.4 整理成標準資料夾結構

把 Pixellab 產出整理為以下結構（資料夾名 = NPC ID）：

```
art_source/characters/<id>/
├── metadata.json
├── rotations/
│   ├── east.png  north.png  south.png  west.png
└── animations/
    ├── idle/
    │   └── {east,north,south,west}/frame_*.png
    └── walk/
        └── {east,north,south,west}/frame_*.png
```

> 之前 Pixellab 可能產出 `Breathing_Idle-<hash>/` 之類的長名稱資料夾，**請改成 `idle/` 與 `walk/`** — 這是專案標準。改名後 metadata.json 內部路徑也要對應更新。

---

## 3. 對話立繪（96×96 portrait）

對話框中的頭像，比 sprite 大且精細。

- Size: **96×96** px
- Style: close-up face/bust，比 sprite 多細節
- Background: 透明
- 命名：`<id>.png`（例 `chen_ayi.png`）
- 存放：`game/assets/textures/portraits/<id>.png`

### Prompt 範本

```
pixel art portrait, 96x96, bust shot, [character description],
RPG dialogue portrait style, expressive face, transparent background
```

各角色提示要點：
- 陳阿姨：`warm smile, market apron, permed hair, Taiwanese auntie`
- 王伯伯：`calm wise eyes, towel on shoulder, thin elderly man`
- 廣師父：`mysterious gaze, shaved head, grey robe, prayer beads`
- 釣魚老人：`cheerful grin, straw hat, tanned weathered face`

---

## 4. 通用規範

### 4.1 ID 命名（**硬性**）

```
✅ 只允許：a-z 0-9 _
✅ 必須以字母開頭
✅ 用底線分隔（如 chen_ayi、old_fisher）
❌ 不可用大寫、空格、連字號、中文、emoji
```

ID 一旦定下會出現在 6 個地方（資料夾、metadata、spritesheet PNG、atlas key、portrait PNG、.tres）— 改名牽涉大，**取名時請慎重**。

### 4.2 像素風格

- Filter Mode 已全局設為 Nearest，不需手動設
- 不要用抗鋸齒 / 模糊 / 漸層柔邊
- 色板維持 32 色內

### 4.3 透明度

- 全部素材必須 RGBA
- 背景完全透明（α=0）
- 邊緣不殘留淡灰色（Photoshop 匯出常見問題）

---

## 5. 提交前自檢

### 角色 spritesheet 序列圖

- [ ] 資料夾名 = ID（小寫底線，如 `chen_ayi`）
- [ ] 每幀大小一致（92×92）
- [ ] 4 方向 × {idle, walk} 共 8 組動畫，幀數齊全
- [ ] idle 4 幀、walk 6 幀
- [ ] idle 是靜止站姿（不能有走路動作）
- [ ] 背景真正透明（不是灰白格子）
- [ ] metadata.json 內部路徑指向 `idle/` 與 `walk/`

### 對話立繪

- [ ] 96×96 px、RGBA、透明背景
- [ ] 命名 `<id>.png`
- [ ] 放在 `game/assets/textures/portraits/`

---

## 下一步

素材交完後 → [② 2-spritesheet-workflow.md](2-spritesheet-workflow.md)（編譯 spritesheet）。
