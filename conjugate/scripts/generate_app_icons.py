"""ユーザー提供の Conjugate ロゴから、PWA / 画面用 PNG を書き出す。

元データは角丸モック（白余白・「Made with AI」入り）なので、緑のアイコン本体を
正方形に切り出し、OS が角丸する前提で四隅を緑で埋める。

使い方:
  python3 conjugate/scripts/generate_app_icons.py path/to/source.png
  python3 conjugate/scripts/generate_app_icons.py   # 既存 icon-512.png から各サイズを再書き出し
"""
from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

from PIL import Image

ICON_DIR = Path(__file__).resolve().parents[1] / "static" / "icons"
SIZES = (16, 32, 180, 192, 512)


def _is_green(r: int, g: int, b: int, a: int = 255) -> bool:
    return a > 200 and g > 150 and g > r + 25 and g > b + 15 and (r + g + b) < 620


def _is_mockup_bg(r: int, g: int, b: int, a: int = 255) -> bool:
    if a < 30:
        return True
    if r > 220 and g > 220 and b > 220:
        return True
    return abs(r - g) < 14 and abs(g - b) < 14 and r > 200


def green_bbox(im: Image.Image) -> tuple[int, int, int, int]:
    px = im.load()
    w, h = im.size
    minx, miny, maxx, maxy = w, h, 0, 0
    found = False
    for y in range(h):
        for x in range(w):
            if _is_green(*px[x, y]):
                found = True
                if x < minx:
                    minx = x
                if y < miny:
                    miny = y
                if x > maxx:
                    maxx = x
                if y > maxy:
                    maxy = y
    if not found:
        raise SystemExit("green icon region not found")
    return minx, miny, maxx, maxy


def square_crop_box(bbox: tuple[int, int, int, int], size: tuple[int, int]) -> tuple[int, int, int, int]:
    minx, miny, maxx, maxy = bbox
    bw = maxx - minx + 1
    bh = maxy - miny + 1
    side = max(bw, bh)
    cx = (minx + maxx) / 2
    cy = (miny + maxy) / 2
    x0 = int(round(cx - side / 2))
    y0 = int(round(cy - side / 2))
    x1 = x0 + side
    y1 = y0 + side
    w, h = size
    if x0 < 0:
        x1 -= x0
        x0 = 0
    if y0 < 0:
        y1 -= y0
        y0 = 0
    if x1 > w:
        x0 -= x1 - w
        x1 = w
    if y1 > h:
        y0 -= y1 - h
        y1 = h
    return max(0, x0), max(0, y0), min(w, x1), min(h, y1)


def fill_corners(im: Image.Image) -> Image.Image:
    """モックの白余白（四隅）だけを、アイコン縁の緑で埋める。"""
    out = im.convert("RGBA")
    px = out.load()
    w, h = out.size
    fallback = (112, 196, 76, 255)
    for y in range(h // 4, 3 * h // 4):
        for x in range(w // 4, 3 * w // 4):
            if _is_green(*px[x, y]):
                fallback = px[x, y]
                break
        else:
            continue
        break

    visited = set()
    q: deque[tuple[int, int]] = deque([(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)])
    bg_pixels: list[tuple[int, int]] = []
    while q:
        x, y = q.popleft()
        if (x, y) in visited or not (0 <= x < w and 0 <= y < h):
            continue
        visited.add((x, y))
        if not _is_mockup_bg(*px[x, y]):
            continue
        bg_pixels.append((x, y))
        q.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

    cx, cy = (w - 1) / 2, (h - 1) / 2
    for x, y in bg_pixels:
        dx, dy = cx - x, cy - y
        dist = (dx * dx + dy * dy) ** 0.5 or 1
        stepx, stepy = dx / dist, dy / dist
        fx, fy = float(x), float(y)
        color = fallback
        for _ in range(int(dist) + 4):
            fx += stepx
            fy += stepy
            ix, iy = int(round(fx)), int(round(fy))
            if 0 <= ix < w and 0 <= iy < h and _is_green(*px[ix, iy]):
                color = px[ix, iy]
                break
        px[x, y] = color
    return out.convert("RGB")


def build_master(source: Image.Image) -> Image.Image:
    box = square_crop_box(green_bbox(source), source.size)
    cropped = source.crop(box)
    if cropped.size[0] != cropped.size[1]:
        side = max(cropped.size)
        canvas = Image.new("RGBA", (side, side), (248, 248, 248, 255))
        ox = (side - cropped.size[0]) // 2
        oy = (side - cropped.size[1]) // 2
        canvas.paste(cropped, (ox, oy))
        cropped = canvas
    return fill_corners(cropped)


def export_sizes(master: Image.Image, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    rgb = master.convert("RGB")
    for size in SIZES:
        resized = rgb.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(dest / f"icon-{size}.png", format="PNG", optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="?", help="角丸モック入りの元画像")
    args = parser.parse_args()

    if args.source:
        master = build_master(Image.open(args.source))
    else:
        path = ICON_DIR / "icon-512.png"
        if not path.exists():
            raise SystemExit(f"missing {path}; pass a source image")
        master = Image.open(path)
    export_sizes(master, ICON_DIR)
    print(f"wrote icons to {ICON_DIR}")


if __name__ == "__main__":
    main()
