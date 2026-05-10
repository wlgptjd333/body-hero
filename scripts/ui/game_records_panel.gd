extends Control
## 게임 기록 패널: 펀치 횟수, 타임어택, 별, 업적 요약

signal back_pressed

@onready var _back_btn: Button = $Panel/VBox/BackButton
@onready var _records_list: VBoxContainer = $Panel/VBox/Scroll/ScrollInner/RecordsList

var _label_pool: Array[Label] = []
var _sep_pool: Array[HSeparator] = []

# GameState.STATS_KEYS 순서와 동일: guard, punch_l, punch_r, upper_l, upper_r
const DISPLAY_NAMES := {
	"guard": "가드",
	"punch_l": "왼손 펀치",
	"punch_r": "오른손 펀치",
	"upper_l": "왼손 어퍼컷",
	"upper_r": "오른손 어퍼컷",
}


func _ready() -> void:
	if _back_btn:
		_back_btn.pressed.connect(_on_back)
		UIThemeHelper.style_button_secondary(_back_btn)

	# 패널과 배경 스타일
	var panel: Panel = $Panel
	if panel:
		UIThemeHelper.style_panel_glass(panel)
	var title: Label = $Panel/VBox/TitleLabel
	if title:
		UIThemeHelper.style_label_title(title)

	_refresh_all()


func _refresh_all() -> void:
	if not _records_list:
		return
	var li: int = 0
	var si: int = 0

	# 1) 액션 누적
	li = _set_header(li, "누적 액션", si)
	si += 1
	for key: String in GameState.STATS_KEYS:
		var name_str: String = DISPLAY_NAMES.get(key, key)
		var count: int = GameState.get_punch_count(key)
		li = _set_label(li, "%s: %d회" % [name_str, count], 16)

	# 2) 타임어택
	li = _set_header(li, "타임어택", si)
	si += 1
	var best: float = GameState.get_best_stage_clear_sec()
	var last: float = GameState.get_last_stage_clear_sec()
	li = _set_label(li, "최고 기록: %s" % GameState.format_stage_clear_time(best), 16)
	li = _set_label(li, "직전 클리어: %s" % GameState.format_stage_clear_time(last), 16)
	var hist: Array[float] = GameState.get_stage_clear_history()
	if hist.is_empty():
		li = _set_label(li, "클리어 기록이 없습니다. 스테이지를 클리어해 보세요!", 14)
	else:
		li = _set_label(li, "최근 기록 (최신 순):", 15)
		var n: int = mini(10, hist.size())
		for i: int in range(n):
			var t: float = hist[i]
			var line: String = "  %d. %s" % [i + 1, GameState.format_stage_clear_time(t)]
			if best >= 0.0 and absf(t - best) < 0.02:
				line += "  ★ 최고"
			li = _set_label(li, line, 14)

	# 3) 스테이지 별
	li = _set_header(li, "스테이지 별", si)
	si += 1
	var stars: Dictionary = GameState.get_all_stage_stars()
	if stars.is_empty():
		li = _set_label(li, "아직 클리어한 스테이지가 없습니다.", 14)
	else:
		for sid: String in stars.keys():
			var s: int = stars[sid]
			var star_str: String = ""
			for i in range(3):
				star_str += "★" if i < s else "☆"
			li = _set_label(li, "  %s: %s" % [sid, star_str], 16)

	# 4) 업적 요약
	li = _set_header(li, "업적", si)
	si += 1
	var defs: Dictionary = GameState.get_achievement_defs()
	var total: int = defs.size()
	var unlocked: int = 0
	for id: String in defs.keys():
		if GameState.is_achievement_unlocked(id):
			unlocked += 1
	li = _set_label(li, "달성: %d / %d" % [unlocked, total], 16)
	for id: String in defs.keys():
		var def: Dictionary = defs[id]
		var is_unlocked: bool = GameState.is_achievement_unlocked(id)
		var icon: String = "🏆" if is_unlocked else "🔒"
		var progress: int = GameState.get_achievement_progress(id)
		var target: int = int(def.get("target", 1))
		li = _set_label(li, "  %s %s (%d/%d)" % [icon, str(def.get("title", id)), progress, target], 14)

	# 사용하지 않는 풀 항목 숨김
	for i: int in range(li, _label_pool.size()):
		_label_pool[i].visible = false
	for i: int in range(si, _sep_pool.size()):
		_sep_pool[i].visible = false


func _set_header(li: int, title: String, si: int) -> int:
	var sep: HSeparator = _get_sep(si)
	sep.visible = true
	var lbl: Label = _get_label(li)
	lbl.text = title
	lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	lbl.add_theme_font_size_override("font_size", 18)
	lbl.add_theme_color_override("font_color", Color(0.95, 0.92, 0.85))
	lbl.visible = true
	return li + 1


func _set_label(idx: int, text: String, font_size: int) -> int:
	var lbl: Label = _get_label(idx)
	lbl.text = text
	lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
	lbl.add_theme_font_size_override("font_size", font_size)
	lbl.add_theme_color_override("font_color", Color(0.88, 0.88, 0.92))
	lbl.visible = true
	return idx + 1


func _get_label(idx: int) -> Label:
	if idx < _label_pool.size():
		return _label_pool[idx]
	var lbl := Label.new()
	lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_records_list.add_child(lbl)
	_label_pool.append(lbl)
	return lbl


func _get_sep(idx: int) -> HSeparator:
	if idx < _sep_pool.size():
		return _sep_pool[idx]
	var sep := HSeparator.new()
	_records_list.add_child(sep)
	_sep_pool.append(sep)
	return sep


func _on_back() -> void:
	back_pressed.emit()
