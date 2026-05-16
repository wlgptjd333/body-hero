extends RefCounted

const STATS_PATH := "user://body_hero_stats.cfg"


static func save_all(
	core_data: Dictionary,
	workout_data: Dictionary,
	challenges_data: Dictionary,
	shop_data: Dictionary,
	achievements_data: Dictionary,
	difficulty_data: String,
	stage_progress_data: Dictionary,
	boss_data: Dictionary,
	upgrade_data: Dictionary,
) -> void:
	var cfg := ConfigFile.new()

	# core stats
	for k: String in core_data.get("stats_keys", []):
		cfg.set_value("stats", k, core_data.get("punch_counts", {}).get(k, 0))

	# workout/profile
	var wd: Dictionary = workout_data
	cfg.set_value("workout", "last_session_calories", wd.get("last_session_calories", 0.0))
	cfg.set_value("workout", "weight_kg", wd.get("weight_kg", 70.0))
	cfg.set_value("workout", "intensity_factor", wd.get("intensity_factor", 1.0))
	cfg.set_value("workout", "height_cm", wd.get("height_cm", 170.0))
	cfg.set_value("workout", "age", wd.get("age", 30))
	cfg.set_value("workout", "gender", wd.get("gender", "male"))
	cfg.set_value("workout", "daily_kcal_goal", wd.get("daily_kcal_goal", 0.0))
	for date_key: String in wd.get("daily_calories", {}).keys():
		cfg.set_value("daily_calories", date_key, wd["daily_calories"][date_key])
	for date_key: String in wd.get("daily_weight_log", {}).keys():
		cfg.set_value("daily_weight_log", date_key, wd["daily_weight_log"][date_key])

	# daily challenges
	var cd: Dictionary = challenges_data
	cfg.set_value("daily_challenges", "date", cd.get("date", ""))
	cfg.set_value("daily_challenges", "sessions_completed", cd.get("sessions_completed", 0))
	var picks: Array[String] = cd.get("picks", [])
	for i: int in range(picks.size()):
		cfg.set_value("daily_challenges", "pick_%d" % i, picks[i])
	for k: String in cd.get("progress", {}).keys():
		cfg.set_value("daily_challenge_progress", k, cd["progress"][k])

	# time attack
	var spd: Dictionary = stage_progress_data
	cfg.set_value("time_attack", "best_sec", spd.get("best_sec", -1.0))
	cfg.set_value("time_attack", "last_sec", spd.get("last_sec", -1.0))
	var hist: Array = spd.get("history", [])
	var hist_csv: String = ""
	for i: int in range(hist.size()):
		if i > 0:
			hist_csv += ","
		hist_csv += str(hist[i])
	cfg.set_value("time_attack", "history_csv", hist_csv)

	# meta/upgrades
	var ud: Dictionary = upgrade_data
	cfg.set_value("meta", "sweat", ud.get("sweat", 0))
	cfg.set_value("meta", "up_hp", ud.get("up_hp", 0))
	cfg.set_value("meta", "up_sta", ud.get("up_stamina", 0))
	cfg.set_value("meta", "up_rec", ud.get("up_recover", 0))

	# difficulty
	cfg.set_value("progress", "difficulty", difficulty_data)

	# stage stars / records
	for sid: String in spd.get("stars", {}).keys():
		cfg.set_value("stage_stars", sid, spd["stars"][sid])
	cfg.set_value("meta", "last_played_stage", spd.get("last_played", "stage_1"))
	for sid: String in spd.get("records", {}).keys():
		var rec: Dictionary = spd["records"][sid]
		cfg.set_value("stage_records", sid + "_best_time", rec.get("best_time", -1.0))
		cfg.set_value("stage_records", sid + "_best_combo", rec.get("best_combo", 0))
		cfg.set_value("stage_records", sid + "_least_dmg", rec.get("least_dmg", -1.0))

	# achievements
	var ad: Dictionary = achievements_data
	for aid: String in ad.get("unlocked", {}).keys():
		cfg.set_value("achievements_unlocked", aid, ad["unlocked"][aid])
	for aid: String in ad.get("progress", {}).keys():
		cfg.set_value("achievement_progress", aid, ad["progress"][aid])

	# shop
	var sdata: Dictionary = shop_data
	for iid: String in sdata.get("owned", {}).keys():
		cfg.set_value("shop_owned", iid, sdata["owned"][iid])
	for iid: String in sdata.get("inventory", {}).keys():
		cfg.set_value("shop_inventory", iid, sdata["inventory"][iid])
	cfg.set_value("shop", "equipped_glove_skin", sdata.get("equipped_glove_skin", ""))
	cfg.set_value("shop", "equipped_hit_effect", sdata.get("equipped_hit_effect", ""))

	# boss
	var bd: Dictionary = boss_data
	cfg.set_value("boss", "phase", bd.get("phase", 0))
	for i: int in range(bd.get("buffs", []).size()):
		var bname: String = str(bd["buffs"][i].get("name", ""))
		cfg.set_value("boss_buffs", "buff_%d" % i, bname)

	cfg.save(STATS_PATH)


static func load_all(stats_keys: Array) -> Dictionary:
	if not FileAccess.file_exists(STATS_PATH):
		return {}
	var cfg := ConfigFile.new()
	if cfg.load(STATS_PATH) != OK:
		return {}

	var data: Dictionary = {}

	# stats
	var punch_counts: Dictionary = {}
	for k: String in stats_keys:
		if cfg.has_section_key("stats", k):
			punch_counts[k] = cfg.get_value("stats", k, 0)
	data["punch_counts"] = punch_counts

	# workout/profile
	var wd: Dictionary = {}
	if cfg.has_section_key("workout", "last_session_calories"):
		wd["last_session_calories"] = float(cfg.get_value("workout", "last_session_calories", 0.0))
	if cfg.has_section_key("workout", "weight_kg"):
		wd["weight_kg"] = maxf(30.0, float(cfg.get_value("workout", "weight_kg", 70.0)))
	if cfg.has_section_key("workout", "intensity_factor"):
		wd["intensity_factor"] = clampf(float(cfg.get_value("workout", "intensity_factor", 1.0)), 0.8, 1.3)
	if cfg.has_section_key("workout", "height_cm"):
		wd["height_cm"] = clampf(float(cfg.get_value("workout", "height_cm", 170.0)), 120.0, 220.0)
	if cfg.has_section_key("workout", "age"):
		wd["age"] = clampi(int(cfg.get_value("workout", "age", 30)), 10, 100)
	if cfg.has_section_key("workout", "gender"):
		wd["gender"] = str(cfg.get_value("workout", "gender", "male"))
	if cfg.has_section_key("workout", "daily_kcal_goal"):
		wd["daily_kcal_goal"] = clampf(float(cfg.get_value("workout", "daily_kcal_goal", 0.0)), 0.0, 2000.0)
	var daily_cal: Dictionary = {}
	if cfg.has_section("daily_calories"):
		for date_key: String in cfg.get_section_keys("daily_calories"):
			daily_cal[date_key] = float(cfg.get_value("daily_calories", date_key, 0.0))
	wd["daily_calories"] = daily_cal
	var daily_wt: Dictionary = {}
	if cfg.has_section("daily_weight_log"):
		for date_key: String in cfg.get_section_keys("daily_weight_log"):
			daily_wt[date_key] = float(cfg.get_value("daily_weight_log", date_key, 0.0))
	wd["daily_weight_log"] = daily_wt
	data["workout"] = wd

	# daily challenges
	var cd: Dictionary = {}
	var ch_date: String = ""
	if cfg.has_section_key("daily_challenges", "date"):
		ch_date = str(cfg.get_value("daily_challenges", "date", ""))
	cd["date"] = ch_date
	cd["sessions_completed"] = 0
	cd["picks"] = [] as Array[String]
	cd["progress"] = {}
	var today_key: String = _today_key_static()
	if ch_date == today_key and cfg.has_section("daily_challenges"):
		cd["sessions_completed"] = int(cfg.get_value("daily_challenges", "sessions_completed", 0))
		var loaded_picks: Array[String] = []
		for i: int in range(3):
			var pk := "pick_%d" % i
			if cfg.has_section_key("daily_challenges", pk):
				loaded_picks.append(str(cfg.get_value("daily_challenges", pk, "")))
		cd["picks"] = loaded_picks
		var ch_progress: Dictionary = {}
		if cfg.has_section("daily_challenge_progress"):
			for pk2: String in cfg.get_section_keys("daily_challenge_progress"):
				ch_progress[pk2] = int(cfg.get_value("daily_challenge_progress", pk2, 0))
		cd["progress"] = ch_progress
		cd["picks_invalid"] = loaded_picks.size() != 3
	data["challenges"] = cd

	# time attack
	var spd: Dictionary = {}
	if cfg.has_section_key("time_attack", "best_sec"):
		spd["best_sec"] = float(cfg.get_value("time_attack", "best_sec", -1.0))
	if cfg.has_section_key("time_attack", "last_sec"):
		spd["last_sec"] = float(cfg.get_value("time_attack", "last_sec", -1.0))
	var history: Array[float] = []
	if cfg.has_section_key("time_attack", "history_csv"):
		var csv: String = str(cfg.get_value("time_attack", "history_csv", ""))
		if not csv.is_empty():
			for part: String in csv.split(","):
				var p: String = part.strip_edges()
				if not p.is_empty():
					var v: float = float(p)
					if is_finite(v) and v > 0.0:
						history.append(v)
	spd["history"] = history
	data["stage_progress"] = spd

	# meta/upgrades
	var ud: Dictionary = {}
	if cfg.has_section_key("meta", "sweat"):
		ud["sweat"] = maxi(0, int(cfg.get_value("meta", "sweat", 0)))
	if cfg.has_section_key("meta", "up_hp"):
		ud["up_hp"] = clampi(int(cfg.get_value("meta", "up_hp", 0)), 0, 20)
	if cfg.has_section_key("meta", "up_sta"):
		ud["up_stamina"] = clampi(int(cfg.get_value("meta", "up_sta", 0)), 0, 20)
	if cfg.has_section_key("meta", "up_rec"):
		ud["up_recover"] = clampi(int(cfg.get_value("meta", "up_rec", 0)), 0, 20)
	data["upgrade"] = ud

	# difficulty
	if cfg.has_section_key("progress", "difficulty"):
		data["difficulty"] = str(cfg.get_value("progress", "difficulty", "normal"))

	# stage stars/records/last_played
	if cfg.has_section("stage_stars"):
		var stars: Dictionary = {}
		for sid: String in cfg.get_section_keys("stage_stars"):
			stars[sid] = clampi(int(cfg.get_value("stage_stars", sid, 0)), 0, 3)
		spd["stars"] = stars
	if cfg.has_section_key("meta", "last_played_stage"):
		spd["last_played"] = str(cfg.get_value("meta", "last_played_stage", "stage_1"))
	if cfg.has_section("stage_records"):
		var records: Dictionary = {}
		for key: String in cfg.get_section_keys("stage_records"):
			if key.ends_with("_best_time"):
				var sid: String = key.substr(0, key.length() - 10)
				if not records.has(sid):
					records[sid] = {}
				records[sid]["best_time"] = float(cfg.get_value("stage_records", key, -1.0))
			elif key.ends_with("_best_combo"):
				var sid: String = key.substr(0, key.length() - 11)
				if not records.has(sid):
					records[sid] = {}
				records[sid]["best_combo"] = int(cfg.get_value("stage_records", key, 0))
			elif key.ends_with("_least_dmg"):
				var sid: String = key.substr(0, key.length() - 10)
				if not records.has(sid):
					records[sid] = {}
				records[sid]["least_dmg"] = float(cfg.get_value("stage_records", key, -1.0))
		spd["records"] = records

	# achievements
	var ad: Dictionary = {}
	var ach_unlocked: Dictionary = {}
	if cfg.has_section("achievements_unlocked"):
		for aid: String in cfg.get_section_keys("achievements_unlocked"):
			ach_unlocked[aid] = bool(cfg.get_value("achievements_unlocked", aid, false))
	ad["unlocked"] = ach_unlocked
	var ach_progress: Dictionary = {}
	if cfg.has_section("achievement_progress"):
		for aid: String in cfg.get_section_keys("achievement_progress"):
			ach_progress[aid] = int(cfg.get_value("achievement_progress", aid, 0))
	ad["progress"] = ach_progress
	data["achievements"] = ad

	# shop
	var sdata: Dictionary = {}
	var shop_owned: Dictionary = {}
	if cfg.has_section("shop_owned"):
		for iid: String in cfg.get_section_keys("shop_owned"):
			shop_owned[iid] = bool(cfg.get_value("shop_owned", iid, false))
	sdata["owned"] = shop_owned
	var shop_inv: Dictionary = {}
	if cfg.has_section("shop_inventory"):
		for iid: String in cfg.get_section_keys("shop_inventory"):
			shop_inv[iid] = int(cfg.get_value("shop_inventory", iid, 0))
	sdata["inventory"] = shop_inv
	if cfg.has_section_key("shop", "equipped_glove_skin"):
		sdata["equipped_glove_skin"] = str(cfg.get_value("shop", "equipped_glove_skin", ""))
	if cfg.has_section_key("shop", "equipped_hit_effect"):
		sdata["equipped_hit_effect"] = str(cfg.get_value("shop", "equipped_hit_effect", ""))
	data["shop"] = sdata

	# boss
	var bd: Dictionary = {}
	if cfg.has_section_key("boss", "phase"):
		bd["phase"] = int(cfg.get_value("boss", "phase", 0))
	data["boss"] = bd

	return data


static func _today_key_static() -> String:
	var dt := Time.get_datetime_dict_from_unix_time(int(Time.get_unix_time_from_system()))
	return "%04d-%02d-%02d" % [int(dt.get("year", 1970)), int(dt.get("month", 1)), int(dt.get("day", 1))]


static func delete_save() -> void:
	if FileAccess.file_exists(STATS_PATH):
		DirAccess.remove_absolute(STATS_PATH)
