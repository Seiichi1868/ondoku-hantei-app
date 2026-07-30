"""Debate app Blueprint。

画面構成（PDA_debate_app_spec.md 「4. Cursorへの初回プロンプト」準拠）:
  1. GET  /debate                                          … ①論題入力画面
  2. GET  /debate/session/<id>                              … ②パート進行画面（録音+タイマー+ガイド文）
  3. GET  /debate/session/<id>/parts/<part>/review          … ③文字起こし確認画面

ジャッジ機能（仕様書 3.）はこのスケルトンには含めない。
"""
import logging
import mimetypes
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from debate.config import (
    ALLOWED_AUDIO_EXTENSIONS,
    AUDIO_DIR,
    DEFAULT_MOTIONS,
    MAX_AUDIO_BYTES,
    PART_GUIDES,
    PART_LABELS,
    PART_ORDER,
    PART_ROLES,
    STATUS_LABELS,
    ensure_dirs,
)
from debate.models import new_session
from debate.storage import get_part, list_sessions, load_session, save_session
from debate.transcription import transcribe_audio

logger = logging.getLogger(__name__)

debate_bp = Blueprint("debate", __name__, url_prefix="/debate")

JST = timezone(timedelta(hours=9))


def _part_meta() -> dict:
    return {
        part: {
            "label": PART_LABELS[part],
            "role": PART_ROLES[part],
            "guide": PART_GUIDES[part],
        }
        for part in PART_ORDER
    }


def _resolve_extension(filename: str, mimetype: str | None) -> str:
    safe_name = secure_filename(filename or "")
    if "." in safe_name:
        return safe_name.rsplit(".", 1)[-1].lower()
    guessed = mimetypes.guess_extension(mimetype or "") or ""
    return guessed.lstrip(".").lower() or "webm"


# ── ①論題入力画面 ─────────────────────────────────────────────
@debate_bp.route("/")
def index():
    ensure_dirs()
    return render_template(
        "debate/index.html",
        default_motions=DEFAULT_MOTIONS,
        recent_sessions=list_sessions(limit=8),
    )


@debate_bp.route("/api/sessions", methods=["POST"])
def create_session():
    payload = request.get_json(silent=True) or {}
    motion = str(payload.get("motion") or "").strip()
    speaker_name = str(payload.get("speaker_name") or "").strip()

    if not motion:
        return jsonify({"error": "論題（motion）を入力してください。"}), 400
    if len(motion) > 500:
        return jsonify({"error": "論題は500文字以内で入力してください。"}), 400

    session = new_session(motion, speaker_name=speaker_name)
    save_session(session)
    return jsonify(session), 201


@debate_bp.route("/api/sessions/<session_id>", methods=["GET"])
def get_session_api(session_id):
    session = load_session(session_id)
    if not session:
        return jsonify({"error": "セッションが見つかりません。"}), 404
    return jsonify(session)


# ── ②パート進行画面 ────────────────────────────────────────────
@debate_bp.route("/session/<session_id>")
def progress_screen(session_id):
    session = load_session(session_id)
    if not session:
        return render_template("debate/not_found.html", session_id=session_id), 404
    return render_template(
        "debate/progress.html",
        session=session,
        part_meta=_part_meta(),
        part_order=PART_ORDER,
        status_labels=STATUS_LABELS,
    )


@debate_bp.route("/api/sessions/<session_id>/parts/<part>/start", methods=["POST"])
def start_part(session_id, part):
    session = load_session(session_id)
    if not session:
        return jsonify({"error": "セッションが見つかりません。"}), 404
    part_data = get_part(session, part)
    if not part_data:
        return jsonify({"error": f"不明なパート: {part}"}), 400

    part_data["start_time"] = datetime.now(JST).isoformat(timespec="seconds")
    part_data["end_time"] = None
    part_data["elapsed_sec"] = None
    part_data["status"] = "recording"
    save_session(session)
    return jsonify(part_data)


@debate_bp.route("/api/sessions/<session_id>/parts/<part>/audio", methods=["POST"])
def upload_part_audio(session_id, part):
    session = load_session(session_id)
    if not session:
        return jsonify({"error": "セッションが見つかりません。"}), 404
    part_data = get_part(session, part)
    if not part_data:
        return jsonify({"error": f"不明なパート: {part}"}), 400
    if "audio" not in request.files:
        return jsonify({"error": "音声ファイルがありません。"}), 400

    audio_file = request.files["audio"]
    if not audio_file.filename:
        return jsonify({"error": "音声ファイルが空です。"}), 400

    ext = _resolve_extension(audio_file.filename, audio_file.mimetype)
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        return jsonify({"error": f"対応していない音声形式です: {ext}"}), 400

    ensure_dirs()
    session_dir = AUDIO_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{part}_{uuid.uuid4().hex[:8]}.{ext}"
    file_path = session_dir / filename
    audio_file.save(file_path)

    if file_path.stat().st_size > MAX_AUDIO_BYTES:
        file_path.unlink(missing_ok=True)
        return jsonify({"error": "音声ファイルが大きすぎます（上限25MB）。"}), 400

    end_time = datetime.now(JST)
    part_data["end_time"] = end_time.isoformat(timespec="seconds")
    part_data["audio_url"] = url_for(
        "debate.serve_audio", session_id=session_id, filename=filename
    )

    if part_data.get("start_time"):
        try:
            start_dt = datetime.fromisoformat(part_data["start_time"])
            part_data["elapsed_sec"] = max(0, round((end_time - start_dt).total_seconds()))
        except ValueError:
            part_data["elapsed_sec"] = None

    part_data["status"] = "transcribing"
    save_session(session)

    try:
        transcript = transcribe_audio(file_path)
        part_data["transcript_raw"] = transcript
        part_data["transcript_edited"] = transcript
        part_data["status"] = "needs_review"
        save_session(session)
        return jsonify(part_data)
    except RuntimeError as exc:
        # パート単位でエラーが起きても他パートのデータは保持したまま、このパートだけ確認待ちに戻す
        part_data["status"] = "needs_review"
        save_session(session)
        return jsonify({"error": str(exc), "part": part_data}), 502
    except Exception as exc:
        logger.exception("Whisper transcription failed: %s", exc)
        part_data["status"] = "needs_review"
        save_session(session)
        return jsonify({"error": f"文字起こしに失敗しました: {exc}", "part": part_data}), 502


# ── ③文字起こし確認画面 ───────────────────────────────────────
@debate_bp.route("/session/<session_id>/parts/<part>/review")
def review_screen(session_id, part):
    session = load_session(session_id)
    if not session:
        return render_template("debate/not_found.html", session_id=session_id), 404
    part_data = get_part(session, part)
    if not part_data:
        return render_template("debate/not_found.html", session_id=session_id), 404
    return render_template(
        "debate/review.html",
        session=session,
        part=part_data,
        meta=_part_meta()[part],
    )


@debate_bp.route("/api/sessions/<session_id>/parts/<part>/confirm", methods=["POST"])
def confirm_part(session_id, part):
    session = load_session(session_id)
    if not session:
        return jsonify({"error": "セッションが見つかりません。"}), 404
    part_data = get_part(session, part)
    if not part_data:
        return jsonify({"error": f"不明なパート: {part}"}), 400

    payload = request.get_json(silent=True) or {}
    edited = str(payload.get("transcript_edited", part_data.get("transcript_edited", "")))
    part_data["transcript_edited"] = edited
    part_data["status"] = "confirmed"
    save_session(session)
    return jsonify(part_data)


@debate_bp.route("/api/sessions/<session_id>/parts/<part>/reset", methods=["POST"])
def reset_part(session_id, part):
    """そのパートだけ録音・やり直しができるよう、状態を初期化する。"""
    session = load_session(session_id)
    if not session:
        return jsonify({"error": "セッションが見つかりません。"}), 404
    part_data = get_part(session, part)
    if not part_data:
        return jsonify({"error": f"不明なパート: {part}"}), 400

    part_data.update(
        {
            "audio_url": "",
            "transcript_raw": "",
            "transcript_edited": "",
            "start_time": None,
            "end_time": None,
            "elapsed_sec": None,
            "status": "not_started",
        }
    )
    save_session(session)
    return jsonify(part_data)


@debate_bp.route("/audio/<session_id>/<path:filename>")
def serve_audio(session_id, filename):
    safe_session_id = Path(session_id).name
    safe_filename = Path(filename).name
    directory = AUDIO_DIR / safe_session_id
    return send_from_directory(directory, safe_filename)
