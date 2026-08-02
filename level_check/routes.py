"""Speaking Level Check Test: 生徒向け Blueprint。

  1. GET  /level_check/                                    … 受験開始画面（情報要求レベルに応じたフォーム）
  2. GET  /level_check/session/<id>                        … 出題・録音・進行画面
  3. GET  /level_check/session/<id>/results                … 結果画面（CEFR帯・タスク別スコア）
"""
import logging
import mimetypes
import random
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

from level_check.config import (
    ALLOWED_AUDIO_EXTENSIONS,
    AUDIO_DIR,
    BACKGROUND_IMAGE_STATIC_PATH,
    MAX_AUDIO_BYTES,
    QA_DEFAULT_TIME_LIMIT_SEC,
    ensure_dirs,
    resolve_info_level,
)
from level_check.jobs import start_process_part_job
from level_check.models import new_part, new_session
from level_check.storage import (
    active_questions,
    get_part,
    get_session_lock,
    load_session,
    load_settings,
    save_session,
)
from level_check.tasks.definitions import TASK_DEFINITIONS

logger = logging.getLogger(__name__)

main_bp = Blueprint(
    "level_check",
    __name__,
    url_prefix="/level_check",
    template_folder="templates",
    static_folder="static",
    static_url_path="/static",
)

JST = timezone(timedelta(hours=9))


def _tokenize_sentence(sentence: str) -> list[str]:
    tokens = [t for t in re.split(r"\s+", sentence.strip()) if t]
    return tokens


def _build_parts_for_session(questions_per_task: int) -> list[dict]:
    parts: list[dict] = []

    repeat_pool = active_questions("repeat")
    for item in random.sample(repeat_pool, min(questions_per_task, len(repeat_pool))):
        parts.append(
            new_part(
                task_type="repeat",
                question_id=item["id"],
                question_text=item["text"],
                target_text=item["text"],
            )
        )

    build_pool = active_questions("sentence_build")
    for item in random.sample(build_pool, min(questions_per_task, len(build_pool))):
        words = _tokenize_sentence(item["target_sentence"])
        shuffled = words[:]
        random.shuffle(shuffled)
        parts.append(
            new_part(
                task_type="sentence_build",
                question_id=item["id"],
                question_text=item["target_sentence"],
                target_text=item["target_sentence"],
                shuffled_words=shuffled,
            )
        )

    qa_pool = active_questions("qa")
    for item in random.sample(qa_pool, min(questions_per_task, len(qa_pool))):
        parts.append(
            new_part(
                task_type="qa",
                question_id=item["id"],
                question_text=item["question"],
                time_limit_sec=item.get("time_limit_sec", QA_DEFAULT_TIME_LIMIT_SEC),
            )
        )

    return parts


def _resolve_extension(filename: str, mimetype: str | None) -> str:
    safe_name = secure_filename(filename or "")
    if "." in safe_name:
        return safe_name.rsplit(".", 1)[-1].lower()
    guessed = mimetypes.guess_extension(mimetype or "") or ""
    return guessed.lstrip(".").lower() or "webm"


@main_bp.route("/")
def index():
    settings = load_settings()
    info_level = resolve_info_level(settings.get("student_info_level"))
    return render_template(
        "level_check/index.html",
        info_level=info_level,
        task_definitions=TASK_DEFINITIONS,
        background_opacity=settings.get("background_opacity"),
        background_image=BACKGROUND_IMAGE_STATIC_PATH,
    )


@main_bp.route("/api/sessions", methods=["POST"])
def create_session():
    ensure_dirs()
    settings = load_settings()
    info_level = resolve_info_level(settings.get("student_info_level"))
    payload = request.get_json(silent=True) or {}

    student_info = {
        "class_name": str(payload.get("class_name") or "").strip(),
        "number": str(payload.get("number") or "").strip(),
        "name": str(payload.get("name") or "").strip(),
    }
    if info_level == "full" and not (student_info["name"] and student_info["class_name"] and student_info["number"]):
        return jsonify({"ok": False, "error": "氏名・クラス・番号を入力してください。"}), 400
    if info_level == "partial" and not (student_info["class_name"] and student_info["number"]):
        return jsonify({"ok": False, "error": "クラス・番号を入力してください。"}), 400
    if info_level == "none":
        student_info = {"class_name": "", "number": "", "name": ""}

    questions_per_task = int(settings.get("questions_per_task", 3))
    parts = _build_parts_for_session(questions_per_task)
    if not parts:
        return jsonify({"ok": False, "error": "出題可能な問題がありません。管理画面で問題を登録してください。"}), 400

    session = new_session(
        info_level=info_level,
        student_info=student_info,
        ai_model_mode=settings.get("ai_model_mode"),
        parts=parts,
    )
    save_session(session)
    return jsonify({"ok": True, "session_id": session["session_id"]}), 201


@main_bp.route("/session/<session_id>")
def progress_screen(session_id):
    session = load_session(session_id)
    if not session:
        return render_template("level_check/not_found.html"), 404
    settings = load_settings()
    return render_template(
        "level_check/progress.html",
        session=session,
        task_definitions=TASK_DEFINITIONS,
        qa_default_time_limit=QA_DEFAULT_TIME_LIMIT_SEC,
        background_opacity=settings.get("background_opacity"),
        background_image=BACKGROUND_IMAGE_STATIC_PATH,
    )


@main_bp.route("/api/sessions/<session_id>", methods=["GET"])
def get_session_api(session_id):
    session = load_session(session_id)
    if not session:
        return jsonify({"ok": False, "error": "セッションが見つかりません。"}), 404
    return jsonify({"ok": True, "session": session})


@main_bp.route("/api/sessions/<session_id>/parts/<part_id>", methods=["GET"])
def get_part_api(session_id, part_id):
    session = load_session(session_id)
    if not session:
        return jsonify({"ok": False, "error": "セッションが見つかりません。"}), 404
    part = get_part(session, part_id)
    if not part:
        return jsonify({"ok": False, "error": "問題が見つかりません。"}), 404
    return jsonify({"ok": True, "part": part})


@main_bp.route("/api/sessions/<session_id>/parts/<part_id>/audio", methods=["POST"])
def upload_part_audio(session_id, part_id):
    with get_session_lock(session_id):
        session = load_session(session_id)
        if not session:
            return jsonify({"ok": False, "error": "セッションが見つかりません。"}), 404
        part = get_part(session, part_id)
        if not part:
            return jsonify({"ok": False, "error": "問題が見つかりません。"}), 404
        if "audio" not in request.files:
            return jsonify({"ok": False, "error": "音声ファイルがありません。マイクの許可をご確認ください。"}), 400

        audio_file = request.files["audio"]
        if not audio_file.filename:
            return jsonify({"ok": False, "error": "音声ファイルが空です。もう一度録音してください。"}), 400

        ext = _resolve_extension(audio_file.filename, audio_file.mimetype)
        if ext not in ALLOWED_AUDIO_EXTENSIONS:
            return jsonify({"ok": False, "error": f"対応していない音声形式です: {ext}"}), 400

        ensure_dirs()
        session_dir = AUDIO_DIR / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{part_id}_{uuid.uuid4().hex[:8]}.{ext}"
        file_path = session_dir / filename
        audio_file.save(file_path)

        if file_path.stat().st_size > MAX_AUDIO_BYTES:
            file_path.unlink(missing_ok=True)
            return jsonify({"ok": False, "error": "音声ファイルが大きすぎます。もう一度、短く録音してください。"}), 400

        try:
            latency_ms = float(request.form.get("response_latency_ms", ""))
        except (TypeError, ValueError):
            latency_ms = None

        now = datetime.now(JST)
        part["audio_url"] = f"/level_check/audio/{session_id}/{filename}"
        part["response_latency_ms"] = latency_ms
        part["end_time"] = now.isoformat(timespec="seconds")
        part["transcript"] = ""
        part["transcript_error"] = ""
        part["status"] = "transcribing"
        save_session(session)
        response_data = dict(part)

    start_process_part_job(session_id, part_id, file_path)
    return jsonify({"ok": True, "part": response_data}), 202


@main_bp.route("/api/sessions/<session_id>/parts/<part_id>/retry", methods=["POST"])
def retry_part(session_id, part_id):
    with get_session_lock(session_id):
        session = load_session(session_id)
        if not session:
            return jsonify({"ok": False, "error": "セッションが見つかりません。"}), 404
        part = get_part(session, part_id)
        if not part:
            return jsonify({"ok": False, "error": "問題が見つかりません。"}), 404

        part.update(
            {
                "audio_url": "",
                "transcript": "",
                "transcript_error": "",
                "response_latency_ms": None,
                "status": "not_started",
                "scores": {},
                "comments": {},
                "weighted_total": None,
                "cefr_band": None,
            }
        )
        if session.get("status") == "done":
            session["status"] = "in_progress"
            session["overall"] = {"weighted_total": None, "cefr_band": None, "score_100": None}
        save_session(session)
        return jsonify({"ok": True, "part": part})


@main_bp.route("/session/<session_id>/results")
def results_screen(session_id):
    session = load_session(session_id)
    if not session:
        return render_template("level_check/not_found.html"), 404
    settings = load_settings()
    return render_template(
        "level_check/results.html",
        session=session,
        task_definitions=TASK_DEFINITIONS,
        background_opacity=settings.get("background_opacity"),
        background_image=BACKGROUND_IMAGE_STATIC_PATH,
    )


@main_bp.route("/audio/<session_id>/<path:filename>")
def serve_audio(session_id, filename):
    safe_session_id = Path(session_id).name
    safe_filename = Path(filename).name
    directory = AUDIO_DIR / safe_session_id
    return send_from_directory(directory, safe_filename)
