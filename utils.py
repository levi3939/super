import requests
from models import Order
from database import db_session
import os
from docx import Document

def process_orders(input_data):
    # 实现订单处理逻辑
    # 这里需要调用DeepSeek API进行数据清洗
    # 然后将订单存入数据库
    pass

def remove_duplicates():
    # 实现订单去重逻辑
    pass

def parse_orders(batch_id):
    # 实现订单解析逻辑
    # 这里需要调用DeepSeek API进行订单解析
    # 然后更新数据库中的订单信息
    pass

def export_to_excel(batch_id):
    # 实现导出到Excel的逻辑
    pass

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'doc', 'docx'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
