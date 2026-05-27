# Body Hero

웹캠 1인칭 헬스 복싱 게임 (Godot 4.6) — Punch your screen to fight! Real-time body tracking with webcam.

> 이전 버전의 **잽(jab)/훅(hook)** 은 `punch_l`/`punch_r`로 통합되었습니다.  
> 레거시 migration 스크립트(`scratch/`) 및 오래된 데이터 백업은 정리되었습니다.

## 빠른 시작

```bash
git clone https://github.com/wlgptjd333/body-hero.git
```

Godot 4.6으로 `project.godot` 열고 **F5** 실행.
- 첫 실행 시 `tools/python_embed/`가 없으면 GitHub Releases에서 자동 다운로드 + 설치합니다.
- 인터넷이 없는 환경에서는 `tools/python_ml_env.zip`을 직접 `tools/` 폴더에 넣으면 오프라인 설치 가능합니다.

## 프로젝트 구조

```
body-hero/
├── project.godot           # Godot 4.6 프로젝트
├── games/boxing/           # 메인 게임
│   ├── scenes/             #   스테이지 1~3, training
│   │   ├── stage_1.tscn
│   │   ├── stage_2.tscn
│   │   ├── stage_3.tscn
│   │   └── training.tscn
│   └── scripts/            #   게임 로직
│       ├── enemy.gd        #   적 FSM (IDLE/ATTACK/EVADE/HIT/DEAD)
│       ├── player.gd       #   플레이어 글러브 + 입력
│       ├── stage.gd        #   스테이지 컨트롤러
│       └── combat_director.gd  # 전투 판정/콤보
├── scripts/
│   ├── game_state.gd       # 전역 상태 (AutoLoad)
│   ├── game_state/         #   하위 모듈
│   │   ├── workout_tracker.gd
│   │   ├── upgrade_system.gd
│   │   ├── achievements.gd
│   │   ├── shop.gd
│   │   └── ...
│   └── ui/                 # UI 패널
│       ├── settings_panel.gd
│       ├── shop_panel.gd
│       └── ui_theme_helper.gd
├── tools/
│   ├── build_python_embed.bat     # 개발자 전용: 임베디드 Python 빌드
│   ├── collect_pose_data.py       # 웹캠 데이터 수집
│   ├── train_pose_classifier_seq.py  # 시퀀스 ML 학습
│   ├── udp_send_webcam_ml.py      # 게임-웹캠 브리지
│   ├── pose_server.py             # ML 서버
│   ├── pose_data.json             # 수집된 포즈 데이터
│   └── *.keras                    # 학습된 ML 모델
├── tests/
│   └── unit/
│       ├── test_enemy_fsm.gd      # FSM 단위 테스트 (23개)
│       └── test_game_state.gd     # GameState 테스트 (36개)
└── assets/
    ├── textures/characters/enemies/  # 버거/콜라/프라이즈 스프라이트
    ├── audio/bgm/                    # BGM
    └── audio/sfx/                    # 효과음
```

## 게임 플레이

### 웹캠 ML (권장)
```bash
cd tools
python_embed\python.exe udp_send_webcam_ml.py
```
Godot 메뉴 → 설정 → 웹캠 탭에서 카메라 설정 후 **적용**하면 스테이지 진입 시 자동 실행됩니다.
게임 내부에서 자동 실행되므로 직접 실행할 필요는 없습니다.

### 키보드 테스트
- **A/D** — 왼/오 펀치
- **Q/E** — 왼/오 어퍼컷
- **스페이스** — 가드 (누르는 동안)
- **S** — 스쿼트 (HP 회복)

## ML 데이터 수집 → 학습

```bash
cd tools
python_embed\python.exe collect_pose_data.py          # 데이터 수집
python_embed\python.exe train_pose_classifier_seq.py  # 4프레임 시퀀스 모델 학습
python_embed\python.exe pose_server.py                # ML 서버 실행
```

개발자 참고: `tools/build_python_embed.bat`로 python_embed 환경을 빌드한 후 위 명령을 실행하세요.

## 테스트

GUT 테스트 프레임워크 (59개, Godot 4.6):
```
프로젝트 → Gut → Run all tests
# 또는 WSL CLI:
~/.local/bin/godot --headless -s addons/gut/gut_cmdln.gd -d --path .
```

## 기술 스택

| 항목 | 버전 |
|------|------|
| Godot Engine | 4.6.2 |
| GDScript | 2.0 |
| Python | 3.10 |
| TensorFlow/Keras | 2.16+ |
| MediaPipe | 0.10+ |

