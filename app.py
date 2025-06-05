from flask import Flask
from flask_login import LoginManager
from config import Config, inject_global_template_variables
from models import db, User
from routes.auth import auth
from routes.main import main
from routes.bets import bets
from routes.blockchain import blockchain_bp
from routes.services import services
from cli import register_cli_commands

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    
    # Initialize login manager
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register context processor
    app.context_processor(inject_global_template_variables)

    # Register blueprints
    app.register_blueprint(auth)
    app.register_blueprint(main)
    app.register_blueprint(bets)
    app.register_blueprint(blockchain_bp)
    app.register_blueprint(services)

    # Register CLI commands
    register_cli_commands(app)

    # Create tables
    with app.app_context():
        db.create_all()

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)