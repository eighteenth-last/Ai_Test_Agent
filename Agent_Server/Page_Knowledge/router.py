"""
页面知识库 API 路由

提供：
  - 知识库查询/浏览/统计
  - 手动录入/删除
  - 健康检查
  - 老化知识查询
  - 页面探索（支持中止）
"""
import asyncio
import logging
import time
from typing import Optional, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.connection import get_db, QdrantCollectionConfig, OneclickSession
from Page_Knowledge.service import PageKnowledgeService
from Page_Knowledge.vector_store import get_vector_store, apply_config_to_store
from Page_Knowledge.embedding import reload_embedding_client
from Page_Knowledge.schema import PageKnowledge

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["页面知识库"])


# ── 请求/响应模型 ──

class LookupRequest(BaseModel):
    url: str
    query_text: str = ""
    domain: str = ""


class StoreRequest(BaseModel):
    url: str
    capabilities: dict


class DeleteRequest(BaseModel):
    url: str


class RetrieveContextRequest(BaseModel):
    query: str
    domain: str = ""
    limit: int = 3


# ── 接口 ──

@router.get("/knowledge/stats")
async def knowledge_stats(db: Session = Depends(get_db)):
    """知识库统计信息"""
    try:
        import asyncio
        from database.connection import PageKnowledgeRecord
        store = get_vector_store()
        health = await asyncio.to_thread(store.health_check)
        # MySQL 真实记录数
        total_records = db.query(PageKnowledgeRecord).count()
        # Qdrant 向量数
        vector_count = health.get("count", 0) if health.get("status") == "healthy" else 0
        # 简单老化统计（30天内未更新）
        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(days=30)
        stale_count = db.query(PageKnowledgeRecord).filter(
            PageKnowledgeRecord.updated_at < cutoff
        ).count()
        qdrant_healthy = health.get("status") == "healthy"
        return {
            "success": True,
            "data": {
                "total_records": total_records,
                "vector_count": vector_count,
                "stale_count": stale_count,
                "qdrant_healthy": qdrant_healthy,
                "qdrant_detail": health,
            }
        }
    except Exception as e:
        logger.error(f"[PageKB API] 统计失败: {e}")
        return {"success": False, "message": str(e)}


@router.get("/knowledge/health")
def knowledge_health():
    """向量数据库健康检查"""
    try:
        store = get_vector_store()
        health = store.health_check()
        return {"success": True, "data": health}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/knowledge/lookup")
async def knowledge_lookup(req: LookupRequest):
    """查询页面知识（精确 + 语义检索）"""
    try:
        result = await PageKnowledgeService.lookup(
            url=req.url,
            query_text=req.query_text,
            domain_filter=req.domain,
        )
        if result:
            knowledge = result["knowledge"]
            return {
                "success": True,
                "data": {
                    "hit": True,
                    "source": result["source"],
                    "score": result["score"],
                    "stale": result.get("stale", False),
                    "knowledge": knowledge.to_dict() if isinstance(knowledge, PageKnowledge) else knowledge,
                }
            }
        return {"success": True, "data": {"hit": False}}
    except Exception as e:
        logger.error(f"[PageKB API] lookup 失败: {e}")
        return {"success": False, "message": str(e)}


@router.post("/knowledge/store")
async def knowledge_store(req: StoreRequest, db: Session = Depends(get_db)):
    """手动存储页面知识"""
    try:
        knowledge = PageKnowledge.from_capabilities(req.url, req.capabilities)
        result = await PageKnowledgeService.store(knowledge, db)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"[PageKB API] store 失败: {e}")
        return {"success": False, "message": str(e)}


@router.post("/knowledge/check-update")
async def knowledge_check_update(req: StoreRequest, db: Session = Depends(get_db)):
    """版本检查并自动更新"""
    try:
        result = await PageKnowledgeService.check_and_update(
            url=req.url,
            new_capabilities=req.capabilities,
            db=db,
        )
        diff_data = None
        if result.get("diff"):
            diff_data = result["diff"].to_dict()

        return {
            "success": True,
            "data": {
                "action": result["action"],
                "diff": diff_data,
                "version": result["knowledge"].version,
                "hash": result["knowledge"].hash_signature,
            }
        }
    except Exception as e:
        logger.error(f"[PageKB API] check-update 失败: {e}")
        return {"success": False, "message": str(e)}


@router.get("/knowledge/list")
async def knowledge_list(domain: str = "", page_type: str = "", limit: int = 100):
    """列出所有页面知识"""
    try:
        items = await PageKnowledgeService.list_all(
            domain=domain, page_type=page_type, limit=limit,
        )
        return {"success": True, "data": {"items": items, "total": len(items)}}
    except Exception as e:
        logger.error(f"[PageKB API] list 失败: {e}")
        return {"success": False, "message": str(e)}


@router.get("/knowledge/detail")
async def knowledge_detail(url: str):
    """获取单个页面知识详情"""
    try:
        detail = await PageKnowledgeService.get_detail(url)
        if detail:
            return {"success": True, "data": detail}
        return {"success": False, "message": "未找到该 URL 的知识记录"}
    except Exception as e:
        logger.error(f"[PageKB API] detail 失败: {e}")
        return {"success": False, "message": str(e)}


@router.post("/knowledge/delete")
async def knowledge_delete(req: DeleteRequest, db: Session = Depends(get_db)):
    """删除指定 URL 的知识"""
    try:
        success = await PageKnowledgeService.delete_knowledge(req.url, db)
        return {"success": success, "message": "已删除" if success else "删除失败"}
    except Exception as e:
        logger.error(f"[PageKB API] delete 失败: {e}")
        return {"success": False, "message": str(e)}


@router.post("/knowledge/retrieve-context")
async def knowledge_retrieve_context(req: RetrieveContextRequest):
    """RAG 上下文检索（给任务规划用）"""
    try:
        contexts = await PageKnowledgeService.retrieve_context(
            query=req.query, domain=req.domain, limit=req.limit,
        )
        items = []
        for ctx in contexts:
            k = ctx.get("knowledge")
            items.append({
                "url": ctx.get("url", ""),
                "summary": ctx.get("summary", ""),
                "page_type": ctx.get("page_type", ""),
                "module_name": ctx.get("module_name", ""),
                "score": ctx.get("score", 0),
                "knowledge": k.to_dict() if isinstance(k, PageKnowledge) else None,
            })
        return {"success": True, "data": {"items": items, "total": len(items)}}
    except Exception as e:
        logger.error(f"[PageKB API] retrieve-context 失败: {e}")
        return {"success": False, "message": str(e)}


@router.get("/knowledge/stale")
async def knowledge_stale(max_age_days: int = 30):
    """查找已老化的知识"""
    try:
        items = await PageKnowledgeService.find_stale_knowledge(max_age_days)
        return {"success": True, "data": {"items": items, "total": len(items)}}
    except Exception as e:
        logger.error(f"[PageKB API] stale 失败: {e}")
        return {"success": False, "message": str(e)}


# ── Collection 配置管理 ──

_DEFAULT_CONFIG = {
    "collection_name": "page_knowledge",
    "vector_size": 1024,
    "distance": "Cosine",
    "qdrant_host": "localhost",
    "qdrant_port": 6333,
    "embedding_model": "Qwen/Qwen3-Embedding-4B",
    "embedding_api_url": "https://api.siliconflow.cn/v1/embeddings",
    "embedding_api_key": "",
}


class CollectionConfigRequest(BaseModel):
    collection_name: str = "page_knowledge"
    vector_size: int = 1024
    distance: str = "Cosine"
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    embedding_model: str = "Qwen/Qwen3-Embedding-4B"
    embedding_api_url: str = "https://api.siliconflow.cn/v1/embeddings"
    embedding_api_key: str = ""


class CollectionCreateRequest(BaseModel):
    force: bool = False


def _config_to_dict(cfg: QdrantCollectionConfig) -> dict:
    return {
        "id": cfg.id,
        "collection_name": cfg.collection_name,
        "vector_size": cfg.vector_size,
        "distance": cfg.distance,
        "qdrant_host": cfg.qdrant_host,
        "qdrant_port": cfg.qdrant_port,
        "embedding_model": cfg.embedding_model,
        "embedding_api_url": cfg.embedding_api_url,
        "embedding_api_key": cfg.embedding_api_key,
        "is_active": cfg.is_active,
        "created_at": str(cfg.created_at) if cfg.created_at else None,
        "updated_at": str(cfg.updated_at) if cfg.updated_at else None,
    }


@router.get("/knowledge/collection-config")
def get_collection_config(db: Session = Depends(get_db)):
    """获取当前 Qdrant Collection 配置（若未配置则返回默认值）"""
    try:
        cfg = db.query(QdrantCollectionConfig).filter_by(is_active=1).order_by(
            QdrantCollectionConfig.id.desc()
        ).first()
        if cfg:
            return {"success": True, "data": _config_to_dict(cfg)}
        return {"success": True, "data": _DEFAULT_CONFIG, "is_default": True}
    except Exception as e:
        logger.error(f"[PageKB API] get_collection_config 失败: {e}")
        return {"success": False, "message": str(e)}


@router.post("/knowledge/collection-config")
def save_collection_config(req: CollectionConfigRequest, db: Session = Depends(get_db)):
    """保存 Collection 配置到数据库（覆盖当前活跃配置）"""
    try:
        cfg = db.query(QdrantCollectionConfig).filter_by(is_active=1).order_by(
            QdrantCollectionConfig.id.desc()
        ).first()
        if cfg:
            cfg.collection_name = req.collection_name
            cfg.vector_size = req.vector_size
            cfg.distance = req.distance
            cfg.qdrant_host = req.qdrant_host
            cfg.qdrant_port = req.qdrant_port
            cfg.embedding_model = req.embedding_model
            cfg.embedding_api_url = req.embedding_api_url
            cfg.embedding_api_key = req.embedding_api_key
        else:
            cfg = QdrantCollectionConfig(
                collection_name=req.collection_name,
                vector_size=req.vector_size,
                distance=req.distance,
                qdrant_host=req.qdrant_host,
                qdrant_port=req.qdrant_port,
                embedding_model=req.embedding_model,
                embedding_api_url=req.embedding_api_url,
                embedding_api_key=req.embedding_api_key,
                is_active=1,
            )
            db.add(cfg)
        db.commit()
        db.refresh(cfg)
        logger.info(f"[PageKB API] 已保存 Collection 配置: {req.collection_name}")
        return {"success": True, "data": _config_to_dict(cfg), "message": "配置已保存"}
    except Exception as e:
        logger.error(f"[PageKB API] save_collection_config 失败: {e}")
        return {"success": False, "message": str(e)}


@router.post("/knowledge/collection-create")
async def create_collection(req: CollectionCreateRequest, db: Session = Depends(get_db)):
    """应用当前配置，创建/初始化 Qdrant Collection（force=True 时先删除再重建）"""
    try:
        import asyncio
        # 加载 DB 配置（若无则用默认值）
        cfg = db.query(QdrantCollectionConfig).filter_by(is_active=1).order_by(
            QdrantCollectionConfig.id.desc()
        ).first()
        config_dict = _config_to_dict(cfg) if cfg else _DEFAULT_CONFIG

        # 热更新单例
        apply_config_to_store(config_dict)
        reload_embedding_client(config_dict)

        store = get_vector_store()

        if req.force:
            # 强制删除旧 collection 再重建
            def _force_recreate():
                try:
                    client = store._get_client()
                    collections = [c.name for c in client.get_collections().collections]
                    if store.collection_name in collections:
                        client.delete_collection(store.collection_name)
                        logger.info(f"[PageKB API] 已删除旧 Collection: {store.collection_name}")
                except Exception as e:
                    logger.warning(f"[PageKB API] 删除旧 Collection 失败（忽略）: {e}")

            await asyncio.to_thread(_force_recreate)

        ok = await asyncio.to_thread(store.ensure_collection)
        if ok:
            health = await asyncio.to_thread(store.health_check)
            return {
                "success": True,
                "message": f"Collection '{store.collection_name}' 初始化成功",
                "data": health,
            }
        else:
            return {
                "success": False,
                "message": f"Collection 初始化失败: {store._last_error or '未知错误'}",
            }
    except Exception as e:
        logger.error(f"[PageKB API] create_collection 失败: {e}")
        return {"success": False, "message": str(e)}


# ── 页面探索专用接口 ──

# 全局探索任务跟踪（用于中止功能）
# task_id → {"cancel_event": asyncio.Event, "browser_session": BrowserSession|None, "temp_session_id": int}
_explore_tasks: Dict[str, Dict[str, Any]] = {}

class ExplorePageRequest(BaseModel):
    url: str
    username: str = ""
    password: str = ""
    user_goal: str = ""


class StopExploreRequest(BaseModel):
    task_id: str


@router.post("/knowledge/explore-page")
async def explore_page(req: ExplorePageRequest, db: Session = Depends(get_db)):
    """
    专用页面探索接口：启动浏览器探索页面，并将结果存入知识库
    
    流程：
    1. 使用 Browser-Use 探索页面
    2. 提取页面能力
    3. 存入 Qdrant 知识库
    
    支持中止：返回 task_id，可通过 /knowledge/stop-explore 中止
    """
    try:
        import asyncio
        from OneClick_Test.service import OneClickService
        
        # 构建探索环境信息
        env_info = {
            "base_url": req.url,
            "username": req.username,
            "password": req.password,
        }
        
        # 构建意图信息（简化版）
        intent = {
            "target_module": req.user_goal or "页面探索",
            "test_scope": req.user_goal or "探索页面结构",
            "scope_type": "single_page",
            "required_modules": [],
        }
        
        # 创建临时会话（用于探索）
        from database.connection import OneclickSession
        temp_session = OneclickSession(
            user_input=req.user_goal or f"探索页面: {req.url}",
            target_url=req.url,
            status='exploring',
        )
        db.add(temp_session)
        db.commit()
        db.refresh(temp_session)
        
        # 生成任务 ID 并注册取消事件
        task_id = f"explore_{temp_session.id}_{int(time.time())}"
        cancel_event = asyncio.Event()
        _explore_tasks[task_id] = {
            "cancel_event": cancel_event,
            "browser_session": None,
            "temp_session_id": temp_session.id,
            "url": req.url,
            "status": "running",
        }
        
        # 启动后台探索任务
        asyncio.create_task(
            _background_explore_task(
                task_id, temp_session.id, req, intent, env_info, cancel_event
            )
        )
        
        return {
            "success": True,
            "message": "页面探索已启动",
            "data": {
                "task_id": task_id,
                "temp_session_id": temp_session.id,
                "status": "running",
            }
        }
        
    except Exception as e:
        logger.error(f"[PageKB API] explore_page 启动失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {"success": False, "message": str(e)}


async def _background_explore_task(
    task_id: str,
    temp_session_id: int,
    req: ExplorePageRequest,
    intent: Dict,
    env_info: Dict,
    cancel_event: asyncio.Event,
):
    """后台执行探索任务 - 使用精准探索模式"""
    from database.connection import SessionLocal
    from OneClick_Test.service import OneClickService
    
    db = SessionLocal()
    try:
        temp_session = db.query(OneclickSession).filter_by(id=temp_session_id).first()
        if not temp_session:
            logger.error(f"[PageKB API] 临时会话不存在: {temp_session_id}")
            _explore_tasks[task_id]["status"] = "failed"
            return
        
        # 使用精准探索模式（OpenClaw 风格）
        logger.info(f"[PageKB API] 开始精准探索页面: {req.url}")
        
        explore_result = await OneClickService._explore_page_with_precision(
            db, temp_session, req.user_goal or f"探索页面: {req.url}", env_info
        )
        
        # 检查是否被取消
        if cancel_event.is_set():
            logger.info(f"[PageKB API] 探索已取消: {task_id}")
            _explore_tasks[task_id]["status"] = "cancelled"
            db.delete(temp_session)
            db.commit()
            return
        
        if not explore_result.get("success"):
            _explore_tasks[task_id]["status"] = "failed"
            _explore_tasks[task_id]["error"] = explore_result.get('message', '未知错误')
            db.delete(temp_session)
            db.commit()
            return
        
        page_data = explore_result.get("page_data", {})
        
        # 精准模式：直接使用 page_data 作为 capabilities
        page_capabilities = page_data
        
        # 检查是否被取消
        if cancel_event.is_set():
            logger.info(f"[PageKB API] 探索已取消: {task_id}")
            _explore_tasks[task_id]["status"] = "cancelled"
            db.delete(temp_session)
            db.commit()
            return
        
        # 存入知识库
        logger.info(f"[PageKB API] 正在存入知识库...")
        kb_result = await PageKnowledgeService.check_and_update(
            url=req.url,
            new_capabilities=page_capabilities,
            db=db,
        )
        
        action = kb_result.get('action', 'created')
        knowledge = kb_result.get('knowledge')
        diff = kb_result.get('diff')
        
        # 更新任务状态
        _explore_tasks[task_id]["status"] = "completed"
        _explore_tasks[task_id]["result"] = {
            "action": action,
            "version": knowledge.version if knowledge else 1,
            "hash": knowledge.hash_signature if knowledge else "",
            "page_data": page_data,
            "capabilities": page_capabilities,
            "diff": diff.to_dict() if diff else None,
            "explore_mode": "precision",  # 固定使用精准模式
        }
        
        # 清理临时会话
        db.delete(temp_session)
        db.commit()
        
        logger.info(f"[PageKB API] 精准探索完成: {task_id}")
        
    except Exception as e:
        logger.error(f"[PageKB API] 后台探索任务失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        _explore_tasks[task_id]["status"] = "failed"
        _explore_tasks[task_id]["error"] = str(e)
        try:
            db.delete(temp_session)
            db.commit()
        except:
            pass
    finally:
        db.close()


@router.post("/knowledge/stop-explore")
async def stop_explore(req: StopExploreRequest):
    """
    中止正在进行的页面探索任务
    """
    try:
        task_id = req.task_id
        
        if task_id not in _explore_tasks:
            return {"success": False, "message": "任务不存在或已完成"}
        
        task_info = _explore_tasks[task_id]
        
        if task_info["status"] in ("completed", "failed", "cancelled"):
            return {"success": False, "message": f"任务已{task_info['status']}，无法中止"}
        
        # 设置取消事件
        cancel_event = task_info["cancel_event"]
        cancel_event.set()
        
        # 如果有浏览器会话，尝试关闭
        browser_session = task_info.get("browser_session")
        if browser_session:
            try:
                await browser_session.kill()
                logger.info(f"[PageKB API] 已关闭浏览器: {task_id}")
            except Exception as e:
                logger.warning(f"[PageKB API] 关闭浏览器失败: {e}")
        
        task_info["status"] = "cancelled"
        
        logger.info(f"[PageKB API] 已中止探索任务: {task_id}")
        
        return {
            "success": True,
            "message": "探索任务已中止",
            "data": {"task_id": task_id, "status": "cancelled"}
        }
        
    except Exception as e:
        logger.error(f"[PageKB API] stop_explore 失败: {e}")
        return {"success": False, "message": str(e)}


@router.get("/knowledge/explore-status/{task_id}")
async def get_explore_status(task_id: str):
    """
    查询页面探索任务状态
    """
    try:
        if task_id not in _explore_tasks:
            return {"success": False, "message": "任务不存在"}
        
        task_info = _explore_tasks[task_id]
        
        response = {
            "success": True,
            "data": {
                "task_id": task_id,
                "status": task_info["status"],
                "url": task_info.get("url", ""),
            }
        }
        
        # 如果已完成，返回结果
        if task_info["status"] == "completed":
            response["data"]["result"] = task_info.get("result", {})
        
        # 如果失败，返回错误信息
        if task_info["status"] == "failed":
            response["data"]["error"] = task_info.get("error", "未知错误")
        
        return response
        
    except Exception as e:
        logger.error(f"[PageKB API] get_explore_status 失败: {e}")
        return {"success": False, "message": str(e)}
