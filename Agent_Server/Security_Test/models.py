"""
安全测试数据模型

作者: 程序员Eighteen
"""
from pydantic import BaseModel
from typing import Optional, Dict, List, Any
from datetime import datetime


class SecurityTargetCreate(BaseModel):
    """创建安全目标请求"""
    name: str
    base_url: str
    description: Optional[str] = None
    target_type: str = "web"
    environment: str = "test"
    auth_config: Optional[Dict] = None
    scan_config: Optional[Dict] = None


class SecurityTargetUpdate(BaseModel):
    """更新安全目标请求"""
    name: Optional[str] = None
    base_url: Optional[str] = None
    description: Optional[str] = None
    target_type: Optional[str] = None
    environment: Optional[str] = None
    auth_config: Optional[Dict] = None
    scan_config: Optional[Dict] = None
    is_active: Optional[int] = None


class ScanTaskCreate(BaseModel):
    """创建扫描任务请求"""
    target_id: int
    scan_type: str  # nuclei/sqlmap/xsstrike/fuzz/full_scan
    config: Optional[Dict] = {}


class ScanTaskResponse(BaseModel):
    """扫描任务响应"""
    id: int
    target_id: int
    scan_type: str
    status: str
    progress: int
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime


class VulnerabilityResponse(BaseModel):
    """漏洞响应"""
    id: int
    target_id: int
    title: str
    severity: str
    vuln_type: Optional[str] = None
    description: Optional[str] = None
    fix_suggestion: Optional[str] = None
    status: str
    risk_score: Optional[int] = None
    first_found: datetime
    last_seen: datetime


class ScanResultResponse(BaseModel):
    """扫描结果响应"""
    id: int
    task_id: int
    tool: str
    severity: str
    title: str
    description: Optional[str] = None
    url: Optional[str] = None
    param: Optional[str] = None
    payload: Optional[str] = None
    created_at: datetime