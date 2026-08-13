"""reportlab による提出帳票 PDF 描画（WeasyPrint が使えない環境向け）。"""

from __future__ import annotations

import io
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ASSETS_FONTS_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"
FONT_REGULAR_NAME = "NotoSansJP-Regular.ttf"
FONT_BOLD_NAME = "NotoSansJP-Bold.ttf"

TEAL = HexColor("#0f766e")
TEAL_DARK = HexColor("#0e7490")
EMERALD = HexColor("#047857")
SLATE = HexColor("#334155")
SLATE_MUTED = HexColor("#64748b")
SLATE_SOFT = HexColor("#94a3b8")
BORDER = HexColor("#99f6e4")
BORDER_SOFT = HexColor("#a7f3d0")
PANEL_BG = HexColor("#ffffff")
BAR_BG = HexColor("#ccfbf1")
BAR_FILL = HexColor("#14b8a6")
TOTAL_BG = HexColor("#ecfdf5")

FONT_REG = "ReportJP"
FONT_BOLD = "ReportJP-Bold"


def _register_fonts() -> None:
    regular = ASSETS_FONTS_DIR / FONT_REGULAR_NAME
    bold = ASSETS_FONTS_DIR / FONT_BOLD_NAME
    if not regular.exists():
        raise FileNotFoundError(f"日本語フォントが見つかりません: {regular}")
    if FONT_REG not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT_REG, str(regular)))
    if FONT_BOLD not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT_BOLD, str(bold if bold.exists() else regular)))


def _wrap_text(text: str, font: str, size: float, max_width: float) -> list[str]:
    text = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if paragraph == "":
            lines.append("")
            continue
        current = ""
        for ch in paragraph:
            candidate = current + ch
            if pdfmetrics.stringWidth(candidate, font, size) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = ch
        lines.append(current)
    return lines or [""]


def _draw_rounded_rect(c: canvas.Canvas, x, y, w, h, radius=4, fill=None, stroke=None, stroke_width=1):
    c.saveState()
    if fill is not None:
        c.setFillColor(fill)
    if stroke is not None:
        c.setStrokeColor(stroke)
        c.setLineWidth(stroke_width)
    c.roundRect(x, y, w, h, radius, fill=1 if fill is not None else 0, stroke=1 if stroke is not None else 0)
    c.restoreState()


def _draw_header(c: canvas.Canvas, report: dict, x, top, width):
    c.setFont(FONT_BOLD, 16)
    c.setFillColor(TEAL)
    c.drawString(x, top - 18, "Vibe Speak News 評価レポート")
    c.setFont(FONT_REG, 9.5)
    c.setFillColor(TEAL_DARK)
    c.drawString(x, top - 34, "Speaking Evaluation Report")

    c.setFont(FONT_BOLD, 8)
    c.setFillColor(TEAL)
    label = "提出日時"
    label_w = pdfmetrics.stringWidth(label, FONT_BOLD, 8)
    c.drawString(x + width - label_w, top - 14, label)
    c.setFont(FONT_REG, 9)
    c.setFillColor(SLATE_MUTED)
    value = report.get("submitted_at_display") or "—"
    value_w = pdfmetrics.stringWidth(value, FONT_REG, 9)
    c.drawString(x + width - value_w, top - 28, value)

    c.setStrokeColor(BORDER)
    c.setLineWidth(1.5)
    c.line(x, top - 44, x + width, top - 44)
    return top - 56


def _draw_panel_title(c: canvas.Canvas, title: str, x, y):
    c.setFont(FONT_BOLD, 8.5)
    c.setFillColor(TEAL)
    c.drawString(x, y, title)
    return y - 14


def _draw_student_panel(c: canvas.Canvas, report: dict, x, y, width) -> float:
    rows = [
        ("授業クラス", report.get("class_name") or "—", "HRクラス", report.get("student_hr_class") or "—"),
        ("出席番号", report.get("student_number") or "—", "名前", report.get("student_name") or "—"),
        ("CEFRレベル評価基準", report.get("level") or "—", "", ""),
    ]
    height = 78
    _draw_rounded_rect(c, x, y - height, width, height, radius=5, fill=PANEL_BG, stroke=BORDER_SOFT)
    cursor = _draw_panel_title(c, "受験者情報", x + 10, y - 14)
    col1 = x + 10
    col2 = x + width * 0.28
    col3 = x + width * 0.52
    col4 = x + width * 0.72
    for label_a, value_a, label_b, value_b in rows:
        c.setFont(FONT_BOLD, 8)
        c.setFillColor(SLATE_MUTED)
        c.drawString(col1, cursor, label_a)
        value_x = max(col2, col1 + pdfmetrics.stringWidth(label_a, FONT_BOLD, 8) + 8)
        c.setFont(FONT_REG, 10)
        c.setFillColor(SLATE)
        c.drawString(value_x, cursor, str(value_a))
        if label_b:
            c.setFont(FONT_BOLD, 8)
            c.setFillColor(SLATE_MUTED)
            c.drawString(col3, cursor, label_b)
            c.setFont(FONT_REG, 10)
            c.setFillColor(SLATE)
            c.drawString(col4, cursor, str(value_b))
        cursor -= 16
    return y - height - 10


def _draw_lesson_panel(c: canvas.Canvas, report: dict, x, y, width) -> float:
    title = str(report.get("lesson_title") or "未分類")
    lines = _wrap_text(title, FONT_BOLD, 11, width - 24)
    height = 36 + max(0, len(lines) - 1) * 14
    _draw_rounded_rect(c, x, y - height, width, height, radius=5, fill=PANEL_BG, stroke=BORDER_SOFT)
    cursor = _draw_panel_title(c, "動画タイトル", x + 10, y - 14)
    c.setFont(FONT_BOLD, 11)
    c.setFillColor(HexColor("#0f172a"))
    for line in lines:
        c.drawString(x + 10, cursor, line)
        cursor -= 14
    return y - height - 10


def _draw_scores_panel(c: canvas.Canvas, report: dict, x, y, width) -> float:
    height = 118
    _draw_rounded_rect(c, x, y - height, width, height, radius=5, fill=PANEL_BG, stroke=BORDER_SOFT)
    cursor = _draw_panel_title(c, "評価スコア", x + 10, y - 14)

    if not report.get("has_scores"):
        c.setFont(FONT_REG, 10)
        c.setFillColor(SLATE_SOFT)
        c.drawString(x + 10, cursor, "スコアデータなし")
        return y - height - 10

    cards = report.get("score_items") or []
    gap = 8
    card_w = (width - 20 - gap * 3) / 4
    card_h = 58
    card_y = cursor - card_h
    for i, score in enumerate(cards):
        cx = x + 10 + i * (card_w + gap)
        _draw_rounded_rect(c, cx, card_y, card_w, card_h, radius=4, fill=HexColor("#ffffff"), stroke=BORDER)
        c.setFont(FONT_BOLD, 7.5)
        c.setFillColor(TEAL_DARK)
        c.drawString(cx + 6, card_y + card_h - 12, score["label"])
        if score["value"] is None:
            c.setFont(FONT_REG, 9)
            c.setFillColor(SLATE_SOFT)
            c.drawString(cx + 6, card_y + 28, "データなし")
            fill_ratio = 0
        else:
            c.setFont(FONT_BOLD, 14)
            c.setFillColor(TEAL)
            c.drawString(cx + 6, card_y + 28, str(score["value"]))
            value_w = pdfmetrics.stringWidth(str(score["value"]), FONT_BOLD, 14)
            c.setFont(FONT_REG, 8)
            c.setFillColor(SLATE_MUTED)
            c.drawString(cx + 6 + value_w + 2, card_y + 30, f"/ {score['max']}")
            fill_ratio = max(0.0, min(1.0, (score["percent"] or 0) / 100))
        bar_x, bar_y, bar_w, bar_h = cx + 6, card_y + 10, card_w - 12, 6
        c.setFillColor(BAR_BG)
        c.roundRect(bar_x, bar_y, bar_w, bar_h, 3, fill=1, stroke=0)
        if fill_ratio > 0:
            c.setFillColor(BAR_FILL)
            c.roundRect(bar_x, bar_y, max(3, bar_w * fill_ratio), bar_h, 3, fill=1, stroke=0)

    total_y = y - height + 10
    _draw_rounded_rect(c, x + 10, total_y, width - 20, 22, radius=4, fill=TOTAL_BG, stroke=BORDER)
    c.setFont(FONT_BOLD, 9.5)
    c.setFillColor(TEAL)
    c.drawString(x + 18, total_y + 7, "合計スコア")
    if report.get("total_score") is None:
        total_font, total_size = FONT_REG, 10
        c.setFont(total_font, total_size)
        c.setFillColor(SLATE_SOFT)
        text = "データなし"
    else:
        total_font, total_size = FONT_BOLD, 13
        c.setFont(total_font, total_size)
        c.setFillColor(EMERALD)
        text = f"{report['total_score']} / {report['total_max']}"
    text_w = pdfmetrics.stringWidth(text, total_font, total_size)
    c.drawString(x + width - 18 - text_w, total_y + 6, text)
    return y - height - 10


def _draw_text_panel_lines(
    c: canvas.Canvas,
    title: str,
    lines: list[str],
    x: float,
    y: float,
    width: float,
    max_bottom: float,
    font_size: float = 8.5,
    line_height: float = 11,
) -> tuple[float, list[str]]:
    """テキストパネルを描画し、入りきらなかった行を返す。"""
    available = y - max_bottom
    if available < 36:
        return y, lines

    max_lines = max(1, int((available - 26) // line_height))
    visible = lines[:max_lines]
    remaining = lines[max_lines:]
    height = max(36, 24 + len(visible) * line_height)

    _draw_rounded_rect(c, x, y - height, width, height, radius=5, fill=PANEL_BG, stroke=BORDER_SOFT)
    cursor = _draw_panel_title(c, title, x + 10, y - 14)
    c.setFont(FONT_REG, font_size)
    c.setFillColor(HexColor("#1e293b"))
    for line in visible:
        c.drawString(x + 10, cursor, line)
        cursor -= line_height
    return y - height - 8, remaining


def _draw_footer(c: canvas.Canvas, report: dict, x, width):
    c.setStrokeColor(BORDER)
    c.setLineWidth(1)
    c.line(x, 14 * mm, x + width, 14 * mm)
    c.setFont(FONT_REG, 8)
    c.setFillColor(SLATE_MUTED)
    c.drawString(x, 10 * mm, f"提出ID: {report.get('id') or '—'}")
    brand = "Vibe Speak News"
    c.drawString(x + width - pdfmetrics.stringWidth(brand, FONT_REG, 8), 10 * mm, brand)


def _draw_page_background(c: canvas.Canvas, page_width, page_height):
    margin = 10 * mm
    _draw_rounded_rect(
        c,
        margin,
        margin,
        page_width - 2 * margin,
        page_height - 2 * margin,
        radius=8,
        fill=HexColor("#f8fffc"),
        stroke=BORDER,
        stroke_width=1.2,
    )


def _start_page(c: canvas.Canvas, report: dict, page_width, page_height, margin_x, content_width, top, *, continuation=False):
    _draw_page_background(c, page_width, page_height)
    if continuation:
        c.setFont(FONT_BOLD, 11)
        c.setFillColor(TEAL)
        name = report.get("student_name") or "生徒"
        c.drawString(margin_x, top - 14, f"{name} — 続き")
        c.setStrokeColor(BORDER)
        c.setLineWidth(1.2)
        c.line(margin_x, top - 22, margin_x + content_width, top - 22)
        return top - 34
    return _draw_header(c, report, margin_x, top, content_width)


def build_pdf_with_reportlab(reports: list[dict]) -> bytes:
    _register_fonts()
    buf = io.BytesIO()
    page_width, page_height = A4
    c = canvas.Canvas(buf, pagesize=A4)
    margin_x = 16 * mm
    content_width = page_width - 2 * margin_x
    top = page_height - 16 * mm
    footer_limit = 18 * mm

    for index, report in enumerate(reports):
        if index:
            c.showPage()

        y = _start_page(c, report, page_width, page_height, margin_x, content_width, top)
        y = _draw_student_panel(c, report, margin_x, y, content_width)
        y = _draw_lesson_panel(c, report, margin_x, y, content_width)
        y = _draw_scores_panel(c, report, margin_x, y, content_width)

        sections = [
            ("要約スピーチ録音結果", _wrap_text(report.get("transcript", "") or "（なし）", FONT_REG, 8.5, content_width - 24)),
            ("AIフィードバック", _wrap_text(report.get("feedback", "") or "（なし）", FONT_REG, 8.5, content_width - 24)),
        ]

        first_page = True
        while sections:
            title, lines = sections[0]
            if first_page:
                # 最初のページは2セクションで残り領域を分け合う
                mid = footer_limit + (y - footer_limit) * 0.48
                y, remaining = _draw_text_panel_lines(
                    c, title, lines, margin_x, y, content_width, max_bottom=mid
                )
                if remaining:
                    sections[0] = (title, remaining)
                else:
                    sections.pop(0)
                first_page = False
            else:
                y, remaining = _draw_text_panel_lines(
                    c, title, lines, margin_x, y, content_width, max_bottom=footer_limit
                )
                if remaining:
                    sections[0] = (title, remaining)
                    c.showPage()
                    y = _start_page(
                        c,
                        report,
                        page_width,
                        page_height,
                        margin_x,
                        content_width,
                        top,
                        continuation=True,
                    )
                else:
                    sections.pop(0)
                    if sections and y < footer_limit + 50:
                        c.showPage()
                        y = _start_page(
                            c,
                            report,
                            page_width,
                            page_height,
                            margin_x,
                            content_width,
                            top,
                            continuation=True,
                        )

        _draw_footer(c, report, margin_x, content_width)

    c.save()
    return buf.getvalue()
