# App 目录说明

该目录包含 FastAPI 后端应用代码。

## 关键文件和目录

- `app_main.py`: FastAPI 应用入口。
- `router/`: 路由层，负责 HTTP 接口、依赖注入和状态码处理。
- `service/`: 服务层，负责业务逻辑。
- `schemas/`: Pydantic 数据结构。
- `models/`: SQLAlchemy ORM 模型。
- `alembic/`: Alembic 数据库迁移配置。
- `alembic/versions/`: 数据库迁移版本文件。当前 `980b32f130df` 是对既有 `init.sql` 表结构的 baseline，后续结构变化应继续新增 migration。
- `start.sh`: 容器启动脚本，等待数据库可用后执行 Alembic 升级，再启动 FastAPI。

## 消息表字段约定

`messages` 表使用 `created_at` 作为创建时间字段，使用 `retrieval_content` 保存本次回答实际检索到的内容快照，使用 `recommended_questions` 保存推荐问题，使用 `think` 保存模型思考过程。不要在消息表中新增或查询 `documents`、`recommend_questions`、`create_time` 这些旧字段名。

## 如何同步数据库表变化

初始化 init.sql后，后面变化，只改 models 目录，然后
```
docker compose exec swxy_api sh -c "cd /app/app && alembic revision --autogenerate -m '描述这次表结构变更'"
```
这会在 app/alembic/versions/xxxx_描述这次表结构变更.py，确认 Alembic 生成的 upgrade() 是你想要的，比如：
```
op.add_column(...)
op.drop_column(...)
op.create_index(...)
```
再执行下面代码
```
docker compose exec swxy_api sh -c "cd /app/app && alembic upgrade head"
```


