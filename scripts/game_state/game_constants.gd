## 게임 밸런스 상수 — 모든 기본값의 단일 진실 공급원(Single Source of Truth).
## 값을 바꾸려면 이 파일만 수정하면 됩니다.
## 다른 파일에서 사용: `const C = preload("res://scripts/game_state/game_constants.gd")`

# --- 플레이어 기본 스탯 ---
const BASE_PLAYER_MAX_HP := 200.0
const BASE_STAMINA_MAX := 100.0
const BASE_STAMINA_PASSIVE_RECOVER := 10.0

# --- 업그레이드 ---
const UPGRADE_HP_PER_STEP := 5.0
const UPGRADE_STAMINA_PER_STEP := 5.0
const UPGRADE_RECOVER_PER_STEP := 0.5
const UPGRADE_MAX_STEPS := 20

# --- 스태미너 소모량 ---
const STAMINA_PUNCH := 5
const STAMINA_UPPERCUT := 10
const STAMINA_SQUAT := 5

# --- 칼로리 추정치 ---
const KCAL_PUNCH := 0.42
const KCAL_UPPERCUT := 0.55
const KCAL_SQUAT := 0.30
const KCAL_GUARD_PER_SEC := 0.06

# --- 칼로리 목표 기본값 ---
const DEFAULT_KCAL_GOAL := 300.0
