## TrustGate — system prompt 組裝器（純函式）
##
## 設計原則：所有依賴透過參數注入，不直接呼叫任何 autoload。
## caller（AIClient / 未來 BeatRunner）負責從 ChapterManager / StoryManager 取資料再傳入。
## 這讓 TrustGate 可獨立測試、避免循環依賴、不會因為 autoload 改名而壞掉。
class_name TrustGate
extends RefCounted

## 構造完整的 NPC 對話 system prompt
##
## 參數：
##   profile         - NPC 設定（NPCProfile，或 fallback NPCConfig）
##   trust           - 當前信任值（StoryManager.npc_relationships.get(npc_id, 0)）
##   flags           - 玩家 flags（StoryManager.player_flags）
##   chapter_overlay - 章節差異片段（ChapterManager.get_npc_overlay(npc_id)）
##
## 回傳：拼好的 system prompt 字串
static func build_system_prompt(
	profile: NPCConfig,
	trust: int,
	flags: Dictionary,
	chapter_overlay: String = ""
) -> String:
	var parts: Array[String] = []

	# 1. 基底人格
	parts.append(profile.system_prompt)

	# 2. 章節 overlay
	if not chapter_overlay.is_empty():
		parts.append("[章節背景] " + chapter_overlay)

	# 以下只有 NPCProfile 才有，NPCConfig 跳過
	if profile is NPCProfile:
		var p: NPCProfile = profile as NPCProfile

		# 3. 講話風格
		if not p.personality_voice.is_empty():
			parts.append("[語氣] " + p.personality_voice)

		# 4. 信任值決定的 allowed topics
		var allowed: Array = []
		for unlock: Dictionary in p.trust_revelations:
			var threshold: int = int(unlock.get("threshold", 0))
			if trust >= threshold:
				var topics: Array = unlock.get("topics", [])
				allowed.append_array(topics)
		if not allowed.is_empty():
			parts.append("[你願意聊] " + ", ".join(allowed))

		# 5. 禁忌主題
		var forbidden: Array = []
		for topic: String in p.forbidden_until_flag:
			var required_flag: String = p.forbidden_until_flag[topic]
			if not flags.get(required_flag, false):
				forbidden.append(topic)
		if not forbidden.is_empty():
			parts.append("[絕對不能提] " + ", ".join(forbidden))

		# 6. 已知事實
		if not p.known_facts.is_empty():
			parts.append("[你知道的事]\n - " + "\n - ".join(p.known_facts))

	# 7. 信任值
	parts.append("[對玩家信任度] %d/100" % trust)

	return "\n".join(parts)


## 後處理：過濾未解鎖的禁忌詞，避免 LLM 違反 prompt 約束
## 將禁忌詞替換為「他」/「那個人」並 log warning。
##
## 回傳：過濾後的字串
static func filter_forbidden(
	text: String,
	profile: NPCConfig,
	flags: Dictionary
) -> String:
	if not (profile is NPCProfile):
		return text
	var p: NPCProfile = profile as NPCProfile
	var result: String = text
	for topic: String in p.forbidden_until_flag:
		var required_flag: String = p.forbidden_until_flag[topic]
		if flags.get(required_flag, false):
			continue   # 已解鎖
		if result.contains(topic):
			push_warning("TrustGate: LLM 提及未解鎖禁忌詞 '%s'，已過濾" % topic)
			result = result.replace(topic, "那個人")
	return result
