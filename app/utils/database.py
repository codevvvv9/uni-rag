from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.base import Base
import os
from dotenv import load_dotenv

# 初始化环境变量
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
# 创建数据库引擎
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
  """获取数据库会话"""
  db = SessionLocal()
  try:
    yield db
  finally:
    db.close()

def init_db():
  """初始化数据库 把所有定义好的ORM模型，**自动在对应数据库里生成数据表**，不存在则新建，已存在则跳过。
  """
  Base.metadata.create_all(bind=engine)