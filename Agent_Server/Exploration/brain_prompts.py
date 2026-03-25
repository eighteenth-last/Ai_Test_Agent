from __future__ import annotations

import json
from typing import Any, Dict


MANAGER_SYSTEM_PROMPT = """你是页面探索任务生成器。
你只负责基于当前页面的结构化事实生成任务 JSON。

必须遵守：
1. 只看当前页面，不推断未观察到的页面或流程。
2. 只输出当前页面待办任务，不输出跨页面执行计划。
3. 不决定 BFS/DFS、任务顺序、页面完成判定，这些由服务端负责。
4. 优先生成两类任务：
   - in_page: 留在当前页面内的交互，如标签切换、展开、分页、筛选、弹窗、表单。
   - navigation: 可能跳转到新页面或新路由的交互。
5. 输出必须是 JSON 对象，不能附带解释性文字。
"""


MANAGER_OUTPUT_SCHEMA = {
    "page_summary": {
        "title": "string",
        "url": "string",
        "key_sections": ["string"],
    },
    "tasks": [
        {
            "task_group": "in_page | navigation",
            "task_type": "button | interaction | form_input | pagination | dialog | navigate",
            "element_label": "string",
            "element_key": "string",
            "has_navigation": False,
            "reason": "string",
        }
    ],
}


def build_manager_prompt(page_facts: Dict[str, Any]) -> str:
    """Build the final slim prompt for current-page task generation only."""
    facts = page_facts or {}
    return "\n".join(
        [
            MANAGER_SYSTEM_PROMPT,
            "",
            "当前页面结构化事实：",
            json.dumps(facts, ensure_ascii=False, indent=2),
            "",
            "输出 JSON schema：",
            json.dumps(MANAGER_OUTPUT_SCHEMA, ensure_ascii=False, indent=2),
            "",
            "请直接输出 JSON。",
        ]
    )
