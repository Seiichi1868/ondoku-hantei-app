"""Debate app 管理画面 Blueprint（背景・透過率の設定、保存済みセッションの一覧・削除）。"""
import os

from flask import Blueprint, jsonify, render_template, request

from debate.settings import (
    BACKGROUND_PRESETS,
    DEFAULT_BACKGROUND_OPACITY,
    JUDGE_MODEL_OPTIONS,
    TRANSCRIPTION_MODES,
    _clamp_opacity,
    load_settings,
    resolve_background,
    resolve_judge_model,
    update_settings,
)
from debate.storage import delete_session, list_sessions

debate_admin_bp = Blueprint("debate_admin", __name__, url_prefix="/debate/admin")

ADMIN_PASSWORD = os.environ.get("DEBATE_ADMIN_PASSWORD", "2479")


def _password_ok(payload: dict) -> bool:
    return str(payload.get("admin_password") or "") == ADMIN_PASSWORD


@debate_admin_bp.route("")
def admin_page():
    settings = load_settings()
    bg = resolve_background(settings.get("background_id"))
    return render_template(
        "debate/admin.html",
        backgrounds=BACKGROUND_PRESETS,
        background=bg,
        background_opacity=settings.get("background_opacity", DEFAULT_BACKGROUND_OPACITY),
    )


@debate_admin_bp.route("/api/settings", methods=["GET", "POST"])
def admin_settings():
    if request.method == "GET":
        settings = load_settings()
        judge_mode = settings.get("judge_model_mode", "4o")
        return jsonify(
            {
                "ok": True,
                **settings,
                **resolve_background(settings.get("background_id")),
                "judge_model": resolve_judge_model(judge_mode),
                "judge_model_modes": [
                    {"id": key, **JUDGE_MODEL_OPTIONS[key]} for key in JUDGE_MODEL_OPTIONS
                ],
            }
        )

    payload = request.get_json(silent=True) or {}
    if not _password_ok(payload):
        return jsonify({"ok": False, "error": "管理パスワードが違います。"}), 403

    updates = {}
    if "background_id" in payload:
        bg_id = str(payload.get("background_id") or "")
        if bg_id in BACKGROUND_PRESETS:
            updates["background_id"] = bg_id
    if "background_opacity" in payload:
        updates["background_opacity"] = _clamp_opacity(payload.get("background_opacity"))
    if "transcription_mode" in payload:
        mode = str(payload.get("transcription_mode") or "")
        if mode in TRANSCRIPTION_MODES:
            updates["transcription_mode"] = mode
    if "judge_model_mode" in payload:
        judge_mode = str(payload.get("judge_model_mode") or "")
        if judge_mode in JUDGE_MODEL_OPTIONS:
            updates["judge_model_mode"] = judge_mode

    if not updates:
        settings = load_settings()
        judge_mode = settings.get("judge_model_mode", "4o")
        return jsonify(
            {
                "ok": True,
                **settings,
                **resolve_background(settings.get("background_id")),
                "judge_model": resolve_judge_model(judge_mode),
                "judge_model_modes": [
                    {"id": key, **JUDGE_MODEL_OPTIONS[key]} for key in JUDGE_MODEL_OPTIONS
                ],
            }
        )

    saved = update_settings(**updates)
    judge_mode = saved.get("judge_model_mode", "4o")
    return jsonify(
        {
            "ok": True,
            **saved,
            **resolve_background(saved.get("background_id")),
            "judge_model": resolve_judge_model(judge_mode),
            "judge_model_modes": [
                {"id": key, **JUDGE_MODEL_OPTIONS[key]} for key in JUDGE_MODEL_OPTIONS
            ],
        }
    )


# ── 保存済みセッション一覧（途中まで進めたディベートの再開・削除） ──────
@debate_admin_bp.route("/api/sessions", methods=["GET"])
def admin_list_sessions():
    if not _password_ok(request.args.to_dict()):
        return jsonify({"ok": False, "error": "管理パスワードが違います。"}), 403
    return jsonify({"ok": True, "sessions": list_sessions(limit=500)})


@debate_admin_bp.route("/api/sessions/<session_id>/delete", methods=["POST"])
def admin_delete_session(session_id):
    payload = request.get_json(silent=True) or {}
    if not _password_ok(payload):
        return jsonify({"ok": False, "error": "管理パスワードが違います。"}), 403

    deleted = delete_session(session_id)
    if not deleted:
        return jsonify({"ok": False, "error": "セッションが見つかりません。"}), 404
    return jsonify({"ok": True})
