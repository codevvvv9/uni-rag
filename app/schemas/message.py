from pydantic import BaseModel, Field, UUID4
from typing import Any, Optional
from datetime import datetime
from typing import List

class MessageResponse(BaseModel):
    message_id: UUID4
    session_id: str
    user_question: str
    model_answer: str
    created_at: datetime
    retrieval_content: Optional[Any] = None
    recommended_questions: List[str] = Field(default_factory=list)
    think: Optional[str] = None
    
    class Config:
        from_attributes = True
        
# 定义返回的文档类型
class FileResponse(BaseModel):
    user_id: str
    file_name: str
    created_at: str
    updated_at: str
    

# 单个会话的响应模型
class SessionResponse(BaseModel):
    session_id: str
    session_name: str
    user_id: str
    created_at: str
    updated_at: str
    
# 会话列表的响应模型
class SessionListResponse(BaseModel):
    sessions: List[SessionResponse]
    user_id: str
