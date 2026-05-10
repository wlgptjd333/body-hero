extends Node
## UI Director: 모든 HUD 업데이트와 승/패 화면 제어를 담당.
## 데이터는 외부(CombatDirector/Main)에서 받아 화면에만 반영.

@onready var _play_time_label: Label = $"../HUD/PlayTimeCorner"
@onready var _training_kill_label: Label = get_node_or_null("../HUD/TrainingKillLabel")
@onready var _training_attack_label: Label = get_node_or_null("../HUD/TrainingAttackLabel")
@onready var _combo_label: Label = $"../Enemy/ComboLabel"
@onready var _enemy_hp_bar: ProgressBar = $"../HUD/TopBar/EnemyHPBar"
@onready var _player_hp_bar: ProgressBar = $"../HUD/BottomBars/PlayerHPBar"
@onready var _player_stamina_bar: ProgressBar = $"../HUD/BottomBars/PlayerStaminaBar"
@onready var _enemy_hp_label: Label = $"../HUD/TopBar/EnemyHPLabel"
@onready var _game_over_layer: CanvasLayer = $"../GameOverLayer"
@onready var _ko_intro_layer: CanvasLayer = $"../KoIntroLayer"
@onready var _win_layer: CanvasLayer = $"../WinLayer"
@onready var _game_over_calories_label: Label = $"../GameOverLayer/GameOverVBox/GameOverCaloriesLabel"
@onready var _game_over_daily_calories_label: Label = $"../GameOverLayer/GameOverVBox/GameOverDailyCaloriesLabel"
@onready var _win_calories_label: Label = $"../WinLayer/WinVBox/WinCaloriesLabel"
@onready var _win_daily_calories_label: Label = $"../WinLayer/WinVBox/WinDailyCaloriesLabel"
@onready var _win_clear_time_label: Label = $"../WinLayer/WinVBox/WinClearTimeLabel"
@onready var _win_stars_label: Label = $"../WinLayer/WinVBox/WinStarsLabel"


func _ready() -> void:
	if _game_over_layer:
		_game_over_layer.process_mode = Node.PROCESS_MODE_ALWAYS as Node.ProcessMode
	if _ko_intro_layer:
		_ko_intro_layer.process_mode = Node.PROCESS_MODE_ALWAYS as Node.ProcessMode
	if _win_layer:
		_win_layer.process_mode = Node.PROCESS_MODE_ALWAYS as Node.ProcessMode


# --- HUD 업데이트 ---

func update_bars(enemy: Node) -> void:
	if _enemy_hp_bar and enemy and "current_hp" in enemy and "max_hp" in enemy and enemy.max_hp > 0.0:
		var ratio: float = clampf(enemy.current_hp / enemy.max_hp, 0.0, 1.0)
		_enemy_hp_bar.value = ratio * 100.0
	if _player_hp_bar:
		_player_hp_bar.value = GameState.get_player_hp_ratio() * 100.0
	if _player_stamina_bar:
		_player_stamina_bar.value = GameState.get_stamina_ratio() * 100.0


func update_play_time(elapsed_sec: float) -> void:
	if _play_time_label:
		var best: float = GameState.get_best_stage_clear_sec()
		var base: String = "플레이 %s" % _format_play_time_sec(elapsed_sec)
		if best > 0.0:
			base += "  |  최고: %s" % GameState.format_stage_clear_time(best)
		_play_time_label.text = base


func _format_play_time_sec(sec: float) -> String:
	var s: float = maxf(sec, 0.0)
	var mi: int = int(s / 60.0)
	var rem: float = s - float(mi) * 60.0
	if mi > 0:
		return "%d:%05.2f" % [mi, rem]
	return "%.1f초" % s


func update_combo(count: int) -> void:
	if not _combo_label:
		return
	if count < 2:
		_combo_label.visible = false
		_combo_label.text = ""
	else:
		_combo_label.visible = true
		var scale: float = 1.0 + minf(float(count) / 50.0, 0.5)
		_combo_label.scale = Vector2(scale, scale)
		# 색상 변화: 2~9 노랑, 10~19 주황, 20~29 빨강, 30+ 별빛
		if count >= 30:
			_combo_label.add_theme_color_override("font_color", Color(1.0, 0.45, 0.9))
		elif count >= 20:
			_combo_label.add_theme_color_override("font_color", Color(1.0, 0.2, 0.2))
		elif count >= 10:
			_combo_label.add_theme_color_override("font_color", Color(1.0, 0.55, 0.1))
		else:
			_combo_label.add_theme_color_override("font_color", Color(1.0, 0.92, 0.35))
		_combo_label.text = "%d COMBO" % count


func update_training(training_mode: bool, kill_count: int, action_counts: Dictionary) -> void:
	if _training_kill_label:
		_training_kill_label.visible = training_mode
		if training_mode:
			_training_kill_label.text = "처치 횟수: %d" % kill_count
	if _training_attack_label:
		_training_attack_label.visible = training_mode
		if training_mode:
			_training_attack_label.text = (
				"펀치L: %d\n펀치R: %d\n어퍼L: %d\n어퍼R: %d\n가드: %d\n스쿼트: %d"
				% [
					int(action_counts.get("punch_l", 0)),
					int(action_counts.get("punch_r", 0)),
					int(action_counts.get("upper_l", 0)),
					int(action_counts.get("upper_r", 0)),
					int(action_counts.get("guard", 0)),
					int(action_counts.get("squat", 0)),
				]
			)


func set_enemy_label(text: String) -> void:
	if _enemy_hp_label:
		_enemy_hp_label.text = text


# --- 오버레이 제어 ---

func show_game_over(kcal: float, today_kcal: float) -> void:
	if _game_over_calories_label:
		_game_over_calories_label.text = "소모 칼로리: %.1f kcal" % kcal
	if _game_over_daily_calories_label:
		_game_over_daily_calories_label.text = "오늘 누적: %.1f kcal" % today_kcal
	if _game_over_layer:
		_game_over_layer.visible = true


func show_win(kcal: float, today_kcal: float, clear_sec: float) -> void:
	if _win_calories_label:
		_win_calories_label.text = "소모 칼로리: %.1f kcal" % kcal
	if _win_daily_calories_label:
		_win_daily_calories_label.text = "오늘 누적: %.1f kcal" % today_kcal
	if _win_clear_time_label:
		_win_clear_time_label.text = "클리어 시간: %s" % GameState.format_stage_clear_time(clear_sec)
	if _win_stars_label:
		var stars: int = GameState.get_stage_stars("stage_1")
		var star_str: String = ""
		for i in range(3):
			star_str += "★" if i < stars else "☆"
		_win_stars_label.text = star_str
	if _win_layer:
		_win_layer.visible = true


func show_ko_intro() -> void:
	if _enemy_hp_label:
		_enemy_hp_label.text = "KO!"
	if _ko_intro_layer:
		_ko_intro_layer.visible = true


func hide_ko_intro() -> void:
	if _ko_intro_layer:
		_ko_intro_layer.visible = false


func show_achievement_popup(_ach_id: String, title: String) -> void:
	var layer := CanvasLayer.new()
	layer.process_mode = Node.PROCESS_MODE_ALWAYS as Node.ProcessMode
	var lbl := Label.new()
	lbl.text = "업적 달성!  " + title
	lbl.add_theme_font_size_override("font_size", 18)
	lbl.add_theme_color_override("font_color", Color(1.0, 0.92, 0.35))
	lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	lbl.anchors_preset = Control.PRESET_CENTER_TOP
	lbl.offset_top = 100.0
	lbl.offset_left = -250.0
	lbl.offset_right = 250.0
	lbl.offset_bottom = 140.0
	layer.add_child(lbl)
	var parent: Node = get_parent()
	if parent:
		parent.add_child(layer)
		var tween := lbl.create_tween()
		tween.tween_property(lbl, "modulate:a", 0.0, 0.5).set_delay(2.5)
		tween.tween_callback(layer.queue_free)
