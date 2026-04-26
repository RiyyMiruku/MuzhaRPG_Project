# ② Spritesheet 編譯流水線

把 [① 1-asset-creation.md](1-asset-creation.md) 產出的序列圖編譯成單張 spritesheet PNG，給遊戲運行時使用。

---

## 0. 為什麼要編譯？

**遊戲運行時只讀 spritesheet，不讀序列圖。**

```
art_source/characters/<id>/        →  game/assets/spritesheet_cache/<id>.png
├── metadata.json                      + atlas_config.json
├── rotations/                          (運行時實際載這個)
└── animations/{idle,walk}/
   (這層只是「來源」)
```

效益：
- **DrawCall 大幅降低** — 24+ 幀只佔 1 個 texture binding（vs 散落 24 個 PNG）
- **記憶體連續** — GPU 喜歡單張大圖
- **載入快** — 1 個 file open 取代 20+ 個

50 NPC 場景中 GPU 使用從 ~8-12% 降到 ~1-2%（保留資源給 LLM 推論）。

---

## 1. 何時跑編譯？

只要 `art_source/characters/` 下有變動就跑：

- 新增角色（新資料夾）
- 修改既有角色的幀（換衣服、調動作）
- 改了 idle/walk 子結構

不需要每次都跑，但**忘記跑會導致遊戲看不到新素材**（因為運行時不讀序列圖）。

---

## 2. 執行指令

從專案根目錄：

```bash
python scripts/generate_spritesheet.py
```

**就這樣。** 預設路徑：
- 輸入：`art_source/characters/`
- 輸出：`game/assets/spritesheet_cache/`

加 `-v` 看詳細輸出：

```bash
python scripts/generate_spritesheet.py -v
```

要自訂路徑：

```bash
python scripts/generate_spritesheet.py --input <src> --output <dst>
```

---

## 3. 產出物

每跑一次會（重新）產出：

```
game/assets/spritesheet_cache/
├── atlas_config.json        ← 對應表（哪個 char、哪個動畫對到 sheet 哪一行/列）
├── chen_ayi.png             ← 各角色的 spritesheet
├── master_guang.png
├── old_fisher.png
├── player.png
└── wang_bobo.png
```

每張 spritesheet 是 552×736（6 欄 × 8 列 × 92 px）：

```
列 0: idle_north / east / west / south  (4 列各 4 幀)
列 4: walk_north / east / west / south  (4 列各 6 幀)
```

`atlas_config.json` 把這些位置對應到 Godot 動畫名（`idle_up`、`walk_right` 等）。

---

## 4. 驗證

跑完後檢查 console：

```
[OK] Successful: 5
[FAIL] Failed:     0
```

**有 fail 就停下來看 error**：通常是 metadata.json 路徑與實際資料夾不符。

---

## 5. 故障排除

| 問題 | 原因 | 修法 |
| --- | --- | --- |
| `metadata.json not found` | 角色資料夾缺 metadata | 從 Pixellab 重新匯出，或手寫一份 |
| `Frame not found: ...` | metadata 路徑指向不存在的檔 | 改 metadata 內部路徑或重命名資料夾使其對齊 |
| 遊戲跑起來看不到新角色 | 編譯沒跑 / 失敗 | 重跑本指令，確認 console 顯示 OK |
| 跑出大寫舊名（如 `Chen_Ayi_-_Market_Vendor.png`） | art_source/characters/ 下還有舊大寫資料夾 | 重命名為小寫 ID（見 [① 1-asset-creation.md](1-asset-creation.md) 4.1） |

---

## 6. 進階：editor 自動跑？

目前是手動 — 跑完後 commit 兩邊變動：

```bash
git add art_source/characters/<id>/        # 序列圖（如果是新增）
git add game/assets/spritesheet_cache/     # spritesheet 產出
git commit -m "新角色: <id>"
git push
```

未來如有需要可考慮：
- Godot editor plugin 監控 art_source 變動
- pre-commit hook 自動編譯
- CI 自動跑

但目前 5 角色的規模手動已經夠了。

---

## 下一步

編譯完後 → [③ 3-asset-usage.md](3-asset-usage.md)（把 NPC 接到遊戲中）。
