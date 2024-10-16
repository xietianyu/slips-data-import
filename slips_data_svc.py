from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
import os
from sqlalchemy import create_engine
from werkzeug.utils import secure_filename
import logging
from concurrent_log_handler import ConcurrentRotatingFileHandler
import numpy as np
from config import Config  # 导入配置文件

app = Flask(__name__)
app.config.from_object(Config)  # 使用配置文件中的参数

db = SQLAlchemy(app)

# 确保上传文件夹存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

if not app.debug:
    file_handler = ConcurrentRotatingFileHandler('app.log', maxBytes=10240, backupCount=10)
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
    file_handler.setFormatter(formatter)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Application startup')

# 首页：上传文件表单
@app.route('/')
def index():
    return render_template('index.html')

# 处理文件上传和数据导入
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part')
        app.logger.warning('No file part in request')
        return redirect(request.url)

    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        app.logger.warning('No selected file')
        return redirect(request.url)

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # 保存文件到服务器指定位置
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        try:
            import_data_to_db(file_path)
            app.logger.info(f'File {filename} uploaded and data imported successfully')
            flash('File uploaded and data imported successfully!', 'success')
        except Exception as e:
            flash(f'An error occurred: {e}')
            app.logger.error(f'Error importing data from file {filename}: {e}')
        return redirect(url_for('index'))
    else:
        flash('Invalid file type')
        app.logger.warning('Invalid file type')
        return redirect(request.url)

def import_data_to_db(file_path):
    # 使用 pandas 读取 HDF5 文件中的数据
    with pd.HDFStore(file_path, 'r') as store:
        # 遍历所有数据集的键
        engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'], pool_size=20, max_overflow=20, pool_timeout=30)
        keys = store.keys()
        for key in keys:
            df = store[key]
            parts = key.strip('/').split('/')
            if len(parts) == 4 and parts[0] == 'ods' and parts[1] == 'db':
                table_name = parts[3].replace('-', '_')
                app.logger.info(f'Processing table {table_name}')
                try:
                    with engine.connect() as conn:
                        with conn.begin() as transaction:
                            try:
                                df.to_sql(table_name, con=conn, if_exists='replace', index=False, chunksize=1000)
                            except Exception as e:
                                transaction.rollback()
                                app.logger.error(f"Error importing data: {e}")
                except Exception as e:
                    app.logger.error(f"Error importing data: {e}")
                    raise e
                app.logger.info(f'Data from {key} imported to table {table_name}')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)