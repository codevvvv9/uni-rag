# 从零手写复刻 Backend 项目

本文按当前 `backend` 工程的真实结构，说明如何从零手写一个等价后端。目标不是一次性复制所有代码，而是按模块逐步搭建：先让服务跑起来，再补认证、数据库、文档解析、知识库检索和 RAG 流式问答。

本教程默认使用 `uv` 管理 Python 环境，使用 Docker Compose 启动 PostgreSQL、Elasticsearch、Redis 和 FastAPI 应用。

## 1. 最终目标

复刻完成后，后端需要具备以下能力：

- 用户注册、登录、JWT 鉴权。
- 创建对话会话。
- 上传临时文档并快速解析，内容保存到 Redis。
- 上传长期知识库文件，解析、分块、向量化后写入 Elasticsearch。
- 基于知识库和当前会话文档进行 RAG 问答。
- 使用 Server-Sent Events 流式返回模型回答。
- 保存会话、消息、文档元数据到 PostgreSQL。
- 查询历史会话、历史消息、用户文档列表，并支持删除文档。

总体架构如下：

```mermaid
flowchart LR
    Client["前端或 API 调用方"] --> API["FastAPI app_main:app"]

    API --> UserRouter["router/user_rt.py<br/>注册、登录、STS Token"]
    API --> ChatRouter["router/chat_rt.py<br/>会话、上传、解析、问答"]
    API --> HistoryRouter["router/history_rt.py<br/>历史、文档列表、删除"]

    UserRouter --> AuthService["service/auth.py"]
    ChatRouter --> QuickParse["service/quick_parse_service.py"]
    ChatRouter --> FileParse["service/core/file_parse.py"]
    ChatRouter --> Retrieval["service/core/retrieval.py"]
    ChatRouter --> ChatService["service/core/chat.py"]
    HistoryRouter --> DocOps["service/document_operations.py"]

    AuthService --> PG[("PostgreSQL<br/>业务元数据")]
    QuickParse --> Redis[("Redis<br/>临时解析内容")]
    FileParse --> ES[("Elasticsearch<br/>文档分片索引")]
    Retrieval --> ES
    ChatService --> Redis
    ChatService --> PG
    DocOps --> ES
    DocOps --> PG

    ChatService --> LLM["DashScope/OpenAI 兼容接口"]
    FileParse --> Embedding["DashScope Embedding"]
```

## 2. 本地准备

安装基础工具：

```bash
# 检查 Docker
docker --version
docker compose version

# 检查 uv
uv --version

# 推荐 Python 3.11
uv python list
```

准备目录：

```bash
mkdir backend
cd backend
```

准备 `.env`，注意不要把真实密钥提交到 Git：

```bash
cat > .env.example <<'EOF'
# Elasticsearch
ELASTIC_PASSWORD=infini_rag_flow
STACK_VERSION=8.11.3
MEM_LIMIT=8073741824
TIMEZONE=Asia/Shanghai

# LLM
DASHSCOPE_API_KEY="your-api-key"
DASHSCOPE_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"

# Runtime
DATABASE_URL=postgresql://postgres:pg123456@gsk_pg:5432/gsk
ES_HOST=http://es01:9200
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
ROOT_PATH=http://localhost:8000
JWT_SECRET_KEY="replace-me"
EOF

cp .env.example .env
```

## 3. 创建目录结构

先创建最小目录骨架：

```bash
mkdir -p app/router
mkdir -p app/service/core
mkdir -p app/service/core/api/utils
mkdir -p app/service/core/conf
mkdir -p app/service/core/rag/app
mkdir -p app/service/core/rag/nlp
mkdir -p app/service/core/rag/utils
mkdir -p app/service/core/deepdoc/parser
mkdir -p app/service/core/deepdoc/vision
mkdir -p app/models
mkdir -p app/schemas
mkdir -p app/utils
mkdir -p app/database
mkdir -p app/exceptions
mkdir -p app/alembic/versions

touch app/router/__init__.py
touch app/service/__init__.py
touch app/service/core/__init__.py
touch app/service/core/rag/__init__.py
touch app/service/core/rag/app/__init__.py
touch app/service/core/rag/nlp/__init__.py
touch app/service/core/rag/utils/__init__.py
touch app/service/core/deepdoc/__init__.py
touch app/service/core/deepdoc/parser/__init__.py
touch app/service/core/deepdoc/vision/__init__.py
touch app/models/__init__.py
touch app/schemas/__init__.py
touch app/utils/__init__.py
touch app/database/__init__.py
```

最终关键结构应接近：

```text
backend/
├── .env
├── docker-compose.yml
├── README.md
└── app/
    ├── app_main.py
    ├── Dockerfile
    ├── requirements.txt
    ├── start.sh
    ├── alembic.ini
    ├── alembic/
    ├── router/
    ├── service/
    ├── models/
    ├── schemas/
    ├── utils/
    ├── database/
    └── exceptions/
```

## 4. 使用 uv 初始化 Python 项目

进入 `app` 目录初始化：

```bash
cd app
uv init --python 3.11
uv venv --python 3.11
```

创建 `requirements.txt`。当前项目依赖较多，建议先按功能分组写入：

```txt
fastapi==0.115.0
fastapi-jwt[authlib]==0.3.0
uvicorn==0.31.0
gunicorn==21.0.0
python-multipart==0.0.11
python-jose==3.5.0
authlib==1.6.0
bcrypt==4.3.0
dotenv==0.9.9
requests==2.32.3
httpx==0.28.1
sqlalchemy==1.4.53
psycopg2-binary==2.9.10
alembic==1.13.1
redis==5.0.1
aioredis==2.0.1
elasticsearch==8.18.1
elasticsearch-dsl==8.18.0
openai==1.88.0
dashscope==1.23.5
python-docx==1.2.0
pdfplumber==0.11.7
pypdf==5.6.0
pandas==2.3.0
openpyxl==3.1.5
python-pptx==1.0.2
markdown==3.8.1
tika==3.1.0
opencv-python==4.11.0.86
onnxruntime==1.22.0
shapely==2.1.2
xgboost==3.0.2
beartype==0.21.0
huggingface_hub==0.33.0
datrie==0.8.2
hanziconv==0.3.2
nltk==3.9.1
chardet==5.2.0
tiktoken==0.9.0
jieba==0.42.1
xxhash==3.5.0
colorlog==6.9.0
llama-index-core==0.10.68.post1
llama-index-postprocessor-dashscope-rerank-custom==0.1.0
```

安装依赖：

```bash
uv pip install -r requirements.txt
uv pip freeze
```

本地开发运行时使用：

```bash
uv run uvicorn app_main:app --reload --host 0.0.0.0 --port 8000
```

## 5. Docker Compose 和容器启动

根目录编写 `docker-compose.yml`，保留四个服务：

- `swxy_api`：FastAPI 主应用。
- `gsk_pg`：PostgreSQL。
- `es01`：Elasticsearch。
- `redis`：临时文档缓存。

核心配置要点：

```yaml
version: "3.8"

services:
  swxy_api:
    build:
      context: ./app
      dockerfile: Dockerfile
    container_name: swxy_api
    env_file:
      - .env
    environment:
      - DATABASE_URL=postgresql://postgres:pg123456@gsk_pg:5432/gsk
      - ES_HOST=http://es01:9200
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - REDIS_DB=0
      - ROOT_PATH=http://localhost:8000
      - TZ=${TIMEZONE}
    ports:
      - "8000:8000"
    volumes:
      - ./app:/app/app
      - ./nltk_data:/usr/local/nltk_data
    command: ["uvicorn", "app_main:app", "--host", "0.0.0.0", "--port", "8000"]
    depends_on:
      - gsk_pg
      - es01
      - redis
    networks:
      - gsk_network

  gsk_pg:
    image: postgres:15-alpine
    container_name: gsk_pg
    environment:
      - POSTGRES_PASSWORD=pg123456
      - POSTGRES_USER=postgres
      - POSTGRES_DB=gsk
    volumes:
      - pg_data:/var/lib/postgresql/data
    networks:
      - gsk_network

  es01:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.3
    container_name: gsk-es-01
    env_file: .env
    environment:
      - node.name=es01
      - ELASTIC_PASSWORD=${ELASTIC_PASSWORD}
      - discovery.type=single-node
      - xpack.security.enabled=true
      - xpack.security.http.ssl.enabled=false
      - xpack.security.transport.ssl.enabled=false
      - ES_JAVA_OPTS=-Xms512m -Xmx512m
      - TZ=${TIMEZONE}
    volumes:
      - gsk_esdata01:/usr/share/elasticsearch/data
    networks:
      - gsk_network

  redis:
    image: redis:7-alpine
    container_name: gsk_redis
    volumes:
      - redis_data:/data
    networks:
      - gsk_network

volumes:
  pg_data:
  redis_data:
  gsk_esdata01:

networks:
  gsk_network:
    driver: bridge
```

`app/Dockerfile` 负责安装系统依赖和 Python 依赖：

```dockerfile
FROM python:3.11.7-slim

RUN apt-get update --fix-missing && \
    apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    make \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app
RUN chmod +x /app/start.sh

ENTRYPOINT ["/app/start.sh"]
```

`app/start.sh` 做三件事：等待 PostgreSQL、执行 Alembic 迁移、启动应用命令。

```bash
#!/bin/bash
set -e

echo "等待数据库连接..."
python -c "
import os, time, psycopg2
from psycopg2 import OperationalError
for i in range(30):
    try:
        conn = psycopg2.connect(os.environ['DATABASE_URL'])
        conn.close()
        print('数据库连接成功')
        break
    except OperationalError:
        print(f'等待数据库... {i + 1}/30')
        time.sleep(2)
else:
    raise SystemExit('数据库连接失败')
"

echo "执行数据库迁移..."
alembic upgrade head || echo "迁移失败，继续启动应用"

echo "启动应用服务..."
exec "$@"
```

启动流程：

```mermaid
flowchart TD
    A["docker compose up -d --build"] --> B["构建 swxy_api 镜像"]
    B --> C["启动 PostgreSQL / ES / Redis"]
    C --> D["启动 swxy_api 容器"]
    D --> E["执行 /app/start.sh"]
    E --> F["等待 DATABASE_URL 可连接"]
    F --> G["alembic upgrade head"]
    G --> H["uvicorn app_main:app"]
    H --> I["访问 http://localhost:8000/docs"]
```

## 6. FastAPI 入口

编写 `app/app_main.py`：

```python
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from router import chat_rt, history_rt, user_rt


root_path = os.getenv("ROOT_PATH", "http://localhost:8000")

app = FastAPI(root_path=root_path)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_rt.router)
app.include_router(user_rt.router)
app.include_router(history_rt.router)
```

先创建空路由，保证服务能启动：

```python
# app/router/user_rt.py
from fastapi import APIRouter

router = APIRouter()
```

`chat_rt.py` 和 `history_rt.py` 同理。

验收：

```bash
uv run uvicorn app_main:app --reload
curl http://localhost:8000/docs
```

## 7. 数据库基础层

`app/models/base.py`：

```python
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
```

`app/utils/database.py`：

```python
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.base import Base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
```

核心表关系：

```mermaid
erDiagram
    users {
        int id PK
        string username
        string password_hash
    }

    sessions {
        string session_id PK
        string session_name
        string user_id
        timestamp created_at
        timestamp updated_at
    }

    messages {
        uuid message_id PK
        string session_id
        text user_question
        text model_answer
        text documents
        text recommended_questions
        text think
        timestamp created_at
    }

    knowledgebases {
        int id PK
        string user_id
        string file_name
        timestamp created_at
        timestamp updated_at
    }

    document_uploads {
        int id PK
        string session_id
        string document_name
        string document_type
        int file_size
        timestamp upload_time
    }

    users ||--o{ sessions : owns
    sessions ||--o{ messages : contains
    sessions ||--o{ document_uploads : records
    users ||--o{ knowledgebases : owns
```

模型文件按表拆分：

- `models/user.py`：`User`
- `models/session.py`：`Session`
- `models/message.py`：`Message`、`KnowledgeBase`
- `models/document_upload.py`：`DocumentUpload`
- `models/__init__.py`：导出 `Base` 和全部模型，供 Alembic 自动发现。

Alembic 初始化分两种模式。本文主线使用 Docker 启动后端，所以迁移命令优先在 `swxy_api` 容器内执行。

如果你是在宿主机本地开发，并且本地 `DATABASE_URL` 能连接到 PostgreSQL，可以用 uv 初始化：

```bash
cd app
uv run alembic init alembic
```

在 `alembic/env.py` 中导入模型元数据：

```python
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from models import Base

target_metadata = Base.metadata
```

Docker 模式下，生成迁移脚本：

```bash
docker compose exec swxy_api bash -lc "cd /app && alembic revision --autogenerate -m 'initial schema'"
```

执行迁移并查看当前版本：

```bash
docker compose exec swxy_api bash -lc "cd /app && alembic upgrade head && alembic current -v"
```

确认 PostgreSQL 中已经生成表：

```bash
docker compose exec gsk_pg psql -U postgres -d gsk -c "\dt"
docker compose exec gsk_pg psql -U postgres -d gsk -c "select * from alembic_version;"
```

如果需要用 Navicat 从宿主机连接 PostgreSQL，给 `gsk_pg` 服务增加端口映射：

```yaml
ports:
  - "15432:5432"
```

Navicat 连接信息：

```text
Host: 127.0.0.1
Port: 15432
User: postgres
Password: pg123456
Database: gsk
```

```mermaid
flowchart LR
    A["SQLAlchemy Models<br/>Python 里的表结构"] --> B["alembic revision --autogenerate<br/>生成迁移脚本"]
    B --> C["alembic upgrade head<br/>执行迁移脚本"]
    C --> D["PostgreSQL 里真实创建表"]
    C --> E["alembic_version<br/>记录当前迁移版本"]
```

## 8. 注册、登录和 JWT

认证链路：

```mermaid
sequenceDiagram
    participant C as Client
    participant R as user_rt.py
    participant A as service/auth.py
    participant P as PostgreSQL

    C->>R: POST /register
    R->>A: register_user(username, password)
    A->>P: 查询 username 是否存在
    A->>P: 写入 users(password_hash)
    R-->>C: 注册成功

    C->>R: POST /login
    R->>A: authenticate(username, password)
    A->>P: 查询用户
    A->>A: verify_password()
    A-->>R: create_token(user_id, username)
    R-->>C: access_token
```

先写密码工具 `app/utils/password.py`：

```python
import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
```

异常类 `app/exceptions/auth.py`：

```python
class AuthError(Exception):
    pass
```

认证服务 `app/service/auth.py` 负责：

- 从数据库查询用户。
- 注册时检查用户名重复。
- 使用 bcrypt 保存密码哈希。
- 使用 `JwtAccessBearerCookie` 创建访问令牌。
- 暴露 `access_security` 给需要鉴权的接口使用。

路由 `app/router/user_rt.py` 提供：

- `POST /register`
- `POST /login`
- `POST /sts-token`

## 9. 会话和 Pydantic Schema

`app/schemas/chat.py`：

```python
from pydantic import BaseModel


class SessionResponse(BaseModel):
    session_id: str
    status: str
    message: str


class ChatRequest(BaseModel):
    message: str
```

`POST /create_session` 的核心逻辑：

```python
import uuid


session_id = str(uuid.uuid4()).replace("-", "")[:16]
return {
    "session_id": session_id,
    "status": "success",
    "message": "Session created successfully",
}
```

该接口只负责生成 ID。真正的会话名称在第一次问答结束后，根据用户问题生成并写入 `sessions` 表。

## 10. 快速文档解析

快速解析适合“当前会话临时文档”，不进入长期知识库。当前项目规则：

- 支持 `docx`、`pdf`、`txt`。
- PDF 不超过 4 页。
- DOCX/TXT 不超过 4000 字符。
- 同一个 `session_id` 只能上传一个临时文档。
- 内容写入 Redis，过期时间 2 小时。
- 上传记录写入 `document_uploads`。

流程：

```mermaid
flowchart TD
    A["POST /quick_parse<br/>session_id + file"] --> B["JWT 鉴权"]
    B --> C["读取文件 bytes"]
    C --> D["校验扩展名 docx/pdf/txt"]
    D --> E{"Redis 是否已有 session_id?"}
    E -- 是 --> F["返回 400"]
    E -- 否 --> G["按格式解析文本"]
    G --> H["校验页数或字符数"]
    H --> I["Redis SETEX session_id content 7200s"]
    I --> J["document_uploads 写入上传记录"]
    J --> K["返回解析摘要"]
```

服务类 `app/service/quick_parse_service.py` 应包含：

- `validate_file_format(filename)`
- `check_session_exists(session_id)`
- `parse_docx(file_content)`
- `parse_pdf(file_content)`
- `parse_txt(file_content)`
- `store_to_redis(session_id, content)`
- `get_from_redis(session_id)`
- `quick_parse_document(session_id, filename, file_content)`
- `get_parsed_content(session_id)`

路由 `app/router/chat_rt.py` 提供：

- `POST /quick_parse?session_id=...`
- `GET /get_parsed_content?session_id=...`
- `GET /sessions/{session_id}/documents`
- `GET /sessions/{session_id}/documents/summary`

## 11. 长期知识库上传

长期知识库上传接口是 `/upload_files`。它和快速解析不同：文件会落盘、解析、分块、向量化，然后写入 Elasticsearch。

流程：

```mermaid
flowchart TD
    A["POST /upload_files<br/>session_id? + files"] --> B["JWT 鉴权并取 user_id"]
    B --> C{"是否传 session_id?"}
    C -- 否 --> D["使用 user_id 作为 session_id"]
    C -- 是 --> E["使用请求 session_id"]
    D --> F["创建 storage/file/{session_id}"]
    E --> F
    F --> G["检查 knowledgebases 是否有同名文件"]
    G --> H["保存文件到本地"]
    H --> I["execute_insert_process(file_path, file_name, session_id)"]
    I --> J["chunk 解析和分块"]
    J --> K["批量生成 embedding"]
    K --> L["组装 ES 文档字段"]
    L --> M["写入 Elasticsearch index=session_id"]
    M --> N["knowledgebases 写入 user_id + file_name"]
    N --> O["返回 success / partial_success / failed"]
```

`app/service/core/file_parse.py` 是编排层，职责：

- 调用 `rag/app/naive.py::chunk()` 解析多格式文件。
- 取每个 chunk 的 `content_with_weight`。
- 调用 embedding 模型批量生成向量。
- 为每个 chunk 生成 `id`、`kb_id`、`doc_id`、`docnm`、`q_1024_vec` 等字段。
- 通过 `ESConnection.insert()` 批量写入 Elasticsearch。

`app/service/core/rag/app/naive.py` 是解析入口，按扩展名分派：

- `.pdf`：PDF/DeepDOC 解析。
- `.docx`：Word 解析。
- `.xlsx` / `.xls`：Excel 解析。
- `.txt`：文本解析。
- `.md`：Markdown 解析。
- `.html`：HTML 解析。
- `.json`：JSON 解析。

`app/service/core/rag/utils/es_conn.py` 封装 Elasticsearch：

- 初始化连接。
- 读取 `conf/mapping.json`。
- `insert()` 批量写入。
- `search()` 混合检索。
- `delete()` 删除文档。

## 12. RAG 检索和流式问答

`POST /chat_on_docs?session_id=...` 是核心问答接口。

时序：

```mermaid
sequenceDiagram
    participant C as Client
    participant R as chat_rt.py
    participant ES as Elasticsearch
    participant Redis as Redis
    participant LLM as DashScope/OpenAI
    participant PG as PostgreSQL

    C->>R: POST /chat_on_docs {message}
    R->>R: JWT 鉴权，提取 user_id
    R->>ES: retrieve_content(user_id, question)
    ES-->>R: top chunks 或空列表
    R->>Redis: GET session_id
    Redis-->>R: 当前会话临时文档或空
    R->>LLM: stream chat completion(prompt + references)
    R-->>C: SSE documents event
    loop 模型流式输出
        LLM-->>R: delta content / reasoning_content
        R-->>C: SSE message event
    end
    R->>LLM: generate_recommended_questions()
    R-->>C: SSE recommended_questions event
    R-->>C: SSE end [DONE]
    R->>PG: INSERT messages
    R->>PG: INSERT sessions if absent
```

拆分实现：

1. `service/core/retrieval.py`
   - 创建 `ESConnection`。
   - 创建 `Dealer`。
   - 调用 `dealer.retrieval()`。
   - 提取 `document_id`、`document_name`、`content_with_weight`。

2. `service/core/chat.py`
   - 从 Redis 读取快速解析内容。
   - 合并 ES 检索内容和 Redis 当前会话内容。
   - 构造 prompt。
   - 调用 OpenAI 兼容接口，开启 `stream=True`。
   - 首先返回文档引用事件。
   - 边接收模型 delta，边返回 SSE。
   - 结束时生成推荐问题。
   - 写入 `messages`。
   - 如果 `sessions` 不存在，生成会话名称并写入。

SSE 输出格式示例：

```text
event: message
data: {"documents": [...]}

event: message
data: {"role": "assistant", "content": "回答片段", "thinking": false}

event: message
data: {"recommended_questions": ["问题1", "问题2", "问题3"]}

event: end
data: [DONE]
```

## 13. 历史和删除接口

`app/router/history_rt.py` 提供：

- `GET /get_files`：查询当前用户上传过的知识库文档。
- `DELETE /delete_file/{file_name}`：删除文档。
- `GET /get_messages?session_id=...`：查询指定会话消息。
- `GET /get_sessions`：查询当前用户所有会话。

删除逻辑写在 `app/service/document_operations.py`：

1. 按 `user_id + file_name` 查询 `knowledgebases`。
2. 使用 `ESConnection` 从对应索引删除 chunk。
3. 删除本地 `storage/file/{user_id}/{file_name}`。
4. 删除 PostgreSQL 元数据。
5. 返回删除结果。

## 14. 启动和验证顺序

完整启动：

```bash
docker compose up -d --build
# docker compose up -d --build swxy_api 一般这个服务更新的多一些
docker compose ps
docker compose logs -f swxy_api
```

检查 API 文档：

```bash
curl http://localhost:8000/docs
```

推荐按以下顺序验收：

```bash
# 1. 注册
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"demo123"}'

# 2. 登录，复制 access_token
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"demo123"}'

# 3. 创建会话
curl -X POST http://localhost:8000/create_session \
  -H "Authorization: Bearer <access_token>"

# 4. 快速解析文档
curl -X POST "http://localhost:8000/quick_parse?session_id=<session_id>" \
  -H "Authorization: Bearer <access_token>" \
  -F "file=@test.txt"

# 5. 查询解析内容
curl "http://localhost:8000/get_parsed_content?session_id=<session_id>" \
  -H "Authorization: Bearer <access_token>"

# 6. 流式问答
curl -N -X POST "http://localhost:8000/chat_on_docs?session_id=<session_id>" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"message":"请总结这份文档"}'

# 7. 查询会话
curl http://localhost:8000/get_sessions \
  -H "Authorization: Bearer <access_token>"

# 8. 查询消息
curl "http://localhost:8000/get_messages?session_id=<session_id>" \
  -H "Authorization: Bearer <access_token>"
```

## 15. 常见问题

### 15.1 uv 和 Docker 的关系

`uv` 用于本地开发环境，典型命令是：

```bash
uv venv --python 3.11
uv pip install -r requirements.txt
uv run uvicorn app_main:app --reload
```

Docker 用于完整服务编排，典型命令是：

```bash
docker compose up -d --build
```

两者不冲突。本地只调 FastAPI 时用 uv；需要 PostgreSQL、ES、Redis 一起跑时用 Docker Compose。

### 15.2 Elasticsearch 启动慢

首次启动会拉镜像、初始化数据目录，可能需要几分钟。查看日志：

```bash
docker compose logs -f es01
```

### 15.3 数据库迁移失败

先确认数据库可连接：

```bash
docker compose exec gsk_pg psql -U postgres -d gsk
```

再进入应用容器执行：

```bash
docker compose exec swxy_api bash
alembic current
alembic upgrade head
```

### 15.4 模型调用失败

检查 `.env`：

```bash
DASHSCOPE_API_KEY="your-api-key"
DASHSCOPE_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
```

不要把真实密钥写入文档、提交记录或截图。

### 15.5 文档解析失败

优先确认：

- 文件是否为空。
- 扩展名是否支持。
- PDF 是否超出页数限制。
- DOCX/TXT 是否超过字符数限制。
- DeepDOC 模型文件是否存在。
- ES 是否可以写入。

## 16. 推荐实现顺序

按下面顺序手写，最容易定位问题：

1. `docker-compose.yml`、`Dockerfile`、`start.sh`
2. `app_main.py` 和空路由
3. 数据库连接、模型、Alembic
4. 注册登录和 JWT
5. 创建会话
6. 快速解析和 Redis
7. 文档上传和本地落盘
8. ES 连接和 mapping
9. 文件解析、分块、embedding、ES 入库
10. 检索和 RAG 流式问答
11. 历史查询和删除
12. README、AGENTS、架构图和接口验收清单

每完成一阶段都先启动验证，不要等所有模块写完再联调。
