"""Instagram 等からの一般公開用エントリポイント（``/public/`` 配下）。

学校用のメイン機能（``flask_app.views.main``）と全く同じ音読練習 UI
（``index.html``）を表示するだけの薄いブループリント。学校用の
``main_bp`` はそのまま流用せず、専用の ``session["user_id"]`` 名前空間
（``public_`` 接頭辞）を発行することで、学習履歴データを学校用と完全に
分離する。

``/public/admin`` や ``/public/health`` のような意図しないパスが増えない
よう、公開する経路は index ページのみに絞っている。
"""

from datetime import datetime

from flask import Blueprint, render_template, session

public_bp = Blueprint("public", __name__)

PUBLIC_USER_ID_PREFIX = "public_"


def _ensure_public_session_user() -> None:
    user_id = session.get("user_id")
    if not isinstance(user_id, str) or not user_id.startswith(PUBLIC_USER_ID_PREFIX):
        session["user_id"] = f"{PUBLIC_USER_ID_PREFIX}{datetime.now().strftime('%Y%m%d%H%M%S%f')}"


@public_bp.route("/")
def public_index():
    _ensure_public_session_user()
    return render_template("index.html")
