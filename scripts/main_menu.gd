extends Control
## 메인 메뉴: 게임 시작, 게임 설명, 설정, 종료 (오른쪽 세로 버튼)

const SCENE_GAME := "res://scenes/main.tscn"
const SCENE_SETTINGS := "res://scenes/ui/settings_panel.tscn"
const SCENE_HOW_TO_PLAY := "res://scenes/ui/how_to_play_panel.tscn"
const SCENE_STATS := "res://scenes/ui/stats_panel.tscn"

@onready var _btn_start: Button = $RightPanel/ButtonBox/BtnStart
@onready var _btn_how_to_play: Button = $RightPanel/ButtonBox/BtnHowToPlay
@onready var _btn_settings: Button = $RightPanel/ButtonBox/BtnSettings
@onready var _btn_stats: Button = $RightPanel/ButtonBox/BtnStats
@onready var _btn_quit: Button = $RightPanel/ButtonBox/BtnQuit

var _ch_titles: Array[Label] = []
var _ch_bars: Array[ProgressBar] = []

@onready var _goal_spin: SpinBox = $LeftPanel/Scroll/MarginContainer/DailyVBox/GoalRow/GoalSpin
@onready var _btn_apply_rec: Button = $LeftPanel/Scroll/MarginContainer/DailyVBox/GoalRow/BtnApplyRec
@onready var _bmi_hint: Label = $LeftPanel/Scroll/MarginContainer/DailyVBox/BmiHint
@onready var _rec_hint: Label = $LeftPanel/Scroll/MarginContainer/DailyVBox/RecHint
@onready var _goal_prog_lbl: Label = $LeftPanel/Scroll/MarginContainer/DailyVBox/GoalProgressLabel
@onready var _goal_prog_bar: ProgressBar = $LeftPanel/Scroll/MarginContainer/DailyVBox/GoalProgressBar
@onready var _goal_hints: Label = $LeftPanel/Scroll/MarginContainer/DailyVBox/GoalHints

var _goal_spin_suppress: bool = false

var _settings_panel: Control
var _how_to_play_panel: Control
var _stats_panel: Control


func _ready() -> void:
	var bgm: AudioStreamPlayer = get_node_or_null("BGM")
	if bgm:
		if AudioServer.get_bus_index("Music") >= 0:
			bgm.bus = "Music"
		# 파일이 아직 없으면 씬이 깨질 수 있어, 런타임에 존재하는 경로만 로드
		if bgm.stream == null:
			_try_load_stream(bgm, [
				"res://assets/audio/bgm/Pixel_Punch_Frenzy.ogg",
				"res://assets/audio/bgm/mainbgm.ogg",
			])
		if bgm.stream and bgm.playing == false:
			bgm.play()
	if _btn_start:
		_btn_start.pressed.connect(_on_start)
	if _btn_how_to_play:
		_btn_how_to_play.pressed.connect(_on_how_to_play)
	if _btn_settings:
		_btn_settings.pressed.connect(_on_settings)
	if _btn_stats:
		_btn_stats.pressed.connect(_on_stats)
	if _btn_quit:
		_btn_quit.pressed.connect(_on_quit)
	_ch_titles = [
		$LeftPanel/Scroll/MarginContainer/DailyVBox/ChallengeRows/Row0/ChTitle0,
		$LeftPanel/Scroll/MarginContainer/DailyVBox/ChallengeRows/Row1/ChTitle1,
		$LeftPanel/Scroll/MarginContainer/DailyVBox/ChallengeRows/Row2/ChTitle2,
	]
	_ch_bars = [
		$LeftPanel/Scroll/MarginContainer/DailyVBox/ChallengeRows/Row0/ChBar0,
		$LeftPanel/Scroll/MarginContainer/DailyVBox/ChallengeRows/Row1/ChBar1,
		$LeftPanel/Scroll/MarginContainer/DailyVBox/ChallengeRows/Row2/ChBar2,
	]
	if _btn_apply_rec:
		_btn_apply_rec.pressed.connect(_on_apply_recommended_goal)
	if _goal_spin:
		_goal_spin.value_changed.connect(_on_goal_spin_changed)
	_refresh_daily_challenges_ui()
	_refresh_daily_goal_ui()


func _notification(what: int) -> void:
	if what == NOTIFICATION_VISIBILITY_CHANGED and is_visible_in_tree():
		_refresh_daily_challenges_ui()
		_refresh_daily_goal_ui()


func _refresh_daily_challenges_ui() -> void:
	var rows: Array[Dictionary] = GameState.get_daily_challenges_for_ui()
	for i: int in range(3):
		if i >= _ch_titles.size() or i >= _ch_bars.size():
			break
		var t: Label = _ch_titles[i]
		var bar: ProgressBar = _ch_bars[i]
		if i < rows.size():
			var r: Dictionary = rows[i]
			var cur: int = int(r.get("current", 0))
			var tgt: int = maxi(1, int(r.get("target", 1)))
			var done: bool = bool(r.get("completed", false))
			t.text = "%s  (%d / %d)" % [str(r.get("title", "")), cur, tgt]
			bar.max_value = float(tgt)
			bar.value = float(mini(cur, tgt))
			if done:
				bar.modulate = Color(0.55, 0.95, 0.65, 1.0)
			else:
				bar.modulate = Color(1, 1, 1, 1)
		else:
			t.text = "—"
			bar.max_value = 1.0
			bar.value = 0.0
			bar.modulate = Color(1, 1, 1, 1)


func _on_apply_recommended_goal() -> void:
	GameState.apply_recommended_daily_kcal_goal()
	_refresh_daily_goal_ui()


func _on_goal_spin_changed(v: float) -> void:
	if _goal_spin_suppress:
		return
	GameState.set_daily_kcal_goal(v)
	_refresh_daily_goal_progress_only()


func _refresh_daily_goal_ui() -> void:
	if _bmi_hint:
		var bmi: float = GameState.get_bmi()
		if bmi > 0.0:
			_bmi_hint.text = "BMI %.1f (%s) · 체중·키·나이·성별은 설정에서 바꿀 수 있어요" % [
				bmi,
				GameState.get_bmi_category_label(),
			]
		else:
			_bmi_hint.text = "키·체중을 설정하면 BMI와 권장 목표를 계산해요"
	if _rec_hint:
		var rec: float = GameState.get_recommended_daily_kcal_goal()
		var src: String = "BMI·BMR 기준 권장(운동 추가 소모 추정): 약 %d kcal/일" % int(roundf(rec))
		if GameState.has_custom_daily_kcal_goal():
			src += " · 지금 목표는 직접 저장된 값"
		else:
			src += " · 지금 목표에 반영 중"
		_rec_hint.text = src
	if _goal_spin:
		_goal_spin_suppress = true
		_goal_spin.value = GameState.get_daily_kcal_goal()
		_goal_spin_suppress = false
	_refresh_daily_goal_progress_only()


func _refresh_daily_goal_progress_only() -> void:
	var h: Dictionary = GameState.get_daily_goal_punch_hints()
	var goal: float = float(h.get("goal", 1.0))
	var today: float = float(h.get("today", 0.0))
	var rem: float = float(h.get("remaining", 0.0))
	if _goal_prog_lbl:
		_goal_prog_lbl.text = (
			"오늘 %.0f / 목표 %.0f kcal\n"
			+ "· 오늘 누적은 한 판이 끝날 때(KO·게임오버·메뉴로 나가기 등) 더해져요"
		) % [today, goal]
	if _goal_prog_bar:
		_goal_prog_bar.max_value = maxf(goal, 1.0)
		_goal_prog_bar.value = mini(today, goal)
		if today >= goal and goal > 0.0:
			_goal_prog_bar.modulate = Color(0.55, 0.95, 0.65, 1.0)
		else:
			_goal_prog_bar.modulate = Color(1, 1, 1, 1)
	if not _goal_hints:
		return
	if rem <= 0.0001 and goal > 0.0 and today >= goal - 0.0001:
		_goal_hints.text = "오늘 목표 칼로리를 채웠어요. 잘했어요!"
		return
	if goal <= 0.0:
		_goal_hints.text = ""
		return
	var j: int = int(h.get("jab_only", 0))
	var hk: int = int(h.get("hook_only", 0))
	var u: int = int(h.get("upper_only", 0))
	var d: int = int(h.get("dodge_only", 0))
	var m: int = int(h.get("mixed_same", 0))
	_goal_hints.text = (
		"남은 약 %.0f kcal을 게임 내 동작 상수만으로 채울 때 대략:\n"
		+ "• 잽만: 약 %d회 · 훅만: 약 %d회 · 어퍼만: 약 %d회 · 회피만: 약 %d회\n"
		+ "• 잽/훅/어퍼를 비슷하게 섞으면: 약 %d회 분량\n"
		+ "(세션 종료 시 MET 보정으로 실제 누적과 다를 수 있어요.)"
	) % [rem, j, hk, u, d, m]


func _try_load_stream(player: AudioStreamPlayer, paths: Array[String]) -> void:
	for p in paths:
		if ResourceLoader.exists(p):
			var res := load(p)
			if res is AudioStream:
				player.stream = res
				return


func _on_start() -> void:
	get_tree().change_scene_to_file(SCENE_GAME)


func _on_how_to_play() -> void:
	if _how_to_play_panel:
		return
	var packed := load(SCENE_HOW_TO_PLAY) as PackedScene
	if not packed:
		return
	_how_to_play_panel = packed.instantiate() as Control
	if _how_to_play_panel:
		add_child(_how_to_play_panel)
		_how_to_play_panel.set_anchors_preset(Control.PRESET_FULL_RECT)
		if _how_to_play_panel.has_signal("back_pressed"):
			_how_to_play_panel.back_pressed.connect(_close_how_to_play)


func _close_how_to_play() -> void:
	if _how_to_play_panel:
		_how_to_play_panel.queue_free()
		_how_to_play_panel = null


func _on_settings() -> void:
	if _settings_panel:
		return
	var packed := load(SCENE_SETTINGS) as PackedScene
	if not packed:
		return
	_settings_panel = packed.instantiate() as Control
	if _settings_panel:
		add_child(_settings_panel)
		_settings_panel.set_anchors_preset(Control.PRESET_FULL_RECT)
		if _settings_panel.has_signal("back_pressed"):
			_settings_panel.back_pressed.connect(_close_settings)


func _close_settings() -> void:
	if _settings_panel:
		_settings_panel.queue_free()
		_settings_panel = null
	_refresh_daily_goal_ui()


func _on_stats() -> void:
	if _stats_panel:
		return
	var packed := load(SCENE_STATS) as PackedScene
	if not packed:
		return
	_stats_panel = packed.instantiate() as Control
	if _stats_panel:
		add_child(_stats_panel)
		_stats_panel.set_anchors_preset(Control.PRESET_FULL_RECT)
		if _stats_panel.has_signal("back_pressed"):
			_stats_panel.back_pressed.connect(_close_stats)


func _close_stats() -> void:
	if _stats_panel:
		_stats_panel.queue_free()
		_stats_panel = null
	_refresh_daily_goal_ui()


func _on_quit() -> void:
	get_tree().quit()
