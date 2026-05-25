from sqlalchemy.orm import Session
from models.document_upload import DocumentUpload
from typing import List, Optional
from datetime import datetime


class DocumentUploadService:
    """文档上传记录服务"""

    @staticmethod
    def create_upload_record(
        session_id: str,
        document_name: str,
        document_type: str,
        db: Session,
        file_size: Optional[int] = None,
    ) -> DocumentUpload:
        """创建文档上传记录"""
        upload_record = DocumentUpload(
            session_id=session_id,
            document_name=document_name,
            document_type=document_type,
            file_size=file_size,
            upload_time=datetime.now(),
        )
        db.add(upload_record)
        db.commit()
        db.refresh(upload_record)
        return upload_record

    @staticmethod
    def get_upload_records_by_session_id(
        session_id: str, db: Session
    ) -> List[DocumentUpload]:
        """根据会话ID获取文档上传记录"""
        return (
            db.query(DocumentUpload)
            .filter(DocumentUpload.session_id == session_id)
            .order_by(DocumentUpload.upload_time.desc())
            .all()
        )

    @staticmethod
    def has_uploaded_documents(session_id: str, db: Session) -> bool:
        """检查指定会话是否有上传的文档"""
        count = db.query(DocumentUpload).filter(DocumentUpload.session_id == session_id).count()
        return count > 0
    
    @staticmethod
    def get_latest_document(session_id: str, db: Session) -> Optional[DocumentUpload]:
        """获取最新的文档上传记录"""
        return (
            db.query(DocumentUpload)
            .filter(DocumentUpload.session_id == session_id)
            .order_by(DocumentUpload.upload_time.desc())
            .first()
        )