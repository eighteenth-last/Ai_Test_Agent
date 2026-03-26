from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ExplorationCacheService:
    """Redis-first cache service for exploration runtime artifacts."""

    _memory_store: Dict[str, Any] = {}

    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/2")
        self.enabled = os.getenv("EXPLORATION_CACHE_ENABLED", "true").lower() == "true"
        self.ttl_seconds = int(os.getenv("EXPLORATION_CACHE_TTL_SECONDS", str(24 * 3600)))
        self._client = None
        self._client_failed = False

    def _get_client(self):
        if not self.enabled:
            return None
        if self._client is not None:
            return self._client
        if self._client_failed:
            return None
        try:
            import redis

            self._client = redis.from_url(self.redis_url, decode_responses=True)
            self._client.ping()
            return self._client
        except Exception as exc:
            logger.warning("[ExplorationCache] Redis unavailable, fallback to memory: %s", exc)
            self._client_failed = True
            return None

    def _fallback_to_memory(self, exc: Exception):
        logger.warning("[ExplorationCache] Redis command failed, fallback to memory: %s", exc)
        self._client = None
        self._client_failed = True

    @staticmethod
    def _json_dumps(data: Any) -> str:
        return json.dumps(data, ensure_ascii=False)

    @staticmethod
    def _json_loads(data: Any, default):
        if data in (None, ""):
            return default
        if isinstance(data, (dict, list)):
            return data
        try:
            return json.loads(data)
        except Exception:
            return default

    def _touch(self, keys: List[str]):
        client = self._get_client()
        if client:
            try:
                if keys:
                    client.expire(*keys, time=self.ttl_seconds)  # type: ignore[arg-type]
            except TypeError:
                for key in keys:
                    try:
                        client.expire(key, self.ttl_seconds)
                    except Exception as exc:
                        self._fallback_to_memory(exc)
                        break
            except Exception as exc:
                self._fallback_to_memory(exc)
        else:
            now = int(time.time()) + self.ttl_seconds
            for key in keys:
                ExplorationCacheService._memory_store[f"{key}::__expire_at"] = now

    def _set_json(self, key: str, value: Any):
        client = self._get_client()
        if client:
            try:
                client.set(key, self._json_dumps(value), ex=self.ttl_seconds)
                return
            except Exception as exc:
                self._fallback_to_memory(exc)
        if True:
            ExplorationCacheService._memory_store[key] = value
            ExplorationCacheService._memory_store[f"{key}::__expire_at"] = int(time.time()) + self.ttl_seconds

    def _get_json(self, key: str, default):
        self._cleanup_expired_memory()
        client = self._get_client()
        if client:
            try:
                return self._json_loads(client.get(key), default)
            except Exception as exc:
                self._fallback_to_memory(exc)
        return ExplorationCacheService._memory_store.get(key, default)

    def _append_json(self, key: str, value: Any):
        client = self._get_client()
        if client:
            try:
                client.rpush(key, self._json_dumps(value))
                client.expire(key, self.ttl_seconds)
                return
            except Exception as exc:
                self._fallback_to_memory(exc)
        if True:
            values = ExplorationCacheService._memory_store.setdefault(key, [])
            if not isinstance(values, list):
                values = []
                ExplorationCacheService._memory_store[key] = values
            values.append(value)
            ExplorationCacheService._memory_store[f"{key}::__expire_at"] = int(time.time()) + self.ttl_seconds

    def _list_json(self, key: str) -> List[Any]:
        self._cleanup_expired_memory()
        client = self._get_client()
        if client:
            try:
                values = client.lrange(key, 0, -1)
                return [self._json_loads(item, {}) for item in values]
            except Exception as exc:
                self._fallback_to_memory(exc)
        values = ExplorationCacheService._memory_store.get(key, [])
        return values if isinstance(values, list) else []

    def _delete_prefix(self, prefix: str):
        client = self._get_client()
        if client:
            try:
                keys = client.keys(f"{prefix}*")
                if keys:
                    client.delete(*keys)
            except Exception as exc:
                self._fallback_to_memory(exc)
        if not client or self._client_failed:
            for key in list(ExplorationCacheService._memory_store.keys()):
                if key.startswith(prefix):
                    ExplorationCacheService._memory_store.pop(key, None)

    @staticmethod
    def _cleanup_expired_memory():
        now = int(time.time())
        expired_prefixes: List[str] = []
        for key, expire_at in list(ExplorationCacheService._memory_store.items()):
            if not key.endswith("::__expire_at"):
                continue
            if isinstance(expire_at, int) and expire_at <= now:
                expired_prefixes.append(key[: -len("::__expire_at")])
        for prefix in expired_prefixes:
            ExplorationCacheService._memory_store.pop(prefix, None)
            ExplorationCacheService._memory_store.pop(f"{prefix}::__expire_at", None)

    @staticmethod
    def session_key(session_id: str) -> str:
        return f"exploration:session:{session_id}"

    @staticmethod
    def frontier_key(session_id: str) -> str:
        return f"exploration:session:{session_id}:frontier"

    @staticmethod
    def navigation_key(session_id: str) -> str:
        return f"exploration:session:{session_id}:navigation"

    @staticmethod
    def session_pages_key(session_id: str) -> str:
        return f"exploration:session:{session_id}:pages"

    @staticmethod
    def session_artifacts_key(session_id: str) -> str:
        return f"exploration:session:{session_id}:artifacts"

    @staticmethod
    def page_meta_key(page_key: str) -> str:
        return f"exploration:page:{page_key}:meta"

    @staticmethod
    def page_scan_key(page_key: str) -> str:
        return f"exploration:page:{page_key}:scan"

    @staticmethod
    def page_tasks_key(page_key: str) -> str:
        return f"exploration:page:{page_key}:tasks"

    @staticmethod
    def page_artifacts_key(page_key: str) -> str:
        return f"exploration:page:{page_key}:artifacts"

    @staticmethod
    def task_result_key(task_id: str) -> str:
        return f"exploration:task:{task_id}:result"

    def start_session(self, session_id: str, payload: Dict[str, Any]):
        self._set_json(self.session_key(session_id), payload)

    def get_session(self, session_id: str) -> Dict[str, Any]:
        return self._get_json(self.session_key(session_id), {})

    def update_session(self, session_id: str, patch: Dict[str, Any]):
        current = self.get_session(session_id)
        current.update(patch)
        self._set_json(self.session_key(session_id), current)

    def append_frontier(self, session_id: str, page_payload: Dict[str, Any]):
        self._append_json(self.frontier_key(session_id), page_payload)

    def list_frontier(self, session_id: str) -> List[Dict[str, Any]]:
        return self._list_json(self.frontier_key(session_id))

    def append_navigation(self, session_id: str, payload: Dict[str, Any]):
        self._append_json(self.navigation_key(session_id), payload)

    def list_navigation(self, session_id: str) -> List[Dict[str, Any]]:
        return self._list_json(self.navigation_key(session_id))

    def save_frontier(self, session_id: str, items: List[Dict[str, Any]]):
        self._set_json(self.frontier_key(session_id), items)

    def update_frontier_entry(self, session_id: str, page_key: str, patch: Dict[str, Any]):
        frontier = self.list_frontier(session_id)
        updated = False
        for item in frontier:
            if str(item.get("page_key") or "") != page_key:
                continue
            item.update(patch)
            updated = True
            break
        if updated:
            self.save_frontier(session_id, frontier)

    def add_session_page(self, session_id: str, page_key: str):
        pages = self._get_json(self.session_pages_key(session_id), [])
        if not isinstance(pages, list):
            pages = []
        if page_key not in pages:
            pages.append(page_key)
            self._set_json(self.session_pages_key(session_id), pages)

    def list_session_pages(self, session_id: str) -> List[str]:
        pages = self._get_json(self.session_pages_key(session_id), [])
        return [str(item) for item in pages] if isinstance(pages, list) else []

    def append_session_artifact(self, session_id: str, payload: Dict[str, Any]):
        self._append_json(self.session_artifacts_key(session_id), payload)

    def list_session_artifacts(self, session_id: str) -> List[Dict[str, Any]]:
        return self._list_json(self.session_artifacts_key(session_id))

    def save_page_meta(self, page_key: str, payload: Dict[str, Any]):
        self._set_json(self.page_meta_key(page_key), payload)

    def get_page_meta(self, page_key: str) -> Dict[str, Any]:
        return self._get_json(self.page_meta_key(page_key), {})

    def save_page_scan(self, page_key: str, payload: Dict[str, Any]):
        self._set_json(self.page_scan_key(page_key), payload)

    def get_page_scan(self, page_key: str) -> Dict[str, Any]:
        return self._get_json(self.page_scan_key(page_key), {})

    def save_page_tasks(self, page_key: str, tasks: List[Dict[str, Any]]):
        self._set_json(self.page_tasks_key(page_key), tasks)

    def get_page_tasks(self, page_key: str) -> List[Dict[str, Any]]:
        return self._get_json(self.page_tasks_key(page_key), [])

    def append_page_artifact(self, page_key: str, payload: Dict[str, Any]):
        self._append_json(self.page_artifacts_key(page_key), payload)

    def list_page_artifacts(self, page_key: str) -> List[Dict[str, Any]]:
        return self._list_json(self.page_artifacts_key(page_key))

    def save_task_result(self, task_id: str, payload: Dict[str, Any]):
        self._set_json(self.task_result_key(task_id), payload)

    def get_task_result(self, task_id: str) -> Dict[str, Any]:
        return self._get_json(self.task_result_key(task_id), {})

    def cleanup_session(self, session_id: str):
        page_keys = self.list_session_pages(session_id)
        self._delete_prefix(f"exploration:session:{session_id}")
        for page_key in page_keys:
            self._delete_prefix(self.page_meta_key(page_key))
            self._delete_prefix(self.page_scan_key(page_key))
            self._delete_prefix(self.page_tasks_key(page_key))
            self._delete_prefix(self.page_artifacts_key(page_key))
        safe_session_id = session_id.replace(":", "_")
        self._delete_prefix(f"exploration:task:task_{safe_session_id}_")
