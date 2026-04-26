#!/usr/bin/env python3
"""
動態生成 Spritesheet - 將序列圖合成單一大圖
用於 Godot 遊戲引擎的性能優化

使用方法:
    python scripts/generate_spritesheet.py
    （無參數時使用專案預設路徑：art_source/characters/ -> game/assets/spritesheet_cache/）

或自訂：
    python scripts/generate_spritesheet.py --input <src> --output <dst>
"""

import json
import os
import sys
from pathlib import Path
from PIL import Image
import argparse


class SpritesheetGenerator:
    """從 metadata.json 生成 Spritesheet"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.frame_size = (92, 92)  # 標準幀尺寸

    def log(self, msg: str):
        if self.verbose:
            print(f"[INFO] {msg}")

    def error(self, msg: str):
        print(f"[ERROR] {msg}", file=sys.stderr)

    def process_character(self, character_dir: Path, output_dir: Path) -> dict:
        """
        處理單個角色
        返回：{
            "name": "player",
            "image_path": "player.png",
            "animations": {...},
            "success": bool
        }
        """
        metadata_path = character_dir / "metadata.json"
        if not metadata_path.exists():
            self.error(f"metadata.json not found: {metadata_path}")
            return {"success": False}

        # 讀 metadata
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        char_name = character_dir.name
        frames_data = metadata.get("frames", {})
        animations = frames_data.get("animations", {})
        rotations = frames_data.get("rotations", {})

        if not animations:
            self.error(f"No animations found for {char_name}")
            return {"success": False}

        self.log(f"Processing {char_name}...")

        # 收集所有 (動畫, 方向) 的幀序列
        rows = []  # [(anim_name, direction, frame_list), ...]
        animation_index = {}  # {(anim_name, direction): row_num}

        row_num = 0
        max_frame_count = 0

        # 動畫優先順序（idle 在前）
        sorted_anims = sorted(
            animations.items(),
            key=lambda x: (not x[0].lower().startswith("idle"), x[0])
        )

        for anim_name, anim_data in sorted_anims:
            # 使用 metadata 中實際的方向順序（即先定義的順序）
            # 以確保 row 號與原始動畫目錄對應
            direction_order = [d for d in anim_data.keys() if d in ["north", "south", "east", "west"]]
            for direction in direction_order:
                frame_paths = anim_data[direction]
                # 轉為絕對路徑
                full_frame_paths = [str(character_dir / p) for p in frame_paths]

                rows.append((anim_name, direction, full_frame_paths))
                animation_index[(anim_name, direction)] = row_num
                row_num += 1
                max_frame_count = max(max_frame_count, len(frame_paths))

        if not rows:
            self.error(f"No valid row sequences for {char_name}")
            return {"success": False}

        # 創建 Spritesheet
        # 尺寸：寬度 = max_frame_count × frame_width，高度 = row_count × frame_height
        width = max_frame_count * self.frame_size[0]
        height = len(rows) * self.frame_size[1]

        self.log(f"  Spritesheet size: {width}x{height} ({len(rows)} rows × {max_frame_count} columns)")

        # 建立 RGBA 圖片
        spritesheet = Image.new("RGBA", (width, height), (0, 0, 0, 0))

        # 填入幀
        for row_idx, (anim_name, direction, frame_paths) in enumerate(rows):
            for col_idx, frame_path in enumerate(frame_paths):
                if not os.path.exists(frame_path):
                    self.error(f"  Frame not found: {frame_path}")
                    continue

                try:
                    frame = Image.open(frame_path).convert("RGBA")
                    # 貼到 Spritesheet
                    x = col_idx * self.frame_size[0]
                    y = row_idx * self.frame_size[1]
                    spritesheet.paste(frame, (x, y))
                except Exception as e:
                    self.error(f"  Failed to load frame {frame_path}: {e}")

        # 儲存 Spritesheet
        output_dir.mkdir(parents=True, exist_ok=True)
        image_path = output_dir / f"{char_name}.png"
        spritesheet.save(image_path, "PNG", compress_level=6)
        self.log(f"  Saved: {image_path}")

        # 生成 Atlas 配置
        atlas_config = {
            "character_name": char_name,
            "frame_size": list(self.frame_size),
            "animations": {}
        }

        for (anim_name, direction), row_idx in animation_index.items():
            frame_count = len(rows[row_idx][2])
            key = f"{self._sanitize(anim_name)}_{direction}"

            atlas_config["animations"][key] = {
                "row": row_idx,
                "start": 0,
                "end": frame_count,
                "fps": 6.0,
                "loop": True,
            }

        return {
            "success": True,
            "name": char_name,
            "image": str(image_path.name),
            "config": atlas_config,
        }

    def process_all_characters(self, input_dir: Path, output_dir: Path) -> dict:
        """處理所有角色"""
        results = {
            "version": "1.0",
            "characters": {},
            "summary": {"successful": 0, "failed": 0},
        }

        if not input_dir.exists():
            self.error(f"Input directory not found: {input_dir}")
            return results

        # 掃描所有角色資料夾
        for char_dir in sorted(input_dir.iterdir()):
            if not char_dir.is_dir() or char_dir.name.startswith("."):
                continue

            result = self.process_character(char_dir, output_dir)
            if result["success"]:
                results["characters"][result["name"]] = result["config"]
                results["summary"]["successful"] += 1
            else:
                results["summary"]["failed"] += 1

        return results

    @staticmethod
    def _sanitize(name: str) -> str:
        """改進的名稱清理邏輯 - 把長名稱縮短為 idle/walk"""
        # 移除時間戳和 UUID
        base = name.split("-")[0].strip().lower()

        # 偵測動畫類型
        if "idle" in base or "breathing" in base:
            anim_type = "idle"
        elif "walk" in base or "animation" in base:
            anim_type = "walk"
        else:
            anim_type = "anim"

        return anim_type


def main():
    parser = argparse.ArgumentParser(
        description="Generate Spritesheet from sequence images"
    )
    repo_root = Path(__file__).resolve().parent.parent
    parser.add_argument(
        "--input",
        default=str(repo_root / "art_source" / "characters"),
        help="Input directory containing character folders (default: art_source/characters/)",
    )
    parser.add_argument(
        "--output",
        default=str(repo_root / "game" / "assets" / "spritesheet_cache"),
        help="Output directory for spritesheet cache (default: game/assets/spritesheet_cache/)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    input_dir = Path(args.input).resolve()
    output_dir = Path(args.output).resolve()

    print("=" * 60)
    print("  Muzha RPG - Spritesheet Generator")
    print("=" * 60)
    print(f"Input:  {input_dir}")
    print(f"Output: {output_dir}")
    print()

    generator = SpritesheetGenerator(verbose=args.verbose)
    results = generator.process_all_characters(input_dir, output_dir)

    # 輸出摘要配置
    if results["characters"]:
        config_path = output_dir / "atlas_config.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\nConfiguration saved: {config_path}")

    print()
    print("=" * 60)
    print(f"[OK] Successful: {results['summary']['successful']}")
    print(f"[FAIL] Failed:     {results['summary']['failed']}")
    print("=" * 60)

    return 0 if results["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
