"""
Qdrant vector store wrapper for Page Knowledge Base.
"""
import os
import logging
import time
import uuid
from typing import List, Dict, Optional, Any

# 跳过系统代理对 localhost 的拦截（防止系统全局代理导致 qdrant-client 请求返回 503）
_no_proxy = os.environ.get("NO_PROXY", "")
_no_proxy_items = {s.strip() for s in _no_proxy.split(",") if s.strip()}
_no_proxy_items.update({"localhost", "127.0.0.1", "::1"})
os.environ["NO_PROXY"] = ",".join(_no_proxy_items)
os.environ["no_proxy"] = os.environ["NO_PROXY"]

logger = logging.getLogger(__name__)

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "page_knowledge")
QDRANT_RETRY_SECONDS = int(os.getenv("QDRANT_RETRY_SECONDS", "30"))


class VectorStore:

    def __init__(
        self,
        host: str = QDRANT_HOST,
        port: int = QDRANT_PORT,
        collection_name: str = QDRANT_COLLECTION,
        vector_size: int = 1024,
        distance: str = "Cosine",
    ):
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.vector_size = vector_size
        self._distance = distance  # Cosine / Dot / Euclid / Manhattan
        self._client = None
        self._initialized = False
        self._retry_seconds = max(QDRANT_RETRY_SECONDS, 1)
        self._unavailable_until = 0.0
        self._last_error = ""

    def reload_config(self, config: dict) -> None:
        """热更新 Qdrant 连接与 Collection 配置，重置内部状态"""
        self.host = config.get("qdrant_host", self.host)
        self.port = int(config.get("qdrant_port", self.port))
        self.collection_name = config.get("collection_name", self.collection_name)
        self.vector_size = int(config.get("vector_size", self.vector_size))
        self._distance = config.get("distance", self._distance)
        # 关闭旧连接，下次使用时重新建立
        self._client = None
        self._initialized = False
        self._unavailable_until = 0.0
        self._last_error = ""
        logger.info(f"[VectorStore] 配置已热更新: {self.host}:{self.port}/{self.collection_name} dim={self.vector_size} distance={self._distance}")

    def _is_temporarily_unavailable(self) -> bool:
        return time.time() < self._unavailable_until

    def _mark_unavailable(self, reason: str, op: str = "") -> None:
        # 已在降级窗口内且错误相同，不重复刷 warning
        if self._is_temporarily_unavailable() and reason == self._last_error:
            return
        self._client = None
        self._initialized = False
        self._last_error = reason
        self._unavailable_until = time.time() + self._retry_seconds
        label = f"{op} failed" if op else "unavailable"
        logger.warning(
            f"[VectorStore] {label}, degraded for {self._retry_seconds}s: {reason}"
        )

    def _mark_available(self) -> None:
        self._last_error = ""
        self._unavailable_until = 0.0

    def _get_client(self):
        if self._is_temporarily_unavailable():
            wait = max(1, int(self._unavailable_until - time.time()))
            raise RuntimeError(
                f"Qdrant temporarily unavailable, retry in {wait}s: {self._last_error or 'unknown'}"
            )
        if self._client is None:
            try:
                from qdrant_client import QdrantClient
                self._client = QdrantClient(
                    host=self.host, port=self.port, timeout=3,
                    check_compatibility=False,
                    prefer_grpc=False,
                )
                logger.info(f"[VectorStore] Connected to Qdrant @ {self.host}:{self.port}")
                self._mark_available()
            except ImportError:
                self._mark_unavailable(
                    "qdrant-client not installed. Run: pip install qdrant-client",
                    "connect",
                )
                raise
            except Exception as e:
                self._mark_unavailable(str(e), "connect")
                raise
        return self._client

    def ensure_collection(self):
        if self._initialized:
            return True
        if self._is_temporarily_unavailable():
            return False
        try:
            from qdrant_client.models import Distance, VectorParams
            client = self._get_client()
            collections = [c.name for c in client.get_collections().collections]
            if self.collection_name not in collections:
                dist_map = {
                    "cosine": Distance.COSINE,
                    "dot": Distance.DOT,
                    "euclid": Distance.EUCLID,
                    "manhattan": Distance.MANHATTAN,
                }
                dist_obj = dist_map.get(self._distance.lower(), Distance.COSINE)
                client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=self.vector_size, distance=dist_obj),
                )
                logger.info(f"[VectorStore] Created collection: {self.collection_name} (dim={self.vector_size})")
            else:
                logger.info(f"[VectorStore] Collection already exists: {self.collection_name}")
            self._initialized = True
            self._mark_available()
            return True
        except Exception as e:
            self._mark_unavailable(str(e), "ensure_collection")
            return False

    def upsert(self, point_id: str, vector: List[float], payload: Dict[str, Any]) -> bool:
        try:
            from qdrant_client.models import PointStruct
            if not self.ensure_collection():
                return False
            if len(vector) != self.vector_size and len(vector) > 0:
                self.vector_size = len(vector)
            client = self._get_client()
            client.upsert(
                collection_name=self.collection_name,
                points=[PointStruct(id=point_id, vector=vector, payload=payload)],
            )
            return True
        except Exception as e:
            self._mark_unavailable(str(e), "upsert")
            return False

    def search(
        self,
        query_vector: List[float],
        limit: int = 5,
        score_threshold: float = 0.0,
        filter_conditions: Optional[Dict] = None,
    ) -> List[Dict]:
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            if not self.ensure_collection():
                return []
            client = self._get_client()
            qdrant_filter = None
            if filter_conditions:
                must = [FieldCondition(key=k, match=MatchValue(value=v)) for k, v in filter_conditions.items()]
                qdrant_filter = Filter(must=must)
            results = client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=qdrant_filter,
            )
            return [{"id": str(r.id), "score": r.score, "payload": r.payload or {}} for r in results]
        except Exception as e:
            self._mark_unavailable(str(e), "search")
            return []

    def get_by_id(self, point_id: str) -> Optional[Dict]:
        try:
            if not self.ensure_collection():
                return None
            client = self._get_client()
            results = client.retrieve(
                collection_name=self.collection_name,
                ids=[point_id],
                with_payload=True,
                with_vectors=False,
            )
            if results:
                r = results[0]
                return {"id": str(r.id), "payload": r.payload or {}}
            return None
        except Exception as e:
            self._mark_unavailable(str(e), "get_by_id")
            return None

    def delete(self, point_id: str) -> bool:
        try:
            from qdrant_client.models import PointIdsList
            if not self.ensure_collection():
                return False
            client = self._get_client()
            client.delete(
                collection_name=self.collection_name,
                points_selector=PointIdsList(points=[point_id]),
            )
            return True
        except Exception as e:
            self._mark_unavailable(str(e), "delete")
            return False

    def scroll_all(self, filter_conditions: Optional[Dict] = None, limit: int = 100) -> List[Dict]:
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            if not self.ensure_collection():
                return []
            client = self._get_client()
            qdrant_filter = None
            if filter_conditions:
                must = [FieldCondition(key=k, match=MatchValue(value=v)) for k, v in filter_conditions.items()]
                qdrant_filter = Filter(must=must)
            results, _next = client.scroll(
                collection_name=self.collection_name,
                limit=limit,
                scroll_filter=qdrant_filter,
                with_payload=True,
                with_vectors=False,
            )
            return [{"id": str(r.id), "payload": r.payload or {}} for r in results]
        except Exception as e:
            self._mark_unavailable(str(e), "scroll_all")
            return []

    def count(self) -> int:
        try:
            if not self.ensure_collection():
                return 0
            client = self._get_client()
            info = client.get_collection(self.collection_name)
            return info.points_count or 0
        except Exception as e:
            self._mark_unavailable(str(e), "count")
            return 0

    def health_check(self) -> Dict:
        if self._is_temporarily_unavailable():
            wait = max(1, int(self._unavailable_until - time.time()))
            return {
                "status": "degraded",
                "host": f"{self.host}:{self.port}",
                "error": self._last_error,
                "retry_in_seconds": wait,
            }
        try:
            client = self._get_client()
            info = client.get_collections()
            collection_names = [c.name for c in info.collections]
            return {
                "status": "healthy",
                "host": f"{self.host}:{self.port}",
                "collections": collection_names,
                "target_collection": self.collection_name,
                "exists": self.collection_name in collection_names,
                "count": self.count() if self.collection_name in collection_names else 0,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "host": f"{self.host}:{self.port}",
                "error": str(e),
            }


def generate_point_id(url: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, url))


_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store


def apply_config_to_store(config: dict) -> None:
    """将 DB 里的 QdrantCollectionConfig 应用到全局 VectorStore 单例"""
    store = get_vector_store()
    store.reload_config(config)
