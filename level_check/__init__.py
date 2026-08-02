def create_level_check_blueprints() -> dict:
    from level_check.routes import main_bp
    from level_check.admin.routes import admin_bp

    return {"main": main_bp, "admin": admin_bp}
