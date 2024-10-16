class Config:
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:7p6chllz@mysql-mysql.kb-service.svc.cluster.local:3306/slips-data'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'QQww1234'
    UPLOAD_FOLDER = 'uploads/'
    ALLOWED_EXTENSIONS = {'hdf5'}