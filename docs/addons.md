# Godot Addons 評估與採用記錄

> 文檔導覽：[INDEX](INDEX.md) — **對象**：程式。**用途**：採用 / 不採用的 addons 紀錄、引入決策清單。

本專案對於外部 Addons 的採用準則：**只引入解決明確痛點且不衝突核心架構的套件**。

---

## ✅ 已採用

### TileMapDual（v5.0.2）

- **路徑**：[game/addons/TileMapDual/](../game/addons/TileMapDual/)
- **啟用**：`game/project.godot` 的 `[editor_plugins]` 區段
- **解決問題**：原生 Godot Terrain Set 用 Pixellab 4×4 autotile 必須手點 144 個 peering bit 點，且邊界容易破圖跳磚
- **取代**：原本的 `scripts/scaffold_zone.py`（已刪除）+ 手動 Terrain Set 編輯流程
- **詳細用法**：[tilemapdual-guide.md](tilemapdual-guide.md)

---

## ✅ 自寫系統（不採用 addon 但有專屬方案）

### 對話系統 — 自寫 StoryBeat + DialogueUI mode 切換（D 方案）

- **採用日期**：2026-04-28
- **取代什麼**：Dialogic / Godot Dialogue Manager
- **核心想法**：
  - Authored Beat（30%）走 `StoryBeat.tres` + `BeatRunner` autoload
  - Constrained AI（60%）走現有 `AIClient` + 新加 `TrustGate` 約束 prompt
  - Free AI（10%）走最低約束的現有 AI 流程
  - 統一 UI：`DialogueUI` 加 `ChoiceButtonsContainer`，beat / AI mode 切換
- **完整設計**：[dialogue-architecture.md](dialogue-architecture.md)
- **為何選 D**：[dialogue-architecture.md](dialogue-architecture.md) 第 14 節對 5 個方案有完整評分（A/B/C/D/E 加權總分 D=7.9 最高）

---

## ❌ 評估後不採用

### Dialogic — ❌ 不採用

- **建議者宣稱解決**：對話 UI、打字機、頭像切換、分歧樹
- **不採用原因**：跟 AI 對話 paradigm 衝突
  - 現有 `DialogueUI.tscn` 為 AI streaming 對話打造（玩家打字輸入 → AI 邊收 token 邊顯示）
  - Dialogic 為視覺小說設計（玩家點選項按鈕 → 預寫文字 typewriter）
  - 同時用會有兩套對話 UI，玩家視覺體驗精神分裂
- **重複功能**：打字機動畫、立繪切換、對話框 — `DialogueUI` 都已實作
- **狀態系統衝突**：Dialogic 自帶變數/分歧 state，會跟 `StoryManager.player_flags / npc_relationships` 重複建立同類資料
- **改用方案**：自寫 `StoryBeat.tres` + 擴充 `DialogueUI` 加 mode 切換（D 方案，見 [dialogue-architecture.md](dialogue-architecture.md)）

### Godot Dialogue Manager — 🟡 暫不採用，留待未來評估

- **建議者宣稱解決**：純文字 DSL 寫劇本、Git 友善、編譯效率高
- **目前不採用原因**：內容量還不到引入新依賴的門檻
  - Chapter 1-3 預計 ~12 beat/章，自寫 `.tres` 可承受
  - 引入 addon 需要 bridge layer 接到現有 `DialogueUI` + `AIClient`，增加維護面
- **何時應該引入（重新評估觸發條件）**：
  - 一章超過 30 個 beat 且 Inspector 編輯 .tres 開始痛苦
  - 加入第三方文字作者（非工程師）需要寫劇本
  - 多語言版本需要外掛字串檔（DM 有 i18n 支援）
- **預期改動範圍**：寫 thin parser，把 `.dialogue` 檔轉成 `StoryBeat` 資源餵給 `BeatRunner`，舊 `.tres` 不丟，逐步遷移

### Phantom Camera

- **建議者宣稱解決**：平滑跟隨、區域鎖定、Boss 拉遠等動態運鏡
- **目前狀態**：**未採用，但保留為未來選項**
- **不採用原因**：當前 Player.tscn 內的單一 Camera2D（zoom 3、跟隨 Player）已足夠 4 個 zone 的需求；過早引入 Phantom Camera 會增加每個 zone 的設定負擔（要在每個 zone 放 PCam 節點、設限制區）
- **何時應該引入**：
  - 出現需要鏡頭鎖定範圍的場景（例：室內房間，鏡頭不能露出邊界外）
  - 加入 Boss 戰／劇情演出需要動態拉遠／推近
  - Cinematic 過場（角色 A 對話時鏡頭聚焦角色 A）
- **預期改動範圍**：移除 Player.tscn 內的 Camera2D，改在每個 zone 場景放 PhantomCamera2D + Target Group 引用 Player

---

## 引入新 Addon 的決策清單

引入前自問：

1. **痛點是什麼？** 最近反覆遇到的具體問題寫下來
2. **核心架構衝突？** Addon 是否假設了我們專案沒有的工作流（例：DialogueManager 假設對話是預寫的）
3. **大小？** 拉一個套件進來會不會塞 50 個自動載入腳本
4. **過渡成本？** 既有的程式／資料能無痛遷移嗎
5. **被遺棄風險？** 套件最後更新時間、Godot 版本支援
6. **能不能 2 行 code 取代？** 簡單功能不要靠套件

通過後再裝。
