# models.py
# 这个文件定义了数据库模型,使用SQLAlchemy ORM
from sqlalchemy import Column, Integer, String, Text, DateTime
from database import Base

class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True)
    batch_id = Column(String(50))
    original_text = Column(Text)
    address = Column(String(255))
    subject = Column(String(100))
    tutoring_time = Column(String(100))
    requirements = Column(Text)
    price = Column(String(50))
    teacher_gender = Column(String(20))
    student_info = Column(Text)
    order_number = Column(String(50))
    # 暂时注释掉 created_at 字段
    # created_at = Column(DateTime)
    # ... 其他字段 ...
