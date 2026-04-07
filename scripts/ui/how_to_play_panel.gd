extends Control
## 단계별 튜토리얼: 웹캠 준비·조작·키보드·전투 팁

signal back_pressed

const _PAGES: Array[String] = [
	"""[center][b][font_size=22]Body Hero 튜토리얼[/font_size][/b][/center]

[b]이 게임은[/b]
웹캠으로 몸 동작을 인식하는 1인칭 복싱·피트니스 게임입니다. 적의 HP를 깎아 [b]KO[/b]하면 승리합니다.

[b]한 번에 익히기[/b]
아래 [b]다음[/b]을 눌러 준비 방법부터 순서대로 읽어 보세요.""",

	"""[b]1. 준비 순서[/b]

1) Godot에서 이 프로젝트를 실행합니다 (메인 메뉴가 보이면 OK).
2) 터미널에서 [code]tools/pose_server.py[/code]를 실행합니다 (ML 추론 서버).
3) 이어서 [code]tools/udp_send_webcam_ml.py[/code]를 실행합니다.

웹캠 화면이 뜨고, UDP로 게임에 동작이 전달됩니다. 자세한 명령은 [code]README.md[/code]를 참고하세요.

[b]팁[/b]
키보드만으로도 동작을 시험할 수 있습니다. 다음 페이지에서 키를 확인하세요.""",

	"""[b]2. 웹캠 동작 (ML 인식)[/b]

• [b]잽[/b]: 한 손을 앞으로 빠르게 뻗기
• [b]어퍼컷[/b]: 한 손을 위로 빠르게 올리기
• [b]훅[/b]: 옆으로 돌려 치는 동작 (모델·설정에 따라 다를 수 있음)
• [b]가드[/b]: 양손을 얼굴 앞에 모아 유지
• [b]회피[/b]: 몸을 좌우로 확실히 움직이기
• [b]제자리걸음[/b]: 어깨를 위아래로 요동 — 스태미너 회복에 도움이 됩니다

같은 펀치가 너무 자주 인식되지 않도록 게임·전송 쪽에 쿨타임이 있습니다.""",

	"""[b]3. 키보드 (테스트용)[/b]

프로젝트 설정의 Input Map 기준 기본 키입니다. [code]설정[/code]에서 바꿀 수 있습니다.

• [b]A[/b] 왼손 잽 · [b]D[/b] 오른손 잽
• [b]Q[/b] 왼 어퍼컷 · [b]E[/b] 오른 어퍼컷
• [b]Z[/b] 왼 훅 · [b]C[/b] 오른 훅
• [b]스페이스[/b] 가드 (누르고 있는 동안 유지, 떼면 해제)

[b]회피[/b]는 기본 키 매핑이 없으며, 웹캠(UDP)으로만 들어옵니다.""",

	"""[b]4. 링 안에서[/b]

• 화면 아래 [b]스태미너[/b]를 보고 펀치를 조절하세요. 바닥이면 가드·펀치가 막힐 수 있습니다.
• 적은 [b]회피[/b] 중일 때 펀치가 빗나갑니다. 타이밍을 보고 치세요.
• 우측 상단 아이콘으로 [b]일시정지[/b]할 수 있습니다. 일시정지 중 [b]Esc[/b]로 바로 재개됩니다.
• [b]통계[/b] 메뉴에서 운동량(칼로리 등)을 확인할 수 있습니다.

준비가 끝났으면 메뉴에서 [b]게임 시작[/b]으로 들어가 보세요!""",
]

@onready var _back_btn: Button = $Panel/VBox/BackButton
@onready var _content: RichTextLabel = $Panel/VBox/ScrollContainer/Content
@onready var _btn_prev: Button = $Panel/VBox/NavRow/BtnPrev
@onready var _btn_next: Button = $Panel/VBox/NavRow/BtnNext
@onready var _page_label: Label = $Panel/VBox/NavRow/PageLabel

var _page: int = 0


func _ready() -> void:
	if _back_btn:
		_back_btn.pressed.connect(_on_back)
	if _btn_prev:
		_btn_prev.pressed.connect(_on_prev)
	if _btn_next:
		_btn_next.pressed.connect(_on_next)
	_apply_page()


func _on_back() -> void:
	back_pressed.emit()


func _on_prev() -> void:
	if _page > 0:
		_page -= 1
		_apply_page()


func _on_next() -> void:
	if _page < _PAGES.size() - 1:
		_page += 1
		_apply_page()


func _apply_page() -> void:
	if _content:
		_content.text = _PAGES[_page]
	if _page_label:
		_page_label.text = "%d / %d" % [_page + 1, _PAGES.size()]
	if _btn_prev:
		_btn_prev.disabled = _page <= 0
	if _btn_next:
		_btn_next.disabled = _page >= _PAGES.size() - 1
