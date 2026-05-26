from sqlalchemy.orm import Session
from sqlalchemy import and_
from models.knowledgebase import KnowledgeBase
from service.core.rag.utils.es_conn import ESConnection
import os
from utils import logger

def delete_document(file_name: str, user_id: str, db: Session) -> dict:
    """
    删除文档及其相关数据

    Args:
        file_name (str): 待删除的文件名
        user_id (str): 用户ID
        db (Session): 数据库会话

    Returns:
        dict: 包含操作状态的字典
    """
    try:
        # 1. 从数据库中删除记录
        db_document = db.query(KnowledgeBase).filter(
            and_(
                KnowledgeBase.file_name == file_name, 
                KnowledgeBase.user_id == user_id
            )
        ).first()
        
        if not db_document:
            return {"status": "error", "message": "Document not found"}
        
        # 获取 user_id作为 ES 索引名字 ，因为 KnowledgeBase 表中没有 session_id字段
        index_name = user_id
        
        # 2. 从 ES 中删除文档
        es_conn = ESConnection()
        # 先搜索文档，查看实际存在的文档
        logger.info(f"搜索索引{index_name}中的文档...")
        
        try:
            search_result = es_conn.es.search(
                index=index_name,
                body={
                    "query": {
                        "match_all": {}
                    },
                    "size": 100
                }
            )
            
            logger.info(f"找到 {search_result['hits']['total']['value']} 条文档")
            # 打印前几个文档的关键字
            for i, hit in enumerate(search_result["hits"]["hits"][:5]):
                source = hit["_source"]
                logger.info(f"文档 {i+1}:")
                logger.info(f"  docnm: {source.get('docnm', 'N/A')}")
                logger.info(f"  docnm_kwd: {source.get('docnm_kwd', 'N/A')}")
                logger.info(f"  kb_id: {source.get('kb_id', 'N/A')} (类型: {type(source.get('kb_id', 'N/A'))})")
                logger.info(f"  doc_id: {source.get('doc_id', 'N/A')}")
        except Exception as e:
            logger.error(f"搜索索引{index_name}失败: {str(e)}")
            return {"status": "error", "message": f"Search index {index_name} failed: {str(e)}"}
        
        # 检查字段映射
        try:
            mapping = es_conn.es.indices.get_mapping(index=index_name)
            if not mapping:
                logger.error(f"索引{index_name}不存在")
                return {"status": "error", "message": f"Index {index_name} does not exist"}
            logger.info(f"索引映射信息{ mapping}")
        except Exception as e:
            logger.error(f"检查索引{index_name}失败: {str(e)}")
            return {"status": "error", "message": f"Check index {index_name} failed: {str(e)}"}
        
        # 尝试删除文档，同时支持字符串和数字类型的 kb_id
        deleted_count = 0
        
        # 准备两种可能得 kb_id
        kb_id_candidates = [user_id] # 字符串类型
        try:
            kb_id_int = int(user_id)
            if kb_id_int != user_id: # 避免重复
                kb_id_candidates.append(kb_id_int) # 数字类型
        except ValueError:
            pass
        
        # 对每个 kb_id 候选值尝试删除文档
        for kb_id in kb_id_candidates:
            if deleted_count > 0:
                break # 如果已经成功删除了文档，就不再尝试
            logger.info(f"尝试使用 kb_id={kb_id} (类型: {type(kb_id)}) 删除文档")
            try:
                delete_query = {
                    "query": {
                        "bool": {
                            "must": [
                                {"match": {"docnm": file_name}}, # 会对查询内容分词，属于模糊 / 全文匹配
                                {"term": {"kb_id": kb_id}} # 不分词、完全严格匹配原始值，属于精准等值查询
                            ]
                        }
                    }
                }
                
                logger.info(f"使用 match 查询删除：{delete_query}, 准备删除文档...")
                
                response = es_conn.es.delete_by_query(
                    index=index_name,
                    body=delete_query,
                    refresh=True
                )
                
                deleted_count = response["deleted"]
                logger.info(f"match 查询删除响应: {response}")
                if deleted_count > 0:
                    logger.info(f"使用 match 查询成功删除 {deleted_count} 条文档")
                    break
            except Exception as e:
                logger.error(f"match 查询删除文档失败: {str(e)}")
        
            # 如果 match 查询失败，尝试使用 term 查询
            deleted_count = es_conn.delete(
                condition={
                    "docnm": file_name, 
                    "kb_id": kb_id
                },
                indexName=index_name,
                knowledgebaseId=None
            )
            if deleted_count > 0:
                logger.info(f"使用 term 查询成功删除 {deleted_count} 条文档")
                break
        
        print(f"从 ES 中已成功删除 {deleted_count} 条文档")
        # 3. 删除本地文件（如果有文件路径字段的话）
        # 注意：KnowledgeBase 模型中没有 file_path 字段，我们需要构造文件路径
        # 假设文件存储在 storage/file/{user_id}/ 目录下
        file_path = f"storage/file/{user_id}/{file_name}"
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"删除本地文件: {file_path}")
            
        # 4. 删除数据库中的记录
        db.delete(db_document)
        db.commit()
        
        return {
            "status": "success",
            "message": f"Successfully deleted {deleted_count} document(s) from ES and database"
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting document: {str(e)}")
        return {"status": "error", "message": f"Failed to delete document: {str(e)}"} 