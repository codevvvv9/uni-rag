from pydantic import BaseModel

# 定义登录请求体的 Pydantic 模型
class LoginRequest(BaseModel):
    password: str
    username: str
    
# 定义请求体的 Pydantic 模型
class RegisterRequest(BaseModel):
    password: str
    username: str
    
# 定义 STS token 请求体的 Pydantic 模型
class STSTokenRequest(BaseModel):
    accessKey: str
    appid: str