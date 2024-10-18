# database.py
# 这个文件设置了数据库连接和会话管理
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import os
from dotenv import load_dotenv
import pymysql
import logging

load_dotenv()  # 这行会加载 .env 文件中的环境变量

# 替换 MySQLdb 为 PyMySQL
pymysql.install_as_MySQLdb()

def create_database_if_not_exists(url):
    db_name = url.split('/')[-1]
    engine = create_engine(url.rsplit('/', 1)[0])
    conn = engine.connect()
    conn.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
    conn.close()

database_url = os.getenv('DATABASE_URL')
create_database_if_not_exists(database_url)

engine = create_engine(database_url)
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()

def test_db_connection():
    try:
        db_session.execute("SELECT 1")
        logging.info("数据库连接测试成功")
    except Exception as e:
        logging.error(f"数据库连接测试失败：{str(e)}")

def init_db():
    import models
    try:
        Base.metadata.create_all(bind=engine)
        logging.info("数据库表创建成功")
        test_db_connection()
    except Exception as e:
        logging.error(f"创建数据库表时出错：{str(e)}")

def table_exists(table_name):
    ins = inspect(engine)
    return ins.has_table(table_name)
