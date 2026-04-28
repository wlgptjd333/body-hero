extends CanvasLayer
## 일시정지 오버레이. 트리가 paused일 때만 보이며, ESC로 재개할 수 있게 한다.
## (일시정지 중에는 Main._process가 멈춰서, ESC를 이 레이어에서 처리해야 함)

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS


func _input(event: InputEvent) -> void:
	if not get_tree().paused:
		return
	if not event.is_action_pressed("ui_cancel"):
		return
	var main: Node = get_parent()
	if main and main.has_method("_toggle_pause"):
		main._toggle_pause()
		get_viewport().set_input_as_handled()
