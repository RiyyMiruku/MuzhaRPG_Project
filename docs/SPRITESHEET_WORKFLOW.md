# Spritesheet 工作流指南

## 概述

本專案使用**混合架構**來優化角色動畫性能：

- **開發層**：序列圖（美術友好，靈活）
- **預編譯層**：Spritesheet（性能最優）
- **運行層**：Godot 智能加載（優先預編譯 > 備選序列圖）

---

## 🔧 設置步驟

### 1. 首次設置

```bash
cd ai_engine/scripts

# 生成所有角色的 Spritesheet
python generate_spritesheet.py \
    --input ../../game/assets/textures/characters/ \
    --output ../../game/assets/spritesheet_cache/
```

**產出物**：

```
game/assets/spritesheet_cache/
├── player.png                    # 預編譯 Spritesheet (552×736)
├── Chen_Ayi_-_Market_Vendor.png
├── Master_Guang_-_Temple_Keeper.png
├── Old_Fisherman.png
├── Wang_Bobo_-_Noodle_Shop_Owner.png
└── atlas_config.json             # 所有角色的動畫配置
```

### 2. 設置 NPC Config （可選）

如果需要手動指定角色資源路徑：

```gdscript
# NPCConfig 資源
character_resource_path = "res://assets/textures/characters/Chen_Ayi_-_Market_Vendor"
```

---

## 📋 工作流

### 場景 A：美術更新了動畫

```bash
# 1. 重新生成 Spritesheet
python generate_spritesheet.py \
    --input ../../game/assets/textures/characters/ \
    --output ../../game/assets/spritesheet_cache/

# 2. 提交到 Git
git add game/assets/spritesheet_cache/
git commit -m "update character animations"

# 3. Godot 會自動使用新的 Spritesheet
```

### 場景 B：添加新角色

```bash
# 1. 將新角色文件夾放到
game/assets/textures/characters/新角色/
  ├── metadata.json
  ├── rotations/
  └── animations/

# 2. 重新生成
python generate_spritesheet.py \
    --input ../../game/assets/textures/characters/ \
    --output ../../game/assets/spritesheet_cache/

# 3. 在 Godot 中：
#    - 創建新 NPCConfig (可選)
#    - 如果 character_resource_path 為空，會自動尋找預編譯版本
```

---

## 🎮 Godot 端加載邏輯

```gdscript
# 自動加載流程
SpriteSheetLoader.smart_load(character_dir_path)

# 優先級：
# 1. 檢查 res://assets/spritesheet_cache/atlas_config.json
# 2. 若存在 → 使用預編譯 Spritesheet (~100ms)
# 3. 若不存在 → 動態生成（開發時或緊急情況 ~500-800ms）
```

**結果動畫名稱**：

```
idle_north, idle_south, idle_east, idle_west
walk_north, walk_south, walk_east, walk_west
```

---

## 📊 性能對比

| 指標                  | 序列圖    | Spritesheet |
| --------------------- | --------- | ----------- |
| 首次加載時間          | 500-800ms | ~100ms      |
| GPU 内存绑定          | 10x/幀    | 1x/幀       |
| 50 NPC 同屏時 GPU占用 | 8-12%     | 1-2%        |

**LLM 友好度**：Spritesheet 減少 80-90% GPU 額外負擔，為 llama-server 保留更多資源

---

## ⚙️ 故障排除

### 問題：Spritesheet 生成失敗

```bash
# 使用 -v 獲取詳細日誌
python generate_spritesheet.py \
    --input ../../game/assets/textures/characters/ \
    --output ../../game/assets/spritesheet_cache/ \
    -v
```

常見原因：

- 缺少 Pillow：`pip install Pillow`
- 路徑不正確：確保 metadata.json 存在
- PNG 文件損壞：檢查是否能用圖片編輯器打開

### 問題：Godot 仍顯示佔位符

1. 確認 `atlas_config.json` 存在
2. 檢查控制台是否有加載錯誤
3. 驗證資源路徑：`res://assets/spritesheet_cache/` 是否在項目中

---

## 💾 版本控制

**應該提交的**：

```
✅ game/assets/spritesheet_cache/atlas_config.json
✅ game/assets/spritesheet_cache/*.png
✅ ai_engine/scripts/generate_spritesheet.py
```

**不應該提交的**：

```
❌ game/assets/textures/characters/*/animations/*.png （原始序列圖）
❌ game/assets/textures/characters/*/metadata.json （源配置）
```

---

## 🚀 未來優化

1. **增量更新** — 只重新生成改動的角色
2. **WebP 支持** — 進一步減少文件大小
3. **多紋理層級** — 不同質量級別按需加載
