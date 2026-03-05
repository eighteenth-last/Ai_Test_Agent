"""
禅道集成 - 服务层

配置管理、Bug 推送 / 同步、用例导入。
"""
import logging
from typing import Optional
from sqlalchemy.orm import Session
from database.connection import ZentaoConfig, BugReport, ExecutionCase
from Zentao_manage.client import ZentaoClient

logger = logging.getLogger(__name__)


# =====================================================================
# 辅助：从数据库获取激活的禅道配置并创建客户端
# =====================================================================

def _get_active_config(db: Session) -> Optional[ZentaoConfig]:
    return db.query(ZentaoConfig).filter(ZentaoConfig.is_active == 1).first()


def _build_client(cfg: ZentaoConfig) -> ZentaoClient:
    return ZentaoClient(
        base_url=cfg.base_url,
        account=cfg.account,
        password=cfg.password,
    )


# =====================================================================
# 1. 配置管理 CRUD
# =====================================================================

class ZentaoConfigService:

    @staticmethod
    def list_configs(db: Session) -> list[dict]:
        rows = db.query(ZentaoConfig).order_by(ZentaoConfig.id.desc()).all()
        return [ZentaoConfigService._to_dict(r) for r in rows]

    @staticmethod
    def get_active(db: Session) -> Optional[dict]:
        cfg = _get_active_config(db)
        return ZentaoConfigService._to_dict(cfg) if cfg else None

    @staticmethod
    def create(db: Session, data: dict) -> dict:
        cfg = ZentaoConfig(**{k: v for k, v in data.items()
                              if hasattr(ZentaoConfig, k)})
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
        return ZentaoConfigService._to_dict(cfg)

    @staticmethod
    def update(db: Session, config_id: int, data: dict) -> dict:
        cfg = db.query(ZentaoConfig).filter(ZentaoConfig.id == config_id).first()
        if not cfg:
            raise ValueError("配置不存在")
        for k, v in data.items():
            if hasattr(cfg, k) and k not in ("id", "created_at"):
                setattr(cfg, k, v)
        db.commit()
        db.refresh(cfg)
        return ZentaoConfigService._to_dict(cfg)

    @staticmethod
    def delete(db: Session, config_id: int):
        cfg = db.query(ZentaoConfig).filter(ZentaoConfig.id == config_id).first()
        if not cfg:
            raise ValueError("配置不存在")
        db.delete(cfg)
        db.commit()

    @staticmethod
    def activate(db: Session, config_id: int) -> dict:
        """激活指定配置，同时取消其他配置的激活"""
        db.query(ZentaoConfig).update({ZentaoConfig.is_active: 0})
        cfg = db.query(ZentaoConfig).filter(ZentaoConfig.id == config_id).first()
        if not cfg:
            raise ValueError("配置不存在")
        cfg.is_active = 1
        db.commit()
        db.refresh(cfg)
        return ZentaoConfigService._to_dict(cfg)

    @staticmethod
    def _to_dict(cfg: ZentaoConfig) -> dict:
        return {
            "id": cfg.id,
            "config_name": cfg.config_name,
            "base_url": cfg.base_url,
            "account": cfg.account,
            "default_product_id": cfg.default_product_id,
            "api_version": cfg.api_version,
            "is_active": cfg.is_active,
            "description": cfg.description,
            "created_at": cfg.created_at.isoformat() if cfg.created_at else None,
            "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
        }


# =====================================================================
# 2. Bug 推送到禅道
# =====================================================================

class ZentaoBugService:

    @staticmethod
    async def push_bug(db: Session, bug_id: int,
                       product_id: int | None = None,
                       severity: int = 3, pri: int = 3) -> dict:
        """将本系统 Bug 推送到禅道"""
        cfg = _get_active_config(db)
        if not cfg:
            raise ValueError("请先配置并激活禅道连接")

        bug: BugReport = db.query(BugReport).filter(BugReport.id == bug_id).first()
        if not bug:
            raise ValueError("Bug 不存在")
        if bug.zentao_bug_id:
            return {"success": False, "message": f"该 Bug 已推送到禅道 (ID={bug.zentao_bug_id})"}

        pid = product_id or cfg.default_product_id
        if not pid:
            raise ValueError("未指定产品ID，且禅道配置中未设置默认产品")

        logger.info(f"[Zentao] 推送 Bug id={bug_id} 到产品 product_id={pid}，"
                    f"禅道配置 default_product_id={cfg.default_product_id}")

        # 组装步骤描述
        steps = _format_bug_steps(bug)

        client = _build_client(cfg)
        result = await client.create_bug(
            product_id=pid,
            title=f"【AI Test Agent】{bug.bug_name}",
            steps=steps,
            severity=severity,
            pri=pri,
            bug_type=_map_error_type(bug.error_type),
        )

        logger.info(f"[Zentao] push_bug 原始响应: {result}")

        # 兼容多种禅道响应结构：flat / {"bug": {...}} / {"data": {...}}
        zentao_id = (
            result.get("id")
            or result.get("bugID")
            or (result.get("bug") or {}).get("id")
            or (result.get("data") or {}).get("id")
        )

        if not zentao_id:
            # 禅道返回了响应但没有 bug ID，说明创建失败
            error_msg = (
                result.get("error")
                or result.get("message")
                or result.get("msg")
                or f"禅道响应中未找到 Bug ID，原始响应: {result}"
            )
            logger.error(f"[Zentao] Bug 创建失败: {error_msg}")
            return {"success": False, "message": str(error_msg)}

        bug.zentao_bug_id = int(zentao_id)
        db.commit()

        return {
            "success": True,
            "zentao_bug_id": int(zentao_id),
            "message": f"Bug 已成功推送到禅道 (ID={zentao_id})"
        }

    @staticmethod
    async def batch_push_bugs(db: Session, bug_ids: list[int],
                              product_id: int | None = None) -> dict:
        """批量推送 Bug 到禅道"""
        results = []
        for bid in bug_ids:
            try:
                r = await ZentaoBugService.push_bug(db, bid, product_id)
                results.append({"bug_id": bid, **r})
            except Exception as e:
                results.append({"bug_id": bid, "success": False, "message": str(e)})
        success_count = sum(1 for r in results if r.get("success"))
        return {
            "total": len(bug_ids),
            "success_count": success_count,
            "failed_count": len(bug_ids) - success_count,
            "details": results
        }

    @staticmethod
    async def sync_bug_status(db: Session, bug_id: int | None = None) -> dict:
        """从禅道同步 Bug 状态到本地"""
        cfg = _get_active_config(db)
        if not cfg:
            raise ValueError("请先配置并激活禅道连接")

        client = _build_client(cfg)

        if bug_id:
            bugs = [db.query(BugReport).filter(BugReport.id == bug_id).first()]
        else:
            bugs = db.query(BugReport).filter(BugReport.zentao_bug_id.isnot(None)).all()

        synced = 0
        errors = []
        for bug in bugs:
            if not bug or not bug.zentao_bug_id:
                continue
            try:
                remote = await client.get_bug(bug.zentao_bug_id)
                remote_status = remote.get("status", "")
                local_status = _map_zentao_status(remote_status)
                if local_status and bug.status != local_status:
                    bug.status = local_status
                    synced += 1
            except Exception as e:
                errors.append({"bug_id": bug.id, "error": str(e)})

        db.commit()
        return {
            "total": len(bugs),
            "synced": synced,
            "errors": errors,
            "message": f"同步完成，更新 {synced} 条"
        }


# =====================================================================
# 3. 从禅道导入测试用例
# =====================================================================

class ZentaoCaseService:

    @staticmethod
    async def import_cases(db: Session, product_id: int | None = None,
                           suite_id: int | None = None,
                           case_ids: list[int] | None = None,
                           limit: int | None = None,
                           concurrency: int = 5) -> dict:
        """从禅道并发导入测试用例到本地用例库"""
        cfg = _get_active_config(db)
        if not cfg:
            raise ValueError("请先配置并激活禅道连接")

        client = _build_client(cfg)
        _conc = max(1, concurrency or 5)

        def _apply_limit(id_list):
            return id_list[:limit] if limit and limit > 0 else id_list

        if case_ids:
            cids = _apply_limit(case_ids)
            cases_data = await _fetch_cases_detail(client, cids, _conc)
        elif suite_id:
            raw = await client.get_test_suite_cases(suite_id)
            cases_data = await _fetch_cases_detail(client, _apply_limit(_extract_case_ids(raw)), _conc)
        elif product_id:
            raw = await client.get_product_cases(product_id)
            cases_data = await _fetch_cases_detail(client, _apply_limit(_extract_case_ids(raw)), _conc)
        else:
            pid = cfg.default_product_id
            if not pid:
                raise ValueError("需要指定 product_id 或 suite_id")
            raw = await client.get_product_cases(pid)
            cases_data = await _fetch_cases_detail(client, _apply_limit(_extract_case_ids(raw)), _conc)

        # 查询已存在的用例标题，用于去重
        existing_titles = {
            row[0] for row in db.query(ExecutionCase.title).filter(
                ExecutionCase.case_type == "禅道导入"
            ).all()
        }

        # 写入本地 execution_cases 表（过滤重复）
        imported = 0
        skipped = 0
        for c in cases_data:
            title = c.get("title", "").strip()
            if not title:
                continue
            if title in existing_titles:
                skipped += 1
                continue
            ec = ExecutionCase(
                title=title,
                module=c.get("module", "禅道导入"),
                precondition=c.get("precondition", ""),
                steps=c.get("steps", "[]"),
                expected=c.get("expected", ""),
                keywords=c.get("keywords", ""),
                priority=str(c.get("priority", 3)),
                case_type="禅道导入",
            )
            db.add(ec)
            existing_titles.add(title)  # 防止同批次内重复
            imported += 1

        db.commit()
        return {
            "success": True,
            "total_fetched": len(cases_data),
            "imported": imported,
            "skipped": skipped,
            "message": f"成功导入 {imported} 条用例，跳过重复 {skipped} 条"
        }

    @staticmethod
    async def list_products(db: Session) -> list:
        """获取禅道产品列表（用于前端选择）"""
        cfg = _get_active_config(db)
        if not cfg:
            raise ValueError("请先配置并激活禅道连接")
        client = _build_client(cfg)
        return await client.get_products()


# =====================================================================
# 内部辅助函数
# =====================================================================

def _format_bug_steps(bug: BugReport) -> str:
    """将本地 Bug 数据格式化为禅道 steps 字段"""
    parts = ["<p><strong>[步骤]</strong></p>"]
    if bug.reproduce_steps:
        parts.append(f"<p>{bug.reproduce_steps}</p>")
    parts.append("<p><strong>[结果]</strong></p>")
    if bug.actual_result:
        parts.append(f"<p>{bug.actual_result}</p>")
    elif bug.result_feedback:
        parts.append(f"<p>{bug.result_feedback}</p>")
    parts.append("<p><strong>[期望]</strong></p>")
    if bug.expected_result:
        parts.append(f"<p>{bug.expected_result}</p>")

    if bug.location_url:
        parts.append(f"<p><strong>[定位地址]</strong> {bug.location_url}</p>")
    if bug.description:
        parts.append(f"<p><strong>[描述]</strong> {bug.description}</p>")
    return "\n".join(parts)


_ERROR_TYPE_MAP = {
    "功能缺陷": "codeerror",
    "UI异常": "interface",
    "性能问题": "performance",
    "安全漏洞": "security",
    "兼容性问题": "compatible",
    "配置错误": "config",
}


def _map_error_type(error_type: str) -> str:
    return _ERROR_TYPE_MAP.get(error_type, "codeerror")


_ZENTAO_STATUS_MAP = {
    "active": "待处理",
    "resolved": "已修复",
    "closed": "已关闭",
}


def _map_zentao_status(zentao_status: str) -> str | None:
    return _ZENTAO_STATUS_MAP.get(zentao_status)


def _extract_case(raw: dict) -> dict:
    """从传统接口的单条用例响应中提取信息"""
    case_data = raw.get("data", raw)
    if isinstance(case_data, str):
        import json
        try:
            case_data = json.loads(case_data)
        except Exception:
            return {}

    case_obj = case_data.get("case", case_data)

    # 提取步骤
    steps_list = case_obj.get("steps", {})
    steps_text = []
    expected_text = []
    if isinstance(steps_list, dict):
        for _, step in sorted(steps_list.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0):
            if isinstance(step, dict):
                steps_text.append(step.get("desc", ""))
                expected_text.append(step.get("expect", ""))
    elif isinstance(steps_list, list):
        for step in steps_list:
            if isinstance(step, dict):
                steps_text.append(step.get("desc", ""))
                expected_text.append(step.get("expect", ""))

    import json
    return {
        "title": case_obj.get("title", ""),
        "module": case_obj.get("moduleName", case_obj.get("module", "")),
        "precondition": case_obj.get("precondition", ""),
        "steps": json.dumps([{"step": s, "expected": e}
                             for s, e in zip(steps_text, expected_text)],
                            ensure_ascii=False),
        "expected": "\n".join(e for e in expected_text if e),
        "keywords": case_obj.get("keywords", ""),
        "priority": case_obj.get("pri", 3),
    }


def _extract_cases_from_list(raw) -> list[dict]:
    """从产品/套件的批量用例响应中提取（兼容 list 和 dict 两种返回格式）"""
    cases = []

    # 部分禅道版本 get_product_cases 已返回 list，直接处理
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                cases.append(_extract_case({"data": {"case": item}}))
        return cases

    # dict 格式响应
    data = raw.get("data", raw)
    if isinstance(data, str):
        import json
        try:
            data = json.loads(data)
        except Exception:
            return []

    # data 本身也可能是 list
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                cases.append(_extract_case({"data": {"case": item}}))
        return cases

    case_list = data.get("cases", data.get("testcases", []))
    if isinstance(case_list, dict):
        case_list = list(case_list.values())

    for item in case_list:
        if isinstance(item, dict):
            cases.append(_extract_case({"data": {"case": item}}))
    return cases


def _parse_case_id(raw_id) -> int | None:
    """将禅道用例 ID 转为整数，兼容 'case_432'、432、'432' 等格式"""
    import re
    s = str(raw_id).strip()
    m = re.search(r'\d+', s)
    if m:
        return int(m.group())
    return None


def _extract_case_ids(raw) -> list:
    """从批量用例响应中提取所有用例 ID 列表"""
    ids = []

    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and item.get("id"):
                cid = _parse_case_id(item["id"])
                if cid:
                    ids.append(cid)
        return ids

    data = raw.get("data", raw) if isinstance(raw, dict) else raw
    if isinstance(data, str):
        import json
        try:
            data = json.loads(data)
        except Exception:
            return []

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("id"):
                cid = _parse_case_id(item["id"])
                if cid:
                    ids.append(cid)
        return ids

    case_list = data.get("cases", data.get("testcases", []))
    if isinstance(case_list, dict):
        case_list = list(case_list.values())

    for item in case_list:
        if isinstance(item, dict) and item.get("id"):
            cid = _parse_case_id(item["id"])
            if cid:
                ids.append(cid)
    return ids


async def _fetch_cases_detail(client, case_ids: list, concurrency: int = 5) -> list:
    """并发拉取用例完整详情（包含 steps/precondition/expected/keywords）"""
    import asyncio
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def _fetch_one(cid):
        async with semaphore:
            try:
                raw = await client.get_test_case(cid)
                c = _extract_case(raw)
                return c if c.get("title") else None
            except Exception as e:
                logger.warning(f"[Zentao] 拉取用例详情 id={cid} 失败: {e}")
                return None

    results = await asyncio.gather(*[_fetch_one(cid) for cid in case_ids])
    return [r for r in results if r is not None]
