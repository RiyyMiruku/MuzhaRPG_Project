# Temp 暫存區（美術組大圖處理）

此資料夾是**美術組拆圖前的暫存空間**，放待處理的原始大圖。

## 用途

- 美術從繪圖軟體匯出的大片 PNG（內含多個 prop 或 tileset）先丟到這裡
- 用 [split_map_assets_gui.py](../../../../ai_engine/scripts/split_map_assets_gui.py) 開啟此資料夾做拆圖
- 拆完的獨立 prop PNG 會輸出到 `props/nature/` 或 `props/urban/`
- **此資料夾的 PNG 檔不進版控**（已加入 .gitignore），不會被誤 push 到 GitHub

## 版控規則

- ✅ 保留 `.gitkeep` 與本 `README.md`（維持資料夾存在）
- ❌ PNG 大圖在此為暫存 — 拆完後**自行刪除本機檔**即可

## 工作流程

1. 把匯出的大圖複製到這裡（可一次丟多張）
2. 執行 `python ai_engine/scripts/split_map_assets_gui.py`
3. GUI 會自動打開 temp/ 作為起始目錄，按住 Ctrl 可**多選檔案批次處理**
4. 拆完後將此資料夾的原始大圖刪除（或留著備份）
