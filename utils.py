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
from sqlalchemy import func

# 加载环境变量
load_dotenv()

# 初始化 OpenAI 客户端
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

def process_orders(input_data: str):
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
    for batch in batches:
        # 清洗数据并获取订单列表
        orders_list = clean_data_with_api(batch)

        # 将订单列表存入数据库
        save_to_database(orders_list)

        processed_orders += len(orders_list)

    # 记录日志
    log_order_processing(len(batches))

    return f"成功处理并存储 {processed_orders} 个订单，共 {len(batches)} 个批次。"

def parse_orders(batch_id):
    # 实现订单解析逻辑
    # 这里需要调用 DeepSeek API 进行订单解析
    # 然后更新数据库中的订单信息
    pass

def export_to_excel(batch_id):
    # 实现导出到 Excel 的逻辑
    pass

def allowed_file(filename):
    """
    检查文件是否是允许的类型。

    Args:
        filename (str): 文件名。

    Returns:
        bool: 如果是允许的文件类型则返回 True，否则返回 False。
    """
    ALLOWED_EXTENSIONS = {'doc', 'docx'}
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
                        "你是一个专门用于清理和格式化订单数据的助手。"
                        "请删除所有无关信息，只保留有效的订单数据。"
                        "请判断订单的分割点，并将每个订单作为单独的条目返回。"
                        "请将清理后的订单列表以 JSON 数组的形式返回，每个元素是一个订单的字符串。"
                        "注意：不要包含任何额外的文本或格式，例如代码块标记、注释或多余的空格。"
                    ),
                },
                {
                    "role": "user",
                    "content": f"请清理以下订单数据，删除所有无效信息，并分割成单独的订单：\n\n{batch}",
                },
            ],
            stream=False
        )

        cleaned_data = response.choices[0].message.content
        logging.debug(f"API 原始返回数据：{cleaned_data}")

        # 移除代码块标记（如果有）
        cleaned_data = cleaned_data.strip()

        # 正则表达式匹配 ``` 开头的代码块
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
            cleaned_data = re.sub(r",\s*]", "]", cleaned_data)  # 去除末尾多余的逗号

            try:
                orders_list = json.loads(cleaned_data)
                logging.info(f"修正后，API 清理后得到 {len(orders_list)} 个订单")
                return orders_list
            except json.JSONDecodeError as e:
                logging.error(f"修正后 JSON 解析仍然失败：{str(e)}")
                return []

    except Exception as e:
        logging.error(f"调用 DeepSeek API 时发生错误：{str(e)}")
        return []  # 如果 API 调用失败，返回空列表

def save_to_database(orders_list: List[str]):
    """
    将清洗后的订单列表存入数据库。

    Args:
        orders_list (List[str]): 清洗后的订单文本列表。
    """
    try:
        batch_id = generate_batch_id()
        logging.info(f"开始保存 {len(orders_list)} 个订单到数据库，批次ID：{batch_id}")
        for order_text in orders_list:
            # 创建新的 Order 对象
            new_order = Order(
                batch_id=batch_id,
                original_text=order_text,
                # 其他字段可以留空或设置为默认值
                order_number='',
                address='',
                subject='',
                time=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                requirements='',
                price=''
            )

            # 将新订单添加到数据库会话
            db_session.add(new_order)

        # 提交所有更改
        db_session.commit()
        logging.info(f"成功保存 {len(orders_list)} 个订单到数据库，批次ID：{batch_id}")
    except Exception as e:
        logging.error(f"保存订单到数据库时出错：{str(e)}")
        db_session.rollback()
    finally:
        # 关闭数据库会话
        db_session.close()

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
    # 使用时间戳生成唯一的批次 ID
    return datetime.now().strftime('%m%d%H%M%S')

def remove_duplicates():
    """
    检查数据库中的重复订单并删除，每个重复订单只保留最后一条（最晚入库的记录）。
    
    Returns:
        int: 删除的重复订单数量
    """
    try:
        # 查找重复的订单
        duplicates = db_session.query(
            Order.original_text,
            func.count(Order.id).label('count'),
            func.max(Order.id).label('max_id')  # 使用 max 而不是 min
        ).group_by(Order.original_text).having(func.count(Order.id) > 1).all()

        total_removed = 0
        for duplicate in duplicates:
            # 删除除最后一个实例外的所有重复订单
            removed = db_session.query(Order).filter(
                Order.original_text == duplicate.original_text,
                Order.id != duplicate.max_id  # 保留 max_id 对应的记录
            ).delete(synchronize_session=False)
            total_removed += removed

        db_session.commit()
        logging.info(f"成功删除 {total_removed} 个重复订单")
        return total_removed
    except Exception as e:
        db_session.rollback()
        logging.error(f"删除重复订单时发生错误：{str(e)}")
        raise
