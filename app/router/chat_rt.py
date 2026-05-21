from fastapi import APIRouter, Body, UploadFile, File, Query, Security, status, Depends
import uuid
from fastapi.responses import StreamingResponse
import os
from dotenv import load_dotenv
from typing import List, Optional
from fastapi_jwt import JwtAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import select
from utils import logger

# 加载环境变量
load_dotenv()

# 配置日志
logger.info(f"ES_HOST: {os.getenv('ES_HOST')}")
logger.info(f"ELASTICSEARCH_URL: {os.getenv('ELASTICSEARCH_URL')}")

# 生成 router
router = APIRouter()
