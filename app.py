# app.py
# 这个文件是Flask应用的主入口,定义了各种路由和API端点
from flask import Flask, render_template, request, send_file, jsonify, Response
from flask_socketio import SocketIO, emit
import os
from dotenv import load_dotenv
from database import db_session, init_db, test_db_connection
from models import Order
from utils import (
    process_orders, 
    parse_orders, 
    export_to_excel, 
    allowed_file, 
    remove_duplicates,
    calculate_commute_times  # 添加这个导入
)
import logging
from docx import Document
from sqlalchemy import func
from utils import parse_and_export_orders
import json
from werkzeug.utils import secure_filename
import traceback

# 确保这行在其他导入之前
load_dotenv()  # 这行会加载 .env 文件中的环境变量

logging.basicConfig(level=logging.DEBUG)
logging.debug(f"DATABASE_URL in app.py: {os.getenv('DATABASE_URL')}")

app = Flask(__name__)
socketio = SocketIO(app)

# 添加 UPLOAD_FOLDER 配置
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')

# 确保上传文件夹存在
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# 配置日志
logging.basicConfig(filename='order_processing.log', level=logging.INFO,
                    format='%(asctime)s - %(message)s', datefmt='%Y年%m%d日%H点%m分')

# 据库初始化
init_db()

exports_dir = os.path.join(os.getcwd(), 'exports')
if not os.path.exists(exports_dir):
    os.makedirs(exports_dir)

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

@app.route('/', methods=['GET', 'POST']) 
def index():
    if request.method == 'POST':
        try:
            input_data = ""
            if 'file' in request.files and request.files['file'].filename != '':
                file = request.files['file']
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    logging.info(f"处理文件：{file_path}")
                    
                    # 使用 python-docx 读取 .docx 文件
                    doc = Document(file_path)
                    input_data = "\n".join([paragraph.text for paragraph in doc.paragraphs])
                else:
                    logging.error("无效的文件类型")
                    return "无效的文件类型", 400
            elif 'order_text' in request.form:
                input_data = request.form['order_text']
            
            if not input_data.strip():
                logging.error("订单数据为空")
                return "订单数据不能为空", 400
            
            logging.info(f"输入数据长度：{len(input_data)}")
            result = process_orders(input_data, progress_callback)
            logging.info(f"处理结果：{result}")
            
            return result, 200
        except Exception as e:
            logging.error(f"处理订单时发生错误：{str(e)}")
            return f"处理订单时发生错误：{str(e)}", 500
    return render_template('index.html')

@app.route('/parse_and_export', methods=['POST'])
def parse_and_export():
    try:
        parsed_count, file_path = parse_and_export_orders(progress_callback)
        if file_path:
            return jsonify({
                "message": f"成功解析 {parsed_count} 个订单",
                "file_path": file_path
            }), 200
        else:
            return jsonify({"message": f"成功解析 {parsed_count} 个订单,但导出失败"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_batches', methods=['GET'])
def get_batches():
    batches = db_session.query(Order.batch_id, func.count(Order.id).label('count')) \
                        .group_by(Order.batch_id) \
                        .all()
    total_count = sum(batch.count for batch in batches)
    batch_list = [{'id': 'all', 'count': total_count}] + [{'id': batch.batch_id, 'count': batch.count} for batch in batches]
    return jsonify(batch_list)

@app.route('/remove_duplicates', methods=['POST'])
def handle_remove_duplicates():
    try:
        logging.info("开始执行去重操作")
        total_orders_before = db_session.query(Order).count()
        logging.info(f"去重前订单总数: {total_orders_before}")

        removed_count = remove_duplicates(progress_callback)

        total_orders_after = db_session.query(Order).count()
        logging.info(f"去重后订单总数: {total_orders_after}")
        logging.info(f"去重操作完成，删除了 {removed_count} 个重复订单")

        return jsonify({"message": f"成功删除 {removed_count} 个重复订单", "removed_count": removed_count}), 200
    except Exception as e:
        logging.error(f"去重操作失败：{str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/download/<path:filename>', methods=['GET'])
def download_file(filename):
    exports_dir = os.path.join(os.getcwd(), 'exports')
    file_path = os.path.join(exports_dir, filename)
    
    logging.info(f"尝试下载文件: {file_path}")
    
    if not os.path.exists(file_path):
        logging.error(f"文件不存在: {file_path}")
        return jsonify({"error": "文件不存在"}), 404
    
    try:
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        logging.error(f"发送文件时发生错误: {str(e)}")
        return jsonify({"error": "文件发送失败"}), 500

@app.route('/calculate_commute_times', methods=['POST'])
def handle_calculate_commute_times():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "没有上传文件"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "没有选择文件"}), 400
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            logging.info(f"成功保存上传的文件: {file_path}")
            
            target_address = request.form.get('target_address')
            if not target_address:
                return jsonify({"error": "未提供目标地址"}), 400
            
            new_file = calculate_commute_times(file_path, target_address, progress_callback)
            
            if os.path.exists(new_file):
                file_size = os.path.getsize(new_file)
                logging.info(f"文件生成成功: {new_file}, 大小: {file_size} 字节")
                return jsonify({
                    "message": "通勤时间计算完成",
                    "file_path": os.path.basename(new_file)  # 只返回文件名，不包含完整路径
                }), 200
            else:
                logging.error(f"文件不存在: {new_file}")
                return jsonify({"error": "生成文件失败"}), 500
        else:
            return jsonify({"error": "不允许的文件类型"}), 400
    except Exception as e:
        logging.error(f"计算通勤时间时发生错误: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

def progress_callback(progress, message):
    socketio.emit('progress_update', {'progress': progress, 'message': message})

def test_db_connection():
    try:
        db_session.execute("SELECT 1")
        logging.info("数据库连接测试成功")
    except Exception as e:
        logging.error(f"数据库连接测试失败：{str(e)}")

# 在主函数中调用这个测试
if __name__ == '__main__':
    test_db_connection()
    socketio.run(app, debug=True)
