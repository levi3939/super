# models.py
# 这个文件定义了数据库模型,使用SQLAlchemy ORM
from sqlalchemy import Column, Integer, String, Text, DateTime
from database import Base
from datetime import datetime

class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True)
    batch_id = Column(String(20), index=True)
    original_text = Column(Text)
    order_number = Column(String(50), index=True)
    address = Column(Text)
    subject = Column(String(100))
    time = Column(DateTime, default=datetime.utcnow)  # 修改为 DateTime 类型，并设置默认值
    requirements = Column(Text)
    price = Column(String(20))

    def __init__(self, batch_id, original_text, order_number, address, subject, time, requirements, price):
        self.batch_id = batch_id
        self.original_text = original_text
        self.order_number = order_number
        self.address = address
        self.subject = subject
        self.time = datetime.strptime(time, '%Y-%m-%d %H:%M:%S') if time else datetime.utcnow()  # 添加时间转换
        self.requirements = requirements
        self.price = price
