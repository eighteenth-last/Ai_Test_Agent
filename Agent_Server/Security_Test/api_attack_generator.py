"""
API 攻击生成器（LLM 差异化核心）

利用 LLM 根据接口文档自动生成安全攻击 DSL，
然后调用 HTTP Runner 执行并分析结果

攻击类型:
- 去 Token / 无鉴权访问
- 越权（修改 user_id）
- 参数越界 / 类型混淆
- SQL 注入 payload
- XSS payload
- JWT 篡改
- 重放请求

作者: Ai_Test_Agent Team
"""
import json
import re
import logging
from typing import List, Dict, Any, Optional

import requests as http_requests

logger = logging.getLogger(__name__)

ATTACK_GENERATION_SYSTEM = """你是一个专业的 API 安全测试专家。根据接口文档信息，生成一组安全攻击测试用例。

每个攻击用例包含:
- name: 攻击名称
- attack_type: 攻击类型（auth_bypass / privilege_escalation / param_overflow / sql_injection / xss / jwt_tamper / replay）
- severity: 预期严重级别（critical / high / medium / low）
- description: 攻击描述
- dsl: 可执行的 HTTP 请求 DSL

DSL 格式:
{
  "method": "GET/POST/PUT/DELETE",
  "path": "/api/xxx",
  "headers": {},
  "query_params": {},
  "body": null 或 {}
}

规则:
1. 每种攻击类型至少生成 1 个用例
2. SQL 注入 payload 使用常见的探测语句（如 ' OR '1'='1、1; DROP TABLE--）
3. XSS payload 使用 <script>alert(1)</script> 等
4. 越权测试: 修改 user_id / role 等参数
5. 无鉴权测试: 去掉 Authorization header
6. 参数越界: 超长字符串、负数、特殊字符
7. 所有内容使用中文描述

返回 JSON:
{
  "attacks": [
    {
      "name": "攻击名称",
      "attack_type": "sql_injection",
      "severity": "critical",
      "description": "攻击描述",
      "dsl": { "method": "POST", "path": "/api/login", "headers": {}, "body": {"username": "admin' OR '1'='1", "password": "test"} },
      "expected_safe_behavior": "应返回 400/401 错误，不应返回数据库信息"
    }
  ]
}"""


async def generate_attack_cases(endpoints: List[Dict], auth_info: Dict = None) -> List[Dict]:
    """
    使用 LLM 生成 API 攻击用例

    Args:
        endpoints: 接口列表 [{"method": "POST", "path": "/api/login", "summary": "...", "params": "..."}]
        auth_info: 鉴权信息 {"type": "bearer", "token": "xxx"} 或 {"type": "basic", ...}

    Returns:
        攻击用例列表
    """
    from llm import get_llm_client

    ep_desc = []
    for ep in endpoints[:10]:  # 限制接口数量
        desc = f"- {ep.get('method', 'GET')} {ep.get('path', '/')}"
        if ep.get("summary"):
            desc += f" ({ep['summary']})"
        if ep.get("params"):
            params_str = ep["params"] if isinstance(ep["params"], str) else json.dumps(ep["params"], ensure_ascii=False)
            desc += f"\n  参数: {params_str[:500]}"
        ep_desc.append(desc)

    auth_desc = "无鉴权信息" if not auth_info else json.dumps(auth_info, ensure_ascii=False)

    user_prompt = f"""接口列表:
{chr(10).join(ep_desc)}

鉴权方式: {auth_desc}

请为以上接口生成全面的安全攻击测试用例。"""

    llm = get_llm_client()
    response = llm.chat(
        messages=[
            {"role": "system", "content": ATTACK_GENERATION_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=4000,
    )

    # 解析 LLM 输出
    cleaned = response.strip()
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", cleaned)
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"```\s*$", "", cleaned)

    try:
        data = json.loads(cleaned)
        return data.get("attacks", [])
    except json.JSONDecodeError:
        logger.warning("[API Attack] LLM 输出 JSON 解析失败")
        return []


async def execute_attack_cases(attacks: List[Dict], base_url: str,
                               default_headers: Dict = None) -> List[Dict]:
    """
    执行攻击用例并分析结果

    Returns:
        带有执行结果的攻击列表
    """
    results = []
    default_headers = default_headers or {}

    for attack in attacks:
        dsl = attack.get("dsl", {})
        method = dsl.get("method", "GET").upper()
        path = dsl.get("path", "/")
        url = f"{base_url.rstrip('/')}{path}"
        headers = {**default_headers, **dsl.get("headers", {})}
        params = dsl.get("query_params", {})
        body = dsl.get("body")

        try:
            resp = http_requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=body if body else None,
                timeout=15,
                allow_redirects=False,
            )

            # 分析响应判断是否存在漏洞
            is_vulnerable = _analyze_response(attack, resp)

            results.append({
                **attack,
                "is_vulnerable": is_vulnerable,
                "response_status": resp.status_code,
                "response_body_trunc": resp.text[:1000],
                "evidence": _extract_evidence(attack, resp) if is_vulnerable else "",
                "url": url,
            })

        except Exception as e:
            results.append({
                **attack,
                "is_vulnerable": False,
                "response_status": None,
                "response_body_trunc": str(e),
                "evidence": "",
                "url": url,
                "error": str(e),
            })

    return results


def _analyze_response(attack: Dict, resp) -> bool:
    """分析响应判断是否存在漏洞"""
    attack_type = attack.get("attack_type", "")
    status = resp.status_code
    body = resp.text.lower()

    if attack_type == "auth_bypass":
        # 无鉴权访问应该返回 401/403，如果返回 200 则可能有漏洞
        return status == 200

    if attack_type == "privilege_escalation":
        # 越权访问应该返回 403，如果返回 200 则可能有漏洞
        return status == 200

    if attack_type == "sql_injection":
        # 检查是否有数据库错误信息泄露
        sql_errors = ["sql syntax", "mysql", "postgresql", "sqlite", "oracle",
                      "syntax error", "unclosed quotation", "unterminated"]
        return any(err in body for err in sql_errors) or status == 500

    if attack_type == "xss":
        # 检查 payload 是否被原样返回（未转义）
        return "<script>" in resp.text or "alert(" in resp.text

    if attack_type == "param_overflow":
        # 服务器应该返回 400，如果返回 500 则可能有问题
        return status == 500

    # 默认: 5xx 响应视为潜在问题
    return status >= 500


def _extract_evidence(attack: Dict, resp) -> str:
    """提取漏洞证据"""
    parts = [f"HTTP {resp.status_code}"]
    body_trunc = resp.text[:500]
    if body_trunc:
        parts.append(f"响应片段: {body_trunc}")
    return " | ".join(parts)
