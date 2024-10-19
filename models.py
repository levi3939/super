# models.py
# 这个文件定义了数据库模型,使用SQLAlchemy ORM
from sqlalchemy import Column, Integer, String, Text, DateTime
from database import Base

class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True)
    batch_id = Column(String(20), index=True)
    original_text = Column(Text)
    order_number = Column(String(50), index=True)
    address = Column(Text)
    subject = Column(String(100))
    time = Column(DateTime)  # 这列保留为订单创建时间
    tutoring_time = Column(String(100))  # 新增列，用于存储家教时间
    requirements = Column(Text)
    price = Column(String(20))
    teacher_gender = Column(String(10))
    student_info = Column(Text)

    def __init__(self, batch_id, original_text, order_number='', address='', subject='', time=None, tutoring_time='', requirements='', price='', teacher_gender='', student_info=''):
        self.batch_id = batch_id
        self.original_text = original_text
        self.order_number = order_number
        self.address = address
        self.subject = subject
        self.time = time
        self.tutoring_time = tutoring_time
        self.requirements = requirements
        self.price = price
        self.teacher_gender = teacher_gender
        self.student_info = student_info
