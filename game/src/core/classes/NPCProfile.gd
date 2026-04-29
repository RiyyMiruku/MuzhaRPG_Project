## NPCProfile — NPCConfig 的擴充版，加入信任值門檻與禁忌主題機制
##
## 何時用 NPCProfile（而非 NPCConfig）：
##   - 該 NPC 涉及主線劇情關鍵字（必須鎖死特定詞直到通關）
##   - 該 NPC 的對話內容會隨信任值漸進解鎖
##   - 該 NPC 屬於特定時代（modern / 1983），需要 era 過濾
##
## 何時用基底 NPCConfig 即可：
##   - 路人、小販、無關劇情核心
class_name NPCProfile
extends NPCConfig

## 角色出現於哪個時代（時空切換用，Phase 2 EraManager 啟用）
@export var era: String = "any"            # "modern" / "1983" / "any"

## 信任值解鎖：當 npc_relationship >= threshold 時，AI 可以聊到的主題
## 範例：
##   [
##     { "threshold": 0,  "topics": ["藥行日常", "中藥知識"] },
##     { "threshold": 30, "topics": ["兒子叛逆", "市場往事"] },
##     { "threshold": 60, "topics": ["承認家裡有上鎖房間"] },
##   ]
@export var trust_revelations: Array = []

## 禁忌主題：必須對應 flag 為 true 才能說
## 範例：{ "林榮華": "ending_finale_active" }
##   → 玩家 flag["ending_finale_active"] == true 之前，AI 不會主動說「林榮華」
@export var forbidden_until_flag: Dictionary = {}

## 此 NPC 知道的事實清單（讓 LLM 不胡謅）
@export var known_facts: Array[String] = []

## 講話風格簡述（注入 prompt）
## 範例：「台語混國語、短句為主、很少表達情緒」
@export_multiline var personality_voice: String = ""
