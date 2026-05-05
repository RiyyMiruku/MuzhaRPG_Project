"""
Generate the test_dummy spritesheet + JSON fixture for SpriteSheetLoader smoke test.
Usage: uv run python scripts/create_dummy_character.py
"""
import json
from pathlib import Path

from PIL import Image

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHARS_DIR = PROJECT_ROOT / "game" / "assets" / "textures" / "characters"
CHARS_DIR.mkdir(parents=True, exist_ok=True)

PNG_OUT = CHARS_DIR / "test_dummy.png"
JSON_OUT = CHARS_DIR / "test_dummy.json"

# ---------------------------------------------------------------------------
# Spritesheet dimensions
# 4 frames wide × 2 rows tall, each cell 92×92
# ---------------------------------------------------------------------------
FRAME_W: int = 92
FRAME_H: int = 92
COLS: int = 4
ROWS: int = 2

IMG_W: int = FRAME_W * COLS   # 368
IMG_H: int = FRAME_H * ROWS   # 184

img = Image.new("RGBA", (IMG_W, IMG_H), (0, 0, 0, 0))

# Row 0 — idle_south: red shades varying by column
RED_BASE = [(200, 50, 50), (220, 80, 80), (240, 110, 110), (255, 140, 140)]
# Row 1 — idle_east: blue shades varying by column
BLUE_BASE = [(50, 50, 200), (80, 80, 220), (110, 110, 240), (140, 140, 255)]

for col in range(COLS):
    # Row 0 (idle_south)
    r, g, b = RED_BASE[col]
    for px in range(FRAME_W):
        for py in range(FRAME_H):
            img.putpixel((col * FRAME_W + px, py), (r, g, b, 255))

    # Row 1 (idle_east)
    r, g, b = BLUE_BASE[col]
    for px in range(FRAME_W):
        for py in range(FRAME_H):
            img.putpixel((col * FRAME_W + px, FRAME_H + py), (r, g, b, 255))

img.save(PNG_OUT, "PNG")

# ---------------------------------------------------------------------------
# JSON atlas config
# ---------------------------------------------------------------------------
config = {
    "character_name": "test_dummy",
    "frame_size": [FRAME_W, FRAME_H],
    "animations": {
        "idle_south": {"row": 0, "start": 0, "end": 4, "fps": 6.0, "loop": True},
        "idle_east":  {"row": 1, "start": 0, "end": 4, "fps": 6.0, "loop": True},
    },
}

JSON_OUT.write_text(json.dumps(config, indent=2), encoding="utf-8")

print(f"Created: {PNG_OUT}  ({PNG_OUT.stat().st_size} bytes)")
print(f"Created: {JSON_OUT}  ({JSON_OUT.stat().st_size} bytes)")
