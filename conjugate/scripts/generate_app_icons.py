"""Vibe Speak Conjugate のアプリアイコンを SVG マスターから PNG に書き出す。

アプリ本体からは呼ばない。幾何は SVG と Pillow で同一座標を共有する。

使い方:
  python3 conjugate/scripts/generate_app_icons.py
  python3 conjugate/scripts/generate_app_icons.py --variant a
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

ICON_DIR = Path(__file__).resolve().parents[1] / "static" / "icons"
GREEN = "#7CB342"
WHITE = "#FFFFFF"
SIZES = (16, 32, 180, 192, 512)
VARIANTS = ("a", "b", "c")


def _scale_pts(points: list[tuple[float, float]], size: int) -> list[tuple[float, float]]:
    s = size / 512.0
    return [(x * s, y * s) for x, y in points]


def draw_plan_a(draw: ImageDraw.ImageDraw, size: int) -> None:
    """現行ロゴ踏襲: 白抜きの人物シルエット。"""
    s = size / 512.0
    # 頭
    draw.ellipse(
        (184 * s, 116 * s, 328 * s, 260 * s),
        fill=WHITE,
    )
    # 肩〜胴。下端はキャンバス外へ伸ばし、OS のマスクで自然に切れる
    draw.ellipse(
        (108 * s, 292 * s, 404 * s, 588 * s),
        fill=WHITE,
    )


def draw_plan_b(draw: ImageDraw.ImageDraw, size: int) -> None:
    """動詞変換モチーフ: 原形→活用形を示す太い矢印。"""
    pts = _scale_pts(
        [
            (86, 208),
            (278, 208),
            (278, 128),
            (436, 256),
            (278, 384),
            (278, 304),
            (86, 304),
        ],
        size,
    )
    draw.polygon(pts, fill=WHITE)


def draw_plan_c(draw: ImageDraw.ImageDraw, size: int) -> None:
    """頭文字モノグラム: 太字の V。"""
    pts = _scale_pts(
        [
            (108, 132),
            (196, 132),
            (256, 348),
            (316, 132),
            (404, 132),
            (292, 432),
            (220, 432),
        ],
        size,
    )
    draw.polygon(pts, fill=WHITE)


DRAWERS = {
    "a": draw_plan_a,
    "b": draw_plan_b,
    "c": draw_plan_c,
}

SVG_A = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-label="Vibe Speak Conjugate">
  <rect width="512" height="512" fill="#7CB342"/>
  <circle cx="256" cy="188" r="72" fill="#fff"/>
  <ellipse cx="256" cy="440" rx="148" ry="148" fill="#fff"/>
</svg>
"""

SVG_B = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-label="Vibe Speak Conjugate">
  <rect width="512" height="512" fill="#7CB342"/>
  <path fill="#fff" d="M86 208h192v-80l158 128-158 128v-80H86z"/>
</svg>
"""

SVG_C = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-label="Vibe Speak Conjugate">
  <rect width="512" height="512" fill="#7CB342"/>
  <path fill="#fff" d="M108 132h88l60 216 60-216h88L292 432h-72z"/>
</svg>
"""

SVGS = {"a": SVG_A, "b": SVG_B, "c": SVG_C}


def render_icon(variant: str, size: int) -> Image.Image:
    oversample = 4 if size <= 192 else 2
    canvas = size * oversample
    img = Image.new("RGB", (canvas, canvas), GREEN)
    DRAWERS[variant](ImageDraw.Draw(img), canvas)
    if oversample != 1:
        img = img.resize((size, size), Image.Resampling.LANCZOS)
    return img


def write_svg(variant: str, path: Path) -> None:
    path.write_text(SVGS[variant], encoding="utf-8")


def export_variant(variant: str, dest: Path, *, prefix: str = "icon") -> None:
    dest.mkdir(parents=True, exist_ok=True)
    write_svg(variant, dest / f"{prefix}.svg")
    for size in SIZES:
        render_icon(variant, size).save(dest / f"{prefix}-{size}.png", format="PNG", optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=VARIANTS, default="a")
    parser.add_argument("--compare", action="store_true", help="3案を comparison/ に書き出す")
    args = parser.parse_args()

    ICON_DIR.mkdir(parents=True, exist_ok=True)

    if args.compare:
        compare_dir = ICON_DIR / "comparison"
        for variant in VARIANTS:
            export_variant(variant, compare_dir, prefix=f"plan-{variant}")
            # ホーム画面相当の見え方も並べる
            render_icon(variant, 180).save(compare_dir / f"plan-{variant}-home.png")
            render_icon(variant, 32).save(compare_dir / f"plan-{variant}-favicon.png")
        print(f"wrote comparison icons to {compare_dir}")
        return

    export_variant(args.variant, ICON_DIR)
    print(f"wrote variant {args.variant} to {ICON_DIR}")


if __name__ == "__main__":
    main()
