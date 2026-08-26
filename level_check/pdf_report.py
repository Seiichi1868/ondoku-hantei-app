"""受験結果 PDF 個票の生成（HTML テンプレート + WeasyPrint / 代替エンジン）。

news_app とは独立。フォントは level_check/assets/fonts/ を優先し、
無ければ同リポジトリの news_app/assets/fonts/ をファイルパスとして参照する。
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from flask import render_template

from level_check.config import CATEGORIES, CATEGORY_LABELS, INFO_LEVEL_LABELS
from level_check.scoring.rubric import DEFAULT_LISTENING_RUBRIC, DEFAULT_SPEAKING_RUBRIC, LISTENING_AXES, SPEAKING_AXES

logger = logging.getLogger(__name__)

FONT_REGULAR_NAME = "NotoSansJP-Regular.ttf"
FONT_BOLD_NAME = "NotoSansJP-Bold.ttf"


def fonts_dir() -> Path:
    local = Path(__file__).resolve().parent / "assets" / "fonts"
    sibling = Path(__file__).resolve().parents[1] / "news_app" / "assets" / "fonts"
    for path in (local, sibling):
        if (path / FONT_REGULAR_NAME).exists():
            return path
    raise FileNotFoundError(
        f"日本語フォントが見つかりません: {local / FONT_REGULAR_NAME}. "
        f"{FONT_REGULAR_NAME} を level_check/assets/fonts/ に配置してください。"
    )


def resolve_font_urls() -> tuple[str, str]:
    directory = fonts_dir()
    regular = directory / FONT_REGULAR_NAME
    bold = directory / FONT_BOLD_NAME
    bold_path = bold if bold.exists() else regular
    return regular.resolve().as_uri(), bold_path.resolve().as_uri()


def _parse_number(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def format_score(value, *, digits: int = 1) -> str:
    number = _parse_number(value)
    if number is None:
        return "—"
    if digits <= 0:
        return str(int(round(number)))
    return f"{number:.{digits}f}"


def format_submitted_at(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%Y/%m/%d %H:%M")
    except ValueError:
        return raw


def _axis_items(axes: dict | None, specs: dict, order: tuple[str, ...], *, maximum: float = 5.0) -> list[dict]:
    source = axes if isinstance(axes, dict) else {}
    items = []
    for key in order:
        spec = specs.get(key) or {}
        number = _parse_number(source.get(key))
        percent = 0
        if number is not None and maximum:
            percent = max(0, min(100, round(number / maximum * 100)))
        items.append(
            {
                "key": key,
                "label": spec.get("label") or key,
                "value": None if number is None else round(number, 1),
                "display": format_score(number, digits=1),
                "max": maximum,
                "percent": percent,
            }
        )
    return items


def _task_prompt(task: dict) -> str:
    for key in ("question_text", "prompt_text", "target_text", "stimulus_text"):
        text = str(task.get(key) or "").strip()
        if text:
            return text
    return ""


def _comment_text(comments: dict | None) -> str:
    if not isinstance(comments, dict):
        return ""
    parts = []
    for value in comments.values():
        text = str(value or "").strip()
        if text:
            parts.append(text)
    return " / ".join(parts)


def _task_score_items(task: dict) -> list[dict]:
    scores = task.get("scores") if isinstance(task.get("scores"), dict) else {}
    track = task.get("score_track") or ""
    category = str(task.get("task_type") or task.get("category") or "").upper()
    if track == "listening" or (not track and category in ("A", "C", "D")):
        order = LISTENING_AXES
        specs = DEFAULT_LISTENING_RUBRIC
    else:
        order = SPEAKING_AXES
        specs = DEFAULT_SPEAKING_RUBRIC
    items = []
    for key in order:
        number = _parse_number(scores.get(key))
        items.append(
            {
                "key": key,
                "label": (specs.get(key) or {}).get("label") or key,
                "display": format_score(number, digits=0) if number is not None and number == int(number) else format_score(number, digits=1),
            }
        )
    return items


def build_report_context(submission: dict) -> dict:
    """1件分の個票表示用データを組み立てる。"""
    student = submission.get("student_info") or {}
    overall = submission.get("overall") or {}
    category_scores = overall.get("category_scores") if isinstance(overall.get("category_scores"), dict) else {}
    info_level = str(submission.get("info_level") or "")

    category_items = []
    for cat in CATEGORIES:
        number = _parse_number(category_scores.get(cat))
        percent = 0 if number is None else max(0, min(100, round(number / 5 * 100)))
        category_items.append(
            {
                "id": cat,
                "label": CATEGORY_LABELS.get(cat, cat),
                "value": None if number is None else round(number, 1),
                "display": format_score(number, digits=1),
                "max": 5,
                "percent": percent,
            }
        )

    tasks = []
    for index, raw in enumerate(submission.get("task_results") or [], start=1):
        if not isinstance(raw, dict):
            continue
        category = str(raw.get("task_type") or raw.get("category") or "").upper()
        weighted = _parse_number(raw.get("weighted_total"))
        tasks.append(
            {
                "index": index,
                "category": category,
                "label": CATEGORY_LABELS.get(category, category or "設問"),
                "prompt": _task_prompt(raw),
                "transcript": str(raw.get("transcript") or "").strip(),
                "transcript_error": str(raw.get("transcript_error") or "").strip(),
                "weighted_display": format_score(weighted, digits=1),
                "cefr_band": raw.get("cefr_band") or "",
                "score_items": _task_score_items(raw),
                "comments": _comment_text(raw.get("comments")),
                "status": raw.get("status") or "",
            }
        )

    speaking_score = _parse_number(overall.get("speaking_level_score") or overall.get("score_100"))
    speaking_sub = _parse_number(overall.get("speaking_subscore"))
    listening_sub = _parse_number(overall.get("listening_subscore"))

    return {
        "id": submission.get("id", ""),
        "submitted_at_display": format_submitted_at(submission.get("submitted_at")),
        "info_level_label": INFO_LEVEL_LABELS.get(info_level, info_level or "—"),
        "class_name": student.get("class_name") or "",
        "student_number": student.get("number") or "",
        "student_name": student.get("name") or "",
        "ai_model_mode": submission.get("ai_model_mode") or "",
        "speaking_level_score": None if speaking_score is None else int(round(speaking_score)),
        "cefr_band": overall.get("cefr_band") or "",
        "speaking_subscore": None if speaking_sub is None else int(round(speaking_sub)),
        "listening_subscore": None if listening_sub is None else int(round(listening_sub)),
        "has_scores": speaking_score is not None or speaking_sub is not None or listening_sub is not None,
        "category_items": category_items,
        "speaking_axes": _axis_items(overall.get("speaking_axes"), DEFAULT_SPEAKING_RUBRIC, SPEAKING_AXES),
        "listening_axes": _axis_items(overall.get("listening_axes"), DEFAULT_LISTENING_RUBRIC, LISTENING_AXES),
        "tasks": tasks,
    }


def render_report_html(submissions: list[dict]) -> str:
    font_regular_url, font_bold_url = resolve_font_urls()
    reports = [build_report_context(s) for s in submissions]
    return render_template(
        "level_check/report_pdf.html",
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
        return HTML(string=html, base_url=str(fonts_dir())).write_pdf()
    except Exception as exc:
        logger.warning("WeasyPrint PDF generation failed: %s", exc)
        return None


def build_submissions_pdf(submissions: list[dict]) -> bytes:
    """提出データリストから PDF バイナリを生成する。

    1) WeasyPrint（HTML テンプレート）を優先
    2) 失敗時は reportlab（同梱 Noto Sans JP）にフォールバック
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

    from level_check.pdf_report_reportlab import build_pdf_with_reportlab

    return build_pdf_with_reportlab(reports)
