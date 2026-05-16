import os
from PIL import Image

def convert_to_true_png(source_path, dest_path):
    try:
        with Image.open(source_path) as img:
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            img.save(dest_path, format="PNG")
        print(f"Successfully converted and saved to: {dest_path}")
    except Exception as e:
        print(f"Error converting {source_path}: {e}")

files = [
    (r"C:\Users\User\.gemini\antigravity\brain\b5b530b9-3fc2-4f4e-a906-bfd2b5e2bc2b\concept_burger_1778551923051.png", "concept_burger.png"),
    (r"C:\Users\User\.gemini\antigravity\brain\b5b530b9-3fc2-4f4e-a906-bfd2b5e2bc2b\concept_cola_1778551941408.png", "concept_cola.png"),
    (r"C:\Users\User\.gemini\antigravity\brain\b5b530b9-3fc2-4f4e-a906-bfd2b5e2bc2b\concept_fries_1778551959327.png", "concept_fries.png"),
    (r"C:\Users\User\.gemini\antigravity\brain\b5b530b9-3fc2-4f4e-a906-bfd2b5e2bc2b\concept_boss_1778551973114.png", "concept_boss.png")
]

dest_dir = r"C:\Users\User\Documents\body-hero\work_images\reference"

for src, name in files:
    convert_to_true_png(src, os.path.join(dest_dir, name))
