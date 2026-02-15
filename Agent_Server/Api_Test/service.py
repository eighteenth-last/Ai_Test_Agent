"""
接口测试服务

实现：智能匹配接口文件、endpoint 级匹配、DSL 生成、HTTP Runner、结果入库

作者: Ai_Test_Agent Team
"""
import json
import time
import traceback
import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

import requests as http_requests
from sqlalchemy.orm import Session

from database.connection import (
    ExecutionCase, ApiSpecVersion, ApiEndpoint, ApiSpec,
    TestRecord, ExecutionBatch, TestReport, BugReport,
    Contact, EmailConfig, EmailRecord
)
from llm import get_llm_client

logger = logging.getLogger(__name__)


class ApiTestService:
    """接口测试服务"""

    @staticmethod
    def match_spec(
        test_case_ids: List[int],
        db: Session,
        top_k: int = 5,
        service_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        智能匹配接口文件

        两段式匹配：
        1. 粗筛：关键词 overlap 筛选候选 spec versions
        2. 精排：LLM 从候选中选出 top1 推荐
        """
        # 获取测试用例
        cases = db.query(ExecutionCase).filter(
            ExecutionCase.id.in_(test_case_ids)
        ).all()
        if not cases:
            return {"success": False, "message": "未找到指定的测试用例"}

        # 合并用例文本
        case_texts = []
        for c in cases:
            text = f"标题: {c.title}"
            if c.steps:
                text += f"\n步骤: {c.steps}"
            if c.expected:
                text += f"\n预期: {c.expected}"
            if c.keywords:
                text += f"\n关键词: {c.keywords}"
            case_texts.append(text)
        combined_text = "\n---\n".join(case_texts)

        # 获取所有 spec versions
        query = db.query(ApiSpecVersion)
        if service_name:
            spec_ids = [s.id for s in db.query(ApiSpec).filter(
                ApiSpec.service_name == service_name
            ).all()]
            if spec_ids:
                query = query.filter(ApiSpecVersion.spec_id.in_(spec_ids))

        versions = query.all()
        if not versions:
            return {"success": False, "message": "暂无已上传的接口文件，请先上传"}

        # 粗筛：关键词 overlap 打分
        candidates = []
        for v in versions:
            spec = db.query(ApiSpec).filter(ApiSpec.id == v.spec_id).first()
            score = _keyword_overlap_score(combined_text, v.parse_summary or '', v.original_filename)
            endpoints = db.query(ApiEndpoint).filter(
                ApiEndpoint.spec_version_id == v.id
            ).all()
            ep_list = [{"method": ep.method, "path": ep.path, "summary": ep.summary or ''} for ep in endpoints]
            candidates.append({
                "spec_version_id": v.id,
                "original_filename": v.original_filename,
                "minio_key": v.minio_key,
                "service_name": spec.service_name if spec else None,
                "endpoint_count": v.endpoint_count,
                "parse_summary": v.parse_summary,
                "score": score,
                "endpoints": ep_list
            })

        # 按分数排序取 topK
        candidates.sort(key=lambda x: x['score'], reverse=True)
        top_candidates = candidates[:top_k]

        # 如果只有一个候选，直接返回
        if len(top_candidates) == 1:
            rec = top_candidates[0]
            return {
                "success": True,
                "data": {
                    "recommended": {
                        "spec_version_id": rec["spec_version_id"],
                        "original_filename": rec["original_filename"],
                        "minio_key": rec["minio_key"],
                        "service_name": rec["service_name"],
                        "endpoint_count": rec["endpoint_count"],
                        "confidence": 0.9,
                        "reason": "仅有一个候选接口文件，自动推荐"
                    },
                    "candidates": [],
                    "preview_endpoints": rec["endpoints"]
                }
            }

        # 精排：LLM 选择最佳
        try:
            llm_result = _llm_rank_specs(combined_text, top_candidates)
        except Exception as e:
            logger.warning(f"LLM 精排失败，使用粗筛结果: {e}")
            llm_result = None

        if llm_result and llm_result.get("recommended"):
            rec_id = llm_result["recommended"]["spec_version_id"]
            rec_item = next((c for c in top_candidates if c["spec_version_id"] == rec_id), top_candidates[0])
            others = [c for c in top_candidates if c["spec_version_id"] != rec_id]
            return {
                "success": True,
                "data": {
                    "recommended": {
                        "spec_version_id": rec_item["spec_version_id"],
                        "original_filename": rec_item["original_filename"],
                        "minio_key": rec_item["minio_key"],
                        "service_name": rec_item["service_name"],
                        "endpoint_count": rec_item["endpoint_count"],
                        "confidence": llm_result["recommended"].get("confidence", 0.8),
                        "reason": llm_result["recommended"].get("reason", "")
                    },
                    "candidates": [
                        {
                            "spec_version_id": c["spec_version_id"],
                            "original_filename": c["original_filename"],
                            "minio_key": c["minio_key"],
                            "service_name": c["service_name"],
                            "endpoint_count": c["endpoint_count"],
                            "confidence": 0.5,
                            "reason": ""
                        } for c in others
                    ],
                    "preview_endpoints": rec_item["endpoints"]
                }
            }

        # fallback: 用粗筛第一名
        rec = top_candidates[0]
        others = top_candidates[1:]
        return {
            "success": True,
            "data": {
                "recommended": {
                    "spec_version_id": rec["spec_version_id"],
                    "original_filename": rec["original_filename"],
                    "minio_key": rec["minio_key"],
                    "service_name": rec["service_name"],
                    "endpoint_count": rec["endpoint_count"],
                    "confidence": 0.7,
                    "reason": "基于关键词匹配推荐"
                },
                "candidates": [
                    {
                        "spec_version_id": c["spec_version_id"],
                        "original_filename": c["original_filename"],
                        "minio_key": c["minio_key"],
                        "service_name": c["service_name"],
                        "endpoint_count": c["endpoint_count"],
                        "confidence": round(c["score"] / max(rec["score"], 1) * 0.7, 2),
                        "reason": ""
                    } for c in others
                ],
                "preview_endpoints": rec["endpoints"]
            }
        }

    @staticmethod
    async def execute_api_test(
        test_case_ids: List[int],
        spec_version_id: int,
        db: Session,
        environment: Optional[Dict] = None,
        mode: str = "llm_enhanced"
    ) -> Dict[str, Any]:
        """
        执行接口测试

        流程：
        1. 读取用例 + 接口文件
        2. 为每条用例匹配 endpoint + 生成 DSL
        3. Runner 执行 HTTP 请求
        4. 结果入库 test_records
        5. 生成报告 test_reports
        6. 失败用例生成 bug_reports + 邮件通知
        """
        # 读取用例
        cases = db.query(ExecutionCase).filter(
            ExecutionCase.id.in_(test_case_ids)
        ).all()
        if not cases:
            return {"success": False, "message": "未找到指定的测试用例"}

        # 读取接口文件
        version = db.query(ApiSpecVersion).filter(
            ApiSpecVersion.id == spec_version_id
        ).first()
        if not version:
            return {"success": False, "message": "未找到指定的接口文件版本"}

        endpoints = db.query(ApiEndpoint).filter(
            ApiEndpoint.spec_version_id == spec_version_id
        ).all()
        ep_list = [{
            "method": ep.method,
            "path": ep.path,
            "summary": ep.summary or '',
            "description": ep.description,
            "params": ep.params,
            "success_example": ep.success_example,
            "error_example": ep.error_example,
            "notes": ep.notes
        } for ep in endpoints]

        base_url = (environment or {}).get("base_url", "http://localhost:8080")
        headers = (environment or {}).get("headers", {})
        variables = (environment or {}).get("variables", {})

        # 创建批次
        batch_no = f"API-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        results = []
        test_record_ids = []
        failed_records = []
        total_duration = 0

        for case in cases:
            start_time = time.time()
            try:
                # 匹配 endpoint + 生成 DSL
                dsl = await _match_endpoint_and_generate_dsl(case, ep_list, mode)

                # 执行 HTTP 请求
                exec_result = _execute_http_request(dsl, base_url, headers, variables)

                duration = int(time.time() - start_time)
                total_duration += duration

                status = "pass" if exec_result["passed"] else "fail"
                error_msg = exec_result.get("error_message", "")

                # 写入 execution_batches
                batch = ExecutionBatch(
                    execution_case_id=case.id,
                    batch=batch_no
                )
                db.add(batch)
                db.flush()

                # 写入 test_records
                record = TestRecord(
                    batch_id=batch.id,
                    test_case_id=case.id,
                    execution_mode='接口测试',
                    total_cases=1,
                    passed_cases=1 if status == "pass" else 0,
                    failed_cases=0 if status == "pass" else 1,
                    execution_log=json.dumps({
                        "spec_version_id": spec_version_id,
                        "minio_key": version.minio_key,
                        "endpoint": dsl.get("endpoint", {}),
                        "request": exec_result.get("request_info", {}),
                        "response": exec_result.get("response_info", {}),
                        "assertions": exec_result.get("assertions", [])
                    }, ensure_ascii=False),
                    status=status,
                    error_message=error_msg if error_msg else None,
                    duration=duration,
                    test_steps=len(exec_result.get("assertions", []))
                )
                db.add(record)
                db.flush()
                test_record_ids.append(record.id)

                case_result = {
                    "test_case_id": case.id,
                    "title": case.title,
                    "status": status,
                    "duration": duration,
                    "endpoint": dsl.get("endpoint", {}),
                    "error_message": error_msg,
                    "record_id": record.id
                }
                results.append(case_result)

                if status == "fail":
                    failed_records.append({
                        "record": record,
                        "case": case,
                        "exec_result": exec_result,
                        "dsl": dsl
                    })

            except Exception as e:
                duration = int(time.time() - start_time)
                total_duration += duration
                logger.error(f"用例 {case.id} 执行异常: {e}\n{traceback.format_exc()}")

                batch = ExecutionBatch(execution_case_id=case.id, batch=batch_no)
                db.add(batch)
                db.flush()

                record = TestRecord(
                    batch_id=batch.id,
                    test_case_id=case.id,
                    execution_mode='接口测试',
                    total_cases=1,
                    passed_cases=0,
                    failed_cases=1,
                    execution_log=json.dumps({"error": str(e)}, ensure_ascii=False),
                    status="fail",
                    error_message=str(e),
                    duration=duration,
                    test_steps=0
                )
                db.add(record)
                db.flush()
                test_record_ids.append(record.id)

                results.append({
                    "test_case_id": case.id,
                    "title": case.title,
                    "status": "fail",
                    "duration": duration,
                    "endpoint": {},
                    "error_message": str(e),
                    "record_id": record.id
                })
                failed_records.append({
                    "record": record,
                    "case": case,
                    "exec_result": {"error_message": str(e)},
                    "dsl": {}
                })

        db.commit()

        pass_count = sum(1 for r in results if r["status"] == "pass")
        fail_count = len(results) - pass_count

        # 生成测试报告
        report_id = None
        try:
            report_id = _generate_api_test_report(
                results, test_record_ids, total_duration, db
            )
        except Exception as e:
            logger.error(f"生成报告失败: {e}")

        # 处理失败用例：生成 Bug + 邮件通知
        bug_report_ids = []
        if failed_records:
            try:
                bug_report_ids = _create_bug_reports(failed_records, db)
                db.commit()
            except Exception as e:
                logger.error(f"生成 Bug 报告失败: {e}")

            try:
                _send_bug_email_notification(failed_records, bug_report_ids, db)
            except Exception as e:
                logger.error(f"发送 Bug 邮件通知失败: {e}")

        return {
            "success": True,
            "data": {
                "test_record_ids": test_record_ids,
                "report_id": report_id,
                "bug_report_ids": bug_report_ids,
                "summary": {
                    "total": len(results),
                    "pass": pass_count,
                    "fail": fail_count,
                    "pass_rate": round(pass_count / len(results) * 100, 2) if results else 0,
                    "duration": total_duration
                },
                "results": results
            }
        }


# ============================================
# 辅助函数
# ============================================

def _keyword_overlap_score(case_text: str, parse_summary: str, filename: str) -> float:
    """关键词 overlap 打分"""
    case_words = set(re.findall(r'[\w/]+', case_text.lower()))
    summary_words = set(re.findall(r'[\w/]+', (parse_summary + ' ' + filename).lower()))
    if not case_words or not summary_words:
        return 0.0
    overlap = case_words & summary_words
    return len(overlap) / max(len(case_words), 1)


def _llm_rank_specs(case_text: str, candidates: List[Dict]) -> Optional[Dict]:
    """LLM 精排候选接口文件"""
    llm = get_llm_client()

    candidates_desc = []
    for c in candidates:
        desc = f"- spec_version_id={c['spec_version_id']}, 文件名={c['original_filename']}, 接口数={c['endpoint_count']}"
        if c.get('parse_summary'):
            desc += f"\n  摘要: {c['parse_summary'][:300]}"
        candidates_desc.append(desc)

    system_prompt = """你是一个接口测试专家。根据测试用例文本，从候选接口文件中选出最匹配的一个。
返回严格 JSON 格式:
{
  "recommended": { "spec_version_id": <int>, "confidence": <0-1>, "reason": "<简短理由>" }
}"""

    user_prompt = f"""测试用例:
{case_text[:2000]}

候选接口文件:
{chr(10).join(candidates_desc)}

请选出最匹配的接口文件。"""

    response = llm.chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.1,
        max_tokens=500
    )

    # 解析 JSON
    cleaned = response.strip()
    if cleaned.startswith('```'):
        cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
        cleaned = re.sub(r'```\s*$', '', cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


async def _match_endpoint_and_generate_dsl(
    case: ExecutionCase,
    endpoints: List[Dict],
    mode: str
) -> Dict[str, Any]:
    """为单条用例匹配 endpoint 并生成可执行 DSL"""
    case_text = f"标题: {case.title}\n步骤: {case.steps}\n预期: {case.expected}"
    if case.test_data:
        case_text += f"\n测试数据: {json.dumps(case.test_data, ensure_ascii=False)}"

    ep_desc = "\n".join([
        f"- {ep['method']} {ep['path']} ({ep['summary']})"
        for ep in endpoints
    ])

    llm = get_llm_client()

    system_prompt = """你是一个接口测试 DSL 生成专家。
根据测试用例和可用接口列表，选择最合适的接口并生成可执行的测试 DSL。

返回严格 JSON:
{
  "endpoint": { "method": "GET|POST|PUT|DELETE", "path": "/xxx" },
  "request": {
    "query_params": {},
    "headers": {},
    "body": null
  },
  "assertions": [
    { "type": "status_code", "expected": 200 },
    { "type": "json_path", "path": "$.code", "expected": 200 }
  ]
}

注意：
- query_params 用于 GET 请求的 URL 参数
- body 用于 POST/PUT 请求体（JSON 格式）
- assertions 至少包含 status_code 断言
- 如果测试用例有测试数据，用它填充请求参数"""

    user_prompt = f"""测试用例:
{case_text}

可用接口:
{ep_desc}

请选择最合适的接口并生成测试 DSL。"""

    response = llm.chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.1,
        max_tokens=2000
    )

    cleaned = response.strip()
    if cleaned.startswith('```'):
        cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
        cleaned = re.sub(r'```\s*$', '', cleaned)

    # 去除 think 标签
    cleaned = re.sub(r'<think>[\s\S]*?</think>', '', cleaned).strip()

    try:
        dsl = json.loads(cleaned)
    except json.JSONDecodeError:
        # fallback: 用第一个 endpoint
        ep = endpoints[0] if endpoints else {"method": "GET", "path": "/"}
        dsl = {
            "endpoint": {"method": ep["method"], "path": ep["path"]},
            "request": {"query_params": {}, "headers": {}, "body": None},
            "assertions": [{"type": "status_code", "expected": 200}]
        }

    return dsl


def _execute_http_request(
    dsl: Dict[str, Any],
    base_url: str,
    extra_headers: Dict = None,
    variables: Dict = None
) -> Dict[str, Any]:
    """执行 HTTP 请求并验证断言"""
    endpoint = dsl.get("endpoint", {})
    method = endpoint.get("method", "GET").upper()
    path = endpoint.get("path", "/")
    req_config = dsl.get("request", {})
    assertions = dsl.get("assertions", [])

    # 变量替换
    url = f"{base_url.rstrip('/')}{path}"
    if variables:
        for k, v in variables.items():
            url = url.replace(f"{{{k}}}", str(v))

    headers = {"Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    if req_config.get("headers"):
        headers.update(req_config["headers"])

    query_params = req_config.get("query_params", {})
    body = req_config.get("body")

    request_info = {
        "method": method,
        "url": url,
        "headers": {k: v for k, v in headers.items() if k.lower() != 'authorization'},
        "query_params": query_params,
        "body": body
    }

    try:
        resp = http_requests.request(
            method=method,
            url=url,
            params=query_params,
            json=body if body else None,
            headers=headers,
            timeout=30
        )

        # 尝试解析 JSON
        try:
            resp_json = resp.json()
        except Exception:
            resp_json = None

        response_info = {
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
            "body_trunc": resp.text[:2000] if resp.text else "",
            "json": resp_json
        }

        # 执行断言
        assertion_results = []
        all_passed = True
        for assertion in assertions:
            a_type = assertion.get("type", "")
            passed = False
            actual = None
            expected = assertion.get("expected")

            if a_type == "status_code":
                actual = resp.status_code
                passed = actual == expected
            elif a_type == "json_path" and resp_json is not None:
                json_path = assertion.get("path", "")
                actual = _extract_json_path(resp_json, json_path)
                passed = actual == expected
            elif a_type == "contains":
                actual = resp.text
                passed = str(expected) in resp.text if expected else False
            elif a_type == "not_empty":
                actual = bool(resp.text)
                passed = actual

            assertion_results.append({
                "type": a_type,
                "expected": expected,
                "actual": actual,
                "passed": passed
            })
            if not passed:
                all_passed = False

        error_message = ""
        if not all_passed:
            failed_assertions = [a for a in assertion_results if not a["passed"]]
            error_message = "; ".join([
                f"{a['type']}: 期望 {a['expected']}, 实际 {a['actual']}"
                for a in failed_assertions
            ])

        return {
            "passed": all_passed,
            "request_info": request_info,
            "response_info": response_info,
            "assertions": assertion_results,
            "error_message": error_message
        }

    except http_requests.exceptions.Timeout:
        return {
            "passed": False,
            "request_info": request_info,
            "response_info": {},
            "assertions": [],
            "error_message": "请求超时 (30s)"
        }
    except http_requests.exceptions.ConnectionError as e:
        return {
            "passed": False,
            "request_info": request_info,
            "response_info": {},
            "assertions": [],
            "error_message": f"连接失败: {str(e)}"
        }
    except Exception as e:
        return {
            "passed": False,
            "request_info": request_info,
            "response_info": {},
            "assertions": [],
            "error_message": f"请求异常: {str(e)}"
        }


def _extract_json_path(data: Any, path: str) -> Any:
    """简易 JSON Path 提取 (支持 $.key.key 格式)"""
    if not path or not data:
        return None
    parts = path.replace('$', '').strip('.').split('.')
    current = data
    for part in parts:
        if not part:
            continue
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


def _generate_api_test_report(
    results: List[Dict],
    test_record_ids: List[int],
    total_duration: int,
    db: Session
) -> Optional[int]:
    """生成接口测试报告"""
    pass_count = sum(1 for r in results if r["status"] == "pass")
    fail_count = len(results) - pass_count

    llm = get_llm_client()

    results_text = json.dumps(results, ensure_ascii=False, indent=2)
    system_prompt = "你是一个专业的接口测试报告生成专家。请根据接口测试结果生成简洁专业的 Markdown 测试报告。"
    user_prompt = f"""接口测试结果:
- 总用例: {len(results)}
- 通过: {pass_count}
- 失败: {fail_count}
- 耗时: {total_duration}s

详情:
{results_text[:4000]}

请生成 Markdown 格式的接口测试报告。"""

    try:
        content = llm.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3
        )
    except Exception:
        content = f"# 接口测试报告\n\n通过: {pass_count}, 失败: {fail_count}, 耗时: {total_duration}s"

    report = TestReport(
        title=f"接口测试报告 - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        summary={
            "total": len(results),
            "pass": pass_count,
            "fail": fail_count,
            "pass_rate": round(pass_count / len(results) * 100, 2) if results else 0,
            "duration": total_duration,
            "execution_mode": "接口测试",
            "test_record_ids": test_record_ids
        },
        details=content,
        format_type="markdown",
        total_steps=sum(1 for r in results)
    )
    db.add(report)
    db.commit()
    return report.id


def _create_bug_reports(
    failed_records: List[Dict],
    db: Session
) -> List[int]:
    """为失败用例创建 Bug 报告"""
    bug_ids = []
    for item in failed_records:
        case = item["case"]
        record = item["record"]
        exec_result = item.get("exec_result", {})
        dsl = item.get("dsl", {})

        endpoint = dsl.get("endpoint", {})
        ep_str = f"{endpoint.get('method', '?')} {endpoint.get('path', '?')}"

        bug = BugReport(
            test_record_id=record.id,
            test_case_id=case.id,
            bug_name=f"[接口测试] {case.title} - {ep_str} 失败",
            error_type="接口错误",
            severity_level="二级",
            reproduce_steps=f"1. 调用接口 {ep_str}\n2. 请求参数: {json.dumps(dsl.get('request', {}), ensure_ascii=False)[:500]}",
            expected_result=case.expected or "接口正常返回",
            actual_result=exec_result.get("error_message", "未知错误"),
            result_feedback=json.dumps(exec_result.get("response_info", {}), ensure_ascii=False)[:1000],
            status="待处理",
            description=f"接口测试失败: {ep_str}\n错误: {exec_result.get('error_message', '')}",
            case_type="接口测试",
            execution_mode="接口测试"
        )
        db.add(bug)
        db.flush()
        bug_ids.append(bug.id)

    return bug_ids


def _send_bug_email_notification(
    failed_records: List[Dict],
    bug_report_ids: List[int],
    db: Session
):
    """发送 Bug 邮件通知给 auto_receive_bug=1 的联系人"""
    contacts = db.query(Contact).filter(Contact.auto_receive_bug == 1).all()
    if not contacts:
        return

    email_config = db.query(EmailConfig).filter(EmailConfig.is_active == 1).first()
    if not email_config:
        return

    # 构建邮件内容
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    subject = f"[AI Test Agent][BUG] 接口测试失败汇总 - {now_str}"

    rows = ""
    for item in failed_records:
        case = item["case"]
        dsl = item.get("dsl", {})
        exec_result = item.get("exec_result", {})
        ep = dsl.get("endpoint", {})
        rows += f"""<tr>
            <td style="padding:8px;border:1px solid #e5e7eb;">{case.title}</td>
            <td style="padding:8px;border:1px solid #e5e7eb;">{ep.get('method','')} {ep.get('path','')}</td>
            <td style="padding:8px;border:1px solid #e5e7eb;color:#dc2626;">{exec_result.get('error_message','')[:200]}</td>
        </tr>"""

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="font-family:sans-serif;background:#f4f5f7;padding:20px;">
<div style="max-width:680px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);">
  <div style="background:linear-gradient(135deg,#dc2626,#ef4444);padding:24px 32px;color:#fff;">
    <h2 style="margin:0;">接口测试失败通知</h2>
    <p style="margin:6px 0 0;opacity:0.85;font-size:13px;">{now_str} · 共 {len(failed_records)} 条失败</p>
  </div>
  <div style="padding:24px 32px;">
    <table width="100%" style="border-collapse:collapse;font-size:13px;">
      <tr style="background:#f8fafc;">
        <th style="padding:8px;border:1px solid #e5e7eb;text-align:left;">用例</th>
        <th style="padding:8px;border:1px solid #e5e7eb;text-align:left;">接口</th>
        <th style="padding:8px;border:1px solid #e5e7eb;text-align:left;">错误</th>
      </tr>
      {rows}
    </table>
    <p style="margin-top:16px;font-size:12px;color:#94a3b8;">Bug ID: {', '.join(str(i) for i in bug_report_ids)}</p>
  </div>
  <div style="background:#f8fafc;padding:12px 32px;text-align:center;font-size:12px;color:#94a3b8;">
    此邮件由 AI 测试平台自动发送
  </div>
</div></body></html>"""

    sender = email_config.sender_email
    provider = email_config.provider or 'resend'
    recipients_result = []
    success_count = 0
    failed_count = 0

    for contact in contacts:
        to_email = email_config.test_email if email_config.test_mode == 1 and email_config.test_email else contact.email
        try:
            if provider == 'aliyun':
                from Build_Report.router import _send_via_aliyun
                _send_via_aliyun(
                    access_key_id=email_config.api_key,
                    access_key_secret=email_config.secret_key,
                    sender=sender,
                    to_email=to_email,
                    subject=subject,
                    html_body=html
                )
            else:
                import resend
                resend.api_key = email_config.api_key
                resend.Emails.send({
                    "from": sender, "to": [to_email],
                    "subject": subject, "html": html
                })
            success_count += 1
            recipients_result.append({"name": contact.name, "email": contact.email, "status": "success"})
        except Exception as e:
            failed_count += 1
            recipients_result.append({"name": contact.name, "email": contact.email, "status": "failed", "error": str(e)})

    record = EmailRecord(
        subject=subject,
        recipients=recipients_result,
        status='success' if failed_count == 0 else ('partial' if success_count > 0 else 'failed'),
        success_count=success_count,
        failed_count=failed_count,
        total_count=len(contacts),
        email_type='bug_notification',
        content_summary=f"接口测试失败通知: {len(failed_records)} 条失败"
    )
    db.add(record)
    db.commit()
