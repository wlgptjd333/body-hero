from pathlib import Path

p = Path(__file__).resolve().parent.parent / "games/boxing/scripts/player.gd"
lines = p.read_text(encoding="utf-8").splitlines()
for i, line in enumerate(lines):
    if line.startswith("## ") and "BodySprite" in line:
        lines[i] = (
            "## "
            "\uc67c\uc190 \uc7cd \ubab8\ud1b5 \uc5f0\ucd9c"
            "(BodySprite \ub178\ub4dc \uc5c6\uc73c\uba74 \uae00\ub7ec\ube0c\ub9cc \ub3d9\uc791)."
        )
        break
p.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("ok")
