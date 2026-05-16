# Body Hero — Domain Language

> Webcam-based first-person boxing game. Godot 4.6 + GDScript.

## Domain Concepts

**Stage (스테이지)**
A boxing match scenario with a specific enemy (Bulgogi Burger, Cola Monster, Fries Monster). Each stage has its own enemy config, background, and BGM.

**Player (플레이어)**
The user's avatar. Has HP, stamina, left/right gloves. Performs actions: punch, uppercut, guard, squat (HP regen).

**Enemy (적)**
AI opponent. Has HP, attack patterns, evade patterns. Can be a boss with phase transitions.

**Combat (전투)**
Resolution of player actions vs enemy state. Punch hits if enemy isn't evading. Damage is multiplied by combo.

**Guard (가드)**
Defensive stance. Reduces incoming damage. Has a minimum duration before release.

**Combo (콤보)**
Consecutive successful hits. Increases damage multiplier.

**Training (훈련장)**
Practice mode with infinite dummy respawn. No enemy attacks. Tracks action counts.

**HUD (헤드업 디스플레이)**
Game UI: HP/stamina bars, combo label, play time, training counters.

**Pause (일시정지)**
Overlay during gameplay. Resume, settings, quit options.

**Webcam ML Bridge (웹캠 ML 브릿지)**
Python process that captures webcam input and sends UDP packets (action strings or coordinate data).

**Boss Phase (보스 페이즈)**
HP threshold triggers phase transition. Player picks a buff before the phase starts.

## Architecture Roles

**GameState** — Global singleton. Owns all persistent state: HP/stamina, stats, achievements, shop, webcam ML lifecycle, difficulty, stage definitions.

**Stage** — Root node of a boxing scene. Owns UDP server, child nodes (Player, Enemy, CombatDirector, UIDirector, StageManager).

**CombatDirector** — Combat resolution logic: hit/miss, combo, win/loss, training kill count. Signal-based communication.

**UIDirector** — HUD updates, overlay visibility (game over, win, KO intro, achievement popups). No game logic.

**StageManager** — Stage setup: background fitting, audio loading, viewport management.

**HitImpactSystem** — AutoLoad singleton. Screen shake, hitstop, camera flash.
