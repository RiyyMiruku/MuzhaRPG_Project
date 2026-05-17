# Godot Addons 評估與採用記錄

> 文檔導覽：[INDEX](INDEX.md) — **對象**：程式。**用途**：採用 / 不採用的 addons 紀錄、引入決策清單。

本專案對於外部 Addons 的採用準則：**只引入解決明確痛點且不衝突核心架構的套件**。

---

## ✅ 已採用

### TileMapDual（v5.0.2）

- **路徑**：[game/addons/TileMapDual/](../game/addons/TileMapDual/)
- **啟用**：`game/project.godot` 的 `[editor_plugins]` 區段
- **解決問題**：原生 Godot Terrain Set 用 Pixellab 4×4 autotile 必須手點 144 個 peering bit 點，且邊界容易破圖跳磚
- **詳細用法**：[tilemapdual-guide.md](tilemapdual-guide.md)

### Phantom Camera 2D（v0.11,2026-05-15 採用）

- **路徑**：[game/addons/phantom_camera/](../game/addons/phantom_camera/)
- **啟用**：`game/project.godot` 的 `[editor_plugins]` + autoload `PhantomCameraManager`
- **解決問題**：cutscene 期間鏡頭從 Player 切到 focal node(如塗黑全家福)+ 自動 tween blend + priority 機制讓 CutsceneDirector 可以 spawn 高 priority virtual cam 暫時奪用
- **整合方式**:`scripts/build_zone.py` 自動 emit `Camera2D + PhantomCameraHost + DefaultCam`(GLUED follow Player,priority 0)到每個 zone
- **重要 .tscn 細節**:typed Node export(`follow_target: Node2D`)必須帶 `node_paths=PackedStringArray("follow_target")` 才會 resolve 成 Node 引用
- **用法**:[CutsceneDirector.gd](../game/src/core/cutscene/CutsceneDirector.gd) `_op_camera_to()`

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

## 引入新 Addon 的決策清單

引入前自問：

1. **痛點是什麼？** 最近反覆遇到的具體問題寫下來
2. **核心架構衝突？** Addon 是否假設了我們專案沒有的工作流（例：DialogueManager 假設對話是預寫的）
3. **大小？** 拉一個套件進來會不會塞 50 個自動載入腳本
4. **過渡成本？** 既有的程式／資料能無痛遷移嗎
5. **被遺棄風險？** 套件最後更新時間、Godot 版本支援
6. **能不能 2 行 code 取代？** 簡單功能不要靠套件

通過後再裝。
