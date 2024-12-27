from flask import Flask
from .extensions import db, bootstrap
from app.config import Config
from .search_preprocessing import ensure_preprocessed_data

def create_app(config_class=Config):
    """Create and configure the Flask application.
    
    Args:
        config_class: Configuration class (default: Config)
        
    Returns:
        Flask application instance
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    bootstrap.init_app(app)

    with app.app_context():
        from .search_preprocessing import ensure_preprocessed_data
        ensure_preprocessed_data()
        from .routes import main_bp
        app.register_blueprint(main_bp)

    return app