from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from config import Config


db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Faça login para continuar.'
login_manager.login_message_category = 'warning'


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from .auth import auth_bp
    from .main import main_bp
    from .users import users_bp
    from .records import records_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(records_bp)

    with app.app_context():
        db.create_all()
        User.create_default_admin()

    return app
