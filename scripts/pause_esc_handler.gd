extends Node
## 일시정지 중에만 동작. ESC 입력 시 부모(Main)의 일시정지 해제를 호출한다.
## Main은 process_mode 기본값으로 두어, 트리가 일시정지되면 게임 로직이 멈추도록 함.

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
