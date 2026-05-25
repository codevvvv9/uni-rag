"""
快速文档解析服务
处理文档解析和Redis存储相关的业务逻辑
"""

import os
import redis
from docx import Document
from io import BytesIO
from fastapi import HTTPException
from utils import logger
from typing import Tuple
import pdfplumber

class QuickParseService:
    """快速文档解析服务类

    支持的文件格式及限制:
    - PDF: 不超过4页
    - DOCX: 不超过4000字符
    - TXT: 不超过4000字符

    解析结果存储到Redis，默认保存2小时
    """

    def __init__(self):
        # Redis 连接配置
        self.redis_host = os.getenv("REDIS_HOST", "redis")
        self.redis_port = int(os.getenv("REDIS_PORT", 6379))
        self.redis_db = int(os.getenv("REDIS_DB", 0))

        self.redis_client = redis.Redis(
            host=self.redis_host,
            port=self.redis_port,
            db=self.redis_db,
            decode_responses=True,
        )

        # 支持的文件格式
        self.supported_formats = ["pdf", "docx", "txt"]
        # 页数限制 仅用于 pdf 4页
        self.max_pages = 4

        # 字符数限制 仅用于 docx 4000字符 txt 4000字符
        self.max_characters = 4000

        # Redis 存储时长 默认2小时
        self.redis_expire_seconds = int(os.getenv("REDIS_EXPIRE", 7200))

    def validate_file_format(self, filename: str) -> str:
        """
        校验文件格式
        :param filename: 文件名
        :return: 文件格式
        """
        if not filename:
            raise HTTPException(status_code=400, detail="文件名不能为空")

        file_extension = filename.lower().split(".")[-1]
        if file_extension not in self.supported_formats:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件格式: {file_extension}，请上传 {', '.join(self.supported_formats)} 格式的文件",
            )

        return file_extension

    def check_session_exists(self, session_id: str) -> bool:
        """
        检查会话是否存在
        """
        return self.redis_client.exists(session_id)

    def parse_docx(self, file_content: bytes, file_extension: str) -> Tuple[str, int]:
        """
        解析doc文件
        返回文本内容和字符数
        """

        try:
            doc = Document(BytesIO(file_content))
            text = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text.append(paragraph.text.strip())

            content = "\n".join(text)
            char_count = len(content)

            # 检查字符数限制
            if char_count > self.max_characters:
                raise HTTPException(
                    status_code=400,
                    detail=f"DOCX文档字符数{char_count}超出字符数限制，请上传小于{self.max_characters}字符的DOCX文档。",
                )

            return content, char_count
        except HTTPException as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to parse DOCX: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"DOCX文档解析错误: {str(e)}")

    def parse_pdf(self, file_content: bytes) -> Tuple[str, int]:
        """解析 PDF

        Args:
            file_content (bytes): 文件内容

        Returns:
            Tuple[str, int]: [文本内容，页数]
        """
        try:
            pdf_file = BytesIO(file_content)
            
            # 使用 pdfplumber 读取 PDF 文件
            with pdfplumber.open(pdf_file) as pdf:
                page_count = len(pdf.pages)
                
                if page_count > self.max_pages:
                    raise HTTPException(
                        status_code=400,
                        detail=f"PDF文档页数{page_count}, 超过限制页数{self.max_pages}"
                    )
                
                text = []
                # 遍历每一页，将文本内容添加到 text 中
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text.append(page_text)
                        
                return '\n'.join(text), page_count
        except HTTPException as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=str(e.detail)
            )
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"解析PDF文件失败: {e}"
            )
    
    def parse_txt(self, file_content: bytes) -> Tuple[str, int]:
        """解析 TXT 文件

        Args:
            file_content (bytes): 文本内容

        Returns:
            Tuple[str, int]: 文本内容和字符
        """
        try:
            encodings = ['utf-8', 'gbk', 'gb2312', 'ascii']
            content = None
            
            for encoding in encodings:
                try:
                    content = file_content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
                
            if content is None:
                raise HTTPException(status_code=400, detail="无法识别的文件编码")
            
            char_count = len(content)
            
            # 检查字符限制
            if char_count > self.max_characters:
                raise HTTPException(
                    status_code=400, 
                    detail=f"文件字符数{char_count}超出限制字符数{self.max_characters}"
                )
            
            return content, char_count
        except HTTPException as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"解析TXT文件失败: {e}"
            )

    def parse_document(self, file_content: bytes, file_extension: str) -> Tuple[str, int]:
        """
        统一解析文档
        :param file_content: 文档内容
        :param file_extension: 文档扩展名
        :return: 
        返回:
        解析结果
        解析结果字符数
        """
        
        file_extension = self.validate_file_format(file_extension)
        
        if file_extension == "docx":
            return self.parse_docx(file_content)
        elif file_extension == "pdf":
            return self.parse_pdf(file_content)
        elif file_extension == "txt":
            return self.parse_txt(file_content)
        else:
            raise HTTPException(status_code=400, detail="不支持的文件格式")
        

    def store_to_redis(self, session_id: str, content: str) -> None:
        """
        存储解析结果到Redis
        """
        
        try:
            self.redis_client.setex(
                session_id,
                self.redis_expire_seconds,
                content
            )
            logger.info(f"存储解析结果到 Redis 成功，session_id: {session_id}, 内容长度: {len(content)}")
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"存储解析结果到 Redis 失败: {str(e)}"
            )
    
    def get_from_redis(self, session_id: str) -> str:
        """
        从 Redis 中获取解析结果
        """
        try:
            content = self.redis_client.get(session_id)
            if content:
                return content
            else:
                raise HTTPException(
                    status_code=404,
                    detail="未找到该会话的解析结果，可能已经过期或者未上传"
                )
        except Exception as e:
            logger.exception(e)
    def get_ttl(self, session_id: str) -> int:
        """获取Redis键的剩余过期时间"""
        return self.redis_client.ttl(session_id)

    def quick_parse_document(self, session_id: str, filename: str, file_content: bytes) -> dict:
        """快速解析文档的主业务逻辑

        Args:
            session_id (str): 会话 id
            filename (str): w文件名
            file_content (bytes): 文件内容

        Returns:
            dict: 文档字典
        """
        # 验证文件格式
        file_extension = self.validate_file_format(filename)
        
        # 检查会话中是否已经存在文档
        if self.check_session_exists(session_id):
            raise HTTPException(
                status_code=400,
                detail="该会话已有文档，每个 session 只能上传一个文档"
            )
        
        # 验证文件内容
        if not file_content:
            raise HTTPException(
                status_code=400,
                detail="文件内容为空"
            )
        
        # 解析文档
        content, count_value = self.parse_document(file_content, file_extension)
        
        # 存储到 Redis
        self.store_to_redis(session_id, content)
        
        # 根据文件类型返回不同的统计信息
        # 根据文件类型返回不同的统计信息
        if file_extension == 'pdf':
            return {
                "status": "success",
                "message": "文档解析完成",
                "session_id": session_id,
                "filename": filename,
                "file_type": file_extension,
                "pages": count_value,
                "content_length": len(content),
                "limit_info": f"PDF页数限制: {self.max_pages}页",
                "expiry_hours": self.redis_expire_seconds // 3600
            }
        else:  # txt 或 docx
            return {
                "status": "success",
                "message": "文档解析完成",
                "session_id": session_id,
                "filename": filename,
                "file_type": file_extension,
                "character_count": count_value,
                "content_length": len(content),
                "limit_info": f"字符数限制: {self.max_characters}字符",
                "expiry_hours": self.redis_expire_seconds // 3600
            }
            
    def get_parsed_content(self, session_id: str) -> dict:
        """获取已解析的文档内容"""
        content = self.get_from_redis(session_id)
        ttl = self.get_ttl(session_id)
        
        return {
            "status": "success",
            "session_id": session_id,
            "content": content,
            "content_length": len(content),
            "remaining_seconds": ttl if ttl > 0 else 0
        }
        
# 创建全局服务实例
quick_parse_service = QuickParseService()