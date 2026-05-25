# Project Notes

## 功能简介

本工程是一个 FastAPI 后端服务，提供用户认证、会话创建、消息和文档相关接口，并通过 PostgreSQL、Redis、Elasticsearch 支撑 RAG 问答流程。

## 关键目录结构

- `app/app_main.py`: FastAPI 应用入口，负责中间件和路由注册。
- `app/router/`: API 路由模块。
- `app/service/`: 业务服务逻辑。
- `app/schemas/`: Pydantic 请求和响应模型。
- `app/models/`: SQLAlchemy ORM 模型。
- `app/alembic/`: Alembic 数据库迁移配置和版本文件。
- `app/alembic/versions/`: 数据库版本迁移脚本。
- `init.sql`: PostgreSQL 首次初始化脚本，当前作为既有数据库基线来源。
