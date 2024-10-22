class Config:
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:AAbb1234@10.10.201.13:3306/slips-data'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'QQww1234'
    UPLOAD_FOLDER = 'uploads/'
    ALLOWED_EXTENSIONS = {'zip'}
    STORAGE_PATH = '/home/slips/data/config/history'