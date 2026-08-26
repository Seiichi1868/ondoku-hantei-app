"""reportlab による受験個票 PDF 描画（WeasyPrint が使えない環境向け）。"""
from __future__ import annotations

import io

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from level_check.pdf_report import FONT_BOLD_NAME, FONT_REGULAR_NAME, fonts_dir

SKY = HexColor("#0284c7")
SKY_DARK = HexColor("#0369a1")
SKY_DEEP = HexColor("#0c4a6e")
SLATE = HexColor("#334155")
SLATE_MUTED = HexColor("#64748b")
SLATE_SOFT = HexColor("#94a3b8")
BORDER = HexColor("#7dd3fc")
BORDER_SOFT = HexColor("#bae6fd")
PANEL_BG = HexColor("#ffffff")
BAR_BG = HexColor("#e0f2fe")
BAR_FILL = HexColor("#38bdf8")
TOTAL_BG = HexColor("#f0f9ff")
PAGE_BG = HexColor("#f8fbff")

FONT_REG = "LevelCheckJP"
FONT_BOLD = "LevelCheckJP-Bold"


def _register_fonts() -> None:
    directory = fonts_dir()
    regular = directory / FONT_REGULAR_NAME
    bold = directory / FONT_BOLD_NAME
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


def _draw_page_background(c: canvas.Canvas, page_width, page_height):
    margin = 10 * mm
    _draw_rounded_rect(
        c,
        margin,
        margin,
        page_width - 2 * margin,
        page_height - 2 * margin,
        radius=8,
        fill=PAGE_BG,
        stroke=BORDER,
        stroke_width=1.2,
    )


def _draw_header(c: canvas.Canvas, report: dict, x, top, width):
    c.setFont(FONT_BOLD, 16)
    c.setFillColor(SKY)
    c.drawString(x, top - 18, "Speaking Level Check Test 評価個票")
    c.setFont(FONT_REG, 9.5)
    c.setFillColor(SKY_DARK)
    c.drawString(x, top - 34, "Individual Score Report")

    c.setFont(FONT_BOLD, 8)
    c.setFillColor(SKY)
    label = "受験日時"
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
    c.setFillColor(SKY)
    c.drawString(x, y, title)
    return y - 14


def _draw_student_panel(c: canvas.Canvas, report: dict, x, y, width) -> float:
    rows = [
        ("クラス", report.get("class_name") or "—", "出席番号", report.get("student_number") or "—"),
        ("氏名", report.get("student_name") or "—", "情報レベル", report.get("info_level_label") or "—"),
    ]
    height = 62
    _draw_rounded_rect(c, x, y - height, width, height, radius=5, fill=PANEL_BG, stroke=BORDER_SOFT)
    cursor = _draw_panel_title(c, "受験者情報", x + 10, y - 14)
    col1 = x + 10
    col2 = x + width * 0.28
    col3 = x + width * 0.52
    col4 = x + width * 0.74
    for label_a, value_a, label_b, value_b in rows:
        c.setFont(FONT_BOLD, 8)
        c.setFillColor(SLATE_MUTED)
        c.drawString(col1, cursor, label_a)
        value_x = max(col2, col1 + pdfmetrics.stringWidth(label_a, FONT_BOLD, 8) + 8)
        c.setFont(FONT_REG, 10)
        c.setFillColor(SLATE)
        c.drawString(value_x, cursor, str(value_a))
        c.setFont(FONT_BOLD, 8)
        c.setFillColor(SLATE_MUTED)
        c.drawString(col3, cursor, label_b)
        c.setFont(FONT_REG, 10)
        c.setFillColor(SLATE)
        c.drawString(col4, cursor, str(value_b))
        cursor -= 16
    return y - height - 10


def _draw_hero_panel(c: canvas.Canvas, report: dict, x, y, width) -> float:
    height = 78
    _draw_rounded_rect(c, x, y - height, width, height, radius=5, fill=PANEL_BG, stroke=BORDER_SOFT)
    cursor = _draw_panel_title(c, "総合結果", x + 10, y - 14)

    score = report.get("speaking_level_score")
    c.setFont(FONT_BOLD, 8)
    c.setFillColor(SKY_DARK)
    c.drawString(x + 10, cursor, "Speaking Level Score")
    if score is None:
        c.setFont(FONT_REG, 16)
        c.setFillColor(SLATE_SOFT)
        c.drawString(x + 10, cursor - 24, "—")
    else:
        c.setFont(FONT_BOLD, 22)
        c.setFillColor(SKY)
        c.drawString(x + 10, cursor - 26, str(score))
        score_w = pdfmetrics.stringWidth(str(score), FONT_BOLD, 22)
        c.setFont(FONT_REG, 10)
        c.setFillColor(SLATE_MUTED)
        c.drawString(x + 12 + score_w, cursor - 22, "/ 90")

    cefr = report.get("cefr_band") or "—"
    c.setFont(FONT_BOLD, 8)
    c.setFillColor(SKY_DARK)
    c.drawString(x + width * 0.38, cursor, "CEFR帯")
    c.setFont(FONT_BOLD, 18)
    c.setFillColor(SKY_DEEP)
    c.drawString(x + width * 0.38, cursor - 24, str(cefr))

    sub_w = (width * 0.28 - 8)
    for i, (label, value) in enumerate(
        (("スピーキング", report.get("speaking_subscore")), ("リスニング", report.get("listening_subscore")))
    ):
        cx = x + width * 0.62 + i * (sub_w + 8)
        _draw_rounded_rect(c, cx, y - height + 10, sub_w, 48, radius=4, fill=TOTAL_BG, stroke=BORDER)
        c.setFont(FONT_BOLD, 7.5)
        c.setFillColor(SKY_DARK)
        c.drawString(cx + 6, y - height + 46, label)
        if value is None:
            c.setFont(FONT_REG, 11)
            c.setFillColor(SLATE_SOFT)
            c.drawString(cx + 6, y - height + 24, "—")
        else:
            c.setFont(FONT_BOLD, 14)
            c.setFillColor(SKY)
            c.drawString(cx + 6, y - height + 22, str(value))
            vw = pdfmetrics.stringWidth(str(value), FONT_BOLD, 14)
            c.setFont(FONT_REG, 8)
            c.setFillColor(SLATE_MUTED)
            c.drawString(cx + 8 + vw, y - height + 24, "/90")
    return y - height - 10


def _draw_score_cards(c: canvas.Canvas, title: str, cards: list[dict], x, y, width, *, columns: int) -> float:
    gap = 6
    card_h = 48
    rows = (len(cards) + columns - 1) // columns if cards else 1
    height = 28 + rows * (card_h + gap)
    _draw_rounded_rect(c, x, y - height, width, height, radius=5, fill=PANEL_BG, stroke=BORDER_SOFT)
    cursor = _draw_panel_title(c, title, x + 10, y - 14)
    if not cards:
        c.setFont(FONT_REG, 9)
        c.setFillColor(SLATE_SOFT)
        c.drawString(x + 10, cursor, "データなし")
        return y - height - 10

    card_w = (width - 20 - gap * (columns - 1)) / columns
    for i, score in enumerate(cards):
        row, col = divmod(i, columns)
        cx = x + 10 + col * (card_w + gap)
        cy = cursor - card_h - row * (card_h + gap)
        _draw_rounded_rect(c, cx, cy, card_w, card_h, radius=4, fill=HexColor("#ffffff"), stroke=BORDER)
        c.setFont(FONT_BOLD, 7)
        c.setFillColor(SKY_DARK)
        c.drawString(cx + 5, cy + card_h - 11, score["label"])
        if score.get("value") is None:
            c.setFont(FONT_REG, 9)
            c.setFillColor(SLATE_SOFT)
            c.drawString(cx + 5, cy + 20, "—")
            fill_ratio = 0
        else:
            c.setFont(FONT_BOLD, 12)
            c.setFillColor(SKY)
            c.drawString(cx + 5, cy + 18, score["display"])
            dw = pdfmetrics.stringWidth(str(score["display"]), FONT_BOLD, 12)
            c.setFont(FONT_REG, 7)
            c.setFillColor(SLATE_MUTED)
            c.drawString(cx + 7 + dw, cy + 20, f"/ {int(score.get('max') or 5)}")
            fill_ratio = max(0.0, min(1.0, (score.get("percent") or 0) / 100))
        bar_x, bar_y, bar_w, bar_h = cx + 5, cy + 8, card_w - 10, 5
        c.setFillColor(BAR_BG)
        c.roundRect(bar_x, bar_y, bar_w, bar_h, 2.5, fill=1, stroke=0)
        if fill_ratio > 0:
            c.setFillColor(BAR_FILL)
            c.roundRect(bar_x, bar_y, max(2.5, bar_w * fill_ratio), bar_h, 2.5, fill=1, stroke=0)
    return y - height - 10


def _task_card_height(task: dict, width: float) -> float:
    inner = width - 24
    prompt_lines = _wrap_text(task.get("prompt") or "（設問なし）", FONT_REG, 8, inner)[:3]
    body = task.get("transcript") or task.get("transcript_error") or "（発話なし）"
    transcript_lines = _wrap_text(f"認識: {body}", FONT_REG, 8, inner)[:3]
    comment_lines = _wrap_text(task.get("comments") or "", FONT_REG, 7.5, inner)[:2] if task.get("comments") else []
    return 28 + 11 * (len(prompt_lines) + len(transcript_lines) + len(comment_lines) + 1)


def _draw_task_card(c: canvas.Canvas, task: dict, x, y, width) -> float:
    height = _task_card_height(task, width)
    _draw_rounded_rect(c, x, y - height, width, height, radius=4, fill=PANEL_BG, stroke=BORDER_SOFT)
    inner = width - 24
    c.setFont(FONT_BOLD, 8.5)
    c.setFillColor(SKY)
    c.drawString(x + 10, y - 14, f"{task['index']}. {task['label']}")
    weighted = f"{task.get('weighted_display') or '—'}/5"
    if task.get("cefr_band"):
        weighted = f"{weighted}  {task['cefr_band']}"
    ww = pdfmetrics.stringWidth(weighted, FONT_BOLD, 8.5)
    c.drawString(x + width - 10 - ww, y - 14, weighted)

    cursor = y - 26
    c.setFont(FONT_REG, 8)
    c.setFillColor(SLATE)
    for line in _wrap_text(task.get("prompt") or "（設問なし）", FONT_REG, 8, inner)[:3]:
        c.drawString(x + 10, cursor, line)
        cursor -= 11

    body = task.get("transcript") or task.get("transcript_error") or "（発話なし）"
    c.setFillColor(SLATE_MUTED)
    for line in _wrap_text(f"認識: {body}", FONT_REG, 8, inner)[:3]:
        c.drawString(x + 10, cursor, line)
        cursor -= 11

    score_text = "  ".join(f"{item['label']} {item['display']}" for item in task.get("score_items") or [])
    c.setFont(FONT_BOLD, 7.5)
    c.setFillColor(SKY_DARK)
    c.drawString(x + 10, cursor, score_text or "未採点")
    cursor -= 11

    if task.get("comments"):
        c.setFont(FONT_REG, 7.5)
        c.setFillColor(SLATE_MUTED)
        for line in _wrap_text(task["comments"], FONT_REG, 7.5, inner)[:2]:
            c.drawString(x + 10, cursor, line)
            cursor -= 11
    return y - height - 6


def _draw_footer(c: canvas.Canvas, report: dict, x, width):
    c.setStrokeColor(BORDER)
    c.setLineWidth(1)
    c.line(x, 14 * mm, x + width, 14 * mm)
    c.setFont(FONT_REG, 8)
    c.setFillColor(SLATE_MUTED)
    c.drawString(x, 10 * mm, f"提出ID: {report.get('id') or '—'}")
    brand = "Speaking Level Check Test"
    c.drawString(x + width - pdfmetrics.stringWidth(brand, FONT_REG, 8), 10 * mm, brand)


def _start_page(c: canvas.Canvas, report: dict, page_width, page_height, margin_x, content_width, top, *, continuation=False):
    _draw_page_background(c, page_width, page_height)
    if continuation:
        c.setFont(FONT_BOLD, 11)
        c.setFillColor(SKY)
        name = report.get("student_name") or report.get("class_name") or "受験者"
        c.drawString(margin_x, top - 14, f"{name} — 設問詳細（続き）")
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
    footer_limit = 20 * mm

    for index, report in enumerate(reports):
        if index:
            c.showPage()

        y = _start_page(c, report, page_width, page_height, margin_x, content_width, top)
        y = _draw_student_panel(c, report, margin_x, y, content_width)
        y = _draw_hero_panel(c, report, margin_x, y, content_width)
        y = _draw_score_cards(c, "カテゴリ別スコア（1〜5）", report.get("category_items") or [], margin_x, y, content_width, columns=3)
        y = _draw_score_cards(c, "スピーキング評価軸", report.get("speaking_axes") or [], margin_x, y, content_width, columns=5)
        y = _draw_score_cards(c, "リスニング評価軸", report.get("listening_axes") or [], margin_x, y, content_width, columns=2)

        tasks = list(report.get("tasks") or [])
        if tasks:
            if y < footer_limit + 70:
                c.showPage()
                y = _start_page(c, report, page_width, page_height, margin_x, content_width, top, continuation=True)
            c.setFont(FONT_BOLD, 8.5)
            c.setFillColor(SKY)
            c.drawString(margin_x, y - 2, "設問ごとの結果")
            y -= 14

        while tasks:
            task = tasks[0]
            needed = _task_card_height(task, content_width) + 6
            if y - needed < footer_limit:
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
            y = _draw_task_card(c, task, margin_x, y, content_width)
            tasks.pop(0)

        _draw_footer(c, report, margin_x, content_width)

    c.save()
    return buf.getvalue()
