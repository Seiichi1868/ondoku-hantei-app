"""ユーザー提供の News ロゴから、PWA / 画面用 PNG を書き出す。

使い方:
  python3 news_app/scripts/generate_app_icons.py path/to/source.png
  python3 news_app/scripts/generate_app_icons.py   # 既存 icon-512.png から各サイズを再書き出し
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

ICON_DIR = Path(__file__).resolve().parents[2] / "static" / "news" / "icons"
SIZES = (16, 32, 180, 192, 512)


def export_sizes(master: Image.Image, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    rgb = master.convert("RGB")
    for size in SIZES:
        resized = rgb.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(dest / f"icon-{size}.png", format="PNG", optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="?", help="正方形の元画像")
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
