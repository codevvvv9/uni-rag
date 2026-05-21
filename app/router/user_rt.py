from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from fastapi.security import OAuth2PasswordRequestForm
from exceptions.auth import AuthError
from service.auth import authenticate, register_user
from schemas.user import LoginRequest, RegisterRequest, STSTokenRequest
import httpx
import asyncio
from sqlalchemy.orm import Session
from utils.database import get_db

router = APIRouter()


    
# 用户认证接口
@router.post("/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    # Depends(get_db) 只会在 FastAPI 路由函数参数里被解析。
    # 这样 db 才是一个真的数据库 Session， 否则只是一个普通的 Dependencies 对象
    
    try:
        # 调用 authenticate 函数进行认证
        token = authenticate(request.username, request.password, db)
        return {"access_token": token, "token_type": "bearer"}
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    


# 用户注册接口
@router.post('/register')
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    try:
        # 调用 register_user 函数进行注册
        register_user(request.username, request.password, db)
        return {"message": "User registered successfully"}
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
        


# 获取 STS token 接口 Security Token Service（安全令牌服务）
@router.post('/sts-token')
async def get_sts_token(request: STSTokenRequest):
    try:
        # 构造请求头
        headers = {
            "Authorization": f"Bearer; {request.accessKey}",
            "Content-Type": "application/json"
        }
        # 
        # 构造请求体
        body = {
            "appid": request.appid,
            "duration": 300
        }
        
        # 调用字节的 STS Token API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openspeech.bytedance.com/api/v1/sts/token",
                headers=headers,
                json=body,
                timeout=30.0
            )
            
            # 返回原始响应
            return response.json()
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="Request timeout when calling STS token API"
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error calling STS token API: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )