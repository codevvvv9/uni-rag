from schemas.document_upload import SessionDocumentsResponse, DocumentUploadResponse, SessionDocumentsSummary
from service.core.api.utils.file_utils import get_project_base_directory
from service.quick_parse_service import quick_parse_service
from service.document_upload_service import DocumentUploadService
from service.core.retrieval import retrieve_content
from service.core.chat import get_chat_completion
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
from utils.database import get_db
from typing import Optional, List
from models.knowledgebase import KnowledgeBase

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


# 快速文档解析接口
@router.post("/quick_parse")
async def quick_parse_document(
    session_id: str = Query(..., description="会话ID"),
    file: UploadFile = File(..., description="待解析的文件"),
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db),
):
    """快速解析文档接口
    - 支持文档格式：docx, pdf, txt
    - 限制文档页数不超过4页
    - 每个session_id只能传递一个文档
    - 解析结果存储到Redis，保存时间为2小时

    Args:
        session_id (str, optional): _description_. Defaults to Query(..., description="会话ID").
        file (UploadFile, optional): _description_. Defaults to File(..., description="待解析的文件").
        credentials (JwtAuthorizationCredentials, optional): _description_. Defaults to Security(access_security).
        db (Session, optional): _description_. Defaults to Depends(get_db).
    """
    try:
        user_id = str(credentials.subject.get("user_id"))
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )

        # 读取文件内容
        file_content = await file.read()
        # 获取文件信息
        file_size = len(file_content)
        file_extension = (
            os.path.splitext(file.filename)[1].lower() if file.filename else ""
        )
        document_type = file_extension.replace(".", "") if file_extension else "unknown"

        # 调用服务层处理业务逻辑
        result = quick_parse_service.quick_parse_document(
            session_id, file.filename, file_content
        )

        # 记录文档上传信息到数据库
        try:
            DocumentUploadService.create_upload_record(
                db=db,
                session_id=session_id,
                document_name=file.filename,
                document_type=document_type,
                file_size=file_size,
            )
            logger.info(
                f"文档上传记录已保存: session_id={session_id}, document_name={file.filename}"
            )
        except Exception as db_error:
            logger.error(f"保存文档上传记录失败: {str(db_error)}")
            # 数据库记录失败不影响主要功能，继续返回解析结果

        logger.info(f"用户{user_id}的文档解析完成，session_id={session_id}")
        return result

    except Exception as e:
        logger.exception(f"快速解析发生未知错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"内部服务器错误: {str(e)}",
        )


# 获取解析内容接口
@router.get("/get_parsed_content")
def get_parsed_content(
    session_id: str = Query(..., description="会话ID"),
    credentials: JwtAuthorizationCredentials = Security(access_security),
):
    # 获取已解析的文档
    # 先拿用户 id
    try:
        user_id = credentials.subject.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
            )

        # 调用服务层获取内容
        result = quick_parse_service.get_parsed_content(session_id)

        logger.info(f"用户 {user_id} 获取解析结果, session_id: {session_id}")

        return result
    except Exception as e:
        logger.error(
            f"用户 {user_id} 获取解析结果失败, session_id: {session_id}, 错误信息: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# 基于 ragFlow知识库对话
@router.post("/chat_on_docs")
async def chat_on_docs(
    session_id: str = Query(...),
    request: ChatRequest = Body(..., description="用户消息"),
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db),
):
    try:
        user_id = str(credentials.subject.get("user_id"))
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        question = request.message

        logger.info(f"开始处理用户{user_id}的请求")
        logger.info(f"用户{user_id}的请求内容: {question}")

        # 先尝试从知识库中检索内容，没有也不报错
        references = []

        try:
            logger.info(f"开始从知识库中检索内容")
            references = retrieve_content(user_id, question)
            logger.info(f"从知识库中检索到{len(references)}条内容")
        except Exception as e:
            logger.info(
                f"用户{user_id}没有知识库或者检索失败{str(e)}，讲不使用知识库内容"
            )
            references = []

        # 调用服务层处理业务逻辑
        logger.info(f"开始处理用户{user_id}的请求，生成回答中……")

        # 返回流式响应
        return StreamingResponse(
            get_chat_completion(session_id, question, references, user_id, db=db),
            media_type="text/event-stream",
        )

    except HTTPException as e:
        logger.error(f"处理用户请求时发生 HTTP 异常: {str(e)}")
        raise e
    except Exception as e:
        logger.exception(f"处理用户请求时发生未知错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"内部服务器错误: {str(e)}",
        )

@router.post("/upload_files")
async def upload_files(
    session_id: Optional[str] = Query(None),
    files: List[UploadFile] = File(...),
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
        
        # 如果没有 session_id，使用 user_id做为 session_id
        if session_id is None:
            session_id = user_id
        
        # 确保 storage/file目录存在
        storage_dir = os.path.join(get_project_base_directory(), "storage/file"  )
        if not os.path.exists(storage_dir):
            os.makedirs(storage_dir)
        
        # 根据 session_id 创建子文件夹
        session_dir = os.path.join(storage_dir, session_id)
        if not os.path.exists(session_dir):
            os.makedirs(session_dir)
        
        # 检查文件名是否重复
        existing_files = []
        for file in files:
            file_name = file.filename
            # 查询数据库中是否已经存在该文件名
            stmt = select(KnowledgeBase).where(
                KnowledgeBase.file_name == file_name,
                KnowledgeBase.user_id == user_id
            )
            
            existing_file = db.execute(stmt).scalar_one_or_none()
            if existing_file:
                existing_files.append(file_name)
                
        if existing_files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"文件名 {', '.join(existing_files)} 已经存在"
            )
        
        # 处理文件上传
        successful_files = []
        failed_files = []
        
        for file in files:
            file_name = os.path.basename(file.filename or "")
            if not file_name:
                failed_files.append("未知文件: 文件名不能为空")
                continue

            file_path = os.path.join(session_dir, file_name)
            
            try:
                # 读取文件内容不为空
                file_content = await file.read()
                if not file_content:
                    failed_files.append(f"{file_name}: 文件内容为空")
                    continue
                
                
                # 对于 Excel 文件进行额外验证
                lower_file_name = file_name.lower()
                if lower_file_name.endswith((".xlsx", ".xls")):
                    # 检查文件头， xlsx 文件应该是 zip 格式
                    if lower_file_name.endswith(".xlsx"):
                        if not file_content.startswith(b'PK'):
                            failed_files.append(f"{file_name}: 不是有效的 XLSX 文件格式，可能是 XLS 文件或文件已损坏")
                            continue
                    elif lower_file_name.endswith(".xls"):
                        # XLS 文件有特定文件头 0xD0 0xCF 0x11 0xE0
                        if not (
                            file_content.startswith(b'\xD0\xCF\x11\xE0')
                            or file_content.startswith(b'\x09\x08')
                        ):
                            failed_files.append(f"{file_name}: 不是有效的 XLS 文件格式，可能是 XLSX 文件或文件已损坏")
                            continue
                
                # 写入文件
                with open(file_path, "wb") as f:
                    f.write(file_content)
                
                # 验证文件大小
                if os.path.getsize(file_path) != len(file_content):
                    failed_files.append(f"{file_name}: 文件大小不匹配")
                    continue
                
                # 保存文件 URL 和 Base64 编码的文件流
                file_url = f"{storage_dir}/{session_id}/{file_name}"
                logger.info(f"正在处理文件 {file_name} ，URL: {file_url}")
                
                # 尝试解析和插入文档
                try:
                    from service.core.file_parser import execute_insert_process

                    execute_insert_process(file_path, file_name, user_id)
                    knowledge_base = KnowledgeBase(
                        user_id=user_id,
                        file_name=file_name,
                    )
                    db.add(knowledge_base)
                    db.commit()
                    successful_files.append(file_name)
                    logger.info(f"文件 {file_name} 处理完成并写入知识库")
                except Exception as e:
                    db.rollback()
                    logger.exception(f"解析或入库文件 {file_name} 失败: {str(e)}")
                    failed_files.append(f"{file_name}: {str(e)}")
                    continue

            except Exception as e:
                logger.exception(f"处理文件 {file_name} 时发生错误: {str(e)}")
                failed_files.append(f"{file_name}: {str(e)}")
                continue
            
        return {
            "status": "success" if successful_files and not failed_files else "partial_success" if successful_files else "failed",
            "successful_files": successful_files,
            "failed_files": failed_files,
            "total_count": len(files),
            "success_count": len(successful_files),
            "failed_count": len(failed_files),
        }
            
        
    except HTTPException as e:
        logger.error(f"处理用户请求时发生 HTTP 异常: {str(e)}")
        raise e
    except Exception as e:
        logger.exception(f"处理用户请求时发生未知错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"内部服务器错误: {str(e)}",
        )
        
@router.get("/sessions/{session_id}/documents", response_model=SessionDocumentsResponse)
async def get_session_documents(
    session_id: str,
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db)
):
    """获取指定对话的所有文档上传记录"""
    try:
        user_id = str(credentials.subject.get("user_id"))
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
        
        # 获取会话中的所有文档记录
        documents = DocumentUploadService.get_upload_records_by_session_id(session_id, db)
        has_documents = len(documents) > 0
        
        return SessionDocumentsResponse(
            session_id=session_id,
            has_documents=has_documents,
            documents=[
                DocumentUploadResponse.model_validate(document) for document in documents    
            ],
            total_count=len(documents),
        )
    except HTTPException as e:
        logger.error(f"获取会话文档信息失败: {str(e)}")
        raise e
    except Exception as e:
        logger.exception(f"获取会话文档信息失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
        
@router.get(
    "/sessions/{session_id}/documents/summary", 
    response_model=SessionDocumentsSummary   
)
async def get_session_document_summary(
    session_id: str,
    credentials: JwtAuthorizationCredentials = Security(access_security),
    db: Session = Depends(get_db)
):
    """获取指定对话的文档上传记录摘要"""
    try:
        user_id = str(credentials.subject.get("user_id"))
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
        
        # 检查是否有上传的文档
        has_documents = DocumentUploadService.has_uploaded_documents(session_id, db)
        
        # 获取最新的文档信息
        latest_document = DocumentUploadService.get_latest_document(session_id, db)
        
        # 获取总文档数量
        all_documents = DocumentUploadService.get_upload_records_by_session_id(session_id, db)
        total_documents = len(all_documents)
        
        return SessionDocumentsSummary(
            session_id=session_id,
            has_documents=has_documents,
            latest_document_name=latest_document.document_name if latest_document else None,
            latest_document_type=latest_document.document_type if latest_document else None,
            latest_upload_time=latest_document.upload_time if latest_document else None,
            total_documents=total_documents
        )
    except HTTPException as e:
        logger.error(f"获取会话文档摘要失败: {str(e)}")
        raise e        
    except Exception as e:
        logger.exception(f"获取会话文档摘要失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
