"""
一键测试 - 会话管理

管理一键测试的会话状态和消息历史
"""
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session

from database.connection import OneclickSession


# 状态机定义
VALID_TRANSITIONS = {
    'init': ['analyzing'],
    'analyzing': ['page_scanned', 'cases_generated', 'failed'],
    'page_scanned': ['cases_generated', 'failed'],
    'cases_generated': ['confirmed', 'failed'],
    'confirmed': ['executing', 'failed'],
    'executing': ['completed', 'failed'],
    'completed': [],
    'failed': ['init'],  # 允许重试
}


class SessionManager:
    """一键测试会话管理器"""

    @staticmethod
    def create_session(db: Session, user_input: str) -> OneclickSession:
        """创建新会话"""
        session = OneclickSession(
            user_input=user_input,
            status='init',
            messages=json.dumps([
                {"role": "user", "content": user_input, "time": datetime.now().isoformat()}
            ], ensure_ascii=False)
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    @staticmethod
    def get_session(db: Session, session_id: int) -> Optional[OneclickSession]:
        """获取会话"""
        return db.query(OneclickSession).filter(OneclickSession.id == session_id).first()

    @staticmethod
    def update_status(db: Session, session: OneclickSession, new_status: str) -> bool:
        """更新会话状态（带状态机校验）"""
        current = session.status
        if new_status not in VALID_TRANSITIONS.get(current, []):
            print(f"[Session] ⚠️ 非法状态转换: {current} → {new_status}")
            return False
        session.status = new_status
        db.commit()
        return True

    @staticmethod
    def add_message(db: Session, session: OneclickSession, role: str, content: str, extra: Dict = None):
        """添加对话消息"""
        messages = json.loads(session.messages) if session.messages else []
        msg = {"role": role, "content": content, "time": datetime.now().isoformat()}
        if extra:
            msg.update(extra)
        messages.append(msg)
        session.messages = json.dumps(messages, ensure_ascii=False)
        db.commit()

    @staticmethod
    def get_messages(session: OneclickSession) -> List[Dict]:
        """获取对话消息"""
        if not session.messages:
            return []
        return json.loads(session.messages) if isinstance(session.messages, str) else session.messages

    @staticmethod
    def list_sessions(db: Session, page: int = 1, page_size: int = 20) -> Dict:
        """获取会话列表"""
        query = db.query(OneclickSession).order_by(OneclickSession.created_at.desc())
        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return {
            "total": total,
            "items": [
                {
                    "id": s.id,
                    "user_input": s.user_input,
                    "status": s.status,
                    "target_url": s.target_url,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                }
                for s in items
            ]
        }
