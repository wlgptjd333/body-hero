import re

with open("scripts/game_state.gd", "r", encoding="utf-8") as f:
    c = f.read()

save_old = r"(?sm)func save_stats\(\) -> void:\n\tvar cfg := ConfigFile.new\(\).*?cfg.save\(STATS_PATH\)\n"

save_new = """func save_stats() -> void:
	_Persistence.save_all(
		_punch_counts,
		STATS_KEYS,
		_workout,
		_daily,
		_shop_module,
		_sweat,
		_upgrade_hp,
		_upgrade_stamina,
		_upgrade_recover,
		_best_stage_clear_sec,
		_last_stage_clear_sec,
		_stage_clear_history,
		_difficulty,
		_stage_stars,
		_last_played_stage_id,
		_stage_records,
		_achievements_unlocked,
		_achievement_progress,
		_boss_phase,
		_boss_buffs_selected
	)
"""

c = re.sub(save_old, save_new, c)

load_old = r"(?sm)func load_stats\(\) -> void:\n\tif not FileAccess.file_exists\(STATS_PATH\):\n\t\trefresh_combat_derived_from_upgrades\(\)\n\t\treturn\n\tvar cfg := ConfigFile.new\(\).*?if cfg\.has_section_key\(\"boss\", \"phase\"\):\n\t\t_boss_phase = int\(cfg\.get_value\(\"boss\", \"phase\", 0\)\)\n"

load_new = """func load_stats() -> void:
	var data: Dictionary = _Persistence.load_all(
		STATS_KEYS,
		DAILY_CHALLENGE_DEFS,
		DAILY_CHALLENGE_POOL_IDS
	)
	if data.is_empty():
		refresh_combat_derived_from_upgrades()
		return
	
	if data.has("punch_counts"):
		_punch_counts = data["punch_counts"]
	
	_workout._last_session_calories = data.get("last_session_calories", 0.0)
	_workout.set_weight_kg(data.get("weight_kg", 70.0))
	_workout.set_intensity_factor(data.get("intensity_factor", 1.0))
	_workout.set_height_cm(data.get("height_cm", 170.0))
	_workout.set_age(data.get("age", 30))
	_workout.set_gender(data.get("gender", "male"))
	_workout.set_daily_kcal_goal(data.get("daily_kcal_goal", 0.0))
	_workout._daily_calories = data.get("daily_calories", {})
	_workout._daily_weight_log = data.get("daily_weight_log", {})
	
	_daily.set_date(data.get("challenge_date", ""))
	_daily.set_sessions_completed(data.get("challenge_sessions_completed", 0))
	var picks: Array[String] = data.get("challenge_picks", [])
	if data.get("challenge_picks_invalid", false) or picks.size() != 3:
		_daily.sync_calendar()
	else:
		_daily.set_picks(picks)
	_daily.set_progress(data.get("challenge_progress", {}))
	
	_best_stage_clear_sec = data.get("best_stage_clear_sec", -1.0)
	_last_stage_clear_sec = data.get("last_stage_clear_sec", -1.0)
	_stage_clear_history = data.get("stage_clear_history", [])
	
	_sweat = data.get("sweat", 0)
	_upgrade_hp = data.get("upgrade_hp", 0)
	_upgrade_stamina = data.get("upgrade_stamina", 0)
	_upgrade_recover = data.get("upgrade_recover", 0)
	
	_difficulty = data.get("difficulty", "normal")
	_stage_stars = data.get("stage_stars", {})
	_last_played_stage_id = data.get("last_played_stage_id", "stage_1")
	_stage_records = data.get("stage_records", {})
	
	_achievements_unlocked = data.get("achievements_unlocked", {})
	_achievement_progress = data.get("achievement_progress", {})
	
	_shop_module._owned_items = data.get("shop_owned", {})
	_shop_module._inventory = data.get("shop_inventory", {})
	_shop_module.equip_glove_skin(data.get("equipped_glove_skin", ""))
	_shop_module.equip_hit_effect(data.get("equipped_hit_effect", ""))
	
	_boss_phase = data.get("boss_phase", 0)
	
	refresh_combat_derived_from_upgrades()
"""

c = re.sub(load_old, load_new, c)

with open("scripts/game_state.gd", "w", encoding="utf-8") as f:
    f.write(c)

print("Done")
