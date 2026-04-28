extends Control
## 통계 패널: 가드·펀치(좌우)·어퍼(좌우) 누적 횟수 표시

signal back_pressed

# GameState.STATS_KEYS 순서와 동일: guard, punch_l, punch_r, upper_l, upper_r
const DISPLAY_NAMES := {
	"guard": "가드",
	"punch_l": "왼손 펀치",
	"punch_r": "오른손 펀치",
	"upper_l": "왼손 어퍼컷",
	"upper_r": "오른손 어퍼컷",
}

@onready var _back_btn: Button = $Panel/VBox/BackButton
@onready var _stats_list: VBoxContainer = $Panel/VBox/Scroll/ScrollInner/StatsList
@onready var _daily_chart: Control = $Panel/VBox/Scroll/ScrollInner/DailyChart
@onready var _weight_spin: SpinBox = $Panel/VBox/Scroll/ScrollInner/WeightRow/WeightSpin
@onready var _weight_save_btn: Button = $Panel/VBox/Scroll/ScrollInner/WeightRow/WeightSaveButton
@onready var _weight_chart: Control = $Panel/VBox/Scroll/ScrollInner/WeightChart


func _ready() -> void:
	if _back_btn:
		_back_btn.pressed.connect(_on_back)
	if _weight_save_btn:
		_weight_save_btn.pressed.connect(_on_weight_save_pressed)
	_refresh_stats()


func _refresh_stats() -> void:
	if not _stats_list:
		return
	# 기존 라벨 제거 후 다시 생성 (씬에 고정 라벨이 있으면 그걸 쓰고, 없으면 동적 생성)
	for c in _stats_list.get_children():
		c.queue_free()
	for key in GameState.STATS_KEYS:
		var name_str: String = DISPLAY_NAMES.get(key, key)
		var count: int = GameState.get_punch_count(key)
		var lbl := Label.new()
		lbl.text = "%s: %d번" % [name_str, count]
		lbl.add_theme_font_size_override("font_size", 18)
		_stats_list.add_child(lbl)
	_refresh_time_attack_section()
	_refresh_daily_chart()
	_refresh_weight_ui()


func _add_stats_row(text: String, font_size: int = 16) -> void:
	var row := Label.new()
	row.text = text
	row.add_theme_font_size_override("font_size", font_size)
	row.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_stats_list.add_child(row)


func _refresh_time_attack_section() -> void:
	if not _stats_list:
		return
	var sep := HSeparator.new()
	_stats_list.add_child(sep)
	var title := Label.new()
	title.text = "타임어택 (스테이지 클리어)"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.add_theme_font_size_override("font_size", 19)
	_stats_list.add_child(title)
	var best: float = GameState.get_best_stage_clear_sec()
	var last: float = GameState.get_last_stage_clear_sec()
	_add_stats_row("최고 기록: %s" % GameState.format_stage_clear_time(best), 17)
	_add_stats_row("직전 클리어: %s" % GameState.format_stage_clear_time(last), 17)
	if best >= 0.0 and last >= 0.0:
		var diff: float = last - best
		if diff <= 0.001:
			_add_stats_row("최고 기록 대비: 신기록 또는 동일", 16)
		else:
			_add_stats_row("최고 기록 대비: +%.2f초 (더 느림)" % diff, 16)
	var hist: Array[float] = GameState.get_stage_clear_history()
	if hist.is_empty():
		_add_stats_row("클리어 기록이 없으면 KO 후 여기에 쌓입니다.", 15)
	else:
		_add_stats_row("최근 기록 (최신 순, 비교는 최고 기록 기준):", 16)
		var n: int = mini(10, hist.size())
		for i: int in range(n):
			var t: float = hist[i]
			var line: String = "  %d. %s" % [i + 1, GameState.format_stage_clear_time(t)]
			if best >= 0.0:
				var d: float = t - best
				if absf(d) < 0.02:
					line += " · 최고"
				elif d > 0.0:
					line += " · +%.2f초" % d
			_add_stats_row(line, 15)


func _refresh_daily_chart() -> void:
	if not _daily_chart:
		return
	var points: Array[Dictionary] = GameState.get_recent_daily_calories(30)
	if _daily_chart.has_method("set_points"):
		_daily_chart.set_points(points)


func _refresh_weight_ui() -> void:
	if _weight_spin:
		var logged: float = GameState.get_today_logged_weight_kg()
		if logged > 0.0:
			_weight_spin.value = logged
		else:
			_weight_spin.value = GameState.get_weight_kg()
	if _weight_chart and _weight_chart.has_method("set_points"):
		var wpoints: Array[Dictionary] = GameState.get_recent_daily_weight_log(30)
		_weight_chart.set_points(wpoints, {
			"value_key": "weight",
			"suffix": "kg",
			"color": Color(0.35, 0.75, 0.95, 0.95),
			"zero_based": false,
		})


func _on_weight_save_pressed() -> void:
	if not _weight_spin:
		return
	GameState.log_today_weight_kg(float(_weight_spin.value))
	_refresh_weight_ui()


func _on_back() -> void:
	back_pressed.emit()
