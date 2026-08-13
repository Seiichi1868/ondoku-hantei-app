"""提出結果 PDF 帳票の生成（HTML テンプレート + WeasyPrint / 代替エンジン）。"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from flask import render_template

logger = logging.getLogger(__name__)

ASSETS_FONTS_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"
FONT_REGULAR_NAME = "NotoSansJP-Regular.ttf"
FONT_BOLD_NAME = "NotoSansJP-Bold.ttf"

SCORE_SPECS = (
    ("content_score", "内容理解", 5),
    ("organization_score", "構成・流れ", 5),
    ("language_score", "英語表現", 5),
    ("speaking_summary_score", "即興要約", 5),
)
TOTAL_MAX = 20


def _font_path(filename: str) -> Path:
    return ASSETS_FONTS_DIR / filename


def resolve_font_urls() -> tuple[str, str]:
    """帳票テンプレート用の font URL（file://）を返す。"""
    regular = _font_path(FONT_REGULAR_NAME)
    bold = _font_path(FONT_BOLD_NAME)
    if not regular.exists():
        raise FileNotFoundError(
            f"日本語フォントが見つかりません: {regular}. "
            f"{FONT_REGULAR_NAME} を news_app/assets/fonts/ に配置してください。"
        )
    bold_path = bold if bold.exists() else regular
    return regular.resolve().as_uri(), bold_path.resolve().as_uri()


def _parse_score(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _format_submitted_at(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%Y/%m/%d %H:%M")
    except ValueError:
        return raw


def build_report_context(submission: dict) -> dict:
    """1件分の帳票表示用データを組み立てる。"""
    score_items = []
    present_count = 0
    for key, label, maximum in SCORE_SPECS:
        value = _parse_score(submission.get(key))
        if value is not None:
            present_count += 1
            percent = max(0, min(100, round(value / maximum * 100))) if maximum else 0
        else:
            percent = 0
        score_items.append(
            {
                "key": key,
                "label": label,
                "value": value,
                "max": maximum,
                "percent": percent,
            }
        )

    total_score = _parse_score(submission.get("total_score"))
    has_scores = present_count > 0 or total_score is not None

    return {
        "id": submission.get("id", ""),
        "submitted_at_display": _format_submitted_at(submission.get("submitted_at")),
        "class_name": submission.get("class_name", ""),
        "student_hr_class": submission.get("student_hr_class", ""),
        "student_number": submission.get("student_number", ""),
        "student_name": submission.get("student_name", ""),
        "level": submission.get("level", ""),
        "lesson_title": submission.get("lesson_title") or "未分類",
        "transcript": submission.get("transcript", "") or "",
        "feedback": submission.get("feedback", "") or "",
        "score_items": score_items,
        "total_score": total_score,
        "total_max": TOTAL_MAX,
        "has_scores": has_scores,
    }


def render_report_html(submissions: list[dict]) -> str:
    font_regular_url, font_bold_url = resolve_font_urls()
    reports = [build_report_context(s) for s in submissions]
    return render_template(
        "news/report_pdf.html",
        reports=reports,
        font_regular_url=font_regular_url,
        font_bold_url=font_bold_url,
    )


def _pdf_via_weasyprint(html: str) -> bytes | None:
    try:
        from weasyprint import HTML
    except Exception as exc:  # ImportError / OSError (missing pango etc.)
        logger.info("WeasyPrint unavailable: %s", exc)
        return None
    try:
        return HTML(string=html, base_url=str(ASSETS_FONTS_DIR)).write_pdf()
    except Exception as exc:
        logger.warning("WeasyPrint PDF generation failed: %s", exc)
        return None


def build_submissions_pdf(submissions: list[dict]) -> bytes:
    """提出データリストから PDF バイナリを生成する。

    1) WeasyPrint（HTML テンプレート）を優先
    2) 失敗時は reportlab（同梱 Noto Sans JP）にフォールバック
       ※ macOS / Render など Pango 未整備環境でも動作させるため
    """
    if not submissions:
        raise ValueError("提出データがありません。")

    reports = [build_report_context(s) for s in submissions]
    try:
        html = render_report_html(submissions)
        pdf = _pdf_via_weasyprint(html)
        if pdf:
            return pdf
    except Exception as exc:
        logger.info("HTML report path skipped: %s", exc)

    from news_app.services.pdf_report_reportlab import build_pdf_with_reportlab

    return build_pdf_with_reportlab(reports)
