from pathlib import Path

p = Path(__file__).resolve().parent / "process_idle_aseprite.py"
t = p.read_text(encoding="utf-8")
head = t[:2500]
if "Multiple .aseprite paths in order" in head:
    print("skip: already present")
    raise SystemExit(0)
a = '    p.add_argument(\n        "--out-dir",\n'
b = """    p.add_argument(
        "--from-aseprites",
        type=Path,
        nargs="+",
        default=None,
        help="Multiple .aseprite paths in order (all exported PNGs per file)",
    )
    p.add_argument(
        "--out-dir",
"""
if a not in t:
    raise SystemExit("anchor missing")
t = t.replace(a, b, 1)
p.write_text(t, encoding="utf-8")
print("inserted")
