"""Conjugate ロゴ（吹き出し + es）から、PWA / 画面用 PNG を書き出す。

元画像は全面ライムの正方形を想定する。OS が角丸マスクをかけるので、
四隅も緑のまま残す。

使い方:
  python3 conjugate/scripts/generate_app_icons.py path/to/source.png
  python3 conjugate/scripts/generate_app_icons.py   # 既存 icon-512.png から各サイズを再書き出し
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

ICON_DIR = Path(__file__).resolve().parents[1] / "static" / "icons"
SIZES = (16, 32, 180, 192, 512)
LIME = (170, 225, 26)


def to_square_rgb(source: Image.Image) -> Image.Image:
    im = source.convert("RGB")
    w, h = im.size
    if w == h:
        return im
    side = max(w, h)
    canvas = Image.new("RGB", (side, side), LIME)
    canvas.paste(im, ((side - w) // 2, (side - h) // 2))
    return canvas


def export_sizes(master: Image.Image, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    rgb = to_square_rgb(master)
    for size in SIZES:
        resized = rgb.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(dest / f"icon-{size}.png", format="PNG", optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="?", help="全面ライムの正方形ソース画像")
    args = parser.parse_args()

    if args.source:
        master = Image.open(args.source)
    else:
        path = ICON_DIR / "icon-512.png"
        if not path.exists():
            raise SystemExit(f"missing {path}; pass a source image")
        master = Image.open(path)
    export_sizes(master, ICON_DIR)
    print(f"wrote icons to {ICON_DIR}")


if __name__ == "__main__":
    main()
