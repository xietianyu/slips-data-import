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
import zipfile
import tempfile
import shutil

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
@app.route('/upload/<upload_type>', methods=['POST'])
def upload_file(upload_type):
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
            handle_uploaded_file(file_path, upload_type)
            app.logger.info(f'File {filename} uploaded and data imported successfully')
            flash('File uploaded and data imported successfully!', 'success')
        except Exception as e:
            flash(f'An error occurred: {e}')
            app.logger.error(f'Error storage data from file {filename}: {e}')
        return redirect(url_for('index'))
    else:
        flash('Invalid file type')
        app.logger.warning('Invalid file type')
        return redirect(request.url)
    
def handle_uploaded_file(file_path,upload_type):
    base_path = os.path.join(app.config['STORAGE_PATH'], upload_type)
    # 清空目标目录的所有文件
    if os.path.exists(base_path):
        shutil.rmtree(base_path)
    os.makedirs(base_path, exist_ok=True)
    # 根据上传的类型 解压zip文件到STORAGE_PATH中对应上传类型的文件夹中去
    with zipfile.ZipFile(file_path, 'r') as zip_ref:
        zip_ref.extractall(base_path)
    # 遍历文件夹 保证每个文件夹下都有hdf5文件和algo_config.json文件 如果缺失一个文件则提示zip压缩包内哪个文件夹缺失哪个文件 一旦缺少文件 就删除所有文件
    for root, dirs, files in os.walk(base_path):
        # 如果dirs下没有hdf5文件或者algo_config.json文件 则删除os.path.join(app.config['STORAGE_PATH'],upload_type)下的所有文件及其子文件夹
        app.logger.info(f'Processing folder {dirs} in {root}')
        for subdir in dirs:
            subdir_path = os.path.join(root, subdir)
            has_hdf5 = any(file.endswith('.hdf5') for file in os.listdir(subdir_path))
            has_algo_config = 'algo_config.json' in os.listdir(subdir_path)

            if not has_hdf5 or not has_algo_config:
                flash(f'An error occurred: {subdir} is missing hdf5 or algo_config.json file')
                app.logger.error(f'Error: {subdir} is missing hdf5 or algo_config.json file')
                return
            
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