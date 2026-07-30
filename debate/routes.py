"""Debate app Blueprint。

画面構成（PDA_debate_app_spec.md 「4. Cursorへの初回プロンプト」準拠）:
  1. GET  /debate                                          … ①論題入力画面
  2. GET  /debate/session/<id>                              … ②パート進行画面（録音+タイマー+ガイド文）
  3. GET  /debate/session/<id>/parts/<part>/review          … ③文字起こし確認画面

ジャッジ機能（仕様書 3.）はこのスケルトンには含めない。
"""
import logging
import mimetypes
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Blueprint, after_this_request, jsonify, render_template, request, send_from_directory, url_for
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
from debate.settings import load_settings, resolve_background
from debate.storage import get_part, get_session_lock, list_sessions, load_session, save_session
from debate.transcription import transcribe_audio

logger = logging.getLogger(__name__)

debate_bp = Blueprint("debate", __name__, url_prefix="/debate")

JST = timezone(timedelta(hours=9))

# 本番は gunicorn + gevent（monkey.patch_all）。通常の threading.Thread は greenlet 化され、
# Whisper の同期 HTTP がイベントループ／ワーカー全体を塞ぎうる。
# gevent.threadpool は本物の OS スレッドで実行するため、リクエスト処理を止めない。
_transcription_pool = None
_transcription_pool_lock = threading.Lock()


def _get_transcription_pool():
    global _transcription_pool
    with _transcription_pool_lock:
        if _transcription_pool is not None:
            return _transcription_pool
        try:
            from gevent.threadpool import ThreadPool

            _transcription_pool = ThreadPool(4)
            logger.info("Using gevent.threadpool.ThreadPool for Whisper jobs")
        except Exception:  # noqa: BLE001 - ローカル開発等で gevent が無い場合のフォールバック
            logger.warning("gevent.threadpool unavailable; falling back to threading.Thread")
            _transcription_pool = None
        return _transcription_pool


def _background_context() -> dict:
    settings = load_settings()
    background = resolve_background(settings.get("background_id"))
    return {
        "background": background,
        "background_opacity": settings.get("background_opacity"),
    }


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
        **_background_context(),
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
        return render_template(
            "debate/not_found.html", session_id=session_id, **_background_context()
        ), 404
    return render_template(
        "debate/progress.html",
        session=session,
        part_meta=_part_meta(),
        part_order=PART_ORDER,
        status_labels=STATUS_LABELS,
        **_background_context(),
    )


@debate_bp.route("/api/sessions/<session_id>/parts/<part>/start", methods=["POST"])
def start_part(session_id, part):
    with get_session_lock(session_id):
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


def _run_transcription_job(session_id: str, part: str, file_path: Path) -> None:
    """バックグラウンドスレッドでWhisper文字起こしを実行し、完了後にセッションへ反映する。

    アップロードのリクエスト処理をここで待たせないことで、
    次のパートの録音をすぐに開始できるようにする。
    """
    error_message = ""
    transcript = ""
    try:
        transcript = transcribe_audio(file_path)
    except RuntimeError as exc:
        error_message = str(exc)
    except Exception as exc:  # noqa: BLE001 - Whisper呼び出しは多様な例外を投げうるため
        logger.exception(
            "Whisper transcription failed for session=%s part=%s: %s", session_id, part, exc
        )
        error_message = f"文字起こしに失敗しました（{type(exc).__name__}）。ネットワーク状況をご確認のうえ再試行してください。"

    with get_session_lock(session_id):
        session = load_session(session_id)
        if not session:
            return
        part_data = get_part(session, part)
        # 処理中にリセット等で状態が変わっていた場合は、古い結果で上書きしない
        if not part_data or part_data.get("status") != "transcribing":
            return

        if error_message:
            part_data["transcript_error"] = error_message
        else:
            part_data["transcript_raw"] = transcript
            part_data["transcript_edited"] = transcript
            part_data["transcript_error"] = ""
        part_data["status"] = "needs_review"
        save_session(session)


def _start_transcription_job(session_id: str, part: str, file_path: Path) -> None:
    pool = _get_transcription_pool()
    if pool is not None:
        pool.spawn(_run_transcription_job, session_id, part, file_path)
        return
    thread = threading.Thread(
        target=_run_transcription_job,
        args=(session_id, part, file_path),
        daemon=True,
    )
    thread.start()


def _kickoff_transcription_after_response(session_id: str, part: str, file_path: Path) -> None:
    """HTTP レスポンス返却後に文字起こしを起動し、アップロード応答を遅らせない。"""

    @after_this_request
    def _start(response):
        try:
            _start_transcription_job(session_id, part, file_path)
        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to kick off transcription job for session=%s part=%s", session_id, part
            )
        return response


@debate_bp.route("/api/sessions/<session_id>/parts/<part>/audio", methods=["POST"])
def upload_part_audio(session_id, part):
    with get_session_lock(session_id):
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
        part_data["transcript_raw"] = ""
        part_data["transcript_edited"] = ""
        part_data["transcript_error"] = ""

        if part_data.get("start_time"):
            try:
                start_dt = datetime.fromisoformat(part_data["start_time"])
                part_data["elapsed_sec"] = max(0, round((end_time - start_dt).total_seconds()))
            except ValueError:
                part_data["elapsed_sec"] = None

        # 文字起こし（Whisper）は時間がかかりうるため、ここでは待たずに
        # レスポンス返却後に OS スレッドで実行する。
        # これにより、このパートの文字起こしが終わる前でも次のパートの録音を開始できる。
        part_data["status"] = "transcribing"
        save_session(session)
        response_data = dict(part_data)

    _kickoff_transcription_after_response(session_id, part, file_path)
    return jsonify(response_data), 202


@debate_bp.route("/api/sessions/<session_id>/parts/<part>/retranscribe", methods=["POST"])
def retranscribe_part(session_id, part):
    """録音済み音声はそのままに、文字起こしだけをやり直す（失敗時の再試行用）。"""
    with get_session_lock(session_id):
        session = load_session(session_id)
        if not session:
            return jsonify({"error": "セッションが見つかりません。"}), 404
        part_data = get_part(session, part)
        if not part_data:
            return jsonify({"error": f"不明なパート: {part}"}), 400
        if not part_data.get("audio_url"):
            return jsonify({"error": "音声データがないため再文字起こしできません。録音からやり直してください。"}), 400

        filename = Path(part_data["audio_url"]).name
        file_path = AUDIO_DIR / session_id / filename
        if not file_path.is_file():
            return jsonify({"error": "音声ファイルが見つかりません。録音からやり直してください。"}), 404

        part_data["status"] = "transcribing"
        part_data["transcript_error"] = ""
        save_session(session)
        response_data = dict(part_data)

    _kickoff_transcription_after_response(session_id, part, file_path)
    return jsonify(response_data), 202


@debate_bp.route("/api/sessions/<session_id>/parts/<part>", methods=["GET"])
def get_part_api(session_id, part):
    """進行画面／確認画面からのポーリング用の軽量エンドポイント。"""
    session = load_session(session_id)
    if not session:
        return jsonify({"error": "セッションが見つかりません。"}), 404
    part_data = get_part(session, part)
    if not part_data:
        return jsonify({"error": f"不明なパート: {part}"}), 400
    return jsonify(part_data)


# ── ③文字起こし確認画面 ───────────────────────────────────────
@debate_bp.route("/session/<session_id>/parts/<part>/review")
def review_screen(session_id, part):
    session = load_session(session_id)
    if not session:
        return render_template(
            "debate/not_found.html", session_id=session_id, **_background_context()
        ), 404
    part_data = get_part(session, part)
    if not part_data:
        return render_template(
            "debate/not_found.html", session_id=session_id, **_background_context()
        ), 404
    return render_template(
        "debate/review.html",
        session=session,
        part=part_data,
        meta=_part_meta()[part],
        **_background_context(),
    )


@debate_bp.route("/api/sessions/<session_id>/parts/<part>/confirm", methods=["POST"])
def confirm_part(session_id, part):
    payload = request.get_json(silent=True) or {}
    with get_session_lock(session_id):
        session = load_session(session_id)
        if not session:
            return jsonify({"error": "セッションが見つかりません。"}), 404
        part_data = get_part(session, part)
        if not part_data:
            return jsonify({"error": f"不明なパート: {part}"}), 400

        edited = str(payload.get("transcript_edited", part_data.get("transcript_edited", "")))
        part_data["transcript_edited"] = edited
        part_data["status"] = "confirmed"
        save_session(session)
        return jsonify(part_data)


@debate_bp.route("/api/sessions/<session_id>/parts/<part>/reset", methods=["POST"])
def reset_part(session_id, part):
    """そのパートだけ録音・やり直しができるよう、状態を初期化する。"""
    with get_session_lock(session_id):
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
                "transcript_error": "",
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
