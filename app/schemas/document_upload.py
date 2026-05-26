from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class DocumentUploadResponse(BaseModel):
    """文档上传记录响应模型"""
    id: int
    session_id: str
    document_name: str
    document_type: str
    file_size: Optional[int]
    upload_time: datetime
    create_time: datetime
    update_time: datetime
    class Config:
        from_attributes = True
        
# 会话文档信息响应模型
class SessionDocumentsResponse(BaseModel):
    """会话文档信息响应模型"""
    session_id: str
    has_documents: bool
    documents: List[DocumentUploadResponse]
    total_count: int
    # 允许 Pydantic 从任意对象的属性里读取数据，常用于 ORM 映射
    class Config:
        from_attributes = True
        
class SessionDocumentsSummary(BaseModel):
    """会话文档信息摘要响应模型"""
    session_id: str
    has_documents: bool
    latest_document_name: Optional[str] = None
    latest_document_type: Optional[str] = None
    latest_upload_time: Optional[datetime] = None
    total_documents: int = 0
    # 允许 Pydantic 从任意对象的属性里读取数据，常用于 ORM 映射
    class Config:
        from_attributes = True