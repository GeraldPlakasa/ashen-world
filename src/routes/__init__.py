"""
Flask Blueprints for Ashen World routes.

Import and register all blueprints here.
"""
from src.routes.main_routes import main_bp
from src.routes.auth_routes import auth_bp
from src.routes.admin_routes import admin_bp
from src.routes.character_routes import character_bp
from src.routes.family_routes import family_bp
from src.routes.stats_routes import stats_bp
from src.routes.api_routes import api_bp
from src.routes.chronicle_routes import chronicle_bp
from src.routes.artifact_routes import artifact_bp
from src.routes.map_routes import map_bp


def register_blueprints(app):
    """Register all blueprints with the Flask app."""
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(character_bp)
    app.register_blueprint(family_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(chronicle_bp)
    app.register_blueprint(artifact_bp)
    app.register_blueprint(map_bp)
