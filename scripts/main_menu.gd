extends Control
## 메인 메뉴: 게임 시작, 업그레이드, 튜토리얼, 홈 이동

const SCENE_GAME := "res://games/boxing/scenes/stage_1.tscn"
const SCENE_STAGE_SELECT := "res://scenes/ui/stage_select.tscn"
const SCENE_HOME_HUB := "res://scenes/home_hub.tscn"
const SCENE_HOW_TO_PLAY := "res://scenes/ui/how_to_play_panel.tscn"
const SCENE_BOXING_UPGRADE := "res://scenes/ui/boxing_upgrade_panel.tscn"
const SCENE_TRAINING := "res://games/boxing/scenes/training.tscn"
const SCENE_SHOP := "res://scenes/ui/shop_panel.tscn"
const SCENE_ACHIEVEMENTS := "res://scenes/ui/achievement_panel.tscn"

@onready var _btn_start: Button = $RightPanel/ButtonBox/BtnStart
@onready var _btn_upgrade: Button = $RightPanel/ButtonBox/BtnUpgrade
@onready var _btn_how_to_play: Button = $RightPanel/ButtonBox/BtnHowToPlay
@onready var _btn_training: Button = $RightPanel/ButtonBox/BtnTraining
@onready var _btn_home: Button = $RightPanel/ButtonBox/BtnHome
@onready var _btn_shop: Button = $RightPanel/ButtonBox/BtnShop
@onready var _btn_achievements: Button = $RightPanel/ButtonBox/BtnAchievements
@onready var _btn_difficulty: Button = $RightPanel/ButtonBox/BtnDifficulty

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

var _how_to_play_panel: Control
var _upgrade_panel: Control
var _shop_panel: Control
var _achievement_panel: Control


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
	if _btn_upgrade:
		_btn_upgrade.pressed.connect(_on_upgrade)
	if _btn_how_to_play:
		_btn_how_to_play.pressed.connect(_on_how_to_play)
	if _btn_training:
		_btn_training.pressed.connect(_on_training)
	if _btn_home:
		_btn_home.pressed.connect(_on_home)
	if _btn_shop:
		_btn_shop.pressed.connect(_on_shop)
	if _btn_achievements:
		_btn_achievements.pressed.connect(_on_achievements)
	if _btn_difficulty:
		_btn_difficulty.pressed.connect(_on_difficulty)
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
	_beautify_ui()
	_refresh_difficulty_button()


func _beautify_ui() -> void:
	# ── 배경 ──
	var bg: TextureRect = $Background
	if bg:
		bg.modulate = Color(0.6, 0.6, 0.7, 1.0)  # 배경 살짝 어둡게

	# ── RightPanel: Glass Panel ──
	var right_panel: PanelContainer = $RightPanel
	if right_panel:
		UIThemeHelper.style_panel_container_glass(right_panel)
	var button_box: VBoxContainer = $RightPanel/ButtonBox
	button_box.add_theme_constant_override("separation", 8)

	# 버튼 스타일링
	UIThemeHelper.style_button_primary(_btn_start)
	UIThemeHelper.style_button_secondary(_btn_training)
	UIThemeHelper.style_button_secondary(_btn_upgrade)
	UIThemeHelper.style_button_secondary(_btn_shop)
	UIThemeHelper.style_button_secondary(_btn_achievements)
	UIThemeHelper.style_button_secondary(_btn_difficulty)
	UIThemeHelper.style_button_secondary(_btn_how_to_play)
	UIThemeHelper.style_button_danger(_btn_home)
	for btn: Button in [_btn_start, _btn_training, _btn_upgrade, _btn_shop, _btn_achievements, _btn_difficulty, _btn_how_to_play, _btn_home]:
		if btn == null:
			continue
		btn.custom_minimum_size = Vector2(0, 42)

	# 섹션 구분 라벨 (accent line + text)
	var make_sep := func(title: String) -> HBoxContainer:
		var hbox := HBoxContainer.new()
		hbox.add_theme_constant_override("separation", 8)
		var line := ColorRect.new()
		line.custom_minimum_size = Vector2(24, 2)
		line.color = UIThemeHelper.C_ACCENT
		line.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		hbox.add_child(line)
		var lbl := Label.new()
		lbl.text = title
		UIThemeHelper.style_label_caption(lbl)
		lbl.add_theme_color_override("font_color", UIThemeHelper.C_ACCENT)
		hbox.add_child(lbl)
		var stretch := Control.new()
		stretch.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		hbox.add_child(stretch)
		return hbox

	# 재정렬
	var order: Array[Button] = [
		_btn_start, _btn_training, _btn_upgrade, _btn_shop,
		_btn_achievements, _btn_difficulty, _btn_how_to_play, _btn_home,
	]
	for btn: Button in order:
		if btn == null:
			continue
		button_box.remove_child(btn)

	button_box.add_child(_btn_start)
	button_box.add_child(_btn_training)
	button_box.add_child(make_sep.call("성장"))
	button_box.add_child(_btn_upgrade)
	button_box.add_child(_btn_shop)
	button_box.add_child(_btn_achievements)
	button_box.add_child(make_sep.call("설정"))
	button_box.add_child(_btn_difficulty)
	button_box.add_child(_btn_how_to_play)
	button_box.add_child(_btn_home)

	# ── LeftPanel: Glass Panel ──
	var left_panel: PanelContainer = $LeftPanel
	if left_panel:
		UIThemeHelper.style_panel_container_glass(left_panel)

	# 도전과제 ProgressBar 숨기고 깔끔한 텍스트로
	for i in range(3):
		if i < _ch_bars.size():
			_ch_bars[i].visible = false
	var challenge_rows: VBoxContainer = $LeftPanel/Scroll/MarginContainer/DailyVBox/ChallengeRows
	if challenge_rows:
		challenge_rows.add_theme_constant_override("separation", 6)

	# 제목 스타일
	var daily_title: Label = $LeftPanel/Scroll/MarginContainer/DailyVBox/DailyMainTitle
	if daily_title:
		UIThemeHelper.style_label_section(daily_title)
		daily_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var daily_sub: Label = $LeftPanel/Scroll/MarginContainer/DailyVBox/DailySubTitle
	if daily_sub:
		UIThemeHelper.style_label_caption(daily_sub)
		daily_sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var goal_title: Label = $LeftPanel/Scroll/MarginContainer/DailyVBox/GoalTitle
	if goal_title:
		UIThemeHelper.style_label_section(goal_title)
		goal_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER

	# 본문 스타일
	if _bmi_hint:
		UIThemeHelper.style_label_caption(_bmi_hint)
	if _rec_hint:
		UIThemeHelper.style_label_caption(_rec_hint)
	if _goal_prog_lbl:
		UIThemeHelper.style_label_body(_goal_prog_lbl)
		_goal_prog_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	if _goal_hints:
		UIThemeHelper.style_label_caption(_goal_hints)
		_goal_hints.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER

	# ProgressBar 스타일
	if _goal_prog_bar:
		UIThemeHelper.style_progress_bar(_goal_prog_bar)


func _notification(what: int) -> void:
	if what == NOTIFICATION_VISIBILITY_CHANGED and is_visible_in_tree():
		_refresh_daily_challenges_ui()
		_refresh_daily_goal_ui()


func _refresh_daily_challenges_ui() -> void:
	var rows: Array[Dictionary] = GameState.get_daily_challenges_for_ui()
	for i: int in range(3):
		if i >= _ch_titles.size():
			break
		var t: Label = _ch_titles[i]
		if i < rows.size():
			var r: Dictionary = rows[i]
			var cur: int = int(r.get("current", 0))
			var tgt: int = maxi(1, int(r.get("target", 1)))
			var done: bool = bool(r.get("completed", false))
			var icon: String = "✓" if done else "○"
			var pct: int = int(100.0 * float(cur) / float(tgt))
			var color: Color = Color(0.55, 0.95, 0.65) if done else Color(0.88, 0.88, 0.92)
			t.text = "%s %s  %d/%d (%d%%)" % [icon, str(r.get("title", "")), cur, tgt, pct]
			t.add_theme_color_override("font_color", color)
		else:
			t.text = "—"
			t.add_theme_color_override("font_color", Color(0.6, 0.6, 0.65))


func _on_apply_recommended_goal() -> void:
	GameState.apply_recommended_daily_kcal_goal()
	_refresh_daily_goal_ui()


func _on_goal_spin_changed(v: float) -> void:
	if _goal_spin_suppress:
		return
	GameState.set_daily_kcal_goal(v)
	_refresh_daily_goal_progress_only()


func _refresh_daily_goal_ui() -> void:
	var bmi: float = GameState.get_bmi()
	var rec: float = GameState.get_recommended_daily_kcal_goal()
	if _bmi_hint:
		if bmi > 0.0:
			_bmi_hint.text = "BMI %.1f (%s)" % [bmi, GameState.get_bmi_category_label()]
		else:
			_bmi_hint.text = "설정에서 키·체중을 입력하면 BMI를 계산해요"
	if _rec_hint:
		var custom: String = "(사용자 지정)" if GameState.has_custom_daily_kcal_goal() else "(권장)"
		_rec_hint.text = "일일 권장 소모: 약 %d kcal %s" % [int(roundf(rec)), custom]
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
		var pct: int = int(100.0 * today / maxf(goal, 1.0))
		if today >= goal and goal > 0.0:
			_goal_prog_lbl.text = "오늘 %.0f / %.0f kcal  ·  목표 달성! ✓" % [today, goal]
			_goal_prog_lbl.add_theme_color_override("font_color", Color(0.55, 0.95, 0.65))
		else:
			_goal_prog_lbl.text = "오늘 %.0f / %.0f kcal  (%d%%)" % [today, goal, pct]
			_goal_prog_lbl.add_theme_color_override("font_color", Color(0.82, 0.88, 0.95))
	if _goal_prog_bar:
		_goal_prog_bar.max_value = maxf(goal, 1.0)
		_goal_prog_bar.value = minf(today, goal)
		if today >= goal and goal > 0.0:
			_goal_prog_bar.modulate = Color(0.55, 0.95, 0.65, 1.0)
		else:
			_goal_prog_bar.modulate = Color(1, 1, 1, 1)
	if not _goal_hints:
		return
	if rem <= 0.0001 and goal > 0.0 and today >= goal - 0.0001:
		_goal_hints.text = "목표 달성! 훌륭해요."
		return
	if goal <= 0.0:
		_goal_hints.text = ""
		return
	var m: int = int(h.get("mixed_same", 0))
	_goal_hints.text = "약 %.0f kcal 남음  ·  펀치/어퍼 섞으면 약 %d회" % [rem, m]


func _try_load_stream(player: AudioStreamPlayer, paths: Array[String]) -> void:
	AudioHelper.try_load_stream(player, paths)


func _on_start() -> void:
	# 이전 씬에서 paused 상태가 남아 있으면 새 씬이 '멈춘 것처럼' 보일 수 있어 강제로 해제
	get_tree().paused = false
	GameState.set_training_mode(false)
	get_tree().change_scene_to_file(SCENE_STAGE_SELECT)


func _on_upgrade() -> void:
	if _upgrade_panel:
		return
	var packed := load(SCENE_BOXING_UPGRADE) as PackedScene
	if not packed:
		return
	_upgrade_panel = packed.instantiate() as Control
	if _upgrade_panel:
		add_child(_upgrade_panel)
		_upgrade_panel.set_anchors_preset(Control.PRESET_FULL_RECT)
		if _upgrade_panel.has_signal("upgrade_closed"):
			_upgrade_panel.upgrade_closed.connect(_close_upgrade)
		if _upgrade_panel.has_method("refresh_display"):
			_upgrade_panel.refresh_display()


func _close_upgrade() -> void:
	if _upgrade_panel:
		_upgrade_panel.queue_free()
		_upgrade_panel = null


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


func _on_training() -> void:
	get_tree().paused = false
	GameState.set_training_mode(true)
	get_tree().change_scene_to_file(SCENE_TRAINING)


func _on_home() -> void:
	# 메인(복싱) 화면에서만 홈 허브로 이동
	get_tree().paused = false
	GameState.set_training_mode(false)
	get_tree().change_scene_to_file(SCENE_HOME_HUB)


func _on_shop() -> void:
	if _shop_panel:
		return
	var packed := load(SCENE_SHOP) as PackedScene
	if not packed:
		return
	_shop_panel = packed.instantiate() as Control
	if _shop_panel:
		add_child(_shop_panel)
		_shop_panel.set_anchors_preset(Control.PRESET_FULL_RECT)
		if _shop_panel.has_signal("back_pressed"):
			_shop_panel.back_pressed.connect(_close_shop)

func _close_shop() -> void:
	if _shop_panel:
		_shop_panel.queue_free()
		_shop_panel = null


func _on_achievements() -> void:
	if _achievement_panel:
		return
	var packed := load(SCENE_ACHIEVEMENTS) as PackedScene
	if not packed:
		return
	_achievement_panel = packed.instantiate() as Control
	if _achievement_panel:
		add_child(_achievement_panel)
		_achievement_panel.set_anchors_preset(Control.PRESET_FULL_RECT)
		if _achievement_panel.has_signal("back_pressed"):
			_achievement_panel.back_pressed.connect(_close_achievements)

func _close_achievements() -> void:
	if _achievement_panel:
		_achievement_panel.queue_free()
		_achievement_panel = null


func _on_difficulty() -> void:
	var cur: String = GameState.get_difficulty()
	var next: String
	match cur:
		GameState.DIFFICULTY_EASY:
			next = GameState.DIFFICULTY_NORMAL
		GameState.DIFFICULTY_HARD:
			next = GameState.DIFFICULTY_EASY
		_:
			next = GameState.DIFFICULTY_HARD
	GameState.set_difficulty(next)
	_refresh_difficulty_button()

func _refresh_difficulty_button() -> void:
	if _btn_difficulty:
		var label: String = GameState.get_difficulty_label()
		_btn_difficulty.text = "난이도: %s" % label
		match GameState.get_difficulty():
			GameState.DIFFICULTY_EASY:
				_btn_difficulty.add_theme_color_override("font_color", Color(0.55, 0.95, 0.65))
			GameState.DIFFICULTY_HARD:
				_btn_difficulty.add_theme_color_override("font_color", Color(1.0, 0.45, 0.45))
			_:
				_btn_difficulty.add_theme_color_override("font_color", Color(1.0, 0.92, 0.35))
