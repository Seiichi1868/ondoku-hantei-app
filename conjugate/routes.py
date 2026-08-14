"""Vibe Speak Conjugate: 生徒（学習者）向けBlueprint。

  1. GET  /conjugate/                                    … トップ（カテゴリ・文型選択）
  2. POST /conjugate/api/sessions                         … セッション作成（JS経由）
  2b.POST /conjugate/start                                … セッション作成（フォーム送信フォールバック）
  3. GET  /conjugate/session/<id>                         … 出題・録音画面
  4. POST /conjugate/api/sessions/<id>/questions/<qid>/targets/<t>/answer … 採点
  5. POST /conjugate/api/sessions/<id>/finish              … セッション終了・サマリ保存
  6. GET  /conjugate/session/<id>/summary                  … 結果画面
"""
import logging
import mimetypes
import uuid
from pathlib import Path

from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from conjugate.audio_convert import normalize_audio_file
from conjugate.config import (
    ALLOWED_AUDIO_EXTENSIONS,
    AUDIO_TMP_DIR,
    MAX_AUDIO_BYTES,
    ensure_dirs,
)
from conjugate.data.conjugations import TENSE_LABELS, TENSE_ORDER
from conjugate.data.verbs import CATEGORY_LABELS, CATEGORY_ORDER
from conjugate.session_logic import build_session_questions, build_summary, grade_target, public_question
from conjugate.storage import (
    get_session_lock,
    load_session,
    load_settings,
    new_session_id,
    save_session,
    save_submission,
    weak_verbs_report,
)
from conjugate.transcription import transcribe_audio

logger = logging.getLogger(__name__)

main_bp = Blueprint(
    "conjugate",
    __name__,
    url_prefix="/conjugate",
    template_folder="templates",
    static_folder="static",
    static_url_path="/static",
)


START_ERROR_MESSAGES = {
    "no_questions": "出題できる問題がありません。管理画面でカテゴリと文型の設定を確認してください。",
}


@main_bp.after_request
def _revalidate_html(response):
    """HTMLは常に再検証させ、古いHTML（＝古いJS/CSSのURL）が残らないようにする。"""
    if response.mimetype == "text/html":
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response


@main_bp.route("/health")
def health():
    return jsonify({"ok": True, "app": "conjugate"})


@main_bp.route("/")
def index():
    settings = load_settings()
    return render_template(
        "conjugate/index.html",
        settings=settings,
        start_error=START_ERROR_MESSAGES.get(request.args.get("error", "")),
        category_labels=CATEGORY_LABELS,
        category_order=CATEGORY_ORDER,
        tense_labels=TENSE_LABELS,
        tense_order=TENSE_ORDER,
    )


def _prepare_session(raw_categories, raw_tenses, raw_count, raw_prioritize_weak) -> dict:
    """選択内容を検証・正規化して、未保存のセッションを組み立てる。"""
    ensure_dirs()
    settings = load_settings()

    categories = [c for c in (raw_categories or settings["enabled_categories"]) if c in CATEGORY_ORDER]
    categories = [c for c in categories if c in settings["enabled_categories"]] or settings["enabled_categories"]

    tenses = [t for t in (raw_tenses or settings["enabled_tenses"]) if t in TENSE_ORDER]
    tenses = [t for t in tenses if t in settings["enabled_tenses"]] or settings["enabled_tenses"]

    try:
        count = int(raw_count or settings["questions_per_session"])
    except (TypeError, ValueError):
        count = settings["questions_per_session"]
    count = max(3, min(50, count))

    prioritize_weak = bool(settings["prioritize_weak_verbs"] if raw_prioritize_weak is None else raw_prioritize_weak)
    gustar_enabled = bool(settings["gustar_enabled"])
    gustar_count = settings["gustar_per_session"] if gustar_enabled else 0

    questions = build_session_questions(
        categories=categories,
        tenses=tenses,
        count=count,
        targets_per_question=settings["targets_per_question"],
        gustar_enabled=gustar_enabled,
        gustar_count=gustar_count,
        prioritize_weak=prioritize_weak,
    )

    return {
        "session_id": new_session_id(),
        "categories": categories,
        "tenses": tenses,
        "strictness": settings["strictness"],
        "asr_engine": settings["asr_engine"],
        "whisper_model": settings["whisper_model"],
        "questions": questions,
        "current_index": 0,
        "status": "in_progress",
    }


@main_bp.route("/api/sessions", methods=["POST"])
def create_session():
    payload = request.get_json(silent=True) or {}
    session = _prepare_session(
        payload.get("categories"),
        payload.get("tenses"),
        payload.get("count"),
        payload.get("prioritize_weak_verbs"),
    )
    if not session["questions"]:
        return jsonify({"ok": False, "error": START_ERROR_MESSAGES["no_questions"]}), 400

    save_session(session)
    return jsonify({"ok": True, "session_id": session["session_id"]}), 201


@main_bp.route("/start", methods=["POST"])
def start_session():
    """index.jsが読み込めない環境でも練習を開始できるフォーム送信の受け口。"""
    session = _prepare_session(
        request.form.getlist("category"),
        request.form.getlist("tense"),
        request.form.get("count"),
        "prioritize_weak_verbs" in request.form,
    )
    if not session["questions"]:
        return redirect(url_for("conjugate.index", error="no_questions"), code=303)

    save_session(session)
    # 303にしてPOST→GETの読み替えをクライアントに依存させない
    return redirect(url_for("conjugate.quiz_screen", session_id=session["session_id"]), code=303)


@main_bp.route("/session/<session_id>")
def quiz_screen(session_id):
    session = load_session(session_id)
    if not session:
        return render_template("conjugate/not_found.html"), 404
    return render_template(
        "conjugate/quiz.html",
        session_id=session_id,
        asr_engine=session.get("asr_engine", "whisper"),
        tense_labels=TENSE_LABELS,
        category_labels=CATEGORY_LABELS,
    )


@main_bp.route("/api/sessions/<session_id>", methods=["GET"])
def get_session_api(session_id):
    session = load_session(session_id)
    if not session:
        return jsonify({"ok": False, "error": "セッションが見つかりません。"}), 404
    public = dict(session)
    public["questions"] = [public_question(q) for q in session["questions"]]
    return jsonify({"ok": True, "session": public})


def _resolve_extension(filename: str, mimetype: str | None) -> str:
    safe_name = secure_filename(filename or "")
    if "." in safe_name:
        return safe_name.rsplit(".", 1)[-1].lower()
    guessed = mimetypes.guess_extension(mimetype or "") or ""
    return guessed.lstrip(".").lower() or "webm"


def _find_question(session: dict, question_id: str) -> dict | None:
    for q in session["questions"]:
        if q["question_id"] == question_id:
            return q
    return None


@main_bp.route("/api/sessions/<session_id>/questions/<question_id>/targets/<target>/answer", methods=["POST"])
def submit_answer(session_id, question_id, target):
    with get_session_lock(session_id):
        session = load_session(session_id)
        if not session:
            return jsonify({"ok": False, "error": "セッションが見つかりません。"}), 404
        question = _find_question(session, question_id)
        if not question:
            return jsonify({"ok": False, "error": "問題が見つかりません。"}), 404
        if target not in question.get("targets", []):
            return jsonify({"ok": False, "error": "指定された文型はこの問題の対象ではありません。"}), 400

        transcript = ""
        transcript_source = "text"

        if "audio" in request.files and request.files["audio"].filename:
            audio_file = request.files["audio"]
            ext = _resolve_extension(audio_file.filename, audio_file.mimetype)
            if ext not in ALLOWED_AUDIO_EXTENSIONS:
                return jsonify({"ok": False, "error": f"対応していない音声形式です: {ext}"}), 400

            ensure_dirs()
            tmp_name = f"{session_id}_{question_id}_{target}_{uuid.uuid4().hex[:8]}.{ext}"
            tmp_path = AUDIO_TMP_DIR / tmp_name
            audio_file.save(tmp_path)

            try:
                if tmp_path.stat().st_size > MAX_AUDIO_BYTES:
                    tmp_path.unlink(missing_ok=True)
                    return jsonify({"ok": False, "error": "音声ファイルが大きすぎます。もう一度、短く録音してください。"}), 400

                norm_path = normalize_audio_file(tmp_path)
                whisper_model = session.get("whisper_model", "whisper-1")
                try:
                    transcript = transcribe_audio(norm_path, model=whisper_model, language="es")
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Whisper transcription failed")
                    return jsonify({"ok": False, "error": f"文字起こしに失敗しました: {exc}"}), 502
                transcript_source = "whisper"
            finally:
                tmp_path.unlink(missing_ok=True)
                norm_candidate = tmp_path.with_suffix(".norm.wav")
                norm_candidate.unlink(missing_ok=True)
        else:
            payload = request.form or request.get_json(silent=True) or {}
            transcript = str(payload.get("transcript") or "").strip()
            transcript_source = "web_speech"
            if not transcript:
                return jsonify({"ok": False, "error": "音声ファイルまたは認識テキストがありません。"}), 400

        strict = session.get("strictness") == "strict"
        result = grade_target(question, target, transcript, strict)
        result["transcript_source"] = transcript_source

        question.setdefault("answers", {})[target] = result
        if all(t in question["answers"] for t in question["targets"]):
            question["status"] = "done"
        save_session(session)

        return jsonify({"ok": True, "result": result})


@main_bp.route("/api/sessions/<session_id>/finish", methods=["POST"])
def finish_session(session_id):
    with get_session_lock(session_id):
        session = load_session(session_id)
        if not session:
            return jsonify({"ok": False, "error": "セッションが見つかりません。"}), 404

        summary = build_summary(session)
        session["status"] = "done"
        session["summary"] = summary
        save_session(session)

        save_submission(
            {
                "session_id": session_id,
                "categories": session.get("categories", []),
                "tenses": session.get("tenses", []),
                "total": summary["total"],
                "correct": summary["correct"],
                "accuracy": summary["accuracy"],
                "level_counts": summary["level_counts"],
            }
        )

    return jsonify({"ok": True, "summary": summary})


@main_bp.route("/session/<session_id>/summary")
def summary_screen(session_id):
    session = load_session(session_id)
    if not session:
        return render_template("conjugate/not_found.html"), 404
    summary = session.get("summary") or build_summary(session)
    return render_template(
        "conjugate/summary.html",
        session=session,
        summary=summary,
        category_labels=CATEGORY_LABELS,
        tense_labels=TENSE_LABELS,
    )


@main_bp.route("/api/weak-verbs")
def weak_verbs_api():
    return jsonify({"ok": True, "weak_verbs": weak_verbs_report()})
