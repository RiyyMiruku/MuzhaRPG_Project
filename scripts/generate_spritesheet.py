"""
Generate a 6-column x 4-row RPG character sprite sheet using the PixelLab API.

Layout:
  Row 1: facing DOWN  — idle + 5 walk frames
  Row 2: facing RIGHT — idle + 5 walk frames
  Row 3: facing LEFT  — idle + 5 walk frames
  Row 4: facing UP    — idle + 5 walk frames

Usage:
  python generate_spritesheet.py --api-key YOUR_KEY --output path/to/output.png
"""

import argparse
import base64
import io
import json
import sys
import time
from pathlib import Path
from urllib import request, error

# pip install Pillow
from PIL import Image

API_BASE = "https://api.pixellab.ai/v1"
CELL_SIZE = 64  # each cell is 64x64 pixels

# Direction mapping for the API
DIRECTIONS = [
    {"name": "down",  "api_dir": "south", "row": 0},
    {"name": "right", "api_dir": "east",  "row": 1},
    {"name": "left",  "api_dir": "west",  "row": 2},
    {"name": "up",    "api_dir": "north", "row": 3},
]

CHARACTER_DESC = (
    "Middle-aged Taiwanese woman, late 40s, market vendor. "
    "Short permed black hair, floral blouse under a beige market apron. "
    "Slightly stout friendly build, warm smile. "
    "16-bit pixel art, top-down 2.5D RPG, warm color palette."
)


def api_call(endpoint: str, payload: dict, api_key: str, retries: int = 3) -> dict:
    """Make a POST request to the PixelLab API with retry logic."""
    url = f"{API_BASE}/{endpoint}"
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    req = request.Request(url, data=data, headers=headers, method="POST")

    for attempt in range(retries):
        try:
            with request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code == 429 and attempt < retries - 1:
                wait = 2 ** (attempt + 1)
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            print(f"HTTP {e.code}: {body}", file=sys.stderr)
            raise
        except error.URLError as e:
            if attempt < retries - 1:
                time.sleep(2)
                continue
            raise


def decode_image(b64_str: str) -> Image.Image:
    """Decode a base64 image string to a PIL Image."""
    # Strip data URI prefix if present
    if b64_str.startswith("data:"):
        b64_str = b64_str.split(",", 1)[1]
    # Fix padding
    missing = len(b64_str) % 4
    if missing:
        b64_str += "=" * (4 - missing)
    img_bytes = base64.b64decode(b64_str)
    return Image.open(io.BytesIO(img_bytes)).convert("RGBA")


def encode_image_b64(img: Image.Image) -> str:
    """Encode a PIL Image to a raw base64 string (no data URI prefix)."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def make_b64_image(img: Image.Image) -> dict:
    """Create a Base64Image dict for the API."""
    # API expects raw base64, no data URI prefix
    return {"type": "base64", "base64": encode_image_b64(img)}


def generate_base_character(api_key: str) -> Image.Image:
    """Generate the base character facing south (down)."""
    print("Step 1: Generating base character (facing south)...")
    payload = {
        "description": CHARACTER_DESC,
        "negative_description": "blurry, anti-aliased, smooth edges, 3D render, realistic, background, scenery",
        "image_size": {"width": CELL_SIZE, "height": CELL_SIZE},
        "text_guidance_scale": 10,
        "no_background": True,
        "view": "low top-down",
        "direction": "south",
    }
    resp = api_call("generate-image-pixflux", payload, api_key)
    b64_raw = resp["image"]["base64"]
    print(f"  Response image base64 starts with: {b64_raw[:80]}...")
    print(f"  Response image base64 length: {len(b64_raw)}")
    img = decode_image(b64_raw)
    # Verify our re-encoding produces valid base64
    test_b64 = encode_image_b64(img)
    print(f"  Re-encoded base64 length: {len(test_b64)}, mod4={len(test_b64) % 4}")
    cost = resp.get("usage", {}).get("usd", 0)
    print(f"  Done. Cost: ${cost:.4f}")
    return img


def rotate_character(base_img: Image.Image, from_dir: str, to_dir: str, api_key: str) -> Image.Image:
    """Rotate the character from one direction to another."""
    print(f"  Rotating {from_dir} -> {to_dir}...")
    payload = {
        "from_image": make_b64_image(base_img),
        "image_size": {"width": CELL_SIZE, "height": CELL_SIZE},
        "from_view": "low top-down",
        "to_view": "low top-down",
        "from_direction": from_dir,
        "to_direction": to_dir,
        "image_guidance_scale": 4.0,
    }
    resp = api_call("rotate", payload, api_key)
    img = decode_image(resp["image"]["base64"])
    cost = resp.get("usage", {}).get("usd", 0)
    print(f"    Done. Cost: ${cost:.4f}")
    return img


def animate_walk(ref_img: Image.Image, direction: str, api_key: str, n_frames: int = 5) -> list:
    """Generate walk animation frames for a given direction."""
    print(f"  Animating walk ({direction}, {n_frames} frames)...")
    payload = {
        "description": CHARACTER_DESC,
        "action": "walk",
        "image_size": {"width": CELL_SIZE, "height": CELL_SIZE},
        "reference_image": make_b64_image(ref_img),
        "negative_description": "standing still, idle, blurry, anti-aliased",
        "text_guidance_scale": 8.0,
        "image_guidance_scale": 2.0,
        "n_frames": n_frames,
        "view": "low top-down",
        "direction": direction,
    }
    resp = api_call("animate-with-text", payload, api_key)
    # Response may use "images" (array) or other keys
    if "images" in resp:
        frames = [decode_image(f["base64"]) for f in resp["images"]]
    elif "image" in resp:
        # Single image fallback — shouldn't happen but just in case
        frames = [decode_image(resp["image"]["base64"])]
    else:
        print(f"    Unexpected response keys: {list(resp.keys())}", file=sys.stderr)
        frames = []
    cost = resp.get("usage", {}).get("usd", 0)
    print(f"    Done. Got {len(frames)} frames. Cost: ${cost:.4f}")
    return frames


def build_spritesheet(idle_images: dict, walk_frames: dict) -> Image.Image:
    """Assemble the final 6x4 sprite sheet."""
    cols, rows = 6, 4
    sheet = Image.new("RGBA", (cols * CELL_SIZE, rows * CELL_SIZE), (0, 0, 0, 0))

    for d in DIRECTIONS:
        row = d["row"]
        name = d["name"]
        y = row * CELL_SIZE

        # Column 0: idle
        idle = idle_images[name].resize((CELL_SIZE, CELL_SIZE), Image.NEAREST)
        sheet.paste(idle, (0, y), idle)

        # Columns 1-5: walk frames
        frames = walk_frames[name]
        for i, frame in enumerate(frames[:5]):
            frame = frame.resize((CELL_SIZE, CELL_SIZE), Image.NEAREST)
            x = (i + 1) * CELL_SIZE
            sheet.paste(frame, (x, y), frame)

    return sheet


def main():
    parser = argparse.ArgumentParser(description="Generate RPG character sprite sheet via PixelLab API")
    parser.add_argument("--api-key", required=True, help="PixelLab API key")
    parser.add_argument("--output", default=None, help="Output PNG path")
    parser.add_argument("--cell-size", type=int, default=64, help="Cell size in pixels (default: 64)")
    args = parser.parse_args()

    global CELL_SIZE
    CELL_SIZE = args.cell_size

    if args.output is None:
        script_dir = Path(__file__).resolve().parent.parent
        args.output = str(script_dir / "game" / "assets" / "textures" / "characters" / "market_vendor.png")

    print(f"=== PixelLab Sprite Sheet Generator ===")
    print(f"Cell size: {CELL_SIZE}x{CELL_SIZE}")
    print(f"Output: {args.output}")
    print()

    # Step 1: Generate base character (south/down)
    base_img = generate_base_character(args.api_key)

    # Step 2: Get idle poses for all 4 directions
    print("\nStep 2: Generating idle poses for all directions...")
    idle_images = {"down": base_img}
    for d in DIRECTIONS:
        if d["api_dir"] == "south":
            continue
        idle_images[d["name"]] = rotate_character(base_img, "south", d["api_dir"], args.api_key)

    # Step 3: Animate walk cycles for each direction
    print("\nStep 3: Generating walk animations...")
    walk_frames = {}
    for d in DIRECTIONS:
        walk_frames[d["name"]] = animate_walk(idle_images[d["name"]], d["api_dir"], args.api_key, n_frames=5)

    # Step 4: Assemble sprite sheet
    print("\nStep 4: Assembling sprite sheet...")
    sheet = build_spritesheet(idle_images, walk_frames)

    # Save
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(str(out_path), "PNG")
    print(f"\nSprite sheet saved to: {out_path}")
    print(f"Dimensions: {sheet.width}x{sheet.height} ({sheet.width // CELL_SIZE} cols x {sheet.height // CELL_SIZE} rows)")
    print("Done!")


if __name__ == "__main__":
    main()
