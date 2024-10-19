# app.py
# 这个文件是Flask应用的主入口,定义了各种路由和API端点
from flask import Flask, render_template, request, send_file, jsonify
from werkzeug.utils import secure_filename
import os
from dotenv import load_dotenv
from database import db_session, init_db, test_db_connection
from models import Order
from utils import process_orders, parse_orders, export_to_excel, allowed_file, remove_duplicates  # 删除 remove_duplicates
import logging
from docx import Document
from sqlalchemy import func

# 确保这行在其他导入之前
load_dotenv()

logging.basicConfig(level=logging.DEBUG)
logging.debug(f"DATABASE_URL in app.py: {os.getenv('DATABASE_URL')}")

app = Flask(__name__)

# 添加 UPLOAD_FOLDER 配置
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')

# 确保上传文件夹存在
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# 配置日志
logging.basicConfig(filename='order_processing.log', level=logging.INFO,
                    format='%(asctime)s - %(message)s', datefmt='%Y年%m月%d日%H点%m分')

# 数据库初始化
init_db()

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
            result = process_orders(input_data)
            logging.info(f"处理结果：{result}")
            
            return result, 200
        except Exception as e:
            logging.error(f"处理订单时发生错误：{str(e)}")
            return f"处理订单时发生错误：{str(e)}", 500
    return render_template('index.html')

@app.route('/parse', methods=['POST'])
def parse():
    batch_id = request.form['batch_id']
    parse_orders(batch_id)
    return "Orders parsed successfully", 200

@app.route('/export', methods=['POST'])
def export():
    batch_id = request.form['batch_id']
    file_path = export_to_excel(batch_id)
    return send_file(file_path, as_attachment=True)

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
        removed_count = remove_duplicates()
        return jsonify({"message": f"成功删除 {removed_count} 个重复订单", "removed_count": removed_count}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    test_db_connection()
    app.run(debug=True)
