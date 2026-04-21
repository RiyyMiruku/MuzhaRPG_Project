# 遊戲角色素材 (Skins) 使用說明書

這份文件將說明如何操作和使用本專案中的 2.5D 像素風 RPG 角色素材 (Skins)。

## 📦 包含的角色列表

目前匯出的角色素材包含以下五位：
1. **陳阿姨 (Chen Ayi)** - 菜市場攤販 (`Chen_Ayi_-_Market_Vendor`)
2. **廣大師 (Master Guang)** - 廟祝 (`Master_Guang_-_Temple_Keeper`)
3. **老漁夫 (Old Fisherman)** - (`Old_Fisherman`)
4. **王伯伯 (Wang Bobo)** - 麵攤老闆 (`Wang_Bobo_-_Noodle_Shop_Owner`)
5. **玩家主角 (Player)** - 大學生 (`player`)

---

## 📂 資料夾結構解析

每個角色資料夾內都會有以下統一的結構：

```text
角色資料夾名稱/
├── metadata.json       # 核心設定檔 (記錄動畫路徑、角色尺寸等)
├── rotations/          # 靜態朝向圖片 (東、南、西、北)
│   ├── east.png
│   ├── north.png
│   ├── south.png
│   └── west.png
└── animations/         # 動態幀 (如走路、待機呼吸等)
    ├── Breathing_Idle.../ # 待機動畫資料夾
    │   ├── east/          # 朝東的動畫幀 (frame_000.png, frame_001.png...)
    │   ├── north/
    │   ├── south/
    │   └── west/
    └── Walking.../        # 走路動畫資料夾
        ├── east/
        ├── north/
        ├── south/
        └── west/
```

---

## 🎮 如何在遊戲引擎中使用 (操作方式)

這些素材是通用的序列圖 (Image Sequence)，主要尺寸設定為 **92x92 像素**，並提供 **4 個方向 (上、下、左、右)**。

你有兩種主要方式可以將他們匯入遊戲引擎（例如 Godot, Unity 或 RPG Maker）：

### 方法 1：手動設定動畫節點 (以 Godot 為例)
1. 將角色資料夾拖曳至專案目錄的資源檔中。
2. 在場景中建立一個 `AnimatedSprite2D` 節點。
3. 在 Sprite Frames 中新建動畫狀態（例如 `idle_down`, `walk_right` 等）。
4. 進入對應的 `animations/` 資料夾，將 `frame_000.png` 到 `frame_005.png` 依序拖曳進去。
5. 調整 FPS（通常這類復古 RPG 走路大約設定在 5 ~ 8 FPS）。

### 方法 2：利用程式自動讀取 `metadata.json`
如果你有大量的角色，可以寫一段腳本：
1. 讓程式讀取資料夾內的 `metadata.json`。
2. 取得 `frames.animations` 與 `frames.rotations` 裡的相對路徑。
3. 程式自動遍歷並載入所有 `.png` 圖片，自動生成並綁定動畫狀態。
*※ 此方法適合有程式基礎的開發者，可以大幅節省手動設定動畫的時間。*

---

## 💡 注意事項

- **去背處理 (Alpha Channel)**：這些圖片背景皆已完全透明，無需再手動去背。
- **像素風格 (Pixel Art)**：素材為 16-bit 像素風格，在遊戲引擎中導入時，請務必將圖片的**過濾模式 (Filter Mode)** 設定為 **Nearest (最近鄰/無過濾)**，以避免圖片邊緣變模糊。
- **視角 (View)**：呈現為 Low Top-down (微俯視)，適合 2D 和 2.5D 的遊戲世界觀。
