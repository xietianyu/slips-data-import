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
import threading
import json
import requests
import time
import calendar

app = Flask(__name__)
app.config.from_object(Config)  # 使用配置文件中的参数

db = SQLAlchemy(app)
address=app.config['TEST_ADDRESS']
# 确保上传文件夹存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['STORAGE_PATH'], exist_ok=True)
os.makedirs(app.config['EXECUTE_PATH'], exist_ok=True)

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


# 每月手动测试master分支 合同计划加作业计划
@app.route('/monthly_test', methods=['POST'])
def monthly_test():
    stage='monthly'
    dirs=os.listdir(app.config['STORAGE_PATH'])
    threads=[]
    for  dir in dirs:
        if os.path.isdir(os.path.join(app.config['STORAGE_PATH'],dir)):
            thread=threading.Thread(target=multi_thread_execute_auto_test,args=(dir,stage))
            thread.start()
            threads.append(thread)
    return jsonify({"status": "Auto test execution started", "threads_started": len(threads)})

# 作业计划分支push 执行相应分支的自动化测试
@app.route('/auto_execute_branch/<plan_type>', methods=['POST'])
def execute_auto_test_branch(plan_type):
    stage='push'
    data = request.get_json()
    # 检查解析结果
    if data is None:
        return jsonify({"error": "Invalid JSON data"}), 400
    # 示例：提取 JSON 中的某个字段
    image_name = data.get("imageName")
    target_path=os.path.join(app.config['STORAGE_PATH'],plan_type,stage)
    thread=threading.Thread(target=thread_execute_plan_auto_test,args=(target_path,plan_type,stage,image_name))
    thread.start()
    return jsonify({"status": "Auto test execution started", "thread_started": 1,"plan_type":plan_type,"stage":stage,"image_name":image_name})
    

def thread_execute_plan_auto_test(path,plan_type,stage,image_name):
    dirs=os.listdir(path)
    for dir in dirs:
        base_path=os.path.join(path,dir)
        exec_path=os.path.join(app.config['EXECUTE_PATH'],plan_type,stage)
        if plan_type=='order_plan':
            planType='orderPlan'
            station='order'
            url = '/orderPlan/newOrderPlan'
            multiThreads=False
            mobiles=['18810322249']
            branch=app.config['ORDER_BRANCH']
        elif plan_type=='s1_plan':
            planType='jobPlan'
            station='S1'
            url = '/jobPlan/newJobPlan'
            multiThreads=False
            mobiles=['18810322249']
            branch=app.config['S1_BRANCH']
        elif plan_type=='d1_plan':
            planType='jobPlan'
            station='D1'
            url = '/jobPlan/newJobPlan'
            multiThreads=True
            mobiles=['13295852013']
            branch=app.config['D1_BRANCH']
        elif plan_type=='d2_plan':
            planType='jobPlan'
            station='D2'
            url = '/jobPlan/newJobPlan'
            multiThreads=True
            mobiles=['15868823089']
            branch=app.config['D2_BRANCH']
        elif plan_type=='t1_plan':
            planType='jobPlan'
            station='T1'
            url = '/jobPlan/newJobPlan'
            multiThreads=True
            mobiles=['18583685796']
            branch=app.config['T1_BRANCH']
        os.makedirs(exec_path, exist_ok=True)
        shutil.copy(os.path.join(base_path,'algo_config.json'),os.path.join(exec_path,'algo_config.json'))
        shutil.copy(os.path.join(base_path,'store.hdf5'),os.path.join(exec_path,'store.hdf5'))
        app.logger.info(f'Copying algo_config.json and store.hdf5 from {os.path.join(base_path)} to {exec_path}')
        utc_time = calendar.timegm(time.gmtime())
        app.logger.info(str(station) + '，计划号：Test' + str(station) + str(utc_time))
        planNo='Test' + str(station) + str(utc_time)
        jobplan_data = {
            "station": str(station),
            "planNo": planNo,
            "decisionNo": "",
            "scheduled": False,
            "planLimitTimeMin": 24,
            "planLimitTimeMax": 30,
            "previousTask": "",
            "launchTask": "",
            "rspType": "",
            "scheduleType": "",
            "scheduleSubClass": "",
            "policy": "",
            "matpool": "",
            "snapNo": "",
            "exec":"algo",
            "dataSource":"test",
            "multiThreads":multiThreads,
            "autoTestType":stage,
            "newImage":image_name
        }
        is_success=flow(planType, url, jobplan_data,multiThreads,stage,station,image_name)
        if is_success == False:
            app.logger.error(f'{branch}分支自动化测试失败，计划号：{planNo}，产线：{station}')
            send_markdown_message(f'{branch}分支自动化测试失败，计划号：{planNo}，产线：{station}',mobiles)
        else:
            app.logger.info(f'{branch}分支自动化测试成功，计划号：{planNo}，产线：{station}')
            send_markdown_message(f'{branch}分支自动化测试成功，计划号：{planNo}，产线：{station}',mobiles)


# master分支合并 release 执行合同和作业计划的自动测试
@app.route('/auto_execute', methods=['POST'])
def execute_auto_test():
    stage='merge'
    dirs=os.listdir(app.config['STORAGE_PATH'])
    threads=[]
    for  dir in dirs:
        if os.path.isdir(os.path.join(app.config['STORAGE_PATH'],dir)):
            thread=threading.Thread(target=multi_thread_execute_auto_test,args=(dir,stage))
            thread.start()
            threads.append(thread)
    return jsonify({"status": "Auto test execution started", "threads_started": len(threads)})

def multi_thread_execute_auto_test(dir,stage):
        base_path=os.path.join(app.config['STORAGE_PATH'],dir,stage)
        exec_path=app.config['EXECUTE_PATH']
        if dir=='order_plan':
            planType='orderPlan'
            station='order'
            url = '/orderPlan/newOrderPlan'
            multiThreads=False
            mobiles=['18810322249']
        elif dir=='s1_plan':
            planType='jobPlan'
            station='S1'
            url = '/jobPlan/newJobPlan'
            multiThreads=False
            mobiles=['18810322249']
        elif dir=='d1_plan':
            planType='jobPlan'
            station='D1'
            url = '/jobPlan/newJobPlan'
            multiThreads=True
            mobiles=['13295852013']
        elif dir=='d2_plan':
            planType='jobPlan'
            station='D2'
            url = '/jobPlan/newJobPlan'
            multiThreads=True
            mobiles=['15868823089']
        elif dir=='t1_plan':
            planType='jobPlan'
            station='T1'
            url = '/jobPlan/newJobPlan'
            multiThreads=True
            mobiles=['18583685796']
        sub_dirs=os.listdir(base_path)
        # sub_dirs_count=len(sub_dirs)
        unique_exec_path=os.path.join(exec_path,dir,stage)
        os.makedirs(unique_exec_path, exist_ok=True)
        for sub_dir in sub_dirs:
            shutil.copy(os.path.join(base_path,sub_dir,'algo_config.json'),os.path.join(unique_exec_path,'algo_config.json'))
            shutil.copy(os.path.join(base_path,sub_dir,'store.hdf5'),os.path.join(unique_exec_path,'store.hdf5'))
            app.logger.info(f'Copying algo_config.json and store.hdf5 from {os.path.join(base_path,sub_dir)} to {unique_exec_path}')
            utc_time = calendar.timegm(time.gmtime())  # 获取时间戳
            app.logger.info(str(station) + '，计划号：Test' + str(station) + str(utc_time))
            planNo='Test' + str(station) + str(utc_time)
            jobplan_data = {
                "station": str(station),
                "planNo": planNo,
                "decisionNo": "",
                "scheduled": False,
                "planLimitTimeMin": 24,
                "planLimitTimeMax": 30,
                "previousTask": "",
                "launchTask": "",
                "rspType": "",
                "scheduleType": "",
                "scheduleSubClass": "",
                "policy": "",
                "matpool": "",
                "snapNo": "",
                "exec":"algo",
                "dataSource":"test",
                "multiThreads":multiThreads,
                "autoTestType":stage
            }
            is_success=flow(planType, url, jobplan_data,multiThreads,stage,station)
            if is_success == False:
                app.logger.error(f'master分支自动化测试失败，计划号：{planNo}，产线：{station}')
                send_markdown_message(f'master分支自动化测试失败，计划号：{planNo}，产线：{station}',mobiles)
            else:
                app.logger.info(f'master分支自动化测试成功，计划号：{planNo}，产线：{station}')
                send_markdown_message(f'master分支自动化测试成功，计划号：{planNo}，产线：{station}',mobiles)

def is_plan_scheduling(plan_type,job_type):
    if plan_type=='jobPlan':
        url='/jobPlan/getAllJobPlans'
        data = {
            "jobType":job_type,
            "pageNo":1,
            "pageSize":10,
            "progress":["计算中"]
        }
    else:
        url='/orderPlan/getAllOrderPlans'
        data = {
            "pageNo":1,
            "pageSize":10,
            "progress":["计算中"]
        }
    res=check_res_code(url, data)
    if res is not False:  # 确认返回值code，不为0不执行
        res_data = extract_field_from_dict(
            json.loads(res.text), "data")  # 返回值转字典，并获取data值
        if res_data.get("jobPlans") == [] or res_data.get("orderPlans") == [] or res_data.get("total") ==0:
            app.logger.info('没有正在执行的任务')
            return False
        else:
            app.logger.info('存在正在执行的任务')
            return True
    return True


# 处理文件上传和数据导入
@app.route('/upload/<upload_type>/<stage>', methods=['POST'])
def upload_file(upload_type,stage):
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
        file_base_path=os.path.join(app.config['UPLOAD_FOLDER'], upload_type,stage)
        os.makedirs(file_base_path, exist_ok=True)
        file_path = os.path.join(file_base_path,filename)
        file.save(file_path)
        try:
            handle_uploaded_file(file_path, upload_type,stage)
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
    
def handle_uploaded_file(file_path,upload_type,stage):
    base_path = os.path.join(app.config['STORAGE_PATH'], upload_type,stage)
    # 清空目标目录的所有文件
    if stage!="monthly":
        if os.path.exists(base_path):
            shutil.rmtree(base_path)
    os.makedirs(base_path, exist_ok=True)
    # 根据上传的类型 解压zip文件到STORAGE_PATH中对应上传类型的文件夹中去 同名文件会覆盖
    with zipfile.ZipFile(file_path, 'r') as zip_ref:
        for file_info in zip_ref.infolist():
            if file_info.compress_type not in [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED]:
                raise ValueError(f"Unsupported compression method: {file_info.compress_type}")
        zip_ref.extractall(base_path)
    # 遍历文件夹 保证每个文件夹下都有hdf5文件和algo_config.json文件 如果缺失一个文件则提示zip压缩包内哪个文件夹缺失哪个文件 一旦缺少文件 就删除所有文件
    for dir in os.listdir(base_path):
        target_dir=os.path.join(base_path, dir)
        if os.path.isdir(target_dir):
            # 如果dirs下没有hdf5文件或者algo_config.json文件 则删除os.path.join(app.config['STORAGE_PATH'],upload_type)下的所有文件及其子文件夹
            app.logger.info(f'Processing folder {dir} in {base_path}')
            has_hdf5 = any(file.endswith('.hdf5') for file in os.listdir(target_dir))
            has_algo_config = 'algo_config.json' in os.listdir(target_dir)
            if not has_hdf5 or not has_algo_config:
                app.logger.error(f'Error: {target_dir} is missing hdf5 or algo_config.json file')
                raise Exception(f'An error occurred: {target_dir} is missing hdf5 or algo_config.json file')
            
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

def interface_post(url, data):  # 调用 post 接口
    response = requests.post(address + url, data=json.dumps(data))
    return response


def extract_field_from_dict(dictionary, field):  # 获取接口返回值指定字段值
    return dictionary.get(field)


def check_res_code(url, data):  # 确认接口返回值code和message
    res = interface_post(url, data)
    res_code = extract_field_from_dict(
        json.loads(res.text), "code")  # 获取返回值code
    res_message = extract_field_from_dict(
        json.loads(res.text), "message")  # 获取返回值message
    if res_code == 0:  # 确认返回值code
        return res
    else:
        print(str(url) + '调用失败，错误码:' + str(res_code))
        print('调用失败，message:' + str(res_message))
        return False


def check_res_progress(url, data):  # 获取排程当前进度
    res = check_res_code(url, data)
    if res is not False:  # 确认返回值code，不为0不执行轮循
        res_data = extract_field_from_dict(
            json.loads(res.text), "data")  # 返回值转字典，并获取data值
        progress = extract_field_from_dict(res_data, "progress")  # 获取排程当前进度
        return progress
    else:
        print('获取排程当前进度失败')
        return False


def new_plan(plan_type, url, data):  # 新建计划
    res = check_res_code(url, data)
    if res is not False:  # 确认返回值code，不为0不执行轮循
        res_data = extract_field_from_dict(
            json.loads(res.text), "data")  # 返回值转字典，并获取data值
        planid = extract_field_from_dict(res_data, str(plan_type)+"Id")
        print('新建计划成功,计划ID：'+str(planid))
        app.logger.info(f'New plan created successfully, plan ID: {planid}')
        return planid
    else:
        print('新建计划失败')
        app.logger.error('Failed to create new plan')
        return False


def schedule(plan_type, planid,multiThreads,stage,station,image_name=None):  # 自动排程
    # 每一分钟检查是否有正在执行的任务 如果有则等待 如果没有则执行自动排程
    while is_plan_scheduling(plan_type,station):
        time.sleep(60)
    url = '/' + plan_type + '/schedule'
    data = {
        plan_type+"Id": planid,
        "multiThreads": multiThreads,
        "exec": "algo",
        "autoTestType":stage,
        "newImage":image_name
    }
    res = check_res_code(url, data)
    if res is not False:  # 确认返回值code，不为0不执行轮循
        print('自动排程成功')
        app.logger.info('Automatic scheduling successful')
        return True
    else:
        print('自动排程失败')
        app.logger.error('Automatic scheduling failed')
        return False


def confirm_progress(plan_type, planid):  # 排程进度轮循
    url = '/' + plan_type + '/getScheduleStatus'
    data = {
        plan_type+"Id": planid
    }
    progress = check_res_progress(url, data)  # 获取进度
    if progress is not False:  # 确认返回值code，不为0不执行轮循
        print(progress)
        while progress < 100:
            time.sleep(60)  # 延迟10秒
            progress = check_res_progress(url, data)
            if progress is not False:  # 确认返回值code，不为0不执行轮循
                print(progress)
            else:
                return False
        print('确认进程为100，结束轮循')
        app.logger.info('Progress confirmed as 100, end polling')
        return True
    else:
        print('调用获取排程进度接口失败')
        app.logger.error('Failed to call the get schedule progress interface')
        return False


def check_task_scheduled(plan_type, planid):  # 确认获取已排任务
    url = '/' + plan_type + '/getScheduledJobs'
    data = {
        plan_type+"Id": planid
    }
    res = check_res_code(url, data)
    if res is not False:  # 确认返回值code，不为0不执行
        res_data = extract_field_from_dict(
            json.loads(res.text), "data")  # 返回值转字典，并获取data值
        if res_data == []:
            print('排程结束无结果')
            app.logger.info('Scheduling ended with no results')
            return False
        else:
            print('排程结束,排程结果正常')
            app.logger.info('Scheduling ended, scheduling results are normal')
            return True
            # print(res_data)
    else:
        print('调用获取已排任务接口失败')
        app.logger.error('Failed to call the get scheduled task interface')
        return False


def flow(plan_type, url, data,multiThreads,stage,station,image_name=None):  # 流程
    planid = new_plan(plan_type, url, data)  # 新建计划
    if planid is not False:
        schedule_situation = schedule(plan_type, planid,multiThreads,stage,station,image_name)  # 自动排程
        if schedule_situation is not False:
            confirm_progress_situation = confirm_progress(
                plan_type, planid)  # 轮循
            if confirm_progress_situation is not False:
                return check_task_scheduled(plan_type, planid)  # 获取已排任务
            else:
                return False
        else:
            return False
    else:
        return False

def send_markdown_message(content,mobiles):
    url=app.config['QYAPI']
    payload = {
        "msgtype": "text",
        "text": {
            "content": content,
            "mentioned_mobile_list": mobiles
        }
    }
    app.logger.info(f'Sending text message: {content}')
    response = requests.post(url,json=payload)
    return response.json()


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)