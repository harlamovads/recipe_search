class Config:
    SECRET_KEY = 'your_secret_key'
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://flask_user:flask_password@db/flask_app_db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False