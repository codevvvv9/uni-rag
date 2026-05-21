from sqlalchemy import Column, Integer, TEXT, String, TIMESTAMP
from sqlalchemy.sql import func
from .base import Base

# 知识库表， 和用户上传的文件关联， 以及后续的知识库构建和查询等功能关联
class KnowledgeBase(Base):
    __tablename__ = 'knowledge_bases'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False)
    file_name = Column(String(255), nullable=False)
    # created_at = Column(TIMESTAMP, nullable=False, server_default='CURRENT_TIMESTAMP')
    # updated_at = Column(TIMESTAMP, nullable=False, server_default='CURRENT_TIMESTAMP')
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())