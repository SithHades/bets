import os
import datetime
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'a_fallback_secret_key_for_development')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///bets.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

def inject_global_template_variables():
    return {
        'current_year': datetime.datetime.now().year,
        'current_server_time': datetime.datetime.now()
    }