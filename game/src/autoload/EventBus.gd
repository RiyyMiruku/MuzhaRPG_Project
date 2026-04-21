## EventBus — 全域事件匯流排
## 用於沒有直接引用關係的系統之間解耦通訊。
## 使用方式：EventBus.npc_interaction_started.emit(npc)
extends Node

# ── NPC / 對話 ────────────────────────────────────────────────────────────
signal npc_interaction_started(npc: Node)
signal npc_interaction_ended()
signal dialogue_response_received(text: String, npc_id: String)
signal dialogue_closed()

# ── 區域切換 ───────────────────────────────────────────────────────────────
signal zone_transition_requested(zone_id: String, entry_point: String)
signal zone_loaded(zone_id: String)

# ── 玩家 ───────────────────────────────────────────────────────────────────
signal player_zone_entered(zone_id: String)
signal player_interacted_with(target: Node)

# ── Prop 互動 ──────────────────────────────────────────────────────────────
## 玩家進入 prop 互動範圍，顯示提示文字（例：「[E] 閱讀公告」）
signal prop_interact_available(prop: Node, prompt: String)
## 玩家離開 prop 互動範圍，隱藏提示
signal prop_interact_unavailable(prop: Node)

# ── UI ─────────────────────────────────────────────────────────────────────
signal hud_message_requested(text: String, duration: float)
signal screen_transition_started()
signal screen_transition_finished()

# ── UI 面板協調 ────────────────────────────────────────────────────────────
## 任何面板開啟時發射，其他面板收到後自動關閉
signal ui_panel_opened(panel_name: String)
## 所有面板關閉時發射，恢復遊戲操作
signal ui_panel_closed()

# ── AI 伺服器 ──────────────────────────────────────────────────────────────
signal ai_server_online()
signal ai_server_offline()
