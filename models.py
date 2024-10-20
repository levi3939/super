# models.py
# 这个文件定义了数据库模型,使用SQLAlchemy ORM
from sqlalchemy import Column, Integer, String, Text, DateTime
from database import Base

class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True)
    original_text = Column(Text)
    # ... 其他字段 ...
