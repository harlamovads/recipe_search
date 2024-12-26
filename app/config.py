import os

class Config:
    """Flask application configuration class."""
    
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your_secret_key'
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://app_user:app_password@db/recipes_db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False