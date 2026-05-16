# UDP Protocol Rules

## Input Modes

Two input modes exist:

### Coordinate Mode

Format:

```txt id="vljlwm"
left_x,left_y,right_x,right_y
```

Used for:

* pose estimation
* motion tracking
* punch direction analysis

Do NOT change this format from GDScript side.

---

### Action Mode

Supported actions:

```txt id="5gxlm2"
punch_l
punch_r
upper_l
upper_r
guard
guard_end
```

These strings are consumed by gameplay logic.

---

## InputMap Actions

Registered actions:

* `punch_left`
* `punch_right`
* `upper_left`
* `upper_right`
* `guard`
* `squat`

Never rename InputMap actions without updating all dependent scripts.

---

## Packet Processing Rules

### Duplicate Prevention

Multiple UDP packets may arrive in a single frame.

Rules:

* Keep `MAX_UDP_PER_FRAME` reasonably high
* Deduplication should happen in gameplay/input layer
* `player.gd` busy flags prevent same-hand overlap

### Punch Cooldowns

Cooldowns should remain near-zero.

Goal:

* preserve real human punching rhythm
* avoid dropped punch inputs

Avoid long hardcoded cooldowns like:

```gdscript id="xjlwmr"
0.35
```

unless explicitly intended.

---

## Separation of Responsibilities

### Python / ML Side (`tools/*.py`)

Responsible for:

* pose detection
* classification
* UDP packet generation
* protocol evolution

### Godot Side

Responsible for:

* consuming packets
* gameplay reactions
* animation triggering

Do not redesign protocol from GDScript side.
