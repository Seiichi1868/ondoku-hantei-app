"""Speaking Level Check Test: 管理画面 Blueprint。

roster 管理・問題バンク編集・結果閲覧・設定切替をすべてここに含む。
"""
import io

import openpyxl
from flask import Blueprint, jsonify, render_template, request, send_file

from level_check.config import (
    AI_MODEL_MODES,
    BACKGROUND_IMAGE_STATIC_PATH,
    INFO_LEVEL_LABELS,
    INFO_LEVELS,
    ADMIN_PASSWORD,
    get_openai_api_key,
    resolve_ai_model_id,
)
from level_check.scoring.rubric import DEFAULT_RUBRIC, RUBRIC_AXES
from level_check.storage import (
    add_or_update_student,
    add_questions,
    delete_question,
    delete_student,
    delete_submission,
    get_submissions,
    import_students_from_excel,
    load_questions,
    load_settings,
    load_students,
    update_question,
    update_settings,
)
from level_check.tasks.definitions import TASK_DEFINITIONS
from level_check.tasks.generator import generate_questions

admin_bp = Blueprint(
    "level_check_admin",
    __name__,
    url_prefix="/level_check/admin",
    template_folder="../templates",
)

_QUESTION_TEXT_FIELD = {
    "repeat": "text",
    "sentence_build": "target_sentence",
    "qa": "question",
}


def _require_model_change_password(payload: dict):
    """AIモデル選択（管理設定）の変更時のみパスワードを要求する。"""
    if str(payload.get("admin_password") or "") != ADMIN_PASSWORD:
        return jsonify({"ok": False, "error": "管理設定のパスワードが違います。"}), 403
    return None


def _settings_payload() -> dict:
    settings = load_settings()
    return {
        "ok": True,
        **settings,
        "ai_model_modes": [{"id": k, **v} for k, v in AI_MODEL_MODES.items()],
        "info_levels": [{"id": lvl, "label": INFO_LEVEL_LABELS[lvl]} for lvl in INFO_LEVELS],
        "rubric_defaults": {axis: DEFAULT_RUBRIC[axis] for axis in RUBRIC_AXES},
        "api_key_configured": bool(get_openai_api_key()),
    }


@admin_bp.route("/")
def admin_page():
    bank = load_questions()
    settings = load_settings()
    return render_template(
        "level_check/admin/index.html",
        settings=settings,
        ai_model_modes=AI_MODEL_MODES,
        info_levels=INFO_LEVELS,
        info_level_labels=INFO_LEVEL_LABELS,
        task_definitions=TASK_DEFINITIONS,
        question_bank=bank,
        background_opacity=settings.get("background_opacity"),
        background_image=BACKGROUND_IMAGE_STATIC_PATH,
    )


# ── 設定 ────────────────────────────────────────────────────

@admin_bp.route("/api/settings", methods=["GET"])
def get_settings():
    return jsonify(_settings_payload())


@admin_bp.route("/api/settings", methods=["POST"])
def save_settings_api():
    payload = request.get_json(silent=True) or {}
    updates = {}
    if "rubric_weights" in payload:
        updates["rubric_weights"] = payload.get("rubric_weights")
    if "student_info_level" in payload:
        updates["student_info_level"] = payload.get("student_info_level")
    if "questions_per_task" in payload:
        updates["questions_per_task"] = payload.get("questions_per_task")
    if "background_opacity" in payload:
        updates["background_opacity"] = payload.get("background_opacity")
    if "ai_model_mode" in payload:
        err = _require_model_change_password(payload)
        if err:
            return err
        updates["ai_model_mode"] = payload.get("ai_model_mode")
    update_settings(**updates)
    return jsonify(_settings_payload())


# ── 生徒名簿（roster） ──────────────────────────────────────

@admin_bp.route("/api/students", methods=["GET"])
def list_students():
    return jsonify({"ok": True, "students": load_students()})


@admin_bp.route("/api/students/upload", methods=["POST"])
def upload_students():
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"ok": False, "error": "ファイルが選択されていません。"}), 400
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        return jsonify({"ok": False, "error": ".xlsx または .xls ファイルを選択してください。"}), 400
    try:
        students = import_students_from_excel(file.read())
        return jsonify({"ok": True, "students": students, "count": len(students)})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "error": f"読み込みエラー: {exc}"}), 500


@admin_bp.route("/api/students", methods=["POST"])
def upsert_student():
    payload = request.get_json(silent=True) or {}
    student = payload.get("student") or {}
    try:
        students = add_or_update_student(student)
        return jsonify({"ok": True, "students": students})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(exc)}), 400


@admin_bp.route("/api/students/<student_id>", methods=["DELETE"])
def remove_student(student_id):
    students = delete_student(student_id)
    return jsonify({"ok": True, "students": students})


# ── 問題バンク ──────────────────────────────────────────────

@admin_bp.route("/api/questions", methods=["GET"])
def list_questions():
    return jsonify({"ok": True, "questions": load_questions()})


@admin_bp.route("/api/questions/<task_type>", methods=["POST"])
def add_question(task_type):
    if task_type not in _QUESTION_TEXT_FIELD:
        return jsonify({"ok": False, "error": f"不明なタスク種別: {task_type}"}), 400
    payload = request.get_json(silent=True) or {}
    item = payload.get("item") or {}
    bank = add_questions(task_type, [item])
    return jsonify({"ok": True, "questions": bank})


@admin_bp.route("/api/questions/<task_type>/<question_id>", methods=["POST"])
def edit_question(task_type, question_id):
    if task_type not in _QUESTION_TEXT_FIELD:
        return jsonify({"ok": False, "error": f"不明なタスク種別: {task_type}"}), 400
    payload = request.get_json(silent=True) or {}
    updates = payload.get("item") or {}
    try:
        bank = update_question(task_type, question_id, updates)
        return jsonify({"ok": True, "questions": bank})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 404


@admin_bp.route("/api/questions/<task_type>/<question_id>", methods=["DELETE"])
def remove_question(task_type, question_id):
    if task_type not in _QUESTION_TEXT_FIELD:
        return jsonify({"ok": False, "error": f"不明なタスク種別: {task_type}"}), 400
    bank = delete_question(task_type, question_id)
    return jsonify({"ok": True, "questions": bank})


@admin_bp.route("/api/questions/<task_type>/generate", methods=["POST"])
def generate_questions_api(task_type):
    if task_type not in _QUESTION_TEXT_FIELD:
        return jsonify({"ok": False, "error": f"不明なタスク種別: {task_type}"}), 400

    payload = request.get_json(silent=True) or {}
    try:
        count = max(1, min(15, int(payload.get("count", 5))))
    except (TypeError, ValueError):
        count = 5

    api_key = get_openai_api_key()
    if not api_key:
        return jsonify({"ok": False, "error": "OpenAI API キーが未設定です。"}), 400

    settings = load_settings()
    model = resolve_ai_model_id(settings.get("ai_model_mode"))
    field = _QUESTION_TEXT_FIELD[task_type]
    existing_texts = [item.get(field, "") for item in load_questions().get(task_type, [])]

    try:
        generated = generate_questions(
            task_type=task_type, count=count, model=model, api_key=api_key, existing_texts=existing_texts
        )
        bank = add_questions(task_type, generated)
        return jsonify({"ok": True, "questions": bank, "generated_count": len(generated)})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "error": f"生成に失敗しました: {exc}"}), 500


# ── 受験結果 ────────────────────────────────────────────────

@admin_bp.route("/api/submissions", methods=["GET"])
def list_submissions():
    return jsonify({"ok": True, "submissions": get_submissions()})


@admin_bp.route("/api/submissions/<submission_id>", methods=["DELETE"])
def remove_submission(submission_id):
    ok = delete_submission(submission_id)
    if not ok:
        return jsonify({"ok": False, "error": "データが見つかりません。"}), 404
    return jsonify({"ok": True})


def _axis_average(task_results: list[dict], axis: str) -> float | None:
    values = []
    for result in task_results:
        scores = result.get("scores") or {}
        if axis in scores and scores[axis] is not None:
            values.append(scores[axis])
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _task_type_average(task_results: list[dict], task_type: str) -> float | None:
    values = [r.get("weighted_total") for r in task_results if r.get("task_type") == task_type and r.get("weighted_total") is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _latency_average(task_results: list[dict]) -> float | None:
    values = [r.get("response_latency_ms") for r in task_results if r.get("response_latency_ms") is not None]
    if not values:
        return None
    return round(sum(values) / len(values))


@admin_bp.route("/api/submissions/export", methods=["GET"])
def export_submissions():
    submissions = get_submissions()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "受験結果"
    headers = [
        "提出日時",
        "情報レベル",
        "クラス",
        "番号",
        "氏名",
        "総合スコア(100点満点)",
        "総合CEFR目安",
        "総合加重スコア",
        "リピート課題スコア",
        "文再構成課題スコア",
        "Q&A課題スコア",
        "流暢さ",
        "発音・明瞭性",
        "文法的正確性",
        "語彙運用",
        "応答速度スコア",
        "平均応答速度(ms)",
        "使用AIモデル",
    ]
    ws.append(headers)

    for s in submissions:
        task_results = s.get("task_results") or []
        student_info = s.get("student_info") or {}
        overall = s.get("overall") or {}
        ws.append(
            [
                s.get("submitted_at", ""),
                s.get("info_level", ""),
                student_info.get("class_name", ""),
                student_info.get("number", ""),
                student_info.get("name", ""),
                overall.get("score_100", ""),
                overall.get("cefr_band", ""),
                overall.get("weighted_total", ""),
                _task_type_average(task_results, "repeat"),
                _task_type_average(task_results, "sentence_build"),
                _task_type_average(task_results, "qa"),
                _axis_average(task_results, "fluency"),
                _axis_average(task_results, "pronunciation"),
                _axis_average(task_results, "accuracy"),
                _axis_average(task_results, "vocabulary"),
                _axis_average(task_results, "response_latency"),
                _latency_average(task_results),
                s.get("ai_model_mode", ""),
            ]
        )

    col_widths = [20, 10, 12, 8, 12, 12, 10, 10, 10, 10, 10, 8, 10, 10, 8, 10, 12, 12]
    for i, width in enumerate(col_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = width

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(
        buf,
        as_attachment=True,
        download_name="level_check_submissions.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
