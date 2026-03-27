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
import os
import time
from typing import Optional, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.connection import (
    get_db,
    resolve_project_context,
    get_active_project_by_id,
    QdrantCollectionConfig,
    OneclickSession,
    TestEnvironment,
)
from Page_Knowledge.service import PageKnowledgeService
from Page_Knowledge.vector_store import get_vector_store, apply_config_to_store
from Page_Knowledge.embedding import reload_embedding_client
from Page_Knowledge.schema import PageKnowledge
from Exploration.cache_service import ExplorationCacheService
from Exploration.dispatcher_service import ExplorationDispatcherService
from Exploration.finalizer import ExplorationFinalizer
from Exploration.orchestrator import ExplorationOrchestrator

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
    project_id: Optional[int] = None


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
        # 获取默认项目
        project = resolve_project_context(db, req.project_id)
        if not project:
            return {"success": False, "message": "没有可用的项目，请先创建并启用一个项目"}

        knowledge = PageKnowledge.from_capabilities(req.url, req.capabilities)
        result = await PageKnowledgeService.store(knowledge, db, project_id=project.id)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"[PageKB API] store 失败: {e}")
        return {"success": False, "message": str(e)}


@router.post("/knowledge/check-update")
async def knowledge_check_update(req: StoreRequest, db: Session = Depends(get_db)):
    """版本检查并自动更新"""
    try:
        project = resolve_project_context(db, req.project_id)
        if not project:
            return {"success": False, "message": "没有可用的项目，请先创建并启用一个项目"}
        if not project:
            return {"success": False, "message": "没有可用的项目，请先创建并启用一个项目"}
        result = await PageKnowledgeService.check_and_update(
            url=req.url,
            new_capabilities=req.capabilities,
            db=db,
            project_id=project.id,
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
                "merged_changes": result.get("merged_changes", 0),
            }
        }
    except Exception as e:
        logger.error(f"[PageKB API] check-update 失败: {e}")
        return {"success": False, "message": str(e)}


@router.get("/knowledge/list")
async def knowledge_list(domain: str = "", page_type: str = "", limit: int = 100, project_id: int = None, db: Session = Depends(get_db)):
    """列出所有页面知识"""
    try:
        from database.connection import get_active_project_by_id

        # 如果未指定项目，使用默认项目
        if project_id is None:
            project = resolve_project_context(db, project_id)
            if not project:
                # 没有启用的项目，返回空列表
                return {"success": True, "data": {"items": [], "total": 0}}
            project_id = project.id
        else:
            # 验证指定的项目是否启用（不报错，只是过滤）
            project = resolve_project_context(db, project_id)
            if not project:
                # 项目未启用，返回空列表
                return {"success": True, "data": {"items": [], "total": 0}}

        items = await PageKnowledgeService.list_all(
            domain=domain, page_type=page_type, limit=limit, project_id=project.id,
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


def _use_queue_exploration() -> bool:
    """Short-term gray switch for the shared browser-use exploration engine."""
    return os.getenv("EXPLORATION_ENGINE_V2", os.getenv("KNOWLEDGE_EXPLORATION_V2", "true")).lower() == "true"

class ExplorePageRequest(BaseModel):
    url: str
    username: str = ""
    password: str = ""
    user_goal: str = ""
    project_id: Optional[int] = None
    env_id: Optional[int] = None
    login_url: str = ""
    extra_credentials: Optional[Dict[str, Any]] = None


class StopExploreRequest(BaseModel):
    task_id: str


def _resolve_explore_environment(req: ExplorePageRequest, db: Session) -> Dict[str, Any]:
    matched_env = None
    if req.env_id:
        matched_env = db.query(TestEnvironment).filter(
            TestEnvironment.id == req.env_id,
            TestEnvironment.is_active == 1,
        ).first()

    target_url = (req.url or "").strip()
    login_url = (req.login_url or "").strip()
    username = req.username or ""
    password = req.password or ""
    extra_credentials = dict(req.extra_credentials or {})
    source = "manual"

    if matched_env:
        target_url = target_url or (matched_env.base_url or "").strip()
        login_url = login_url or (matched_env.login_url or matched_env.base_url or "").strip()
        username = username or (matched_env.username or "")
        password = password or (matched_env.password or "")
        if isinstance(matched_env.extra_credentials, dict):
            merged_credentials = dict(matched_env.extra_credentials)
            merged_credentials.update(extra_credentials)
            extra_credentials = merged_credentials
        source = f"test_env:{matched_env.name}"

    login_url = login_url or target_url
    return {
        "base_url": target_url,
        "target_url": target_url,
        "login_url": login_url,
        "username": username,
        "password": password,
        "extra_credentials": extra_credentials,
        "headless": os.getenv("HEADLESS", "false").lower() == "true",
        "_env_id": matched_env.id if matched_env else None,
        "_source": source,
        "env_name": matched_env.name if matched_env else source,
    }


def _resolve_project_id(req: ExplorePageRequest, db: Session) -> Optional[int]:
    project = resolve_project_context(db, req.project_id)
    return project.id if project else None


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

        # 构建探索环境信息
        env_info = _resolve_explore_environment(req, db)
        project_id = _resolve_project_id(req, db)
        if project_id is None:
            return {"success": False, "message": "没有可用的项目，请先创建并启用一个项目"}
        target_url = env_info.get("target_url", "")
        if not target_url:
            return {"success": False, "message": "未找到目标 URL，请选择测试环境或手动填写 URL"}

        # 创建临时会话（用于探索）
        from database.connection import OneclickSession
        temp_session = OneclickSession(
            project_id=project_id,
            user_input=req.user_goal or f"探索页面: {req.url}",
            target_url=target_url,
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
            "url": target_url,
            "status": "running",
            "engine": "",
            "current_task": "",
            "events": [],
            "artifact_summary": None,
        }

        # 启动后台探索任务
        asyncio.create_task(
            _background_explore_task(
                task_id, temp_session.id, req, env_info, cancel_event
            )
        )

        return {
            "success": True,
            "message": "页面探索已启动",
            "data": {
                "task_id": task_id,
                "temp_session_id": temp_session.id,
                "status": "running",
                "env_source": env_info.get("_source", ""),
                "project_id": project_id,
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
    env_info: Dict,
    cancel_event: asyncio.Event,
):
    """后台执行探索任务 - 使用精准探索模式"""
    from database.connection import SessionLocal
    from OneClick_Test.service import OneClickService

    db = SessionLocal()
    temp_session = None
    try:
        temp_session = db.query(OneclickSession).filter_by(id=temp_session_id).first()
        if not temp_session:
            logger.error(f"[PageKB API] 临时会话不存在: {temp_session_id}")
            _explore_tasks[task_id]["status"] = "failed"
            return

        def _status_callback(event_type: str, payload: Dict[str, Any]):
            task_state = _explore_tasks.get(task_id)
            if not task_state:
                return
            if event_type == "engine.selected":
                task_state["engine"] = payload.get("engine", task_state.get("engine", ""))
            elif event_type == "task.started":
                task_state["current_task"] = payload.get("title", "")
            elif event_type == "artifact.ready":
                task_state["artifact_summary"] = payload.get("summary")

            if payload:
                events = task_state.setdefault("events", [])
                events.append({
                    "type": event_type,
                    "payload": payload,
                    "ts": int(time.time()),
                })
                if len(events) > 50:
                    del events[:-50]

        use_queue = _use_queue_exploration()
        logger.info(
            "[PageKB API] 开始页面探索: url=%s mode=%s",
            env_info.get("target_url", req.url),
            "browser_use" if use_queue else "precision_browser_use",
        )

        if use_queue:
            explore_result = await ExplorationOrchestrator.run(
                mode="knowledge",
                goal=req.user_goal or f"探索页面: {req.url}",
                env_info=env_info,
                session_ref=_explore_tasks[task_id],
                cancel_event=cancel_event,
                status_callback=_status_callback,
            )
        else:
            explore_result = await OneClickService._explore_page_with_precision(
                db, temp_session, req.user_goal or f"探索页面: {req.url}", env_info
            )

        # 检查是否被取消
        if cancel_event.is_set():
            logger.info(f"[PageKB API] 探索已取消: {task_id}")
            _explore_tasks[task_id]["status"] = "cancelled"
            exploration_session_id = str(_explore_tasks[task_id].get("exploration_session_id") or "")
            if exploration_session_id:
                ExplorationFinalizer().cleanup_session_cache(exploration_session_id)
            db.delete(temp_session)
            db.commit()
            return

        if not explore_result.get("success"):
            _explore_tasks[task_id]["status"] = "failed"
            _explore_tasks[task_id]["error"] = explore_result.get('message', '未知错误')
            exploration_session_id = str(_explore_tasks[task_id].get("exploration_session_id") or "")
            if exploration_session_id:
                ExplorationFinalizer().cleanup_session_cache(exploration_session_id)
            db.delete(temp_session)
            db.commit()
            return

        page_data = explore_result.get("page_data", {})
        exploration_session_id = str(
            explore_result.get("exploration_session_id")
            or _explore_tasks[task_id].get("exploration_session_id")
            or ""
        )

        # 精准模式：直接使用 page_data 作为 capabilities
        page_capabilities = page_data

        # 检查是否被取消
        if cancel_event.is_set():
            logger.info(f"[PageKB API] 探索已取消: {task_id}")
            _explore_tasks[task_id]["status"] = "cancelled"
            if exploration_session_id:
                ExplorationFinalizer().cleanup_session_cache(exploration_session_id)
            db.delete(temp_session)
            db.commit()
            return

        # 存入知识库
        logger.info(f"[PageKB API] 正在存入知识库...")
        if use_queue and exploration_session_id:
            finalizer = ExplorationFinalizer()
            finalized = await finalizer.finalize_page_knowledge(
                session_id=exploration_session_id,
                url=env_info.get("target_url", req.url),
                page_data=page_capabilities,
                db=db,
                project_id=temp_session.project_id,
                cleanup=True,
            )
            page_capabilities = finalized.get("capabilities", page_capabilities)
            kb_result = finalized.get("knowledge_result", {})
        else:
            kb_result = await PageKnowledgeService.check_and_update(
                url=env_info.get("target_url", req.url),
                new_capabilities=page_capabilities,
                db=db,
                project_id=temp_session.project_id,
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
            "explore_mode": "browser_use" if use_queue else "precision_browser_use",
            "engine": _explore_tasks[task_id].get("engine", ""),
            "current_task": _explore_tasks[task_id].get("current_task", ""),
            "events": _explore_tasks[task_id].get("events", []),
            "artifact_summary": _explore_tasks[task_id].get("artifact_summary"),
            "exploration_session_id": exploration_session_id,
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
        exploration_session_id = str(_explore_tasks.get(task_id, {}).get("exploration_session_id") or "")
        if exploration_session_id:
            ExplorationFinalizer().cleanup_session_cache(exploration_session_id)
        try:
            if temp_session is not None:
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
        exploration_session_id = str(task_info.get("exploration_session_id") or "")
        if exploration_session_id:
            ExplorationFinalizer().cleanup_session_cache(exploration_session_id)

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
        exploration_session_id = str(task_info.get("exploration_session_id", "") or "")
        cache_debug: Dict[str, Any] = {}
        if exploration_session_id:
            dispatcher = ExplorationDispatcherService(ExplorationCacheService())
            cache_debug = dispatcher.get_session_snapshot(exploration_session_id)
            cache_debug["session_completion"] = dispatcher.finalize_session_if_ready(exploration_session_id)

        response = {
            "success": True,
            "data": {
                "task_id": task_id,
                "status": task_info["status"],
                "url": task_info.get("url", ""),
                "exploration_session_id": exploration_session_id,
                "engine": task_info.get("engine", ""),
                "current_task": task_info.get("current_task", ""),
                "events": task_info.get("events", []),
                "artifact_summary": task_info.get("artifact_summary"),
                "cache_debug": cache_debug,
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
