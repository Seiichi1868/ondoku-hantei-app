"""Vibe Speak Conjugate 用のアニメ風背景を、一回限り生成するスクリプト。

アプリ本体からは呼ばない。OpenAI Images API（gpt-image-1-mini）で静的ファイルを作り、
conjugate/static/images/backgrounds/ に保存する。

使い方:
  python3 conjugate/scripts/generate_anime_backgrounds.py
  python3 conjugate/scripts/generate_anime_backgrounds.py --only mountain forest
"""
from __future__ import annotations

import argparse
import base64
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

OUT_DIR = Path(__file__).resolve().parents[1] / "static" / "images" / "backgrounds"
MODEL = "gpt-image-1-mini"
SIZE = "1536x1024"
QUALITY = "medium"

STYLE_LOCK = (
    "Soft pastel anime-style landscape illustration for a mobile study app. "
    "Color palette: sage green (#E9EFDF), cream, pale mint, and muted olive with gentle gradients. "
    "Style: soft flat illustration, rounded shapes, restrained outlines, lots of gradient, "
    "no photorealistic texture, no harsh shadows, no saturated primary colors, no 3D render. "
    "Composition: wide landscape banner, calm cozy atmosphere, generous empty sky or mist "
    "in the upper/center area for text overlay."
)

SCENES = {
    "mountain": {
        "filename": "bg_anime_mountain_01.png",
        "prompt": (
            "Soft anime-style mountain landscape at sunrise, pastel sage green and cream color gradient, "
            "gentle rolling hills, distant layered mountain silhouettes, a sea of soft clouds in the valleys, "
            "warm pale peach light on the horizon. "
            + STYLE_LOCK
        ),
    },
    "forest": {
        "filename": "bg_anime_forest_01.png",
        "prompt": (
            "Anime-style misty forest, pastel sage green tones, soft rounded trees, simplified foliage, "
            "warm morning light filtering as pale cream glow, quiet path fading into fog. "
            + STYLE_LOCK
        ),
    },
    "clouds": {
        "filename": "bg_anime_clouds_01.png",
        "prompt": (
            "Gentle anime-style cloud sea over mountains, pastel green and cream gradient sky, "
            "rounded soft cloud shapes like cotton, distant mountain peaks peeking through, "
            "calm meditative mood. "
            + STYLE_LOCK
        ),
    },
    "hills": {
        "filename": "bg_anime_hills_01.png",
        "prompt": (
            "Anime-style rolling hills and meadow, pastel sage grassland, gentle cream wildflowers, "
            "soft rounded hill silhouettes receding into the distance, quiet countryside, empty sky. "
            + STYLE_LOCK
        ),
    },
    "lake": {
        "filename": "bg_anime_lake_01.png",
        "prompt": (
            "Anime-style quiet lake with mountains, glassy still water reflecting pale sage hills, "
            "soft cream sky, simplified shoreline, calm mirror-like surface, lots of empty sky. "
            + STYLE_LOCK
        ),
    },
    "coast": {
        "filename": "bg_anime_coast_01.png",
        "prompt": (
            "Anime-style calm coastline at dusk, pastel sage and cream sunset, gentle rounded cliffs, "
            "quiet sea with soft gradient water, no dramatic waves, peaceful evening shoreline. "
            + STYLE_LOCK
        ),
    },
}


API_URL = "https://api.openai.com/v1/images/generations"


def generate_one(api_key: str, key: str, scene: dict) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUT_DIR / scene["filename"]
    print(f"generating {key} -> {dest.name} ...", flush=True)
    response = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "prompt": scene["prompt"],
            "size": SIZE,
            "quality": QUALITY,
            "output_format": "png",
            "n": 1,
        },
        timeout=180,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"{key}: HTTP {response.status_code} {response.text}")
    body = response.json()

    image_b64 = (body.get("data") or [{}])[0].get("b64_json")
    if not image_b64:
        raise RuntimeError(f"{key}: API returned no image data: {body}")
    dest.write_bytes(base64.b64decode(image_b64))
    print(f"  saved {dest} ({dest.stat().st_size} bytes)", flush=True)
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate anime-style Conjugate backgrounds once.")
    parser.add_argument("--only", nargs="+", choices=sorted(SCENES), help="Generate only these scene keys.")
    args = parser.parse_args()

    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        print("OPENAI_API_KEY がありません。.env を確認してください。", file=sys.stderr)
        return 1

    keys = args.only or list(SCENES)
    for key in keys:
        generate_one(api_key, key, SCENES[key])
    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
