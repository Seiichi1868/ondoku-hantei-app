def create_news_blueprints() -> dict:
    from news_app.routes.main import main_bp
    from news_app.routes.admin import admin_bp
    from news_app.services.storage import appearance_context

    def inject_appearance():
        return appearance_context()

    main_bp.context_processor(inject_appearance)
    admin_bp.context_processor(inject_appearance)
    return {"main": main_bp, "admin": admin_bp}
