# 歷史文檔（已完成的計畫與決策紀錄）

這個資料夾保存「**當時的計畫 / ADR**」做為 git history 之外的可讀紀錄。**日常開發不需要看這裡**；想了解目前怎麼做就看 `docs/INDEX.md` 列出的活躍文檔。

## 目錄

| 檔案 | 寫於 | 主題 | 為什麼留著 |
|---|---|---|---|
| `2026-05-art-pipeline-refactor-adr.md` | 2026-05-05 | 美術各類型生成方法決策（pixflux vs MCP vs bitforge…） | 提供「為什麼選 Pixellab v2 `create_character` / `create_topdown_tileset`」的理由；現已不用 MCP server |
| `2026-05-art-pipeline-design-spec.md` | 2026-05-05 | Orchestrator 設計規範 — 4 個 CLI 拆分、stage / resume / 批次模式 | 解釋現行 orchestrator 為何這樣切分 |
| `2026-05-art-pipeline-orchestrators-plan.md` | 2026-05-05 | Orchestrator 實作計畫（已完成） | step-by-step 開發紀錄 |
| `2026-05-art-pipeline-unification-plan.md` | 2026-05-05 | 統一 spritesheet 流程的實作計畫（已完成） | 紀錄 frame-bake refactor 前的狀態 |
| `2026-05-asset-dashboard-plan.md` | 2026-05-05 | Web UI dashboard 實作計畫（已完成） | 紀錄前後端切割決策 |

## 重要提醒

這些檔案多次提到 **MCP server**（已於 2026-05-12 退役）和**舊版 frame-PNG 流程**（已於 2026-05-12 改為直接 bake 進 spritesheet）。內容反映寫作當時的狀態，**不要當作現況依據**。
