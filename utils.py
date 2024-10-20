# utils.py
# 这个文件包含了一些实用函数，用于处理订单数据、解析订单、导出数据等操作

import requests
from models import Order
from database import db_session
import os
import math
from typing import List
import logging
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime
import json
from sqlalchemy import func, or_
import pandas as pd
from tkinter import Tk, filedialog
import os
import tkinter as tk
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import openpyxl
import traceback

# 加载环境变量
load_dotenv()

# 初始化 OpenAI 客户端
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

def process_orders(input_data: str, progress_callback):
    """
    处理输入的订单数据。

    Args:
        input_data (str): 输入的订单数据字符串。

    Returns:
        str: 处理结果的描述信息。
    """
    # 将输入数据分批
    batches = split_orders(input_data)

    processed_orders = 0
    total_batches = len(batches)
    
    for i, batch in enumerate(batches):
        # 清洗数据并获取订单列表
        orders_list = clean_data_with_api(batch)

        # 将订单列表存入数据
        save_to_database(orders_list)

        processed_orders += len(orders_list)
        progress = (i + 1) / total_batches * 100
        progress_callback(progress, f"已处理 {processed_orders} 个订单")

    # 记录日志
    log_order_processing(total_batches)

    return f"成功处理并存储 {processed_orders} 个订单，共 {total_batches} 个批次。"

def parse_orders():
    """
    解析数据库中尚未解析的订单。
    """
    try:
        unprocessed_orders = Order.query.filter(or_(
            Order.address == '',
            Order.address == None
        )).all()
        
        logging.info(f"找到 {len(unprocessed_orders)} 个未解析的订单")

        parsed_count = 0
        for order in unprocessed_orders:
            parsed_data = parse_order_with_api(order.original_text)
            
            if parsed_data:  # 只有在成功解析时才更新订单信息
                order.address = parsed_data.get('地址', '')
                order.subject = parsed_data.get('科目', '')
                order.tutoring_time = parsed_data.get('上课时间', '')
                order.requirements = parsed_data.get('要求', '')
                order.price = parsed_data.get('价格', '')
                order.teacher_gender = parsed_data.get('老师性别', '')
                order.student_info = parsed_data.get('学生情况', '')
                
                db_session.add(order)
                parsed_count += 1
            else:
                logging.warning(f"订单 {order.id} 解析失败")

        db_session.commit()
        logging.info(f"成功解析并更新 {parsed_count} 个订单")
        return parsed_count
    except Exception as e:
        db_session.rollback()
        logging.error(f"解析订单时发生错误：{str(e)}")
        raise

def parse_order_with_api(order_text):
    """
    使用 DeepSeek API 解析单个订单。
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一个专门用于解析订单信息的助手。请从给定的订单文本中提取以下信息："
                        "地址、科目、上课时间、要求、价格、老师性别、学生情况。"
                        "请以JSON格式返回结果，键名为上述字段名。不要包含何额外的解释或格式。"
                    ),
                },
                {
                    "role": "user",
                    "content": f"请解析以下订单信息：\n\n{order_text}",
                },
            ],
            stream=False
        )

        # 获取API响应内容
        content = response.choices[0].message.content.strip()
        logging.debug(f"API原始响应：{content}")

        # 尝试直接解析JSON
        try:
            parsed_data = json.loads(content)
            return parsed_data
        except json.JSONDecodeError:
            # 如果直接解析失败，尝试提取JSON部分
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                try:
                    parsed_data = json.loads(json_match.group())
                    return parsed_data
                except json.JSONDecodeError:
                    logging.error("无从API响应中提取有效的JSON数据")
            else:
                logging.error("API响应中没有找到JSON格式的数据")

        # 如果所有尝试都失败，返回空字典
        return {}

    except Exception as e:
        logging.error(f"调用 DeepSeek API 解析订单时发生错误：{str(e)}")
        return {}

def export_to_excel(data):
    """
    将解析后的订单结果导出为 Excel 文件。

    Args:
        data (list): 包含订单数据的列表。

    Returns:
        str: 导出的 Excel 文件名。
    """
    try:
        df = pd.DataFrame(data)
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"orders_export_{timestamp}.xlsx"
        
        # 确保 exports 目录存在
        exports_dir = os.path.join(os.getcwd(), 'exports')
        os.makedirs(exports_dir, exist_ok=True)
        
        # 构建完整的文件路径
        file_path = os.path.join(exports_dir, filename)
        
        # 导出到 Excel
        df.to_excel(file_path, index=False)
        
        logging.info(f"成功导出 {len(data)} 个订单到 {file_path}")
        return filename  # 只返回文件名,不返回完整路径
    except Exception as e:
        logging.error(f"导出订单到 Excel 时发生错误：{str(e)}")
        raise

def allowed_file(filename):
    """
    检查文件是否是允许的类型。

    Args:
        filename (str): 文件名。

    Returns:
        bool: 如果是允许的文件类型则返回 True，否则返回 False。
    """
    ALLOWED_EXTENSIONS = {'doc', 'docx', 'xlsx', 'xls'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def split_orders(input_data: str, max_chars: int = 4000) -> List[str]:
    """
    将输入的订单数据按照指定的最大字符数进行分批。

    Args:
        input_data (str): 输入的订单数据字符串。
        max_chars (int): 每批的最大字符数，默认为 4000。

    Returns:
        List[str]: 分批后的订单数据列表。
    """
    # 计算需要分成多少批
    num_batches = math.ceil(len(input_data) / max_chars)

    # 使用列表推导式创建分批后的订单数据
    batches = [input_data[i*max_chars:(i+1)*max_chars] for i in range(num_batches)]

    return batches

def clean_data_with_api(batch: str) -> List[str]:
    """
    使用 DeepSeek API 清理订单数据，删除无效信息，并分割订单。

    Args:
        batch (str): 需要清理的订单数据批次。

    Returns:
        List[str]: 清理并分割后的订单列表。
    """
    try:
        logging.info("调用 DeepSeek API 清理数据")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "是专门用于清理和格式化订单数据的助手。"
                        "请删除所有无关信息，只保留有效的订单数据。"
                        "请判断订单的分割点，并将每个单作为单的条目返回。"
                        "请将清理后的订单列表以 JSON 数组的形式返回，每个元素是一个订单的字符串。"
                        "注意：不要包含任何额外的文本或格式，例如代码块标记、注释或多余的空格。"
                    ),
                },
                {
                    "role": "user",
                    "content": f"请清理以下订单数据，删除所有无效信息，并分成单独的订单：\n\n{batch}",
                },
            ],
            stream=False
        )

        cleaned_data = response.choices[0].message.content
        logging.debug(f"API 原始返回数据：{cleaned_data}")

        # 移除代码块标记（如果有）
        cleaned_data = cleaned_data.strip()

        # 正则表达配 ``` 开头的代码块
        import re

        # 匹配 ``` 开头和结尾的内容，包括可能的语言标识
        code_block_pattern = r"^```(?:\w+)?\n(.*)```$"
        match = re.match(code_block_pattern, cleaned_data, re.DOTALL)
        if match:
            cleaned_data = match.group(1).strip()
        else:
            # 如果不匹配，再尝试去除单独的 ``` 标记
            if cleaned_data.startswith("```"):
                cleaned_data = cleaned_data[3:].strip()
            if cleaned_data.endswith("```"):
                cleaned_data = cleaned_data[:-3].strip()

        logging.debug(f"去除代码块标记后的数据：{cleaned_data}")

        # 尝试解析 JSON
        try:
            orders_list = json.loads(cleaned_data)
            logging.info(f"API 清理后得到 {len(orders_list)} 个订单")
            return orders_list
        except json.JSONDecodeError as e:
            logging.error(f"JSON 解析错误：{str(e)}")
            logging.error(f"API 返回的原始数据：{cleaned_data}")

            # 尝试修正常见的 JSON 格式错误
            cleaned_data = cleaned_data.replace("'", "\"")  # 替换单引号为双引号
            cleaned_data = re.sub(r",\s*]", "]", cleaned_data)  # 去末尾多余的逗号

            try:
                orders_list = json.loads(cleaned_data)
                logging.info(f"修正后，API 清理后得到 {len(orders_list)} 个订单")
                return orders_list
            except json.JSONDecodeError as e:
                logging.error(f"修正后 JSON 解析仍然失败：{str(e)}")
                return []

    except Exception as e:
        logging.error(f"调用 DeepSeek API 时发生错误：{str(e)}")
        return []  # 如果 API 调用失败，回空列表

def save_to_database(orders_list):
    try:
        if not isinstance(orders_list, list):
            raise TypeError("orders_list 必须是一个列表")
        
        batch_id = generate_batch_id()
        for order_text in orders_list:
            if not isinstance(order_text, str):
                raise TypeError("每个订单必须是字符串类型")
            
            order = Order(
                batch_id=batch_id,
                original_text=order_text,
                # 其他字段暂时留空，后续可以通过解析填充
                address='',
                subject='',
                tutoring_time='',
                requirements='',
                price='',
                teacher_gender='',
                student_info='',
                order_number=''
                # 暂时注释掉 created_at 字段
                # created_at=datetime.now()
            )
            db_session.add(order)
        db_session.commit()
        logging.info(f"成功保存 {len(orders_list)} 个订单到数据库，批次ID：{batch_id}")
    except Exception as e:
        db_session.rollback()
        logging.error(f"保存订单到数据库时出错：{str(e)}")
        raise

def log_order_processing(num_batches: int):
    """
    记录订单处理的日志信息。

    Args:
        num_batches (int): 处理的批次数。
    """
    now = datetime.now()
    log_message = f"{now.strftime('%Y年%m月%d日%H点%M分')} 处理了 {num_batches} 个订单批次。处理编号 {now.strftime('%m-%d-%H%M')}"
    logging.info(log_message)

def generate_batch_id() -> str:
    """
    生成批次 ID 的函数。

    Returns:
        str: 生成的批次 ID。
    """
    # 使用时间戳生唯一的批次 ID
    return datetime.now().strftime('%m%d%H%M%S')

def remove_duplicates(progress_callback):
    """
    检查数据库中的重复订单并删除，每个重复订单只保留最后一条（最晚入库的记录）。
    
    Returns:
        int: 删除的重复订单数量
    """
    try:
        # 首先检查是否存在任何重复
        duplicate_count = db_session.query(
            Order.original_text, func.count(Order.id)
        ).group_by(Order.original_text).having(func.count(Order.id) > 1).count()

        logging.info(f"检测到 {duplicate_count} 组重复订单")

        if duplicate_count == 0:
            logging.info("数据库中没有重复订单")
            return 0

        # 查找重复的订单
        duplicates = db_session.query(
            Order.original_text,
            func.count(Order.id).label('count'),
            func.max(Order.id).label('max_id')
        ).group_by(Order.original_text).having(func.count(Order.id) > 1).all()

        logging.info(f"找到 {len(duplicates)} 组重复订单")

        total_duplicates = len(duplicates)
        total_removed = 0
        for i, duplicate in enumerate(duplicates):
            logging.info(f"处理重复组 {i+1}/{total_duplicates}: 原始文本 '{duplicate.original_text[:50]}...'")
            # 删除除最后一个实例外的所有重复订单
            removed = db_session.query(Order).filter(
                Order.original_text == duplicate.original_text,
                Order.id != duplicate.max_id
            ).delete(synchronize_session=False)
            total_removed += removed
            logging.info(f"从该组中删除了 {removed} 个重复订单")
            
            progress = (i + 1) / total_duplicates * 100 if total_duplicates > 0 else 100
            progress_callback(progress, f"已处理 {i + 1}/{total_duplicates} 组重复订单")

        db_session.commit()
        logging.info(f"成功删除 {total_removed} 个重复订单")
        return total_removed
    except Exception as e:
        db_session.rollback()
        logging.error(f"删除重复订单时发生错误：{str(e)}")
        raise

def parse_and_export_orders(progress_callback):
    """
    解析数据库中尚未解析的订单,并同时导出为Excel文件。
    """
    try:
        unprocessed_orders = Order.query.filter(or_(
            Order.address == '',
            Order.address == None
        )).all()
        
        total_orders = len(unprocessed_orders)
        logging.info(f"找 {total_orders} 个未解析的订单")

        parsed_data = []
        for i, order in enumerate(unprocessed_orders):
            parsed_order = parse_order_with_api(order.original_text)
            
            if parsed_order:  # 只有在成功解析时才更新订单信息
                order.address = parsed_order.get('地址', '')
                order.subject = parsed_order.get('科目', '')
                order.tutoring_time = parsed_order.get('上课时间', '')
                order.requirements = parsed_order.get('要求', '')
                order.price = parsed_order.get('价格', '')
                order.teacher_gender = parsed_order.get('老师性别', '')
                order.student_info = parsed_order.get('学生情况', '')
                
                db_session.add(order)
                parsed_data.append({
                    '地址': order.address,
                    '科目': order.subject,
                    '上课时间': order.tutoring_time,
                    '要求': order.requirements,
                    '价格': order.price,
                    '老师性别': order.teacher_gender,
                    '学生情况': order.student_info,
                    '原始订单': order.original_text
                })
            else:
                logging.warning(f" {order.id} 析失败")
            
            progress = (i + 1) / total_orders * 90  # 解析占90%的进度
            progress_callback(progress, f"已解析 {i + 1}/{total_orders} 个订单")

        db_session.commit()
        logging.info(f"成功解析并更新 {len(parsed_data)} 个订单")

        if parsed_data:
            progress_callback(95, "正在导出到Excel...")
            file_path = export_to_excel(parsed_data)
            progress_callback(100, "导出完成")
            return len(parsed_data), file_path
        else:
            return 0, None

    except Exception as e:
        db_session.rollback()
        logging.error(f"解析订单时生错误：{str(e)}")
        raise

def read_excel_file(file_path):
    """
    读取Excel文件并返回DataFrame。

    Args:
        file_path (str): Excel文件的路径

    Returns:
        pd.DataFrame: 包含Excel数据的DataFrame
    """
    try:
        df = pd.read_excel(file_path, engine='openpyxl')
        return df
    except Exception as e:
        logging.error(f"读取Excel文件时发生错误: {str(e)}")
        raise

def geocode_baidu(address):
    ak = os.getenv('BAIDU_MAP_AK')
    if not ak:
        raise ValueError("未设置百度地图API密钥")
    
    url = "http://api.map.baidu.com/geocoding/v3/"
    params = {
        "address": address,
        "output": "json",
        "ak": ak
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    if data['status'] == 0:
        result = data['result']
        return (result['location']['lat'], result['location']['lng'])
    else:
        return None

def calculate_commute_times(excel_file, target_address, progress_callback):
    check_baidu_api_key()
    logging.info(f"开始处理文件: {excel_file}")
    logging.info(f"目标地址: {target_address}")

    try:
        # 读取Excel文件
        df = read_excel_file(excel_file)
        logging.info(f"成功读取Excel文件，共 {len(df)} 行数据")
        logging.info(f"列名: {df.columns.tolist()}")
        
        # 确保必要的列存在
        required_columns = ['地址', '科目', '上课时间', '要求', '价格', '老师性别', '学生情况', '原始订单']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Excel文件缺少以下必要的列: {', '.join(missing_columns)}")
        
        # 获取目标地址的坐标
        target_coords = geocode_baidu(target_address)
        if not target_coords:
            raise ValueError("无法获取目标地址的坐标")
        logging.info(f"目标地址坐标: {target_coords}")
        
        # 初始化新列
        df['通勤时间'] = ''
        
        total_rows = len(df)
        for index, row in df.iterrows():
            address = row['地址']
            try:
                # 获取订单地址的坐标
                coords = geocode_baidu(address)
                if coords:
                    # 计算直线距离
                    distance = geodesic(coords, target_coords).kilometers
                    
                    # 根据距离选择交通方式并计算时间
                    if distance < 5:  # 假设5公里以内用自行车
                        mode = "bicycling"
                    else:
                        mode = "transit"
                    
                    # 调用百度地图API获取实际通勤时间
                    commute_time = get_baidu_commute_time(coords, target_coords, mode)
                    
                    df.at[index, '通勤时间'] = commute_time
                    logging.info(f"地址 '{address}' 的通勤时间: {commute_time}")
                else:
                    df.at[index, '通勤时间'] = '地址无法解析'
                    logging.warning(f"无法解析地址: {address}")
            except Exception as e:
                df.at[index, '通勤时间'] = f'错误: {str(e)}'
                logging.error(f"处理地址 '{address}' 时发生错误: {str(e)}")
                logging.error(traceback.format_exc())
            
            # 更新进度
            progress = (index + 1) / total_rows * 100
            progress_callback(progress, f"已处理 {index + 1}/{total_rows} 个地址")
        
        # 修改这部分
        exports_dir = os.path.join(os.getcwd(), 'exports')
        output_filename = f"orders_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}_with_commute_times.xlsx"
        output_file = os.path.join(exports_dir, output_filename)
        df.to_excel(output_file, index=False)
        logging.info(f"尝试生成包含通勤时间的Excel文件: {output_file}")
        
        # 验证文件是否成功生成
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file)
            logging.info(f"成功生成文件: {output_file}, 大小: {file_size} 字节")
        else:
            logging.error(f"文件生成失败: {output_file}")
            raise FileNotFoundError(f"无法生成文件: {output_file}")
        
        return output_file
    except Exception as e:
        logging.error(f"计算通勤时间时发生错误: {str(e)}")
        logging.error(traceback.format_exc())
        raise

def get_baidu_commute_time(origin, destination, mode):
    """
    调用百度地图API获取通勤时间
    
    Args:
        origin (tuple): 起点坐标 (纬度, 经度)
        destination (tuple): 终点坐标 (纬度, 经度)
        mode (str): 交通方式 ('bicycling' 或 'transit')
    
    Returns:
        str: 通勤时间
    """
    ak = os.getenv('BAIDU_MAP_AK')  # 从环境变量获取百度地图API密钥
    if not ak:
        raise ValueError("未设置百度地图API密钥")
    
    url = f"http://api.map.baidu.com/directionlite/v1/{mode}"
    params = {
        "origin": f"{origin[0]},{origin[1]}",
        "destination": f"{destination[0]},{destination[1]}",
        "ak": ak
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    if data['status'] == 0:
        duration = data['result']['routes'][0]['duration']
        return f"{duration // 60}分钟"
    else:
        return "无法获取"

def check_baidu_api_key():
    ak = os.getenv('BAIDU_MAP_AK')
    if not ak:
        raise ValueError("未设置百度地图API密钥。请在 .env 文件中添加 BAIDU_MAP_AK=你的密钥")
    return ak

