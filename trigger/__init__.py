"""Vibe Speak Trigger: 完全独立の Flask ブループリントパッケージ。

news_app / flask_app / level_check / conjugate 等、他アプリとのコード上の
依存関係は一切持たない（import しない）。UI の配色・雰囲気のみ Vibe Speak News を
参考に踏襲しているが、実装（CSS値・テンプレート）はこのパッケージ内に個別コピーする。
"""


def create_trigger_blueprints() -> dict:
    from trigger.routes import main_bp
    from trigger.admin.routes import admin_bp

    return {"main": main_bp, "admin": admin_bp}
