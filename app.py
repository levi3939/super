from flask import Flask, render_template, request, send_file
from werkzeug.utils import secure_filename
import os
from dotenv import load_dotenv
from database import db_session, init_db
from models import Order
from utils import process_orders, remove_duplicates, parse_orders, export_to_excel, allowed_file
import logging

load_dotenv()  # 加载环境变量

app = Flask(__name__)

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
        if 'file' in request.files:
            file = request.files['file']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                orders = process_orders(file_path)
            else:
                return "Invalid file type", 400
        else:
            orders = process_orders(request.form['order_text'])
        
        remove_duplicates()
        return "Orders processed successfully", 200
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

if __name__ == '__main__':
    app.run(debug=True)
