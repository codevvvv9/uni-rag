from fastapi import (
    APIRouter,
    Body,
    HTTPException,
    UploadFile,
    File,
    Query,
    Security,
    status,
    Depends,
)
import uuid
from fastapi.responses import StreamingResponse
import os
from dotenv import load_dotenv
from typing import List, Optional
from fastapi_jwt import JwtAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import select
from utils import logger
from schemas.chat import SessionResponse, ChatRequest
from service.auth import access_security

# 加载环境变量
load_dotenv()

# 配置日志
logger.info(f"ES_HOST: {os.getenv('ES_HOST')}")
logger.info(f"ELASTICSEARCH_URL: {os.getenv('ELASTICSEARCH_URL')}")

# 生成 router
router = APIRouter()


# 创建一个新的对话 Session
@router.post("/create_session", response_model=SessionResponse)
async def create_session(
    credentials: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        # 从认证凭据的用户主体信息中，安全提取用户 ID
        user_id = credentials.subject.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized",
            )

        session_id = str(uuid.uuid4()).replace("-", "")[:16]

        return {
            "session_id": session_id,
            "status": "success",
            "message": "Session created successfully",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
