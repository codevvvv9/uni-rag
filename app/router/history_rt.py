from fastapi import (
    APIRouter, Depends, HTTPException, Query, Security, status
)
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session
from utils.database import get_db
from models.knowledgebase import KnowledgeBase
from schemas.message import FileResponse, SessionListResponse, SessionResponse, MessageResponse
from fastapi_jwt import JwtAuthorizationCredentials
from service.auth import access_security
from typing import List
from sqlalchemy import select, text
from urllib.parse import unquote # 导入 URL 解码工具，用来把 % 开头的编码转成正常文字。
from utils import logger

router = APIRouter()

@router.get("/get_messages", response_model=List[MessageResponse])
async def get_messages_by_session_id(
    session_id: str,
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db)
):
    try:
        user_id = str(credentials.subject.get("user_id"))
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
        
        # 查询messages 表中对应的 session_id的消息
        messages_data: List[Row] = db.execute(
            text(
                """
                SELECT message_id, session_id, user_question, model_answer, documents, recommended_questions, think, created_at FROM messages WHERE session_id = :session_id"
                """
            ),
            {"session_id": session_id}
        ).fetchall()
        
        # 构造返回数据
        messages: List[dict] = []
        for message in messages_data:
            messages.append({
                "message_id": message.message_id,
                "session_id": message.session_id,
                "user_question": message.user_question,
                "model_answer": message.model_answer,
                "documents": message.documents,
                "recommended_questions": message.recommended_questions,
                "think": message.think,
                "created_at": message.created_at.strftime("%Y-%m-%d %H:%M:%S")
            })
        
        return messages
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
        
@router.get("/get_sessions", response_model=SessionListResponse)
async def get_sessions_by_user_id(
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db)
):
    try:
        user_id = str(credentials.subject.get("user_id"))
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
        
        # 查询sessions 表中对应的 user_id的会话
        sessions_data: List[Row] = db.execute(
            text(
                """
                SELECT * FROM sessions WHERE user_id = :user_id"
                """
            ),
            {"user_id": user_id}
        ).fetchall()
        
        # 构造返回数据
        sessions: List[dict] = []
        for session in sessions_data:
            sessions.append(SessionResponse(
                session_id=session.session_id,
                session_name=session.session_name,
                user_id=session.user_id,                
                created_at=session.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                updated_at=session.updated_at.strftime("%Y-%m-%d %H:%M:%S")
            ))
        
        return {"user_id": user_id, "sessions": sessions}
    except HTTPException as e:
        logger.error(f"获取会话信息失败: {str(e)}")
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )