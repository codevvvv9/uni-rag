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
    """获取数据库会话

    该函数作为依赖项生成器，用于创建并管理数据库会话的生命周期。
    它确保在请求处理完成后正确关闭数据库连接，防止资源泄漏。

    Yields:
        Session: 一个 SQLAlchemy 数据库会话实例。
    """
    db = SessionLocal()
    try:
        # 生成数据库会话供调用者使用，并在执行完毕后确保关闭连接
        yield db
    finally:
        db.close()

def init_db():
  """初始化数据库 把所有定义好的ORM模型，**自动在对应数据库里生成数据表**，不存在则新建，已存在则跳过。
  """
  Base.metadata.create_all(bind=engine)