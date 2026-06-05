=====================================================================
  Body Hero (v1.1.0) — 설치 및 사용 가이드
=====================================================================

ZIP을 푼 후 게임을 실행하고, 웹캠 ML을 사용하며,
필요시 직접 데이터를 수집·학습하는 방법을 담고 있습니다.


---------------------------------------------------------------------
1. 시스템 요구사항
---------------------------------------------------------------------

  OS        : Windows 10 / 11 (64비트)
  CPU       : Intel Core i5-8세대 이상 (웹캠 ML 사용 시 권장)
  RAM       : 8 GB 이상 권장
  GPU       : 없어도 됨 (CPU 전용 모드 기본)
  웹캠      : USB 웹캠 또는 노트북 내장 웹캠 (선택)
  저장공간  : 약 2 GB (압축 해제 시)

  ※ 웹캠이 없어도 키보드로 게임 플레이는 완전히 가능합니다.


---------------------------------------------------------------------
2. 설치 방법
---------------------------------------------------------------------

  1) 이 ZIP 파일을 원하는 폴더에 압축 해제하세요.
     (예: C:\Games\BodyHero\)

  2) 끝입니다. 별도 설치가 필요 없습니다.


---------------------------------------------------------------------
3. 게임 실행
---------------------------------------------------------------------

  압축 해제한 폴더에서 "Body Hero.exe"를 더블클릭하세요.

  ※ 첫 실행 시 Windows Defender가 차단할 수 있습니다.
     "추가 정보"를 클릭한 뒤 "실행"을 눌러주세요.
     (파일 우클릭 → 속성 → "차단 해제" 체크도 가능)


---------------------------------------------------------------------
4. 키보드 조작법
---------------------------------------------------------------------

  키보드만으로도 게임을 완벽하게 즐길 수 있습니다.

    A 또는 Z        : 왼손 펀치 (Punch Left)
    D 또는 C        : 오른손 펀치 (Punch Right)
    Q               : 왼손 어퍼컷 (Upper Left)
    E               : 오른손 어퍼컷 (Upper Right)
    Space           : 가드 (Guard) — 누르는 동안 유지
    S               : 스쿼트 (Squat) — HP 회복

  ※ 키 리바인딩: 게임 내 설정 메뉴에서 변경 가능


---------------------------------------------------------------------
5. 웹캠 ML (동작 인식) 사용법
---------------------------------------------------------------------

  웹캠을 켜고 실제로 주먹을 뻗으면 화면 속 글러브가 따라 움직입니다.

  5-1. 기본 설정
  ----------------
    1) 게임 실행 → [메인 메뉴] → [설정]
    2) [웹캠] 탭 클릭
    3) [카메라 목록 새로고침] 버튼 클릭
       → 사용 가능한 웹캠 목록이 표시됩니다.
    4) 목록에서 원하는 웹캠을 선택
    5) [적용] 버튼 클릭
    6) 스테이지에 진입하면 웹캠 ML이 자동 실행됩니다.
       (화면 왼쪽 아래에 웹캠 화면이 표시됩니다.)

  5-2. 목록에 웹캠이 안 뜰 때
  ----------------
    - [카메라 목록 새로고침]을 2~3회 다시 클릭해보세요.
    - [카메라 백엔드]를 변경 후 새로고침:
        auto (기본) → dshow → msmf → default
    - 외장 웹캠을 연결한 직후라면 5~10초 기다렸다 새로고침하세요.

  5-3. 외장 웹캠 연결 후 인식이 안 될 때
  ----------------
    - 내장 웹캠이 인덱스 0, 외장 웹캠이 인덱스 1인 경우가 많습니다.
    - [카메라 인덱스]를 0, 1, 2 순서로 하나씩 시도해보세요.

  5-4. ML 속도 프로필 선택
  ----------------
    설정의 [웹캠] 탭에서 선택할 수 있습니다:

      정밀 (precise)       : 정확도 우선. 반응은 약간 느리지만 오인식 최소화
      균형 (balanced)      : 기본값. 정확도와 반응 속도의 균형
      신속 (rapid)         : 빠른 연타에 최적화
      최고 속도 (max_speed): 최고의 반응 속도 (오인식 위험 약간 증가)

  5-5. 웹캠 ML이 자동으로 안 켜질 때
  ----------------
    1) cmd(명령 프롬프트)를 열고 tools 폴더로 이동:
         cd C:\Games\BodyHero\tools
         (실제 압축 해제 경로로 바꾸세요)
    2) 수동 실행:
         run_python.bat udp_send_webcam_ml.py --camera-index 0 --profile balanced
    3) 콘솔에 표시되는 에러 메시지를 확인하세요.


---------------------------------------------------------------------
6. 개발자 및 학습자용 가이드
---------------------------------------------------------------------

  직접 포즈 데이터를 수집하거나, 새로 학습한 모델을
  게임에 적용하려는 사용자를 위한 내용입니다.

  6-1. 폴더 구조
  ----------------
    BodyHero/
    ├── Body Hero.exe                  ← Godot 게임 실행 파일
    ├── README.txt                     ← 이 파일
    └── tools/
        ├── run_python.bat             ← Python 헬퍼
        ├── python_embed/              ← Python 3.10 + TensorFlow + MediaPipe
        │   └── python.exe             ← Python 실행 파일
        ├── udp_send_webcam_ml.py      ← 웹캠 ML 브리지 (게임 연동)
        ├── collect_pose_data.py       ← 포즈 데이터 수집기
        ├── train_pose_classifier_seq.py  ← 4프레임 모델 학습
        ├── cv_capture.py              ← 웹캠 캡처 유틸리티
        ├── pose_normalize.py            ← 랜드마크 정규화
        ├── pose_class_names.py        ← 동작 클래스 정의
        ├── pose_classifier_seq_len4.keras  ← 현재 게임에 탑재된 ML 모델
        └── pose_classifier.keras      ← 가드 폴백용 보조 모델

  6-2. Python 환경
  ----------------
    본 게임에는 Python 임베디드 환경이 포함되어 있습니다.
    따로 Python을 설치하거나 PATH를 설정할 필요가 없습니다.

    모든 Python 명령은 run_python.bat를 통해 실행하세요:

      cd tools
      run_python.bat [스크립트명] [옵션]

    예시:
      run_python.bat collect_pose_data.py
      run_python.bat train_pose_classifier_seq.py

  6-3. 포즈 데이터 수집
  ----------------
      cd tools
      run_python.bat collect_pose_data.py

    실행 후 화면 안내에 따라:
      - 웹캠 앞에서 동작을 취합니다.
      - 키보드 숫자 키로 라벨을 지정합니다.
          1=none(대기)  2=guard(가드)  3=punch_l  4=punch_r
          5=upper_l     6=upper_r      7=squat
      - Q를 누르면 종료합니다.

    결과물:
      tools/pose_data.json              ← 수집된 랜드마크 데이터
      tools/pose_recordings_meta.json   ← 녹화 구간 정보

  6-4. 모델 학습
  ----------------
      cd tools
      run_python.bat train_pose_classifier_seq.py

    학습 완료 후 생성되는 파일:
      tools/pose_classifier_seq_len4.keras

    게임을 재시작하면 새 모델이 적용됩니다.

  6-5. 학습 결과 검증
  ----------------
      cd tools
      run_python.bat validate_recording_holdout.py

    결과:
      tools/classification_report_seq_holdout.txt

  6-6. 웹캠 ML 단독 테스트 (게임 없이)
  ----------------
      cd tools
      run_python.bat udp_send_webcam_ml.py --headless --profile balanced

    옵션:
      --camera-index N        : 카메라 인덱스 (기본 0)
      --camera-backend NAME   : 백엔드 (auto/dshow/msmf/default)
      --profile NAME          : 프로필 (precise/balanced/rapid/max_speed)
      --headless              : 미리보기 창 없이 실행
      --debug-topk 5          : 상위 5개 예측 확률 표시
      --punch-confidence 0.7  : 펀치 인식 확률 하한


---------------------------------------------------------------------
7. 고급 설정
---------------------------------------------------------------------

  7-1. ML 브리지 커맨드 라인 옵션
  ----------------
    udp_send_webcam_ml.py 전체 옵션:

      --camera-index 0          : 웹캠 인덱스
      --camera-backend auto     : 백엔드 (auto/dshow/msmf/default)
      --process-w 480           : 처리 너비
      --process-h 360           : 처리 높이
      --profile balanced        : 속도/정확도 프로필
      --gpu                     : MediaPipe GPU 가속 (기본 CPU)
      --full-model              : 정확도 높은 Full 모델 (기본 Lite)
      --roi                     : ROI 모드 (혼잡한 환경용)
      --debug-topk 5            : 상위 K개 예측 확률 표시
      --punch-confidence 0.85   : 펀치 최소 확률
      --skip-guard-single       : 가드 단일 프레임 단축 비활성화
      --full-body-squat         : 전신 스쿼트 판정 (하체 인식 필요)
      --upper-windup-punch-suppress : 어퍼 윈드업 시 직선 펀치 억제
      --attack-rearm-frames 3   : 공격 재장전 프레임

    예시 (전시회):
      run_python.bat udp_send_webcam_ml.py --roi --profile precise --camera-backend dshow

  7-2. 저사양 노트북 튜닝
  ----------------
    tools/udp_send_webcam_ml.py 파일을 메모장으로 열어
    78행을 다음과 같이 수정하세요:

      PROCESS_W, PROCESS_H = 320, 240  ← 기존 480, 360에서 변경
      PROCESS_EVERY_N_FRAMES = 2         ← 기본 1에서 변경 (15 FPS 처리)

    해상도를 낮추면 CPU 부하가 크게 줄어듭니다.


---------------------------------------------------------------------
8. 문제 해결 (Troubleshooting)
---------------------------------------------------------------------

  Q: 게임이 안 켜져요.
  A: Windows Defender가 차단했을 수 있습니다.
     "추가 정보"를 클릭한 뒤 "실행"을 누르세요.
     또는 Body Hero.exe 우클릭 → 속성 → "차단 해제" 체크.

  Q: 웹캠이 설정 목록에 안 떠요.
  A: [카메라 목록 새로고침] 버튼을 2~3회 클릭하세요.
     외장 웹캠을 방금 연결했다면 5~10초 기다렸다 새로고침하세요.
     [카메라 백엔드]를 auto → dshow → msmf → default 순으로 바꿔보세요.

  Q: 웹캠 ML이 켜지지 않아요.
  A: run_python.bat를 사용해 수동으로 실행해보세요:
       cd tools
       run_python.bat udp_send_webcam_ml.py --camera-index 0
     콘솔에 표시되는 에러 메시지를 확인하세요.

  Q: Python 명령어가 안 먹어요.
  A: 본 게임은 시스템 Python이 필요 없습니다.
     반드시 run_python.bat를 사용하세요.
       run_python.bat collect_pose_data.py

  Q: 웹캠 화면이 안 보여요.
  A: 웹캠 ML은 별도 Python 프로세스가 실행되며, 첫 로딩에 10~30초 걸립니다.
     키보드로 플레이하면서 기다리세요. 화면 왼쪽 아래에 웹캠 화면이 나타납니다.
     계속 안 보이면 run_python.bat로 수동 실행해보세요.

  Q: 실행 중 튕겨요.
  A: 그래픽 드라이버를 최신 버전으로 업데이트하세요.
     내장 그래픽(Intel HD) 사용 시 Windows 업데이트를 확인하세요.


---------------------------------------------------------------------
9. 프로젝트 정보
---------------------------------------------------------------------

  Body Hero
  웹캠 기반 1인칭 헬스 복싱 게임

  게임 엔진     : Godot Engine 4.6
  스크립트      : GDScript 2.0
  ML 프레임워크 : Python 3.10 + TensorFlow/Keras
  포즈 추정     : MediaPipe Pose
  통신          : UDP (localhost)
  아키텍처      : Conv1D(64, k=3) → GAP → Dense(7)
  모델 파라미터 : 19,783개
  정확도        : 99.22% (recording-based holdout 20%)

  GitHub        : https://github.com/wlgptjd333/body-hero
  라이선스      : MIT License © 2026 JiHyesung

  ※ 협성대학교 졸업작품으로 제작되었습니다.

=====================================================================
