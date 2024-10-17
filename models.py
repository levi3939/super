from sqlalchemy import Column, Integer, String, Text
from database import Base

class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True)
    batch_id = Column(String(10))
    original_text = Column(Text)
    order_number = Column(String(50))
    address = Column(Text)
    subject = Column(String(100))
    time = Column(String(50))
    requirements = Column(Text)
    price = Column(String(20))

    def __init__(self, batch_id, original_text):
        self.batch_id = batch_id
        self.original_text = original_text
