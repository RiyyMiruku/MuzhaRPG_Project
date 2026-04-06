# Art Asset Generation Guide

> AI 生圖提示詞與美術規格指南
> Last updated: 2026-04-06

## General Style Keywords

所有角色和場景應維持統一的視覺風格：

```
pixel art, top-down RPG, 2.5D perspective, 16-bit style,
warm color palette, Taiwanese urban setting
```

---

## 1. Character Sprites

### Spritesheet Format (FINAL SPEC)

```
┌────┬────┬────┬────┬────┬────┐
│ I  │ W1 │ W2 │ W3 │ W4 │ W5 │  Row 0: 正面（下）
├────┼────┼────┼────┼────┼────┤
│ I  │ W1 │ W2 │ W3 │ W4 │ W5 │  Row 1: 右側
├────┼────┼────┼────┼────┼────┤
│ I  │ W1 │ W2 │ W3 │ W4 │ W5 │  Row 2: 左側
├────┼────┼────┼────┼────┼────┤
│ I  │ W1 │ W2 │ W3 │ W4 │ W5 │  Row 3: 背面（上）
└────┴────┴────┴────┴────┴────┘

I  = Idle（站立靜止，單幀，雙手自然下垂、雙腳併攏）
W1~W5 = Walk cycle（走路循環，5 幀）
```

**嚴格要求：**
- **6 columns × 4 rows** = 24 frames total
- Frame size: all frames must be **exactly equal width and height**
- Background: **真正的透明 alpha**（不要灰白格子假透明）
- File format: **PNG**
- Character must be **centered** within each frame
- Shadow optional (if included, must be consistent across all frames)
- **Idle 幀必須是完全靜止的站姿**，不能有走路動作

### Player Character

```
pixel art character sprite sheet, top-down RPG, 4 directions (front/back/left/right),
6 frames per direction: 1 standing idle + 5 walk cycle,
first frame each row is standing still (arms down, feet together),
young male college student, brown hair, blue casual shirt, dark pants, sneakers,
transparent background, consistent pixel size, equal frame grid, game-ready spritesheet
```

### 陳阿姨 (Chen Ayi - Market Vendor)

```
pixel art character sprite sheet, top-down RPG, 4 directions,
6 frames per direction: 1 standing idle + 5 walk cycle,
first frame each row is standing still,
middle-aged Taiwanese woman, short permed hair, market apron over floral blouse,
warm friendly expression, slight stout build,
transparent background, equal frame grid, spritesheet layout
```

### 王伯伯 (Wang Bobo - Noodle Shop Owner)

```
pixel art character sprite sheet, top-down RPG, 4 directions,
6 frames per direction: 1 standing idle + 5 walk cycle,
first frame each row is standing still,
elderly Taiwanese man, thin build, white undershirt with towel on shoulder,
calm expression, slightly hunched posture,
transparent background, equal frame grid, spritesheet layout
```

### 廣師父 (Master Guang - Temple Keeper)

```
pixel art character sprite sheet, top-down RPG, 4 directions,
6 frames per direction: 1 standing idle + 5 walk cycle,
first frame each row is standing still,
elderly monk/temple keeper, shaved head, grey traditional Chinese robe,
serene mysterious expression, prayer beads around neck,
transparent background, equal frame grid, spritesheet layout
```

### 釣魚老人 (Old Fisherman)

```
pixel art character sprite sheet, top-down RPG, 4 directions,
6 frames per direction: 1 standing idle + 5 walk cycle,
first frame each row is standing still,
old fisherman, straw hat, loose shirt, rolled-up pants, holding fishing rod,
relaxed cheerful expression, tanned skin,
transparent background, equal frame grid, spritesheet layout
```

---

## 2. NPC Portraits (Dialogue Box)

用於對話框左側的頭像，較大較精細。

- Size: **96×96** px
- Style: close-up face/bust, more detail than sprite
- Background: transparent or solid dark

### Prompts

```
pixel art portrait, 96x96, bust shot, [character description],
RPG dialogue portrait style, expressive face, transparent background
```

Each NPC:
- 陳阿姨: `warm smile, market apron, permed hair, Taiwanese auntie`
- 王伯伯: `calm wise eyes, towel on shoulder, thin elderly man`
- 廣師父: `mysterious gaze, shaved head, grey robe, prayer beads`
- 釣魚老人: `cheerful grin, straw hat, tanned weathered face`

---

## 3. TileSet (Map Tiles) — FINAL SPEC

### 基本參數

| 項目 | 值 | 說明 |
|------|-----|------|
| Tile 尺寸 | **16×16 px** | 像素美術標準 |
| Camera zoom | **3x** | 每個 tile 顯示為 48 螢幕像素 |
| 地圖尺寸 | **40×30 tiles**（640×480 px） | 每個區域的建議大小 |
| 視窗 | 960×540 | zoom 3x 下可見約 20×11 tiles |

### TileSet 圖片格式

```
單張 PNG，所有 tile 排成 10 列格子：

┌──┬──┬──┬──┬──┬──┬──┬──┬──┬──┐
│01│02│03│04│05│06│07│08│09│10│  每格 16×16 px
├──┼──┼──┼──┼──┼──┼──┼──┼──┼──┤
│11│12│13│14│15│16│17│18│19│20│
├──┼──┼──┼──┼──┼──┼──┼──┼──┼──┤
│..│..│..│..│..│..│..│..│..│..│
└──┴──┴──┴──┴──┴──┴──┴──┴──┴──┘

整張圖寬 160 px，高度依 tile 數量而定
需要透明的 tile（如樹冠）使用 alpha 透明
```

**嚴格要求：**
- 每格**嚴格 16×16 px**，無間距、無邊框
- 同一張圖內風格/色調統一
- 地面 tile 需要可**無縫拼接**（邊緣能銜接）

### 分層結構（每個區域場景 2-3 層）

```
Layer 0 (Ground):  草地、道路、水面 — 完全填滿，無透明
Layer 1 (Objects): 牆壁、攤位、樹幹 — 有碰撞，阻擋玩家移動
Layer 2 (Overlay): 樹冠、屋簷 — 無碰撞，Y-Sort 遮擋在玩家上方
```

### Zone: 政大正門 (zone_nccu) — 校園風格

```
pixel art tileset, top-down RPG, 16x16 tiles, seamless edges,
university campus entrance, brick pathway, green grass, trees, iron gate,
bulletin board, lamp posts, stone bench,
Taiwanese urban style, warm afternoon lighting,
10 columns grid, transparent background where needed
```

**Tile 清單 (建議 20~30 tiles):**
| # | Tile | Layer | 碰撞 |
|---|------|-------|------|
| 01 | 草地 | Ground | 無 |
| 02 | 磚道 | Ground | 無 |
| 03 | 柏油路 | Ground | 無 |
| 04 | 草地邊緣（上） | Ground | 無 |
| 05 | 草地邊緣（左） | Ground | 無 |
| 06 | 校門柱 | Objects | 有 |
| 07 | 圍牆 | Objects | 有 |
| 08 | 布告欄 | Objects | 有 |
| 09 | 樹幹 | Objects | 有 |
| 10 | 樹冠 | Overlay | 無 |
| 11 | 路燈 | Objects | 有 |
| 12 | 石椅 | Objects | 有 |
| 13 | 花叢 | Objects | 無 |
| 14 | 垃圾桶 | Objects | 有 |

### Zone: 木柵市場 (zone_market) — 傳統市場

```
pixel art tileset, top-down RPG, 16x16 tiles, seamless edges,
traditional Taiwanese market street, vendor stalls, awnings, wet floor tiles,
hanging signs with Chinese text, crates of vegetables, red lanterns,
bustling market atmosphere, warm indoor lighting,
10 columns grid, transparent background where needed
```

**Tile 清單:**
| # | Tile | Layer | 碰撞 |
|---|------|-------|------|
| 01 | 磁磚地 | Ground | 無 |
| 02 | 濕地面（反光） | Ground | 無 |
| 03 | 排水溝蓋 | Ground | 無 |
| 04 | 攤位框架（左） | Objects | 有 |
| 05 | 攤位框架（右） | Objects | 有 |
| 06 | 遮雨棚 | Overlay | 無 |
| 07 | 鐵捲門 | Objects | 有 |
| 08 | 磚牆 | Objects | 有 |
| 09 | 菜籃 | Objects | 有 |
| 10 | 水果箱 | Objects | 有 |
| 11 | 招牌 | Overlay | 無 |
| 12 | 紅燈籠 | Overlay | 無 |
| 13 | 塑膠椅 | Objects | 無 |
| 14 | 電線桿 | Objects | 有 |

### Zone: 指南宮 (zone_zhinan) — 山林廟宇

```
pixel art tileset, top-down RPG, 16x16 tiles, seamless edges,
Taiwanese mountain temple, stone steps, traditional red pillars, incense burner,
forest trees, bamboo, stone path, temple roof edges,
misty mountain atmosphere, green and red color scheme,
10 columns grid, transparent background where needed
```

**Tile 清單:**
| # | Tile | Layer | 碰撞 |
|---|------|-------|------|
| 01 | 泥土路 | Ground | 無 |
| 02 | 石板路 | Ground | 無 |
| 03 | 石階（上段） | Ground | 無 |
| 04 | 石階（中段） | Ground | 無 |
| 05 | 石階（下段） | Ground | 無 |
| 06 | 紅色廟柱 | Objects | 有 |
| 07 | 屋簷邊緣 | Overlay | 無 |
| 08 | 香爐 | Objects | 有 |
| 09 | 山林樹幹 | Objects | 有 |
| 10 | 山林樹冠 | Overlay | 無 |
| 11 | 竹子 | Objects | 有 |
| 12 | 青苔石頭 | Objects | 有 |
| 13 | 祈福牌 | Objects | 無 |
| 14 | 石碑 | Objects | 有 |

### Zone: 道南河濱 (zone_riverside) — 河岸公園

```
pixel art tileset, top-down RPG, 16x16 tiles, seamless edges,
riverside park, calm water surface, grassy riverbank, walking path,
wooden bench, street lamp, bridge railing, reeds,
late afternoon golden light, peaceful urban park,
10 columns grid, transparent background where needed
```

**Tile 清單:**
| # | Tile | Layer | 碰撞 |
|---|------|-------|------|
| 01 | 草地 | Ground | 無 |
| 02 | 步道（磚） | Ground | 無 |
| 03 | 河堤（水泥） | Ground | 無 |
| 04 | 靜水（幀1） | Ground | 無 |
| 05 | 靜水（幀2） | Ground | 無 |
| 06 | 河岸邊緣 | Ground | 無 |
| 07 | 蘆葦 | Objects | 無 |
| 08 | 柳樹幹 | Objects | 有 |
| 09 | 柳樹冠 | Overlay | 無 |
| 10 | 矮灌木 | Objects | 無 |
| 11 | 木椅 | Objects | 有 |
| 12 | 路燈 | Objects | 有 |
| 13 | 橋欄杆 | Objects | 有 |
| 14 | 釣魚桿架 | Objects | 無 |

---

## 4. UI Elements (Optional)

### Dialogue Box Background

```
pixel art UI panel, RPG dialogue box, dark semi-transparent background,
rounded corners, subtle border glow, 960x200 pixels
```

### Menu Buttons

```
pixel art UI button, RPG style, wooden/stone texture,
normal/hover/pressed states, 160x40 pixels
```

---

## 5. Output Checklist

### 角色 Spritesheet

- [ ] 背景是真正的 alpha 透明（不是灰白格子）
- [ ] 每幀大小完全一致（等距格子）
- [ ] 6 列 × 4 行 = 24 幀
- [ ] 每行第 1 幀是靜止站姿（不是走路姿勢）
- [ ] 每行第 2~6 幀是走路循環
- [ ] 4 個方向順序：下、右、左、上
- [ ] 角色在每幀中位置居中（不偏移）
- [ ] 陰影一致（可選）

### TileSet

- [ ] 每格嚴格 16×16 px
- [ ] 10 列排列，無間距
- [ ] 地面 tile 可無縫拼接
- [ ] 需要透明的 tile 使用 alpha 通道
- [ ] 同一區域風格/色調統一

### 通用

- [ ] 檔案格式為 PNG
- [ ] 檔名使用英文小寫 + 底線（如 `chen_ayi.png`）
- [ ] 放到正確的目錄位置

## 6. File Placement

```
game/assets/textures/
├── characters/
│   ├── player.png              # 玩家 spritesheet (6col × 4row)
│   ├── chen_ayi.png            # 陳阿姨 spritesheet
│   ├── wang_bobo.png           # 王伯伯 spritesheet
│   ├── master_guang.png        # 廣師父 spritesheet
│   └── old_fisher.png          # 釣魚老人 spritesheet
├── portraits/
│   ├── chen_ayi_portrait.png   # 96×96 dialogue portrait
│   ├── wang_bobo_portrait.png
│   ├── master_guang_portrait.png
│   └── old_fisher_portrait.png
├── tilesets/
│   ├── tileset_nccu.png        # 政大正門 (10col, 16×16 per tile)
│   ├── tileset_market.png      # 木柵市場
│   ├── tileset_zhinan.png      # 指南宮
│   └── tileset_riverside.png   # 道南河濱
└── ui/
    ├── dialogue_box.png
    └── button.png
```

放好檔案後，告知每個 spritesheet 的**單幀尺寸**（如 64×64 或 96×96），即可整合進 Godot。
TileSet 只需放好 PNG，程式會自動以 16×16 切割。
