# Autotile (自動圖塊) 生成與使用指南

本文檔說明如何使用 Pixellab AI 的 **Tilesets** 功能來生成 Autotile（自動圖塊），並解釋其在遊戲引擎中的應用方式。這將大幅提升《MuzhaRPG》地圖製作的效率與質感。

---

## 1. 什麼是 Autotile？

在傳統的 2D RPG 地圖製作中，如果要在「草地」上畫一條「柏油路」，你需要手動拼接直線、轉角、十字路口等數十種不同邊緣的圖塊。
**Autotile (自動圖塊 / 地形圖塊)** 是一張將所有可能發生的「邊緣交界處」整合在一起的 Sprite Sheet。當你將這張圖匯入遊戲引擎（如 Godot 的 Terrain Set 或 Unity 的 Rule Tile）後，你只需要像拿畫筆一樣塗抹，引擎就會**自動幫你計算並選擇正確的轉角與邊緣**，實現無縫的地形融合。

---

## 2. 如何在 Pixellab AI 中生成 Autotile

請放棄使用單一的「Texture」或「Maps」生成，改用專屬的 **Tilesets** 功能：

### 步驟 A：基礎設置
- 切換到 Pixellab 的 **Tilesets** 標籤頁。
- **Tile Size**: 選擇 `16x16`。
- **Map orientation**: 選擇 `Top-down` (正上俯視)。

### 步驟 B：設定雙層地形 (Terrain)
Autotile 需要定義「底層」與「上層」兩種地形，AI 會自動幫你畫出它們之間的交界線。
1. **Lower Terrain (底層地形)**：通常是大面積的基底。例如：`grass texture, pixel art`
2. **Upper Terrain (上層地形)**：覆蓋在底層上的道路或特殊地形。例如：`asphalt road texture, pixel art`

### 步驟 C：設定邊緣融合 (Transition)
這是 Autotile 的靈魂，決定了上下層交界處的視覺效果：
- **Transition (融合比例)**：
  - `None`: 邊緣銳利，適合人工建築（如水泥地接磁磚）。
  - `Small (25%)` 或 `Large (50%)`: 邊緣自然過渡，適合大自然地形（如草地接泥土路）。
- **Transition Description (邊緣描述)**：
  - 這是非常強大的細節設定。請在這裡用簡單英文描述交界處有什麼東西。
  - 範例：`grey concrete curb` (灰色路緣石)、`small pebbles and moss` (碎石與青苔)、`faded white painted line` (斑駁白線)。

生成後，將整張大圖直接下載（不需要切分），命名為 `autotile_[下層]_[上層].png`。

---

## 3. MuzhaRPG 區域 Autotile 推薦配方

以下是針對我們專案中四個區域的推薦設定配方：

### 🏫 政大正門 (zone_nccu)
*   **組合**：草地 + 柏油路 / 紅磚道
*   **Lower Terrain**: `green grass texture`
*   **Upper Terrain**: `dark asphalt road texture` (或 `red brick pathway texture`)
*   **Transition**: `Small (25%)`
*   **Transition Description**: `grey concrete curb` (灰色路緣石)

### ⛩️ 指南宮 (zone_zhinan)
*   **組合**：泥土路 + 石板路
*   **Lower Terrain**: `brown dirt path texture`
*   **Upper Terrain**: `irregular stone path texture`
*   **Transition**: `Large (50%)`
*   **Transition Description**: `small pebbles and moss` (小碎石與青苔) 或 `overgrown weeds` (叢生雜草)

### 🏞️ 道南河濱 (zone_riverside)
*   **組合**：靜水面 + 水泥河堤
*   **Lower Terrain**: `calm blue water surface`
*   **Upper Terrain**: `grey concrete riverbank`
*   **Transition**: `Small (25%)`
*   **Transition Description**: `mossy concrete edge with small ripples` (長滿青苔的邊緣與微小水波)

### 🛒 木柵市場 (zone_market)
*   市場內部通常是單一材質（傳統磁磚 `traditional market floor tiles`），若需要破舊感，可嘗試：
*   **Lower Terrain**: `rough concrete floor`
*   **Upper Terrain**: `traditional market floor tiles`
*   **Transition**: `None`
*   **Transition Description**: `cracked tiles showing concrete underneath` (破裂磁磚露出水泥)

---

## 4. 在遊戲引擎中的使用概念
1. 將下載的 `autotile_xxx.png` 放入對應區域的資料夾（如 `素材/tilesets/nccu/`）。
2. 在 **Godot 4.x** 中：將該圖加入 TileSet，設置好 Texture Region Size 為 16x16，然後在 Terrain Sets 中為這張圖設定「Bitmask (碰撞遮罩/位元遮罩)」。
3. 設置完成後，即可在 TileMap 節點中使用 Terrain 筆刷，無腦塗抹畫出漂亮的路徑！
