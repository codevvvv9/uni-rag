from openai import OpenAI
import os
import json
import redis
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from utils.database import get_db
from fastapi import Depends, HTTPException, status
from utils import logger
from dotenv import load_dotenv
from sqlalchemy.orm import Session
load_dotenv()

# Redis客户端初始化
def get_redis_client():
    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = os.getenv("REDIS_PORT", 6379)
    redis_db = os.getenv("REDIS_DB", 0)
    return redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)

def get_quick_parse_content(session_id: str) -> str:
    """从 Redis 获取快速解析的文档内容"""
    try:
        redis_client = get_redis_client()
        content = redis_client.get(session_id)
        if content:
            logger.info(f"从 Redis 获取到快速解析内容，session_id: {session_id}, 长度: {len(content)}")
            return content
        else:
            logger.info(f"Redis 中未找到快速解析内容，session_id: {session_id}")
            return None
    except Exception as e:
        logger.error(f"从 Redis 获取快速解析内容失败: {str(e)}")
        return None

# 根据用户提问问题，生成相关推荐问题
def generate_recommend_questions(
    user_question: str, 
    retrieved_content: str = None, 
    session_id: str = None
) -> list[str]:
    """
    根据用户提问生成相关推荐问题。

    :param user_question: 用户提问
    :param retrieved_content: 检索到的内容（可选，用于判断是否有相关文档）
    :param session_id: 会话ID（可选）
    :return: 推荐问题列表
    """
    # 判断是够上有文档上下文
    has_documents = bool(retrieved_content and len(retrieved_content) > 0)
    
    # 获取文档主题信息（简化版）
    document_topics = []
    if has_documents:
        # 只获取文档名称作为主题参考，避免内容过程
        document_names = list(set([ ref.get("document_name", '') for ref in retrieved_content if ref.get("document_name")]))
        # 最多三个文档名称
        document_topics = document_names[:3]
    
    # 构造优化后的提示词
    context_info = ''
    if has_documents and document_topics:
        context_info = f"当前对话基于这些文档：{', '.join(document_topics)}"
        
    
    prompt = f"""
    你是一个智能助手，请基于用户的问题，生成3 个相关的推荐问题，帮助用户更深入的探索这个话题。
    
    用户问题： f{user_question}
    
    {context_info}
    
    要求：
    1. 生成的问题应该与用户问题相关，但从不同的角度深入
    2. 问题要具体、有价值，能够吸引用户获得更多有用的信息
    3. 如果有文档上下文，可以围绕文档主题生成相关问题
    4. 返回 JSON 格式，包含 recommended_questions数组
    
    输出格式：
    {{
        "recommended_questions": [
            "具体问题1",
            "具体问题2",
            "具体问题3"
        ]
    }}
    
    请直接返回 JSON，不要包含其他问题
    """
    
    try:
        # 调用大模型生成推荐问题
        client = OpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url=os.getenv("DASHSCOPE_BASE_URL")
        )
        completion = client.chat.completions.create(
            model="qwen3.6-flash",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            stream=False,
            timeout=30
        )
        
        # 提取生成的推荐问题
        if completion.choices:
            response = completion.choices[0].message.content
            logger.info(f"大模型返回的推荐问题原始响应：{response}")
        
            try:
                # 清理响应内容，去掉可能得 markdown代码块标识
                import re
                cleaned_response = response.strip()
                
                # 使用正则表达式去掉```json开头和```结尾
                json_pattern = r'^```(?:json)?\s*\n?(.*?)\n?```$'
                match = re.search(json_pattern, cleaned_response, re.DOTALL | re.IGNORECASE)
                
                if match:
                    cleaned_response = match.group(1).strip()
                    logger.info(f'检测到 markdown 格式，已自动去除')
                
                logger.info(f'清理后的响应内容是: {cleaned_response}')
                
                # 解析 JSON 响应
                response_json = json.loads(cleaned_response)
                recommended_questions = response_json.get("recommended_questions", [])
                logger.info(f'解析后的推荐问题列表是: {recommended_questions}')
                
                # 验证推荐问题格式
                if isinstance(recommended_questions, list) and len(recommended_questions) > 0:
                    return recommended_questions
                else:
                    logger.warning(f'推荐问题格式不正确或者为空，返回空列表')
                    return []
            except json.JSONDecodeError as e:
                logger.error(f'JSON 解析错误，返回空列表，错误信息：{str(e)}')
                logger.error(f'原始响应：{response}')
                logger.error(f"清理后的响应内容：{ cleaned_response if 'clean_response' in locals() else "未处理"}")
                
        else:
            logger.warning(f'大模型没有返回任何选择')
            return []
        
    except Exception as e:
        logger.error(f'大模型调用失败，错误信息：{str(e)}')
        return []
    
def generate_session_name(user_question):
    prompt = f"""
        请根据以下用户提问，生成一个简洁且具有代表性的会话名称：
        用户提问：{user_question}
        
        要求：
        1. 会话名称应该简洁明了，能够概括用户提问的主题。
        2. 返回一个 JSON 对象，包含一个字段 "session_name"，值为生成的会话名称。
        
        输出格式示例：
        {{
            "session_name": "用户提问的会话名称"
        }}
        
        请严格按照上述格式返回 JSON 对象
    """
    # 调用大模型生成会话名称
    try:
        client = OpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url=os.getenv("DASHSCOPE_BASE_URL")
        )
        completion = client.chat.completions.create(
            model="qwen3.6-flash",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            stream=False,
            timeout=30
        )
        
        # 提取生成的会话名称
        if completion.choices:
            response = completion.choices[0].message.content
            logger.info(f"大模型返回的会话名称原始响应：{response}")
            try:
                response_json = json.loads(response)
                session_name = response_json.get("session_name", "")
                logger.info(f'解析后的会话名称是：{session_name}')
                return session_name
            except json.JSONDecodeError as e:
                logger.error(f'JSON 解析错误，返回空字符串，错误信息：{str(e)}')
                return user_question
    except Exception as e:
        logger.error(f'发生错误，返回空字符串，错误信息：{str(e)}')
        return user_question
    
# 把对话数据写入数据库
def write_chat_to_db(
    session_id: str, 
    user_question: str, 
    model_answer: str, 
    retrieval_content, 
    recommended_questions, 
    think,
    db: Session
):
    """ 
    将对话数据写入数据库
    :param session_id: 会话ID
    :param user_question: 用户问题
    model_answer: 模型回答
    retrieval_content: 检索结果
    """
    
    try:
        documents_json = json.dumps(retrieval_content, ensure_ascii=False)
        
        db.execute(
            text(
                """
                INSERT INTO messages (session_id, user_question, model_answer, documents, recommend_questions, think)
                VALUES (:session_id, :user_question, :model_answer, :documents, :recommend_questions, :think)
                """
            ),
            {
                "session_id": session_id,
                "user_question": user_question,
                "model_answer": model_answer,
                "documents": documents_json,
                "recommended_questions": recommended_questions,
                "think": think,
            }
        )
        
        db.commit()
        logger.info(f"对话数据插入成功……，session_id: {session_id}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"插入对话数据失败: {str(e)}")

def update_session_name(session_id: str, question: str, user_id: str, db: Session):
    """
    根据 session_id 查询数据库表sessions，有的话直接跳过，没有的话先生成 session_name 再插入
    :param session_id: 会话ID
    :param question: 问题
    
    """
    
    try:
        # 查询sessions表中是否存在该session_id
        query_result = db.execute(
            text("SELECT session_name FROM sessions WHERE session_id = :session_id"),
            {"session_id": session_id}
        ).fetchone()
        
        if query_result:
            # 如果查到了，直接跳过了
            logger.info(f"Session {session_id} exists, skipping")
        else:
            if question:
                session_name = generate_session_name(question)
                db.execute(
                    """
                    INSERT INTO sessions (session_id, session_name, user_id)
                    VALUES (:session_id, :session_name, :user_id)
                    """,
                    {"session_id": session_id, "session_name": session_name, "user_id": user_id}
                )
                
                db.commit()
                logger.info(f"New Session {session_id} inserted, session_name: {session_name}")
            else:
                logger.info(f"Failed to retrieve question for session {session_id}, skipping insertion.")
                
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Update session name failed: {str(e)}")
    

def get_chat_completion(session_id, question, retrieved_content, user_id, db: Session):
    """
    获取 流式聊天完成结果，并按照指定的格式输出。
    :param session_id: 会话ID
    :param question: 用户问题
    :param retrieved_content: 从知识库中检索的结果
    :param user_id: 用户ID
    :return: 流式输出的生成器，每个元素符合SSE的格式的字符串
    """
    
    # 获取快速解析的文档内容
    quick_parse_content = get_quick_parse_content(session_id)
    
    # 构建参考的内容
    reference_parts = []
    reference_id = 1
    
    # 1. 添加知识库检索内容
    if retrieved_content:
        knowledge_base_refs = []
        for ref in retrieved_content:
            knowledge_base_ref = f"[{reference_id}] {ref['content_with_weight']}"
            knowledge_base_refs.append(knowledge_base_ref)
            reference_id += 1
        if knowledge_base_refs:
            reference_parts.append("**知识库内容**\n" + "\n".join(knowledge_base_refs))
    
    # 2. 添加快速解析文档内容
    if quick_parse_content:
        # 将快速解析内容按段落分割，避免内容过长
        quick_content_paragraphs = [
            para.strip()
            for para in quick_parse_content.split("\n") if para.strip()
        ]
        
        if quick_content_paragraphs:
            # 限制快速解析内容的长度，避免提示词过长
            max_quick_content_length = 4000
            truncated_content = quick_parse_content[:max_quick_content_length]
            if len(truncated_content) > max_quick_content_length:
                truncated_content += "...内容已截断"
            
            reference_parts.append(f"**当前会话文档内容**\n[{reference_id}] {truncated_content}")
            reference_id += 1
    
    # 组合所有参考内容
    if reference_parts:
        # 让列表的每一项之间空出一行，让文本排版更宽松、可读性更高，
        formatted_reference = "\n\n".join(reference_parts)
    else:
        formatted_reference = "暂无相关参考内容"
        
    prompt = f"""
你是一个专业的智能助手，擅长基于提供的参考资料回答用户的问题。请遵循一下原则：

**回答要求：**
1. 优先基于参考内容回答，确保回答准确可靠
2. 在回答中，每一块内容都必须标注引用的来源，格式为：##引用编号$$。例如： ##1$$ 标识引用自第一条参考内容。
3. 如果参考内容不足以完全回答问题，可以结合常识补充，但需明确区分
4. 回答要条理清晰、语言自然流畅
5. 如果没有相关参考内容，请诚实说明并提供一般性建议

**参考内容：**
{formatted_reference}

**问题：**
{question}

请基于以上信息提供专业、准确的回答
"""

    print(prompt)

    try:
        # 初始化 OpenAI 客户端
        client = OpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url=os.getenv("DASHSCOPE_BASE_URL")
        )
        
        # 调用模型生成回答
        completion = client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )
        
        # 返回检索内容和快速解析内容
        all_documents = retrieved_content.copy() if retrieved_content else []
        
        # 如果有快速解析内容，将其格式化后，添加到文档列表中
        if quick_parse_content:
            # 将快速解析内容分段，避免单个文档过长
            max_chunk_length = 2000
            content_chunks = []
            
            if len(quick_parse_content) > max_chunk_length:
                # 按段落分割内容
                paragraphs = [p.strip() for p in quick_parse_content.split("\n") if p.strip()]
                current_chunk = ""
                for para in paragraphs:
                    if len(current_chunk) + len(para) <= max_chunk_length:
                        current_chunk += para + "\n"
                    else:
                        if current_chunk:
                            content_chunks.append(current_chunk.strip())
                        current_chunk = para + "\n"
                    

                if current_chunk:
                    content_chunks.append(current_chunk.strip())
            else:
                content_chunks = [quick_parse_content]
            
            # 将每块内容块格式化成文档格式添加到 all_documents 列表中
            for i, chunk in enumerate(content_chunks, start=1):
                quick_parse_doc = {
                    "document_id": f"quick_parse_{session_id}_{i}",
                    "document_name": f"当前会话文档-第{i+1}部分" if len(content_chunks) > 1 else "当前会话文档",
                    # "content": chunk,
                    "content_with_weight": chunk,
                    "id": f"quick_parse_{session_id}_{i}",
                    "position": []
                }
                all_documents.append(quick_parse_doc)
            
            logger.info(f"快速解析内容已经添加到文档列表中，session_id: {session_id}，共有 {len(content_chunks)} 块内容")
        
        message = {
            "documents": all_documents
        }
        
        json_message = json.dumps(message, ensure_ascii=False)
        
        # 生成器
        yield f"event: message\ndata: {json_message}\n\n"
        
        # 处理流式响应
        model_answer = ""  # 初始化模型回答
        think = ""  # 初始化思考过程
        recommend_questions = []  # 初始化推荐问题
        
        for chunk in completion:
            if chunk["choices"][0]["finish_reason"] == "stop":
                # 结束生成了，就生成推荐问题
                try:
                    logger.info("开始生成推荐问题...")
                    recommend_questions = generate_recommend_questions(question, retrieved_content, session_id)
                    logger.info(f"推荐问题生成结果：{recommend_questions}")
                    
                    if recommend_questions:
                        message = {
                            "recommend_questions": recommend_questions
                        }
                        json_message = json.dumps(message, ensure_ascii=False)
                        yield f"event: message\ndata: {json_message}\n\n"
                        logger.info("推荐问题已推送到客户端")
                    else:
                        logger.warning("推荐问题生成为空")
                        
                except Exception as e:
                    logger.error(f"生成推荐问题失败：{str(e)}")
                    recommend_questions = []
                
                # 结束时发送[DONE]事件
                yield "event: end\ndata: [DONE]\n\n"
                # 将对话数据写入数据库
                logger.info("最终回答是: \n")
                logger.info(model_answer)
                write_chat_to_db(session_id, question, model_answer, retrieved_content, recommend_questions, think, db)
                
                # 生成会话名称
                update_session_name(session_id, question, user_id, db)
                break
            else:
                # 实时处理流式响应
                delta = chunk["choices"][0]["delta"]
                if delta.get("content"):
                    # 累加模型回答
                    model_answer += delta["content"] # 累加大模型回答
                    message = {
                        "role": "assistant",
                        "content": delta["content"],
                        "thinking": False,
                    }
                    json_message = json.dumps(message, ensure_ascii=False)
                    yield f"event: message\ndata: {json_message}\n\n"
                else:
                    # 累加思考过程
                    think += delta.reasoning_content
                    message = {
                        "role": "assistant",
                        "content": delta.reasoning_content,
                        "thinking": True,
                    }
                    json_message = json.dumps(message, ensure_ascii=False)
                    yield f"event: message\ndata: {json_message}\n\n"
    except Exception as e:
        # 发生错误时返回错误信息
        error_message = {
            "role": "error",
            "content": str(e)
        }
        json_error_message = json.dumps(error_message, ensure_ascii=False)
        yield f"event: error\ndata: {json_error_message}\n\n"