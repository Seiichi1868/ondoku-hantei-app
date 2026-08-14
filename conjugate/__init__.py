"""Vibe Speak Conjugate: tú(二人称単数)活用の瞬発力トレーナー。

news_app / level_check / debate とは完全に独立したBlueprintパッケージ。
他アプリのモジュールをimportしない（platformルール準拠）。
"""


def create_conjugate_blueprints() -> dict:
    from conjugate.routes import main_bp
    from conjugate.admin.routes import admin_bp

    return {"main": main_bp, "admin": admin_bp}
