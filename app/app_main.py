from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from router import chat_rt
from router import user_rt
from router import history_rt
import os

# 从环境变量读取 root_path，默认为 "http://localhost:8001"
root_path = os.getenv("ROOT_PATH", "http://localhost:8001")

# 创建 FastAPI 应用，并设置 root_path，默认开启了 swagger 文档的访问路径
app = FastAPI(root_path=root_path)
# 添加 CORS 中间件，允许所有来源、方法和头部，生产环境中应限制具体的来源
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有源，生产环境中应该设置具体的源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头
)

# 包含路由模块
app.include_router(chat_rt.router)
app.include_router(user_rt.router)
app.include_router(history_rt.router)

if __name__=='__main__':
    import uvicorn
    uvicorn.run(app, host="", port=8001)