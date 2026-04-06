# Art Asset Generation Guide

> AI 生圖提示詞與美術規格指南

## General Style Keywords

所有角色和場景應維持統一的視覺風格：

```
pixel art, top-down RPG, 2.5D perspective, 16-bit style,
warm color palette, Taiwanese urban setting
```

---

## 1. Character Sprites

### Spritesheet Format

```
┌──┬──┬──┬──┬──┬──┐
│下1│下2│下3│下4│下5│下6│  idle (1-2) + walk (3-6)
├──┼──┼──┼──┼──┼──┤
│左1│左2│左3│左4│左5│左6│
├──┼──┼──┼──┼──┼──┤
│右1│右2│右3│右4│右5│右6│
├──┼──┼──┼──┼──┼──┤
│上1│上2│上3│上4│上5│上6│
└──┴──┴──┴──┴──┴──┘
```

- Frame size: **64×64** or **96×96** px per frame
- Background: **transparent (alpha)**
- File format: **PNG**
- Arrangement: 6 columns × 4 rows = 24 frames

### Player Character

```
pixel art character sprite sheet, top-down RPG, 4 directions (front/back/left/right),
6 frames per direction (2 idle + 4 walk cycle),
young male college student, brown hair, blue casual shirt, dark pants, sneakers,
transparent background, consistent pixel size, game-ready spritesheet layout
```

### 陳阿姨 (Chen Ayi - Market Vendor)

```
pixel art character sprite sheet, top-down RPG, 4 directions,
middle-aged Taiwanese woman, short permed hair, market apron over floral blouse,
warm friendly expression, slight stout build,
transparent background, pixel art style, spritesheet layout
```

### 王伯伯 (Wang Bobo - Noodle Shop Owner)

```
pixel art character sprite sheet, top-down RPG, 4 directions,
elderly Taiwanese man, thin build, white undershirt with towel on shoulder,
calm expression, slightly hunched posture,
transparent background, pixel art style, spritesheet layout
```

### 廣師父 (Master Guang - Temple Keeper)

```
pixel art character sprite sheet, top-down RPG, 4 directions,
elderly monk/temple keeper, shaved head, grey traditional Chinese robe,
serene mysterious expression, prayer beads around neck,
transparent background, pixel art style, spritesheet layout
```

### 釣魚老人 (Old Fisherman)

```
pixel art character sprite sheet, top-down RPG, 4 directions,
old fisherman, straw hat, loose shirt, rolled-up pants, holding fishing rod,
relaxed cheerful expression, tanned skin,
transparent background, pixel art style, spritesheet layout
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

## 3. TileSet (Map Tiles)

### Format

- Tile size: **16×16** px per tile
- Arrange tiles in a single PNG spritesheet (e.g., 16 columns × N rows)
- Background: **transparent** where applicable (e.g., tree tops)

### Zone: 政大正門 (zone_nccu)

```
pixel art tileset, top-down RPG, 16x16 tiles,
university campus entrance, brick pathway, green grass, trees, iron gate,
bulletin board, lamp posts, stone bench,
Taiwanese urban style, warm afternoon lighting
```

Tiles needed: grass, brick path, stone wall, gate, tree, bench, lamp post

### Zone: 木柵市場 (zone_market)

```
pixel art tileset, top-down RPG, 16x16 tiles,
traditional Taiwanese market street, vendor stalls, awnings, wet floor tiles,
hanging signs with Chinese text, crates of vegetables, red lanterns,
bustling market atmosphere
```

Tiles needed: market floor, stall frame, awning, crate, sign, lantern, wall

### Zone: 指南宮 (zone_zhinan)

```
pixel art tileset, top-down RPG, 16x16 tiles,
Taiwanese mountain temple, stone steps, traditional red pillars, incense burner,
forest trees, bamboo, stone path, temple roof edges,
misty mountain atmosphere, green and red color scheme
```

Tiles needed: stone step, pillar, incense burner, bamboo, forest tree, stone path

### Zone: 道南河濱 (zone_riverside)

```
pixel art tileset, top-down RPG, 16x16 tiles,
riverside park, calm water surface, grassy riverbank, walking path,
wooden bench, street lamp, bridge railing, reeds,
late afternoon golden light, peaceful urban park
```

Tiles needed: water, riverbank, grass, path, bench, lamp, bridge, reeds

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

生圖完成後，確認以下事項：

- [ ] 背景已去除（透明 PNG）
- [ ] 每幀大小一致（等距格子）
- [ ] 動畫幀數符合規格（idle 2 + walk 4 = 6 per direction）
- [ ] 4 個方向都有（下、左、右、上）
- [ ] 角色在每幀中位置居中（不偏移）
- [ ] 陰影一致（可選：腳下圓形陰影）

## 6. File Placement

```
game/assets/textures/
├── characters/
│   ├── player.png              # 玩家 spritesheet (6×4 frames)
│   ├── chen_ayi.png
│   ├── wang_bobo.png
│   ├── master_guang.png
│   └── old_fisher.png
├── portraits/
│   ├── chen_ayi_portrait.png   # 96×96 dialogue portrait
│   ├── wang_bobo_portrait.png
│   ├── master_guang_portrait.png
│   └── old_fisher_portrait.png
├── tilesets/
│   ├── tileset_nccu.png
│   ├── tileset_market.png
│   ├── tileset_zhinan.png
│   └── tileset_riverside.png
└── ui/
    ├── dialogue_box.png
    └── button.png
```

放好檔案後，告知每個 spritesheet 的單幀尺寸（如 64×64 或 96×96），即可整合進 Godot。
